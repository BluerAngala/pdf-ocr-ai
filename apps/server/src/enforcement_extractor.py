#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强制执行组 - 裁定PDF信息提取模块

功能：
1. 从裁定PDF中提取关键信息（案号、当事人、执行标的、日期、审判员/书记员等）
2. 支持多个申请执行人和被执行人的识别
3. 通过责令号或法院案号与台账进行关联
4. 支持撤回执行裁定识别
5. 支持责令号范围展开（如"3360号至3361号"）
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from paths import ROOT, USER_DATA_DIR

from config_loader import load_config

_cfg = load_config()
_enforcement_cfg = _cfg.raw_config.get('enforcement', {})
_extraction_cfg = _enforcement_cfg.get('extraction', {})


CJK_RANGE = re.compile(r'([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])\s+([\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])')
CJK_PUNCT = re.compile(r'([\u4e00-\u9fff])\s+([，。；：、！？…——（）《》〔〕【】［］""])')
CJK_DIGIT_BEFORE = re.compile(r'([\u4e00-\u9fff])\s+(\d)')
CJK_DIGIT_AFTER = re.compile(r'(\d)\s+([\u4e00-\u9fff])')
CJK_BRACKET_BEFORE = re.compile(r'([（(])\s+(\d{4})')
CJK_BRACKET_AFTER = re.compile(r'(\d{4})\s+([）)])')


def remove_cjk_spacing(text: str) -> str:
    """移除中文字符之间的排版间距（多轮替换，直至稳定）"""
    two_group_patterns = [
        CJK_RANGE,
        CJK_PUNCT,
        CJK_DIGIT_BEFORE,
        CJK_DIGIT_AFTER,
        CJK_BRACKET_BEFORE,
        CJK_BRACKET_AFTER,
    ]
    single_group_patterns = [
        (re.compile(r'(\d)\s+号'), r'\1号'),
        (re.compile(r'粤\s+(\d+)'), r'粤\1'),
        (re.compile(r'行审\s+(\d+)'), r'行审\1'),
    ]
    for _ in range(10):
        prev = text
        for pat in two_group_patterns:
            text = pat.sub(r'\1\2', text)
        for pat, repl in single_group_patterns:
            text = pat.sub(repl, text)
        if text == prev:
            break
    return text


CHINESE_DIGIT_MAP = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9,
    '〇': 0, '○': 0, '零': 0,
}

CHINESE_DIGIT_ONLY = {'一', '二', '三', '四', '五', '六', '七', '八', '九', '〇', '○', '零'}


def chinese_digits_to_int(text: str) -> Optional[int]:
    """将中文数字字符串转为整数（支持二十八→28、二〇二五→2025）"""
    text = text.replace('○', '〇').replace('零', '〇')

    if all(ch in CHINESE_DIGIT_ONLY for ch in text):
        result = ''
        for ch in text:
            if ch in CHINESE_DIGIT_MAP:
                result += str(CHINESE_DIGIT_MAP[ch])
        return int(result) if result else None

    current = 0
    result = 0
    for ch in text:
        if ch in CHINESE_DIGIT_MAP:
            current = CHINESE_DIGIT_MAP[ch]
        elif ch == '十':
            current = (current or 1) * 10
            result += current
            current = 0
        elif ch == '百':
            current = (current or 1) * 100
            result += current
            current = 0
        else:
            return None
    result += current
    return result if result > 0 else None


def chinese_date_to_arabic(text: str) -> str:
    """将中文日期字符串（如'二〇二五年四月二十八日'）转为阿拉伯数字格式（'2025年4月28日'）"""
    year_match = re.search(r'(二[〇○]([一二三四五六七八九十〇]{2}))年', text)
    month_match = re.search(r'([一二三四五六七八九十〇]{1,2})月', text)
    day_match = re.search(r'([一二三四五六七八九十〇]{1,3})日', text)

    if year_match:
        year_str = year_match.group(1)
        year_num = chinese_digits_to_int(year_str)
        text = text.replace(year_match.group(0), f'{year_num}年')

    if month_match:
        month_str = month_match.group(1)
        month_num = chinese_digits_to_int(month_str)
        text = text.replace(month_match.group(0), f'{month_num}月')

    if day_match:
        day_str = day_match.group(1)
        day_num = chinese_digits_to_int(day_str)
        text = text.replace(day_match.group(0), f'{day_num}日')

    return text


