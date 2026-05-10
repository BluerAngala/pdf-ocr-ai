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


class RulingTextExtractor:
    """裁定书文本信息提取器"""
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则表达式模式"""
        # 法院案号
        court_case_pattern = _extraction_cfg.get('court_case_pattern', r'[（(]\d{4}[）)]\s*粤\s*\d+\s*行审\s*\d+\s*号')
        self.court_case_re = re.compile(court_case_pattern)
        
        # 责令号
        notice_pattern = _extraction_cfg.get('notice_number_in_ruling_pattern', 
                                             r'穗公积金中心[^\s，。；《》]*?责字[〔\[(［【]\d{4}[〕\)\]］】]\d+(?:-\d+)?号')
        self.notice_re = re.compile(notice_pattern)
        
        # 执行标的金额
        self.amount_res = []
        for pattern in _extraction_cfg.get('amount_patterns', []):
            try:
                # 处理YAML转义问题：将\d转换为\d
                pattern = pattern.replace('\\d', r'\d')
                self.amount_res.append(re.compile(pattern))
            except re.error:
                continue
        
        # 裁定日期
        self.date_res = []
        for pattern in _extraction_cfg.get('date_patterns', []):
            try:
                # 处理YAML转义问题：将\d转换为\d
                pattern = pattern.replace('\\d', r'\d')
                self.date_res.append(re.compile(pattern))
            except re.error:
                continue
        
        # 审判员
        self.judge_res = []
        for pattern in _extraction_cfg.get('judge_patterns', []):
            try:
                self.judge_res.append(re.compile(pattern))
            except re.error:
                continue
        
        # 书记员
        self.clerk_res = []
        for pattern in _extraction_cfg.get('clerk_patterns', []):
            try:
                self.clerk_res.append(re.compile(pattern))
            except re.error:
                continue
        
        # 申请执行人
        self.applicant_res = []
        for pattern in _extraction_cfg.get('applicant_patterns', []):
            try:
                self.applicant_res.append(re.compile(pattern))
            except re.error:
                continue
        
        # 被执行人
        self.respondent_res = []
        for pattern in _extraction_cfg.get('respondent_patterns', []):
            try:
                self.respondent_res.append(re.compile(pattern))
            except re.error:
                continue
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本：移除多余换行和空格，便于正则匹配"""
        # 将换行符替换为空格，避免跨行内容被连接在一起
        text = text.replace('\n', ' ').replace('\r', ' ')
        # 标准化空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def extract(self, text: str) -> RulingInfo:
        """从文本中提取裁定信息"""
        info = RulingInfo(raw_text=text)
        
        # 预处理文本以便更好地匹配
        processed_text = self._preprocess_text(text)
        
        # 提取法院案号
        info.court_case_number = self._extract_court_case_number(text)
        
        # 提取责令号（使用预处理后的文本）
        info.notice_numbers = self._extract_notice_numbers(processed_text)
        
        # 提取申请执行人
        info.applicants = self._extract_applicants(text)
        
        # 提取被执行人
        info.respondents = self._extract_respondents(text)
        
        # 提取执行标的金额（使用预处理后的文本）
        info.execution_amount = self._extract_amount(processed_text)
        
        # 提取裁定日期
        info.ruling_date = self._extract_date(text)
        
        # 提取审判员
        info.judge = self._extract_judge(text)
        
        # 提取书记员
        info.clerk = self._extract_clerk(text)
        
        return info
    
    def _extract_court_case_number(self, text: str) -> str:
        """提取法院案号"""
        match = self.court_case_re.search(text)
        if match:
            # 标准化格式：统一使用中文括号
            case_num = match.group(0)
            case_num = case_num.replace('(', '（').replace(')', '）')
            case_num = case_num.replace('[', '（').replace(']', '）')
            return case_num
        return ""
    
    def _extract_notice_numbers(self, text: str) -> List[str]:
        """提取责令号列表"""
        matches = self.notice_re.findall(text)
        # 去重并保持顺序
        seen = set()
        result = []
        for match in matches:
            # 标准化括号
            normalized = match.replace('(', '〔').replace(')', '〕')
            normalized = normalized.replace('[', '〔').replace(']', '〕')
            normalized = normalized.replace('（', '〔').replace('）', '〕')
            normalized = normalized.replace('［', '〔').replace('］', '〕')
            normalized = normalized.replace('【', '〔').replace('】', '〕')
            if normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result
    
    def _extract_applicants(self, text: str) -> List[Dict[str, str]]:
        """提取申请执行人列表"""
        applicants = []
        seen = set()
        
        for pattern in self.applicant_res:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                # 清理常见后缀
                name = self._clean_party_name(name)
                if name and name not in seen and len(name) > 2:
                    seen.add(name)
                    applicants.append({
                        'name': name,
                        'type': '申请执行人'
                    })
        
        return applicants
    
    def _extract_respondents(self, text: str) -> List[Dict[str, str]]:
        """提取被执行人列表"""
        respondents = []
        seen = set()
        
        for pattern in self.respondent_res:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                # 清理常见后缀
                name = self._clean_party_name(name)
                if name and name not in seen and len(name) > 2:
                    seen.add(name)
                    respondents.append({
                        'name': name,
                        'type': '被执行人'
                    })
        
        return respondents
    
    def _clean_party_name(self, name: str) -> str:
        """清理当事人名称"""
        # 移除常见的地址、代码等后缀
        suffixes = [
            '，住所地', ',住所地', '，统一社会信用代码', ',统一社会信用代码',
            '，法定代表人', ',法定代表人', '，职务', ',职务',
            '，住所', ',住所', '，地址', ',地址',
        ]
        for suffix in suffixes:
            if suffix in name:
                name = name.split(suffix)[0]
        return name.strip()
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """提取执行标的金额"""
        for pattern in self.amount_res:
            match = pattern.search(text)
            if match:
                amount_str = match.group(1)
                # 移除千分位逗号和空格
                amount_str = amount_str.replace(',', '').replace(' ', '')
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        """提取裁定日期"""
        for pattern in self.date_res:
            match = pattern.search(text)
            if match:
                # 如果有捕获组，使用第一个捕获组；否则使用整个匹配
                date_str = match.group(1) if match.lastindex else match.group(0)
                # 标准化日期格式
                date_str = date_str.replace('○', '〇').replace('零', '〇')
                return date_str
        return None
    
    def _extract_judge(self, text: str) -> str:
        """提取审判员"""
        # 移除空格后匹配
        text_no_space = text.replace(' ', '').replace('\u3000', '')
        for pattern in self.judge_res:
            match = pattern.search(text_no_space)
            if match:
                return match.group(1).strip()
        return ""
    
    def _extract_clerk(self, text: str) -> str:
        """提取书记员"""
        # 移除空格后匹配
        text_no_space = text.replace(' ', '').replace('\u3000', '')
        for pattern in self.clerk_res:
            match = pattern.search(text_no_space)
            if match:
                return match.group(1).strip()
        return ""


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
