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
        
        details = {
            'file_name': file_name,
            'total_pages': ocr_result.get('total_pages', 0),
            'pages_processed': len(ocr_result.get('pages', [])),
            'detected_notices': [],
            'matched_case': None,
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
        }
        
        # 检查是否识别到任何内容
        if not ocr_result.get('pages'):
            accuracy['text_quality'] = 'empty'
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
        
        if matched:
            return ValidationResult(
                status=ValidationStatus.PASS,
                file_name=file_name,
                file_type='notice',
                message=f'成功识别并匹配责令号: {detected_notices[0]}',
                details=details,
                suggestions=[],
                timing=timing,
                accuracy=accuracy
            )
        else:
            # 尝试模糊匹配
            best_match, ratio = self._fuzzy_match_notice(normalized_detected[0])
            if best_match and ratio >= _cfg.fuzzy_match_threshold:
                details['fuzzy_match'] = {'target': best_match, 'ratio': ratio}
                accuracy['match_confidence'] = int(ratio * 100)
                return ValidationResult(
                    status=ValidationStatus.WARNING,
                    file_name=file_name,
                    file_type='notice',
                    message=f'识别到责令号但未精确匹配，模糊匹配相似度: {ratio:.1%}',
                    details=details,
                    suggestions=[
                        f'识别结果: {detected_notices[0]}',
                        f'建议匹配: {best_match}',
                        '请人工确认是否匹配正确'
                    ],
                    timing=timing,
                    accuracy=accuracy
                )
            else:
                return ValidationResult(
                    status=ValidationStatus.FAIL,
                    file_name=file_name,
                    file_type='notice',
                    message=f'识别到责令号但无法匹配台账: {detected_notices[0]}',
                    details=details,
                    suggestions=[
                        '检查台账 Excel 是否包含此责令号',
                        '检查责令号格式是否正确（如括号类型）',
                        f'识别到的责令号: {detected_notices[0]}',
                        f'期望的责令号示例: {self.expected_notice_numbers[0] if self.expected_notice_numbers else "N/A"}'
                    ],
                    timing=timing,
                    accuracy=accuracy
                )
    
    def validate_application_ocr(self, file_name: str, ocr_result: Dict, 
                                  expected_cases: int) -> ValidationResult:
        """验证申请书 OCR 结果"""
        details = {
            'file_name': file_name,
            'total_pages': ocr_result.get('total_pages', 0),
            'expected_cases': expected_cases,
            'detected_cases': 0,
            'keywords_found': [],
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
            return ValidationResult(
                status=ValidationStatus.WARNING,
                file_name=file_name,
                file_type='application',
                message=f'识别到 {case_count} 个案件，期望 {expected_cases} 个',
                details=details,
                suggestions=[
                    '检查申请书页数是否正确（应为 2 页/案件）',
                    '检查是否有缺失或多余的案件',
                    f'当前页数: {details["total_pages"]} 页',
                    f'期望页数: {expected_cases * _cfg.pages_per_case["申请书"]} 页（{expected_cases} 案件 × {_cfg.pages_per_case["申请书"]} 页）'
                ],
                timing=timing,
                accuracy=accuracy
            )
        
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
        
        details = {
            'file_name': file_name,
            'total_pages': ocr_result.get('total_pages', 0),
            'expected_count': expected_count,
            'doc_type': doc_type,
            'keywords_found': [],
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
            return ValidationResult(
                status=ValidationStatus.WARNING,
                file_name=file_name,
                file_type=doc_type,
                message=f'页数不匹配: 实际 {actual_pages} 页，期望 {expected_pages} 页',
                details=details,
                suggestions=[
                    f'检查 {doc_type} 页数是否正确（应为 {_cfg.pages_per_case[doc_cfg_key]} 页/公司）',
                    '确认台账公司数量是否正确',
                    f'实际页数: {actual_pages} 页',
                    f'期望页数: {expected_pages} 页（{expected_count} 公司 × {_cfg.pages_per_case[doc_cfg_key]} 页）'
                ],
                timing=timing,
                accuracy=accuracy
            )
        
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
        
        return {
            'summary': {
                'total': total,
                'passed': passed,
                'warnings': warnings,
                'failed': failed,
                'pass_rate': passed / total if total > 0 else 0,
            },
            'timing_statistics': timing_stats,
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
def validate_ocr_results(cases: List[Dict], ocr_cache_dir: Path,
                         input_dir: Optional[Path] = None,
                         output_report_path: Optional[Path] = None) -> Dict:
    """
    验证所有 OCR 结果

    Args:
        cases: 台账案件列表
        ocr_cache_dir: OCR 缓存目录
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
        for cache_file in sorted(ocr_cache_dir.glob('*_ultra_result.json')):
            name = cache_file.stem.replace('_ultra_result', '')
            if name not in tuple(dt.key for dt in _cfg.doc_types if not dt.is_notice):
                notice_files.append(f'{name}.pdf')

    for source_name in notice_files:
        stem = source_name.replace('.pdf', '')
        cache_file = ocr_cache_dir / f'{stem}_ultra_result.json'
        if cache_file.exists():
            ocr_result = json.loads(cache_file.read_text(encoding='utf-8'))
            result = validator.validate_notice_ocr(source_name, ocr_result)
            validator.validation_report.append(result)
    
    for dt in _cfg.doc_types:
        if dt.is_notice:
            continue
        cache_file = ocr_cache_dir / f'{dt.key}{_cfg.ocr_cache_suffix}'
        if cache_file.exists():
            ocr_result = json.loads(cache_file.read_text(encoding='utf-8'))
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