@dataclass
class RulingInfo:
    """裁定书提取信息数据结构"""
    court_case_number: str = ""
    notice_numbers: List[str] = field(default_factory=list)
    applicants: List[Dict[str, str]] = field(default_factory=list)
    respondents: List[Dict[str, str]] = field(default_factory=list)
    execution_amount: Optional[float] = None
    ruling_date: Optional[str] = None
    judge: str = ""
    clerk: str = ""
    court_name: str = "广州铁路运输法院"
    ruling_result: str = "准予强制执行"
    is_withdraw: bool = False

    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
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
            'is_withdraw': self.is_withdraw,
        }


@dataclass
class ExtractionResult:
    """提取结果（带置信度）"""
    value: Any
    confidence: float = 0.0
    source: str = ""

    def __bool__(self):
        return self.value is not None and self.confidence > 0


class RuleBasedExtractor:
    """基于规则的提取器（配置驱动）"""

    def __init__(self, rules_config: List[Dict[str, Any]]):
        self.rules = []
        for rule in rules_config:
            try:
                pattern = rule.get('pattern', '')
                pattern = pattern.replace('\\d', r'\d')
                pattern = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), pattern)
                compiled = re.compile(pattern)
                self.rules.append({
                    'name': rule.get('name', 'unnamed'),
                    'pattern': compiled,
                    'weight': rule.get('weight', 1.0),
                    'post_process': rule.get('post_process'),
                })
            except re.error as e:
                print(f"WARN: 规则编译失败: {rule.get('name')}, 错误: {e}")

    def extract(self, text: str) -> ExtractionResult:
        best_result = ExtractionResult(None, 0.0, "")
        for rule in self.rules:
            match = rule['pattern'].search(text)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                if rule['post_process']:
                    value = self._apply_post_process(value, rule['post_process'])
                confidence = rule['weight'] * self._calculate_match_quality(match, text)
                if confidence > best_result.confidence:
                    best_result = ExtractionResult(value, confidence, rule['name'])
        return best_result

    def extract_all(self, text: str) -> List[ExtractionResult]:
        results = []
        for rule in self.rules:
            for match in rule['pattern'].finditer(text):
                value = match.group(1) if match.lastindex else match.group(0)
                if rule['post_process']:
                    value = self._apply_post_process(value, rule['post_process'])
                confidence = rule['weight'] * self._calculate_match_quality(match, text)
                results.append(ExtractionResult(value, confidence, rule['name']))
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    def _calculate_match_quality(self, match: re.Match, text: str) -> float:
        match_len = len(match.group(0))
        if match_len < 3:
            return 0.5
        elif match_len > 100:
            return 0.7
        return 1.0

    def _apply_post_process(self, value: str, process_name: str) -> Any:
        processors = {
            'parse_amount': self._parse_amount,
            'normalize_date': self._normalize_date,
            'clean_name': self._clean_name,
        }
        processor = processors.get(process_name)
        return processor(value) if processor else value

    @staticmethod
    def _parse_amount(amount_str: str) -> Optional[float]:
        try:
            cleaned = amount_str.replace(',', '').replace(' ', '').replace('，', '')
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        date_str = date_str.replace('○', '〇').replace('零', '〇')
        return date_str.strip()

    @staticmethod
    def _clean_name(name: str) -> str:
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
        court_case_rules = [{
            'name': 'court_case',
            'pattern': _extraction_cfg.get('court_case_pattern', r'[（(]\d{4}[）)]粤\d+行审\d+号'),
            'weight': 1.0,
        }]
        self.court_case_extractor = RuleBasedExtractor(court_case_rules)

        notice_rules = [{
            'name': 'notice_number',
            'pattern': _extraction_cfg.get('notice_number_in_ruling_pattern',
                                          r'穗公积金中心\S*?责字[〔\[(［【]\d{4}[〕\)\]］】]\d+号'),
            'weight': 1.0,
        }]
        self.notice_extractor = RuleBasedExtractor(notice_rules)

        amount_rules = []
        for i, pattern in enumerate(_extraction_cfg.get('amount_patterns', [])):
            amount_rules.append({
                'name': f'amount_rule_{i}',
                'pattern': pattern,
                'weight': 1.0 - (i * 0.1),
                'post_process': 'parse_amount',
            })
        self.amount_extractor = RuleBasedExtractor(amount_rules)

        date_rules = []
        for i, pattern in enumerate(_extraction_cfg.get('date_patterns', [])):
            date_rules.append({
                'name': f'date_rule_{i}',
                'pattern': pattern,
                'weight': 1.0 - (i * 0.1),
                'post_process': 'normalize_date',
            })
        self.date_extractor = RuleBasedExtractor(date_rules)

        judge_rules = []
        for i, pattern in enumerate(_extraction_cfg.get('judge_patterns', [])):
            judge_rules.append({
                'name': f'judge_rule_{i}',
                'pattern': pattern,
                'weight': 1.0,
                'post_process': 'clean_name',
            })
        self.judge_extractor = RuleBasedExtractor(judge_rules)

        clerk_rules = []
        for i, pattern in enumerate(_extraction_cfg.get('clerk_patterns', [])):
            clerk_rules.append({
                'name': f'clerk_rule_{i}',
                'pattern': pattern,
                'weight': 1.0,
                'post_process': 'clean_name',
            })
        self.clerk_extractor = RuleBasedExtractor(clerk_rules)

        applicant_rules = []
        for i, pattern in enumerate(_extraction_cfg.get('applicant_patterns', [])):
            applicant_rules.append({
                'name': f'applicant_rule_{i}',
                'pattern': pattern,
                'weight': 1.0,
                'post_process': 'clean_name',
            })
        self.applicant_extractor = RuleBasedExtractor(applicant_rules)

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
        """预处理文本：移除换行，移除CJK间距"""
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text)
        text = remove_cjk_spacing(text)
        return text.strip()

    def _detect_withdraw(self, text: str) -> bool:
        """检测是否为撤回执行裁定"""
        keywords = _extraction_cfg.get('withdraw_keywords', ['撤回执行', '撤回强制执行', '不准予强制执行', '不予执行'])
        for kw in keywords:
            if kw in text:
                return True
        return False

    def _expand_notice_ranges(self, text: str) -> List[str]:
        """展开责令号范围（如 3360号至3361号 → 两个独立的责令号）"""
        range_pattern = _extraction_cfg.get('notice_number_range_pattern',
                                            r'责字[〔\[(［【](\d{4})[〕\)\]］】](\d+)号至(\d+)号')
        expanded = []
        for match in re.finditer(range_pattern, text):
            year = match.group(1)
            start_num = int(match.group(2))
            end_num = int(match.group(3))
            for num in range(start_num, end_num + 1):
                expanded.append(f'责字〔{year}〕{num}号')
        return expanded

    def extract(self, text: str) -> RulingInfo:
        """从文本中提取裁定信息"""
        info = RulingInfo(raw_text=text)

        compact_text = self._preprocess_text(text)

        case_result = self.court_case_extractor.extract(compact_text)
        if case_result:
            info.court_case_number = self._normalize_case_number(case_result.value)

        notice_results = self.notice_extractor.extract_all(compact_text)
        info.notice_numbers = self._normalize_notice_numbers(notice_results)

        range_notices = self._expand_notice_ranges(compact_text)
        for rn in range_notices:
            normalized = self._normalize_notice_number(rn)
            existing_normalized = [self._normalize_notice_number(n) for n in info.notice_numbers]
            if normalized not in existing_normalized:
                info.notice_numbers.append(rn)

        info.notice_numbers = self._dedup_notice_numbers(info.notice_numbers)

        applicant_results = self.applicant_extractor.extract_all(text)
        info.applicants = self._convert_to_party_list(applicant_results, '申请执行人')

        respondent_results = self.respondent_extractor.extract_all(text)
        info.respondents = self._convert_to_party_list(respondent_results, '被执行人')

        amount_result = self.amount_extractor.extract(compact_text)
        if amount_result:
            info.execution_amount = amount_result.value

        date_result = self.date_extractor.extract(compact_text)
        if date_result:
            info.ruling_date = date_result.value

        judge_result = self.judge_extractor.extract(compact_text)
        if judge_result:
            info.judge = self._clean_person_name(judge_result.value.strip())

        clerk_result = self.clerk_extractor.extract(compact_text)
        if clerk_result:
            info.clerk = self._clean_person_name(clerk_result.value.strip())

        info.is_withdraw = self._detect_withdraw(text)
        if info.is_withdraw:
            info.ruling_result = "撤回执行"

        if not info.ruling_date:
            info.ruling_date = self._extract_date_by_proximity(compact_text)

        return info

    def _extract_date_by_proximity(self, text: str) -> Optional[str]:
        """后备日期提取：在审判员/书记员附近的日期"""
        for target in ['审判员', '书记员', '本件与原本核对无异']:
            idx = text.find(target)
            if idx >= 0:
                segment = text[max(0, idx - 100):idx + 100]
                date_result = self.date_extractor.extract(segment)
                if date_result:
                    return date_result.value
        return None

    def extract_with_confidence(self, text: str) -> Dict[str, Any]:
        compact_text = self._preprocess_text(text)

        return {
            'court_case_number': self.court_case_extractor.extract(compact_text),
            'notice_numbers': self.notice_extractor.extract_all(compact_text),
            'applicants': self.applicant_extractor.extract_all(text),
            'respondents': self.respondent_extractor.extract_all(text),
            'execution_amount': self.amount_extractor.extract(compact_text),
            'ruling_date': self.date_extractor.extract(compact_text),
            'judge': self.judge_extractor.extract(compact_text),
            'clerk': self.clerk_extractor.extract(compact_text),
            'is_withdraw': self._detect_withdraw(text),
        }

    def _normalize_case_number(self, case_num: str) -> str:
        """标准化法院案号：去除所有空格，统一括号为中文括号"""
        case_num = case_num.replace(' ', '')
        case_num = case_num.replace('(', '（').replace(')', '）')
        case_num = case_num.replace('[', '（').replace(']', '）')
        return case_num

    def _normalize_notice_number(self, num: str) -> str:
        """标准化责令号：统一括号为〔〕"""
        num = num.replace('(', '〔').replace(')', '〕')
        num = num.replace('[', '〔').replace(']', '〕')
        num = num.replace('（', '〔').replace('）', '〕')
        num = num.replace('［', '〔').replace('］', '〕')
        num = num.replace('【', '〔').replace('】', '〕')
        num = num.replace(' ', '')
        return num

    def _normalize_notice_numbers(self, results: List[ExtractionResult]) -> List[str]:
        seen = set()
        normalized = []
        for result in results:
            num = self._normalize_notice_number(result.value)
            if num not in seen:
                seen.add(num)
                normalized.append(result.value)
        return normalized

    @staticmethod
    def _clean_person_name(name: str) -> str:
        """清理人名，去除尾部可能混入的日期数字或标记"""
        noise_chars = {'二', '〇', '○', '零', '一', '三', '四', '五', '六', '七', '八', '九', '十', '—', '本'}
        while len(name) > 1 and name[-1] in noise_chars:
            name = name[:-1]
        name = re.sub(r'—?\d+—?$', '', name)
        return name.strip()

    def _dedup_notice_numbers(self, numbers: List[str]) -> List[str]:
        """去除短格式责令号（如'责字〔2023〕3360号'为'穗公积金中心萝岗责字〔2023〕3360号'的子串）"""
        normalized = [(n, self._normalize_notice_number(n)) for n in numbers]
        result = []
        for num, norm_num in normalized:
            is_subset = False
            for other, norm_other in normalized:
                if other != num and norm_other.endswith(norm_num) and len(norm_other) > len(norm_num):
                    is_subset = True
                    break
            if not is_subset:
                result.append(num)
        return result

    def _convert_to_party_list(self, results: List[ExtractionResult], party_type: str) -> List[Dict[str, str]]:
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
                print(f"WARN: OCR引擎加载失败，将使用pdfplumber文本提取")
                self.use_ocr = False
        return self._ocr_engine

    def extract_from_pdf(self, pdf_path: Path) -> RulingInfo:
        """从PDF文件中提取裁定信息"""
        text = self._extract_text_from_pdf(pdf_path)

        if len(text.strip()) < 100 and self.use_ocr:
            text = self._extract_text_with_ocr(pdf_path)

        text = self._apply_corrections(text)

        return self.text_extractor.extract(text)

    def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        try:
            import pdfplumber
            texts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    texts.append(text)
            return "\n".join(texts)
        except Exception as e:
            print(f"WARN: pdfplumber提取失败: {e}")
            return ""

    def _extract_text_with_ocr(self, pdf_path: Path) -> str:
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
            print(f"WARN: OCR提取失败: {e}")
            return ""

    def _apply_corrections(self, text: str) -> str:
        corrections = _enforcement_cfg.get('ocr_corrections', [])
        for correction in corrections:
            wrong = correction.get('wrong', '')
            correct = correction.get('correct', '')
            if wrong and correct:
                text = text.replace(wrong, correct)
        return text


