#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
非诉组识别结果验证器

负责验证 OCR 识别结果是否符合标准，处理识别失败的情况
"""

import json
import re
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from config_loader import load_config
from non_litigation_export import normalize_notice_number, discover_notice_files

_cfg = load_config()


class ValidationStatus(Enum):
    """验证状态"""
    PASS = "pass"           # 验证通过
    WARNING = "warning"     # 警告（有瑕疵但可用）
    FAIL = "fail"           # 失败（需要人工介入）


@dataclass
class ValidationResult:
    """验证结果"""
    status: ValidationStatus
    file_name: str
    file_type: str  # 'notice', 'application', 'authorization', 'letter'
    message: str
    details: Dict
    suggestions: List[str]
    timing: Dict  # 耗时信息
    accuracy: Dict  # 准确度信息


class NonLitigationValidator:
    """非诉组识别结果验证器"""
    
    # 责令号标准格式
    NOTICE_PATTERN = _cfg.notice_pattern
    APPLICATION_KEYWORDS = _cfg.doc_type_map['申请书'].validation_keywords
    AUTHORIZATION_KEYWORDS = _cfg.doc_type_map['授权书'].validation_keywords
    LETTER_KEYWORDS = _cfg.doc_type_map['所函'].validation_keywords
    _DOC_TYPE_KEY_MAP = {'authorization': '授权书', 'letter': '所函'}
    
    def __init__(self, cases: List[Dict]):
        """
        初始化验证器
        
        Args:
            cases: 台账中的案件列表
        """
        self.cases = cases
        self.expected_notice_numbers = [normalize_notice_number(c['notice_number']) for c in cases]
        self.expected_company_names = [c['company_name'] for c in cases]
        self.validation_report: List[ValidationResult] = []
        self.timing_stats: Dict[str, List[float]] = {
            'notice': [],
            'application': [],
            'authorization': [],
            'letter': []
        }
    
    @staticmethod
    def _get_notice_root_number(notice_number: str) -> str:
        normalized = normalize_notice_number(notice_number)
        return re.sub(r'-\d+号$', '号', normalized)

    def validate_notice_ocr(self, file_name: str, ocr_result: Dict) -> ValidationResult:
        """
        验证责催文件 OCR 结果
        
        Args:
            file_name: 文件名
            ocr_result: OCR 识别结果
            
        Returns:
            ValidationResult: 验证结果
        """
        start_time = datetime.now()
        
        pages = ocr_result.get('pages', [])
        details = {
            'file_name': file_name,
            'total_pages': ocr_result.get('total_pages', 0),
            'pages_processed': len(pages),
            'detected_notices': [],
            'matched_case': None,
            'fallback_pages': sum(1 for p in pages if p.get('fallback_used')),
            'region_pages': sum(1 for p in pages if p.get('method') == 'region_first'),
            'stopped_early': ocr_result.get('stopped_early', False),
            'optimization_strategy': ocr_result.get('optimization_strategy', ocr_result.get('method', 'unknown')),
            'selected_notice': ocr_result.get('selected_notice'),
            'selected_page': ocr_result.get('selected_page'),
            'candidate_notices': ocr_result.get('candidate_notices', []),
            'matched_target': ocr_result.get('matched_target'),
            'matched_target_notice': ocr_result.get('matched_target_notice'),
            'export_match_type': ocr_result.get('export_match_type'),
            'same_root_remap': ocr_result.get('same_root_remap', False),
            'diagnostic_category': 'basis_mismatch' if ocr_result.get('same_root_remap', False) else None,
            'diagnostic_reason': '识别主号成功，但导出目标被同根号子号重映射' if ocr_result.get('same_root_remap', False) else '',
        }
        
        # 提取耗时信息
        timing = {
            'total_duration': ocr_result.get('total_duration', 0),
            'method': ocr_result.get('method', 'unknown'),
            'pages_timings': [p.get('duration', 0) for p in ocr_result.get('pages', [])],
            'avg_time_per_page': 0,
        }
        
        if timing['pages_timings']:
            timing['avg_time_per_page'] = sum(timing['pages_timings']) / len(timing['pages_timings'])
        
        # 准确度信息
        accuracy = {
            'ocr_confidence': 'N/A',  # RapidOCR 不提供置信度
            'text_quality': 'unknown',
            'extraction_success': False,
            'fallback_rate': round(details['fallback_pages'] / max(details['pages_processed'], 1) * 100, 2),
            'region_first_hit_rate': round(details['region_pages'] / max(details['pages_processed'], 1) * 100, 2),
        }
        
        # 检查是否识别到任何内容
        if not ocr_result.get('pages'):
            accuracy['text_quality'] = 'empty'
            details['diagnostic_category'] = 'ocr_failure'
            details['diagnostic_reason'] = 'OCR 未识别到任何内容'
            return ValidationResult(
                status=ValidationStatus.FAIL,
                file_name=file_name,
                file_type='notice',
                message='OCR 未识别到任何内容',
                details=details,
                suggestions=[
                    '检查 PDF 文件是否损坏',
                    '检查 PDF 是否为扫描件（需要 OCR）',
                    '尝试提高 DPI 重新识别'
                ],
                timing=timing,
                accuracy=accuracy
            )
        
        # 提取所有识别到的责令号
        detected_notices = []
        full_text = ''
        for page in ocr_result['pages']:
            text = page.get('text', '')
            full_text += text + '\n'
            matches = self.NOTICE_PATTERN.findall(text)
            detected_notices.extend(matches)
        
        details['detected_notices'] = detected_notices
        details['full_text_preview'] = full_text[:500] if full_text else ''
        
        # 评估文本质量
        if len(full_text) > _cfg.text_quality['notice']['good']:
            accuracy['text_quality'] = 'good'
        elif len(full_text) > _cfg.text_quality['notice']['fair']:
            accuracy['text_quality'] = 'fair'
        else:
            accuracy['text_quality'] = 'poor'
        
        # 检查是否识别到责令号
        if not detected_notices:
            details['diagnostic_category'] = 'ocr_failure'
            details['diagnostic_reason'] = '未识别到责令号'
            return ValidationResult(
                status=ValidationStatus.FAIL,
                file_name=file_name,
                file_type='notice',
                message='未识别到责令号',
                details=details,
                suggestions=[
                    '检查 PDF 第一页是否包含责令号',
                    '检查 OCR 识别质量（文字是否清晰）',
                    f'识别到的文本预览: {full_text[:200]}...' if full_text else '无文本内容'
                ],
                timing=timing,
                accuracy=accuracy
            )
        
        # 标准化检测到的责令号
        normalized_detected = [normalize_notice_number(n) for n in detected_notices]
        details['normalized_notices'] = normalized_detected
        selected_notice = normalize_notice_number(details['selected_notice']) if details.get('selected_notice') else None
        target_notice = normalize_notice_number(details['matched_target_notice']) if details.get('matched_target_notice') else None
        if selected_notice and selected_notice not in normalized_detected:
            normalized_detected.insert(0, selected_notice)

        same_root_remap = bool(
            details.get('same_root_remap')
            or (
                selected_notice
                and target_notice
                and selected_notice != target_notice
                and self._get_notice_root_number(selected_notice) == self._get_notice_root_number(target_notice)
            )
        )
        details['same_root_remap'] = same_root_remap
        if same_root_remap:
            details['same_root_remap_summary'] = {
                'selected_notice': selected_notice,
                'target_notice': target_notice,
                'matched_target': details.get('matched_target'),
                'export_match_type': details.get('export_match_type'),
            }
            details['diagnostic_category'] = 'basis_mismatch'
            details['diagnostic_reason'] = '识别主号成功，但导出目标被同根号子号重映射'

        # 检查是否匹配台账中的责令号
        matched = False
        match_confidence = 0
        for detected in normalized_detected:
            if detected in self.expected_notice_numbers:
                matched = True
                details['matched_case'] = detected
                match_confidence = 100
                break
        
        accuracy['extraction_success'] = matched
        accuracy['match_confidence'] = match_confidence
        
        primary_notice = selected_notice or (normalized_detected[0] if normalized_detected else None)

        if matched or same_root_remap:
            status = ValidationStatus.WARNING if same_root_remap else ValidationStatus.PASS
            message = f'成功识别并匹配责令号: {primary_notice}'
            suggestions = []
            if matched:
                accuracy['extraction_success'] = True
                accuracy['match_confidence'] = 100
            if same_root_remap:
                message = f'识别主号成功，但按同根目标导出: {primary_notice} -> {target_notice}'
                suggestions = [
                    f'OCR 选中主号: {primary_notice}',
                    f'当前导出目标: {target_notice}',
                    '请人工确认台账是否应保留子号命名'
                ]
            return ValidationResult(
                status=status,
                file_name=file_name,
                file_type='notice',
                message=message,
                details=details,
                suggestions=suggestions,
                timing=timing,
                accuracy=accuracy
            )
        else:
            # 尝试模糊匹配
            best_match, ratio = self._fuzzy_match_notice(primary_notice) if primary_notice else (None, 0)
            if best_match and ratio >= _cfg.fuzzy_match_threshold:
                details['fuzzy_match'] = {'target': best_match, 'ratio': ratio}
                details['diagnostic_category'] = 'fuzzy_mapping'
                details['diagnostic_reason'] = f'识别结果未精确命中台账，存在模糊匹配候选: {best_match}'
                accuracy['match_confidence'] = int(ratio * 100)
                return ValidationResult(
                    status=ValidationStatus.WARNING,
                    file_name=file_name,
                    file_type='notice',
                    message=f'识别到责令号但未精确匹配，模糊匹配相似度: {ratio:.1%}',
                    details=details,
                    suggestions=[
                        f'识别结果: {primary_notice}',
                        f'建议匹配: {best_match}',
                        '请人工确认是否匹配正确'
                    ],
                    timing=timing,
                    accuracy=accuracy
                )
            else:
                details['diagnostic_category'] = 'heuristic_mismatch'
                details['diagnostic_reason'] = '识别到责令号，但无法匹配台账中的标准责令号'
                return ValidationResult(
                    status=ValidationStatus.FAIL,
                    file_name=file_name,
                    file_type='notice',
                    message=f'识别到责令号但无法匹配台账: {primary_notice}',
                    details=details,
                    suggestions=[
                        '检查台账 Excel 是否包含此责令号',
                        '检查责令号格式是否正确（如括号类型）',
                        f'识别到的责令号: {primary_notice}',
                        f'期望的责令号示例: {self.expected_notice_numbers[0] if self.expected_notice_numbers else "N/A"}'
                    ],
                    timing=timing,
                    accuracy=accuracy
                )
    
    def validate_application_ocr(self, file_name: str, ocr_result: Dict, 
                                  expected_cases: int) -> ValidationResult:
        """验证申请书 OCR 结果"""
        pages = ocr_result.get('pages', [])
        details = {
            'file_name': file_name,
            'total_pages': ocr_result.get('total_pages', 0),
            'expected_cases': expected_cases,
            'detected_cases': 0,
            'keywords_found': [],
            'boundary_pages_detected': [p.get('page') for p in pages if p.get('boundary_detected')],
            'fallback_pages': sum(1 for p in pages if p.get('fallback_used')),
            'optimization_strategy': ocr_result.get('optimization_strategy', ocr_result.get('method', 'unknown')),
        }
        
        # 耗时信息
        timing = {
            'total_duration': ocr_result.get('total_duration', 0),
            'method': ocr_result.get('method', 'unknown'),
            'pages_timings': [p.get('duration', 0) for p in ocr_result.get('pages', [])],
            'avg_time_per_page': 0,
        }
        
        if timing['pages_timings']:
            timing['avg_time_per_page'] = sum(timing['pages_timings']) / len(timing['pages_timings'])
        
        # 准确度信息
        accuracy = {
            'text_quality': 'unknown',
            'case_detection_accuracy': 0,
            'keyword_detection_rate': 0,
            'fallback_rate': round(details['fallback_pages'] / max(len(pages), 1) * 100, 2),
            'boundary_detection_rate': 0,
        }
        
        if not ocr_result.get('pages'):
            accuracy['text_quality'] = 'empty'
            return ValidationResult(
                status=ValidationStatus.FAIL,
                file_name=file_name,
                file_type='application',
                message='OCR 未识别到任何内容',
                details=details,
                suggestions=['检查 PDF 文件是否损坏', '检查 PDF 是否为扫描件'],
                timing=timing,
                accuracy=accuracy
            )
        
        # 检查关键字
        full_text = '\n'.join([p.get('text', '') for p in ocr_result['pages']])
        keywords_found = []
        for keyword in self.APPLICATION_KEYWORDS:
            if keyword in full_text:
                keywords_found.append(keyword)
        
        details['keywords_found'] = keywords_found
        accuracy['keyword_detection_rate'] = len(keywords_found) / len(self.APPLICATION_KEYWORDS) * 100
        
        # 评估文本质量
        if len(full_text) > _cfg.text_quality['application']['good']:
            accuracy['text_quality'] = 'good'
        elif len(full_text) > _cfg.text_quality['application']['fair']:
            accuracy['text_quality'] = 'fair'
        else:
            accuracy['text_quality'] = 'poor'
        
        # 统计案件数量（通过"强制执行申请书"出现次数）
        case_count = full_text.count('强制执行申请书')
        details['detected_cases'] = case_count

        # 计算案件检测准确度
        if expected_cases > 0:
            accuracy['case_detection_accuracy'] = min(case_count / expected_cases * 100, 100) if case_count <= expected_cases * 1.5 else 50
            accuracy['boundary_detection_rate'] = min(len(details['boundary_pages_detected']) / expected_cases * 100, 100)
        
        # 验证
        if case_count == 0:
            return ValidationResult(
                status=ValidationStatus.FAIL,
                file_name=file_name,
                file_type='application',
                message='未识别到"强制执行申请书"关键字',
                details=details,
                suggestions=[
                    '检查 PDF 是否为申请书',
                    '检查 OCR 识别质量',
                    f'识别到的文本长度: {len(full_text)} 字符',
                    f'文本预览: {full_text[:300]}...' if full_text else '无文本内容'
                ],
                timing=timing,
                accuracy=accuracy
            )
        
        if case_count != expected_cases:
            details['case_count_info'] = f'识别到 {case_count} 个案件，台账期望 {expected_cases} 个'
        
        return ValidationResult(
            status=ValidationStatus.PASS,
            file_name=file_name,
            file_type='application',
            message=f'成功识别 {case_count} 个案件',
            details=details,
            suggestions=[],
            timing=timing,
            accuracy=accuracy
        )
    
    def validate_company_document_ocr(self, file_name: str, ocr_result: Dict,
                                       expected_count: int, doc_type: str) -> ValidationResult:
        """验证授权书/所函 OCR 结果"""
        keywords = self.AUTHORIZATION_KEYWORDS if doc_type == 'authorization' else self.LETTER_KEYWORDS
        
        pages = ocr_result.get('pages', [])
        details = {
            'file_name': file_name,
            'total_pages': ocr_result.get('total_pages', 0),
            'expected_count': expected_count,
            'doc_type': doc_type,
            'keywords_found': [],
            'fallback_pages': sum(1 for p in pages if p.get('fallback_used')),
            'region_usable_pages': sum(1 for p in pages if p.get('region_usable')),
            'marker_detected_pages': sum(1 for p in pages if p.get('marker_detected')),
            'optimization_strategy': ocr_result.get('optimization_strategy', ocr_result.get('method', 'unknown')),
        }
        
        # 耗时信息
        timing = {
            'total_duration': ocr_result.get('total_duration', 0),
            'method': ocr_result.get('method', 'unknown'),
            'pages_timings': [p.get('duration', 0) for p in ocr_result.get('pages', [])],
            'avg_time_per_page': 0,
        }
        
        if timing['pages_timings']:
            timing['avg_time_per_page'] = sum(timing['pages_timings']) / len(timing['pages_timings'])
        
        # 准确度信息
        accuracy = {
            'text_quality': 'unknown',
            'keyword_detection_rate': 0,
            'page_count_match': False,
            'fallback_rate': round(details['fallback_pages'] / max(len(pages), 1) * 100, 2),
            'region_usable_rate': round(details['region_usable_pages'] / max(len(pages), 1) * 100, 2),
            'marker_detection_rate': 0,
        }
        
        if not ocr_result.get('pages'):
            accuracy['text_quality'] = 'empty'
            return ValidationResult(
                status=ValidationStatus.FAIL,
                file_name=file_name,
                file_type=doc_type,
                message='OCR 未识别到任何内容',
                details=details,
                suggestions=['检查 PDF 文件是否损坏', '检查 PDF 是否为扫描件'],
                timing=timing,
                accuracy=accuracy
            )
        
        # 检查关键字
        full_text = '\n'.join([p.get('text', '') for p in ocr_result['pages']])
        keywords_found = []
        for keyword in keywords:
            if keyword in full_text:
                keywords_found.append(keyword)
        
        details['keywords_found'] = keywords_found
        accuracy['keyword_detection_rate'] = len(keywords_found) / len(keywords) * 100 if keywords else 0
        accuracy['marker_detection_rate'] = round(details['marker_detected_pages'] / max(len(pages), 1) * 100, 2)
        
        # 评估文本质量
        if len(full_text) > _cfg.text_quality['company_doc']['good']:
            accuracy['text_quality'] = 'good'
        elif len(full_text) > _cfg.text_quality['company_doc']['fair']:
            accuracy['text_quality'] = 'fair'
        else:
            accuracy['text_quality'] = 'poor'
        
        # 验证页数
        actual_pages = ocr_result.get('total_pages', 0)
        doc_cfg_key = self._DOC_TYPE_KEY_MAP.get(doc_type, doc_type)
        expected_pages = expected_count * _cfg.pages_per_case[doc_cfg_key]
        accuracy['page_count_match'] = (actual_pages == expected_pages)
        
        if actual_pages != expected_pages:
            details['page_info'] = f'实际 {actual_pages} 页，台账期望 {expected_pages} 页（{expected_count} 公司 × {_cfg.pages_per_case[doc_cfg_key]} 页）'
        
        if not keywords_found:
            return ValidationResult(
                status=ValidationStatus.WARNING,
                file_name=file_name,
                file_type=doc_type,
                message=f'未识别到关键字: {keywords}',
                details=details,
                suggestions=[
                    f'检查 PDF 是否为{doc_type}',
                    '检查 OCR 识别质量',
                    f'识别到的文本长度: {len(full_text)} 字符',
                    f'文本预览: {full_text[:300]}...' if full_text else '无文本内容',
                    '关键字可能识别错误，建议人工确认'
                ],
                timing=timing,
                accuracy=accuracy
            )
        
        return ValidationResult(
            status=ValidationStatus.PASS,
            file_name=file_name,
            file_type=doc_type,
            message=f'验证通过: {actual_pages} 页，识别到关键字',
            details=details,
            suggestions=[],
            timing=timing,
            accuracy=accuracy
        )
    
    def _fuzzy_match_notice(self, detected: str) -> Tuple[Optional[str], float]:
        """模糊匹配责令号"""
        from difflib import SequenceMatcher
        
        best_match = None
        best_ratio = 0
        
        for expected in self.expected_notice_numbers:
            ratio = SequenceMatcher(None, detected, expected).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = expected
        
        return best_match, best_ratio
    
    def generate_report(self) -> Dict:
        """生成验证报告"""
        total = len(self.validation_report)
        passed = sum(1 for r in self.validation_report if r.status == ValidationStatus.PASS)
        warnings = sum(1 for r in self.validation_report if r.status == ValidationStatus.WARNING)
        failed = sum(1 for r in self.validation_report if r.status == ValidationStatus.FAIL)
        
        # 计算耗时统计
        timing_stats = {
            'notice': {'total': 0, 'avg': 0, 'min': 0, 'max': 0, 'count': 0},
            'application': {'total': 0, 'avg': 0, 'min': 0, 'max': 0, 'count': 0},
            'authorization': {'total': 0, 'avg': 0, 'min': 0, 'max': 0, 'count': 0},
            'letter': {'total': 0, 'avg': 0, 'min': 0, 'max': 0, 'count': 0},
        }
        
        for r in self.validation_report:
            file_type = r.file_type
            duration = r.timing.get('total_duration', 0)
            if file_type in timing_stats and duration > 0:
                stats = timing_stats[file_type]
                if stats['count'] == 0:
                    stats['min'] = duration
                    stats['max'] = duration
                else:
                    stats['min'] = min(stats['min'], duration)
                    stats['max'] = max(stats['max'], duration)
                stats['total'] += duration
                stats['count'] += 1
        
        # 计算平均值
        for stats in timing_stats.values():
            if stats['count'] > 0:
                stats['avg'] = stats['total'] / stats['count']
        
        # 将 ValidationResult 转换为字典
        def result_to_dict(r: ValidationResult) -> Dict:
            return {
                'status': r.status.value,
                'file_name': r.file_name,
                'file_type': r.file_type,
                'message': r.message,
                'details': r.details,
                'suggestions': r.suggestions,
                'timing': r.timing,
                'accuracy': r.accuracy,
            }
        
        accuracy_summary = {
            'exact_notice_matches': sum(1 for r in self.validation_report if r.file_type == 'notice' and r.status == ValidationStatus.PASS),
            'fuzzy_notice_matches': sum(1 for r in self.validation_report if r.file_type == 'notice' and r.details.get('fuzzy_match')),
            'same_root_remap_warnings': sum(1 for r in self.validation_report if r.file_type == 'notice' and r.details.get('same_root_remap')),
            'notice_failures': sum(1 for r in self.validation_report if r.file_type == 'notice' and r.status == ValidationStatus.FAIL),
            'basis_mismatch_warnings': sum(1 for r in self.validation_report if r.details.get('diagnostic_category') == 'basis_mismatch'),
            'fuzzy_mapping_warnings': sum(1 for r in self.validation_report if r.details.get('diagnostic_category') == 'fuzzy_mapping'),
            'ocr_or_heuristic_failures': sum(1 for r in self.validation_report if r.details.get('diagnostic_category') in {'ocr_failure', 'heuristic_mismatch'}),
            'documents_with_high_fallback': sum(1 for r in self.validation_report if r.details.get('fallback_pages', 0) >= 2),
            'fallback_pages_total': sum(r.details.get('fallback_pages', 0) for r in self.validation_report),
            'boundary_pages_detected': sum(len(r.details.get('boundary_pages_detected', [])) for r in self.validation_report if r.file_type == 'application'),
            'marker_detected_pages': sum(r.details.get('marker_detected_pages', 0) for r in self.validation_report if r.file_type in {'authorization', 'letter'}),
        }

        optimization_guardrails = {
            'warning_count': warnings,
            'failed_count': failed,
            'fallback_pages_total': accuracy_summary['fallback_pages_total'],
            'needs_review': failed > 0 or warnings > 0,
        }

        return {
            'summary': {
                'total': total,
                'passed': passed,
                'warnings': warnings,
                'failed': failed,
                'pass_rate': passed / total if total > 0 else 0,
            },
            'timing_statistics': timing_stats,
            'accuracy_summary': accuracy_summary,
            'optimization_guardrails': optimization_guardrails,
            'details': [result_to_dict(r) for r in self.validation_report],
            'failed_items': [result_to_dict(r) for r in self.validation_report if r.status == ValidationStatus.FAIL],
            'warning_items': [result_to_dict(r) for r in self.validation_report if r.status == ValidationStatus.WARNING],
        }
    
    def save_report(self, output_path: Path):
        """保存验证报告"""
        report = self.generate_report()
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\n📄 验证报告已保存: {output_path}")


# 便捷函数 (validate_ocr_results 已在上方定义)
def validate_ocr_results(cases: List[Dict], ocr_results: Dict[str, Dict],
                         input_dir: Optional[Path] = None,
                         output_report_path: Optional[Path] = None) -> Dict:
    """
    验证所有 OCR 结果

    Args:
        cases: 台账案件列表
        ocr_results: OCR 识别结果字典 {source_name: result_dict}
        input_dir: 输入目录（用于动态发现责催文件）
        output_report_path: 报告输出路径

    Returns:
        验证报告字典
    """
    validator = NonLitigationValidator(cases)

    # 验证责催文件 - 动态发现
    if input_dir and input_dir.exists():
        notice_files = discover_notice_files(input_dir)
    else:
        notice_files = []
        non_notice_keys = {dt.key for dt in _cfg.doc_types if not dt.is_notice}
        for key in ocr_results:
            name = key.replace('.pdf', '')
            if name not in non_notice_keys:
                notice_files.append(key)

    for source_name in notice_files:
        ocr_result = ocr_results.get(source_name)
        if ocr_result is None:
            bare = source_name.replace('.pdf', '')
            ocr_result = ocr_results.get(f'{bare}.pdf') or ocr_results.get(bare)
        if ocr_result is not None:
            result = validator.validate_notice_ocr(source_name, ocr_result)
            validator.validation_report.append(result)
    
    for dt in _cfg.doc_types:
        if dt.is_notice:
            continue
        ocr_result = ocr_results.get(f'{dt.key}.pdf') or ocr_results.get(dt.key)
        if ocr_result is not None:
            if dt.key == '申请书':
                result = validator.validate_application_ocr(f'{dt.key}.pdf', ocr_result, len(cases))
            else:
                doc_type_str = 'authorization' if dt.key == '授权书' else 'letter'
                result = validator.validate_company_document_ocr(
                    f'{dt.key}.pdf', ocr_result, len(cases), doc_type_str
                )
            validator.validation_report.append(result)
    
    # 生成报告
    report = validator.generate_report()
    
    if output_report_path:
        validator.save_report(output_report_path)
    
    return report
