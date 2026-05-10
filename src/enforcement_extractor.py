#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强制执行组 - 裁定PDF信息提取模块

功能：
1. 从裁定PDF中提取关键信息（案号、当事人、执行标的、日期、审判员/书记员等）
2. 支持多个申请执行人和被执行人的识别
3. 通过责令号或法院案号与台账进行关联
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))

from config_loader import load_config

_cfg = load_config()
_enforcement_cfg = _cfg.raw_config.get('enforcement', {})
_extraction_cfg = _enforcement_cfg.get('extraction', {})


@dataclass
class RulingInfo:
    """裁定书提取信息数据结构"""
    court_case_number: str = ""                    # 法院案号，如（2025）粤7101行审3355号
    notice_numbers: List[str] = field(default_factory=list)  # 关联的责令号列表
    applicants: List[Dict[str, str]] = field(default_factory=list)   # 申请执行人列表
    respondents: List[Dict[str, str]] = field(default_factory=list)  # 被执行人列表
    execution_amount: Optional[float] = None       # 执行标的金额
    ruling_date: Optional[str] = None              # 裁定日期
    judge: str = ""                                # 审判员
    clerk: str = ""                                # 书记员
    court_name: str = "广州铁路运输法院"            # 法院名称
    ruling_result: str = "准予强制执行"             # 裁定结果
    
    # 原始文本（用于调试）
    raw_text: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'court_case_number': self.court_case_number,
            'notice_numbers': self.notice_numbers,
            'applicants': self.applicants,
            'respondents': self.respondents,
            'execution_amount': self.execution_amount,
            'ruling_date': self.ruling_date,
            'judge': self.judge,
            'clerk': self.clerk,
            'court_name': self.court_name,
            'ruling_result': self.ruling_result,
        }


@dataclass
class ExtractionResult:
    """提取结果（带置信度）"""
    value: Any
    confidence: float = 0.0
    source: str = ""  # 使用的规则/策略名称
    
    def __bool__(self):
        return self.value is not None and self.confidence > 0


class RuleBasedExtractor:
    """基于规则的提取器（配置驱动）"""
    
    def __init__(self, rules_config: List[Dict[str, Any]]):
        """
        初始化规则提取器
        
        Args:
            rules_config: 规则配置列表，每项包含：
                - name: 规则名称
                - pattern: 正则表达式
                - weight: 权重（置信度基础分）
                - post_process: 后处理函数名（可选）
        """
        self.rules = []
        for rule in rules_config:
            try:
                pattern = rule.get('pattern', '')
                # 处理YAML转义
                pattern = pattern.replace('\\d', r'\d')
                compiled = re.compile(pattern)
                self.rules.append({
                    'name': rule.get('name', 'unnamed'),
                    'pattern': compiled,
                    'weight': rule.get('weight', 1.0),
                    'post_process': rule.get('post_process'),
                })
            except re.error as e:
                print(f"[WARN] 规则编译失败: {rule.get('name')}, 错误: {e}")
    
    def extract(self, text: str) -> ExtractionResult:
        """
        使用所有规则尝试提取，返回置信度最高的结果
        """
        best_result = ExtractionResult(None, 0.0, "")
        
        for rule in self.rules:
            match = rule['pattern'].search(text)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                
                # 后处理
                if rule['post_process']:
                    value = self._apply_post_process(value, rule['post_process'])
                
                # 计算置信度（基于权重和匹配质量）
                confidence = rule['weight'] * self._calculate_match_quality(match, text)
                
                if confidence > best_result.confidence:
                    best_result = ExtractionResult(value, confidence, rule['name'])
        
        return best_result
    
    def extract_all(self, text: str) -> List[ExtractionResult]:
        """返回所有匹配结果（按置信度排序）"""
        results = []
        
        for rule in self.rules:
            for match in rule['pattern'].finditer(text):
                value = match.group(1) if match.lastindex else match.group(0)
                
                if rule['post_process']:
                    value = self._apply_post_process(value, rule['post_process'])
                
                confidence = rule['weight'] * self._calculate_match_quality(match, text)
                results.append(ExtractionResult(value, confidence, rule['name']))
        
        # 按置信度排序
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results
    
    def _calculate_match_quality(self, match: re.Match, text: str) -> float:
        """计算匹配质量（0-1之间）"""
        # 匹配长度适中得分高
        match_len = len(match.group(0))
        if match_len < 3:
            return 0.5
        elif match_len > 100:
            return 0.7
        return 1.0
    
    def _apply_post_process(self, value: str, process_name: str) -> Any:
        """应用后处理"""
        processors = {
            'parse_amount': self._parse_amount,
            'normalize_date': self._normalize_date,
            'clean_name': self._clean_name,
        }
        processor = processors.get(process_name)
        return processor(value) if processor else value
    
    @staticmethod
    def _parse_amount(amount_str: str) -> Optional[float]:
        """解析金额字符串"""
        try:
            # 移除千分位逗号和空格
            cleaned = amount_str.replace(',', '').replace(' ', '').replace('，', '')
            return float(cleaned)
        except ValueError:
            return None
    
    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """标准化日期格式"""
        # 统一中文零字符
        date_str = date_str.replace('○', '〇').replace('零', '〇')
        return date_str.strip()
    
    @staticmethod
    def _clean_name(name: str) -> str:
        """清理名称"""
        suffixes = [
            '，住所地', ',住所地', '，统一社会信用代码', ',统一社会信用代码',
            '，法定代表人', ',法定代表人', '，职务', ',职务',
            '，住所', ',住所', '，地址', ',地址',
        ]
        for suffix in suffixes:
            if suffix in name:
                name = name.split(suffix)[0]
        return name.strip()