def extract_ruling_from_pdf(pdf_path: Path, use_ocr: bool = True) -> RulingInfo:
    extractor = RulingPDFExtractor(use_ocr=use_ocr)
    return extractor.extract_from_pdf(pdf_path)


def batch_extract_rulings(pdf_dir: Path, use_ocr: bool = True) -> Dict[str, RulingInfo]:
    results = {}
    extractor = RulingPDFExtractor(use_ocr=use_ocr)

    for pdf_file in sorted(pdf_dir.glob("*.pdf")):
        print(f"INFO: 处理: {pdf_file.name}")
        try:
            info = extractor.extract_from_pdf(pdf_file)
            key = info.court_case_number if info.court_case_number else pdf_file.stem
            results[key] = info
        except Exception as e:
            print(f"ERROR: 处理 {pdf_file.name} 失败: {e}")

    return results


def process_enforcement_cases(input_dir: Path, excel_path: Path, use_ocr: bool = True, mock_mode: bool = False) -> Dict[str, Any]:
    """
    强制执行组完整处理流程（供 server.py 调用）

    流程：
    1. 批量提取裁定PDF信息
    2. 加载台账并与提取结果匹配
    3. 返回结构化的处理结果
    """
    from enforcement_product import load_enforcement_cases

    if mock_mode:
        print(f"INFO: Mock 模式：使用模拟数据")
        mock_results = _build_mock_rulings(input_dir)
        pdf_results = mock_results
    else:
        pdf_results = batch_extract_rulings(input_dir, use_ocr=use_ocr)
    processed = len(pdf_results)

    extracted = []
    for key, info in pdf_results.items():
        extracted.append(info.to_dict())

    stats = {"total_pdfs": processed, "total_excel_rows": 0, "matched_rows": 0, "unmatched_rows": 0, "withdraw_count": 0}
    updated_excel_path = ""

    output_dir = USER_DATA_DIR / "output" / "enforcement"
    output_dir.mkdir(parents=True, exist_ok=True)

    if excel_path.exists():
        try:
            registry = load_enforcement_cases(excel_path)
            stats["total_excel_rows"] = len(registry.cases)

            for info in pdf_results.values():
                if info.is_withdraw:
                    stats["withdraw_count"] += 1

            matched_count = 0
            print(f"[DEBUG] 开始匹配: 台账行数={len(registry.cases)}, PDF数={len(pdf_results)}")
            for case in registry.cases:
                print(f"[DEBUG] 台账案件: 责令号='{case.notice_number}'")
                for info in pdf_results.values():
                    print(f"[DEBUG]   PDF案件: 案号='{info.court_case_number}', 责令号列表={info.notice_numbers}")
                    for ocr_notice in info.notice_numbers:
                        # 使用与台账加载相同的标准化逻辑
                        norm_ocr = registry._normalize_notice_number(ocr_notice)
                        norm_excel = registry._normalize_notice_number(case.notice_number)
                        print(f"[DEBUG]     比较: OCR='{norm_ocr}' vs Excel='{norm_excel}'")
                        if norm_ocr.endswith(norm_excel) or norm_excel.endswith(norm_ocr):
                            print(f"[DEBUG]     ✓ 匹配成功!")
                            matched_count += 1
                            break
                    else:
                        continue
                    break
            stats["matched_rows"] = matched_count
            stats["unmatched_rows"] = max(0, len(registry.cases) - matched_count)

            from enforcement_export import build_output_excel
            excel_output = output_dir / "执行组识别结果.xlsx"
            try:
                build_output_excel(registry, pdf_results, excel_output)
                updated_excel_path = str(excel_output.resolve())
            except Exception:
                pass
        except Exception as e:
            print(f"WARN: 台账匹配/导出失败: {e}")

    return {
        "processed": processed,
        "extracted": extracted,
        "updated_excel_path": updated_excel_path,
        "output_dir": str(output_dir.resolve()),
        "stats": stats,
    }


def _build_mock_rulings(input_dir: Path) -> Dict[str, RulingInfo]:
    """构造 mock 裁定信息，用于快速测试 UI 流程"""
    mock_data = [
        RulingInfo(
            court_case_number="（2025）粤7101行审3355号",
            notice_numbers=["穗公积金中心责字〔2025〕3355号"],
            applicants=[{"name": "广州住房公积金管理中心", "role": "申请执行人"}],
            respondents=[{"name": "张某", "role": "被执行人"}],
            execution_amount=15000.0,
            ruling_date="2025-01-15",
            judge="李某",
            clerk="王某",
            ruling_result="准予强制执行",
            is_withdraw=False,
        ),
        RulingInfo(
            court_case_number="（2025）粤7101行审3423号",
            notice_numbers=["穗公积金中心责字〔2025〕3423号"],
            applicants=[{"name": "广州住房公积金管理中心", "role": "申请执行人"}],
            respondents=[{"name": "陈某", "role": "被执行人"}],
            execution_amount=28000.0,
            ruling_date="2025-02-20",
            judge="赵某",
            clerk="刘某",
            ruling_result="准予强制执行",
            is_withdraw=False,
        ),
        RulingInfo(
            court_case_number="（2025）粤7101行审3500号",
            notice_numbers=["穗公积金中心责字〔2025〕3500号"],
            applicants=[{"name": "广州住房公积金管理中心", "role": "申请执行人"}],
            respondents=[{"name": "黄某", "role": "被执行人"}],
            execution_amount=5200.0,
            ruling_date="2025-03-10",
            judge="李某",
            clerk="王某",
            ruling_result="撤回执行",
            is_withdraw=True,
        ),
    ]
    results = {}
    for info in mock_data:
        key = info.court_case_number
        results[key] = info
        print(f"INFO: Mock: {key}")
    return results


if __name__ == "__main__":
    test_pdf = Path("样本材料/强制组-自动化/提取信息/（2025）粤7101行审3355号.pdf")
    if test_pdf.exists():
        info = extract_ruling_from_pdf(test_pdf, use_ocr=False)
        print("\n提取结果:")
        print(json.dumps(info.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"测试文件不存在: {test_pdf}")