class RulingTextExtractor:
    """裁定书文本信息提取器（配置驱动）"""
    
    def __init__(self):
        self._init_extractors()
    
    def _init_extractors(self):
        """初始化配置驱动的提取器"""
        # 法院案号提取器
        court_case_rules = [{
            'name': 'court_case',
            'pattern': _extraction_cfg.get('court_case_pattern', r'[（(]\d{4}[）)]\s*粤\s*\d+\s*行审\s*\d+\s*号'),
            'weight': 1.0,
        }]
        self.court_case_extractor = RuleBasedExtractor(court_case_rules)
        
        # 责令号提取器
        notice_rules = [{
            'name': 'notice_number',
            'pattern': _extraction_cfg.get('notice_number_in_ruling_pattern', 
                                          r'穗公积金中心[^\s，。；《》]*?责字[〔\[(［【]\d{4}[〕\)\]］】]\d+(?:-\d+)?号'),
            'weight': 1.0,
        }]
        self.notice_extractor = RuleBasedExtractor(notice_rules)
        
        # 金额提取器（多规则）
        amount_rules = []
        for i, pattern in enumerate(_extraction_cfg.get('amount_patterns', [])):
            amount_rules.append({
                'name': f'amount_rule_{i}',
                'pattern': pattern,
                'weight': 1.0 - (i * 0.1),  # 前面的规则权重更高
                'post_process': 'parse_amount',
            })
        self.amount_extractor = RuleBasedExtractor(amount_rules)
        
        # 日期提取器（多规则）
        date_rules = []
        for i, pattern in enumerate(_extraction_cfg.get('date_patterns', [])):
            date_rules.append({
                'name': f'date_rule_{i}',
                'pattern': pattern,
                'weight': 1.0 - (i * 0.1),
                'post_process': 'normalize_date',
            })
        self.date_extractor = RuleBasedExtractor(date_rules)
        
        # 审判员提取器
        judge_rules = []
        for i, pattern in enumerate(_extraction_cfg.get('judge_patterns', [])):
            judge_rules.append({
                'name': f'judge_rule_{i}',
                'pattern': pattern,
                'weight': 1.0,
                'post_process': 'clean_name',
            })
        self.judge_extractor = RuleBasedExtractor(judge_rules)
        
        # 书记员提取器
        clerk_rules = []
        for i, pattern in enumerate(_extraction_cfg.get('clerk_patterns', [])):
            clerk_rules.append({
                'name': f'clerk_rule_{i}',
                'pattern': pattern,
                'weight': 1.0,
                'post_process': 'clean_name',
            })
        self.clerk_extractor = RuleBasedExtractor(clerk_rules)
        
        # 申请执行人提取器
        applicant_rules = []
        for i, pattern in enumerate(_extraction_cfg.get('applicant_patterns', [])):
            applicant_rules.append({
                'name': f'applicant_rule_{i}',
                'pattern': pattern,
                'weight': 1.0,
                'post_process': 'clean_name',
            })
        self.applicant_extractor = RuleBasedExtractor(applicant_rules)
        
        # 被执行人提取器
        respondent_rules = []
        for i, pattern in enumerate(_extraction_cfg.get('respondent_patterns', [])):
            respondent_rules.append({
                'name': f'respondent_rule_{i}',
                'pattern': pattern,
                'weight': 1.0,
                'post_process': 'clean_name',
            })
        self.respondent_extractor = RuleBasedExtractor(respondent_rules)
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本：移除多余换行和空格，便于正则匹配"""
        # 将换行符替换为空格，避免跨行内容被连接在一起
        text = text.replace('\n', ' ').replace('\r', ' ')
        # 标准化空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def extract(self, text: str) -> RulingInfo:
        """从文本中提取裁定信息（使用配置驱动的规则引擎）"""
        info = RulingInfo(raw_text=text)
        
        # 预处理文本以便更好地匹配
        processed_text = self._preprocess_text(text)
        
        # 提取法院案号
        case_result = self.court_case_extractor.extract(text)
        if case_result:
            info.court_case_number = self._normalize_case_number(case_result.value)
        
        # 提取责令号（使用预处理后的文本）
        notice_results = self.notice_extractor.extract_all(processed_text)
        info.notice_numbers = self._normalize_notice_numbers(notice_results)
        
        # 提取申请执行人
        applicant_results = self.applicant_extractor.extract_all(text)
        info.applicants = self._convert_to_party_list(applicant_results, '申请执行人')
        
        # 提取被执行人
        respondent_results = self.respondent_extractor.extract_all(text)
        info.respondents = self._convert_to_party_list(respondent_results, '被执行人')
        
        # 提取执行标的金额（使用预处理后的文本）
        amount_result = self.amount_extractor.extract(processed_text)
        if amount_result:
            info.execution_amount = amount_result.value
        
        # 提取裁定日期
        date_result = self.date_extractor.extract(text)
        if date_result:
            info.ruling_date = date_result.value
        
        # 提取审判员
        judge_result = self.judge_extractor.extract(text)
        if judge_result:
            info.judge = judge_result.value
        
        # 提取书记员
        clerk_result = self.clerk_extractor.extract(text)
        if clerk_result:
            info.clerk = clerk_result.value
        
        return info
    
    def extract_with_confidence(self, text: str) -> Dict[str, Any]:
        """提取信息并返回置信度（用于调试和优化）"""
        processed_text = self._preprocess_text(text)
        
        results = {
            'court_case_number': self.court_case_extractor.extract(text),
            'notice_numbers': self.notice_extractor.extract_all(processed_text),
            'applicants': self.applicant_extractor.extract_all(text),
            'respondents': self.respondent_extractor.extract_all(text),
            'execution_amount': self.amount_extractor.extract(processed_text),
            'ruling_date': self.date_extractor.extract(text),
            'judge': self.judge_extractor.extract(text),
            'clerk': self.clerk_extractor.extract(text),
        }
        
        return results
    
    def _normalize_case_number(self, case_num: str) -> str:
        """标准化法院案号格式"""
        case_num = case_num.replace('(', '（').replace(')', '）')
        case_num = case_num.replace('[', '（').replace(']', '）')
        return case_num
    
    def _normalize_notice_numbers(self, results: List[ExtractionResult]) -> List[str]:
        """标准化责令号列表"""
        seen = set()
        normalized = []
        for result in results:
            num = result.value
            # 标准化括号
            num = num.replace('(', '〔').replace(')', '〕')
            num = num.replace('[', '〔').replace(']', '〕')
            num = num.replace('（', '〔').replace('）', '〕')
            num = num.replace('［', '〔').replace('］', '〕')
            num = num.replace('【', '〔').replace('】', '〕')
            if num not in seen:
                seen.add(num)
                normalized.append(num)
        return normalized
    
    def _convert_to_party_list(self, results: List[ExtractionResult], party_type: str) -> List[Dict[str, str]]:
        """将提取结果转换为当事人列表"""
        parties = []
        seen = set()
        
        for result in results:
            name = result.value
            if name and name not in seen and len(name) > 2:
                seen.add(name)
                parties.append({
                    'name': name,
                    'type': party_type,
                    'confidence': result.confidence,
                })
        
        return parties


class RulingPDFExtractor:
    """裁定PDF文件信息提取器"""
    
    def __init__(self, use_ocr: bool = True):
        self.use_ocr = use_ocr
        self.text_extractor = RulingTextExtractor()
        self._ocr_engine = None
    
    def _get_ocr_engine(self):
        """延迟初始化OCR引擎"""
        if self._ocr_engine is None and self.use_ocr:
            try:
                from pdf_ocr_ultra import UltraFastOCR, OCRConfig
                config = OCRConfig(
                    dpi=_cfg.ocr_dpi,
                    max_image_size=_cfg.ocr_max_image_size,
                    parallel_workers=1,
                )
                self._ocr_engine = UltraFastOCR(config, skip_warmup=True)
            except ImportError:
                print("[WARN] OCR引擎加载失败，将使用pdfplumber文本提取")
                self.use_ocr = False
        return self._ocr_engine
    
    def extract_from_pdf(self, pdf_path: Path) -> RulingInfo:
        """从PDF文件中提取裁定信息"""
        # 首先尝试使用pdfplumber提取文本
        text = self._extract_text_from_pdf(pdf_path)
        
        # 如果文本太短或为空，使用OCR
        if len(text.strip()) < 100 and self.use_ocr:
            text = self._extract_text_with_ocr(pdf_path)
        
        # 应用OCR纠错
        text = self._apply_corrections(text)
        
        # 提取信息
        return self.text_extractor.extract(text)
    
    def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """使用pdfplumber提取文本"""
        try:
            import pdfplumber
            texts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    texts.append(text)
            return "\n".join(texts)
        except Exception as e:
            print(f"[WARN] pdfplumber提取失败: {e}")
            return ""
    
    def _extract_text_with_ocr(self, pdf_path: Path) -> str:
        """使用OCR提取文本"""
        ocr = self._get_ocr_engine()
        if ocr is None:
            return ""
        
        try:
            result = ocr.process_pdf(pdf_path)
            texts = []
            for page_result in result.get('pages', []):
                page_text = page_result.get('text', '')
                texts.append(page_text)
            return "\n".join(texts)
        except Exception as e:
            print(f"[WARN] OCR提取失败: {e}")
            return ""
    
    def _apply_corrections(self, text: str) -> str:
        """应用OCR纠错"""
        corrections = _enforcement_cfg.get('ocr_corrections', [])
        for correction in corrections:
            wrong = correction.get('wrong', '')
            correct = correction.get('correct', '')
            if wrong and correct:
                text = text.replace(wrong, correct)
        return text


def extract_ruling_from_pdf(pdf_path: Path, use_ocr: bool = True) -> RulingInfo:
    """
    从裁定PDF中提取信息的便捷函数
    
    Args:
        pdf_path: PDF文件路径
        use_ocr: 是否使用OCR（当pdfplumber提取失败时）
    
    Returns:
        RulingInfo: 提取的裁定信息
    """
    extractor = RulingPDFExtractor(use_ocr=use_ocr)
    return extractor.extract_from_pdf(pdf_path)


def batch_extract_rulings(pdf_dir: Path, use_ocr: bool = True) -> Dict[str, RulingInfo]:
    """
    批量提取目录下所有裁定PDF的信息
    
    Args:
        pdf_dir: 包含裁定PDF的目录
        use_ocr: 是否使用OCR
    
    Returns:
        Dict[str, RulingInfo]: 以法院案号为键的提取结果字典
    """
    results = {}
    extractor = RulingPDFExtractor(use_ocr=use_ocr)
    
    for pdf_file in sorted(pdf_dir.glob("*.pdf")):
        print(f"[INFO] 处理: {pdf_file.name}")
        try:
            info = extractor.extract_from_pdf(pdf_file)
            if info.court_case_number:
                results[info.court_case_number] = info
            else:
                # 如果无法提取案号，使用文件名作为键
                results[pdf_file.stem] = info
        except Exception as e:
            print(f"[ERROR] 处理 {pdf_file.name} 失败: {e}")
    
    return results


if __name__ == "__main__":
    # 测试代码
    test_pdf = Path("样本材料/强制组-自动化/提取信息/（2025）粤7101行审3355号.pdf")
    if test_pdf.exists():
        info = extract_ruling_from_pdf(test_pdf, use_ocr=False)
        print("\n提取结果:")
        print(json.dumps(info.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"测试文件不存在: {test_pdf}")
