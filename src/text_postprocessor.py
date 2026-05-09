#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 文本后处理器
功能：
1. 统一括号格式
2. 忽略空格换行，统一括号为英文括号
3. 修正常见识别错误文字
4. 识别案号，把括号改为中文括号输出
5. 优化识别公司名称
6. 结构化提取功能一/功能二所需字段
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class TextCorrection:
    """文本修正规则"""
    pattern: str
    replacement: str
    description: str


class TextPostProcessor:
    """OCR 文本后处理器"""
    
    COMMON_ERRORS = {
        '【': '[',
        '】': ']',
        '（': '(',
        '）': ')',
        '〔': '[',
        '〕': ']',
        '［': '[',
        '］': ']',
        '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
        '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
        'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', 'Ｅ': 'E',
        'Ｆ': 'F', 'Ｇ': 'G', 'Ｈ': 'H', 'Ｉ': 'I', 'Ｊ': 'J',
        'Ｋ': 'K', 'Ｌ': 'L', 'Ｍ': 'M', 'Ｎ': 'N', 'Ｏ': 'O',
        'Ｐ': 'P', 'Ｑ': 'Q', 'Ｒ': 'R', 'Ｓ': 'S', 'Ｔ': 'T',
        'Ｕ': 'U', 'Ｖ': 'V', 'Ｗ': 'W', 'Ｘ': 'X', 'Ｙ': 'Y',
        'Ｚ': 'Z',
        'ａ': 'a', 'ｂ': 'b', 'ｃ': 'c', 'ｄ': 'd', 'ｅ': 'e',
        'ｆ': 'f', 'ｇ': 'g', 'ｈ': 'h', 'ｉ': 'i', 'ｊ': 'j',
        'ｋ': 'k', 'ｌ': 'l', 'ｍ': 'm', 'ｎ': 'n', 'ｏ': 'o',
        'ｐ': 'p', 'ｑ': 'q', 'ｒ': 'r', 'ｓ': 's', 'ｔ': 't',
        'ｕ': 'u', 'ｖ': 'v', 'ｗ': 'w', 'ｘ': 'x', 'ｙ': 'y',
        'ｚ': 'z',
        '房公积金': '住房公积金',
    }
    
    COMPANY_KEYWORDS = [
        '有限责任公司', '股份有限公司', '集团有限公司', '有限公司',
        '集团公司', '股份公司', '事务所', '管理中心', '研究院',
        '协会', '中心', '公司'
    ]

    NOISE_PREFIXES = ['准予强制执行', '附：', '附件：', '1 ', '2 ', '3 ', '4 ', '5 ', '序号', '号 ']
    
    def __init__(self):
        self.corrections: List[TextCorrection] = []
        self._init_corrections()
    
    def _init_corrections(self):
        self.corrections.append(TextCorrection(
            pattern=r'[(\[]?(\d{4})[)\]]?([粤穗])',
            replacement=r'（\1）\2',
            description='年份括号标准化'
        ))
        self.corrections.append(TextCorrection(
            pattern=r'(责字|行审|民初|刑初|执字)[（\[〔]?(\d{4})[）\]〕]?(\d+(?:-\d+)?)号',
            replacement=r'\1〔\2〕\3号',
            description='决定书编号标准化'
        ))
    
    def normalize_brackets(self, text: str) -> str:
        bracket_map = {
            '（': '(', '）': ')', '【': '[', '】': ']',
            '〔': '[', '〕': ']', '［': '[', '］': ']'
        }
        for full, half in bracket_map.items():
            text = text.replace(full, half)
        return text
    
    def remove_extra_whitespace(self, text: str) -> str:
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        text = '\n'.join(line.strip() for line in text.split('\n'))
        return text
    
    def correct_common_errors(self, text: str) -> str:
        fullwidth = '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
        halfwidth = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        for f, h in zip(fullwidth, halfwidth):
            text = text.replace(f, h)
        corrections = {
            r'住\s*房\s*公\s*积\s*金': '住房公积金',
            r'有\s*限\s*公\s*司': '有限公司',
            r'统\s*一\s*社\s*会\s*信\s*用\s*代\s*码': '统一社会信用代码',
            r'法\s*定\s*代\s*表\s*人': '法定代表人',
            r'委\s*托\s*代\s*理\s*人': '委托代理人',
            r'申\s*请\s*执\s*行\s*人': '申请执行人',
            r'被\s*执\s*行\s*人': '被执行人',
            r'审\s*判\s*员': '审判员',
            r'书\s*记\s*员': '书记员',
            r'行\s*政\s*裁\s*定\s*书': '行政裁定书',
            r'责\s*令\s*限\s*期\s*办\s*理\s*决\s*定\s*书': '责令限期办理决定书',
            r'催\s*告\s*书': '催告书',
            r'审判员\s*([\u4e00-\u9fa5])\s*([\u4e00-\u9fa5])': r'审判员\1\2',
            r'书记员\s*([\u4e00-\u9fa5])\s*([\u4e00-\u9fa5])': r'书记员\1\2',
        }
        for pattern, replacement in corrections.items():
            text = re.sub(pattern, replacement, text)
        return text
    
    def extract_and_format_case_numbers(self, text: str) -> Tuple[str, List[Dict]]:
        case_numbers = []
        court_pattern = r'[(\[]\s*(\d{4})\s*[)\]]\s*(粤|穗)\s*(\d+)\s*(行审|民初|刑初|执|行)\s*(\d+)\s*号'

        def replace_court_case(match):
            year = match.group(1)
            region = match.group(2)
            court_code = match.group(3)
            case_type = match.group(4)
            number = match.group(5)
            formatted = f'（{year}）{region}{court_code}{case_type}{number}号'
            case_numbers.append({
                'original': match.group(0),
                'formatted': formatted,
                'type': '法院案号',
                'year': year,
                'region': region,
                'case_type': case_type,
                'number': number
            })
            return formatted

        text = re.sub(court_pattern, replace_court_case, text)

        decision_pattern = r'(.{2,30}?字)\s*[\[(]\s*(\d{4})\s*[\])]\s*(\d+(?:-\d+)?)\s*号'

        def replace_decision_case(match):
            prefix = match.group(1)
            year = match.group(2)
            number = match.group(3)
            formatted = f'{prefix}〔{year}〕{number}号'
            case_numbers.append({
                'original': match.group(0),
                'formatted': formatted,
                'type': '决定书编号',
                'prefix': prefix,
                'year': year,
                'number': number
            })
            return formatted

        text = re.sub(decision_pattern, replace_decision_case, text)
        return text, case_numbers
    
    def optimize_company_names(self, text: str) -> str:
        for keyword in self.COMPANY_KEYWORDS:
            pattern = rf'(\S+)\s+{keyword}'
            replacement = rf'\1{keyword}'
            text = re.sub(pattern, replacement, text)

        company_corrections = {
            r'广东\s*润生\s*箱包\s*制造\s*有限公司': '广东润生箱包制造有限公司',
            r'三菱\s*电机\s*[(（]\s*广州\s*[)）]\s*压缩机\s*有限公司': '三菱电机（广州）压缩机有限公司',
            r'广州\s*住房\s*公积金\s*管理\s*中心': '广州住房公积金管理中心',
            r'广东\s*省\s*新闻\s*工作\s*者\s*协会': '广东省新闻工作者协会',
            r'广东\s*岭南\s*律师\s*事务所': '广东岭南律师事务所',
        }
        for pattern, replacement in company_corrections.items():
            text = re.sub(pattern, replacement, text)
        return text

    def normalize_decision_number(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r'^[^穗粤广]*', '', text)
        text = re.sub(r'^(附：|附件：|准予强制执行)', '', text)
        text = re.sub(r'^\d+\s*', '', text)
        text = re.sub(r'\s+', '', text)
        text = text.replace('(', '〔').replace(')', '〕').replace('[', '〔').replace(']', '〕')
        text = re.sub(r'号.*$', '号', text)
        return text.strip()

    def expand_decision_number_ranges(self, text: str) -> List[str]:
        results = []
        pattern = re.compile(r'(穗公积金中心[^\s，。；、《》]*?责字[〔\[(［【]\d{4}[〕\)\]］】])(\d+(?:-\d+)?)号至\s*(\d+(?:-\d+)?)号')
        for prefix, start, end in pattern.findall(text):
            if '-' in start or '-' in end:
                if start == end:
                    results.append(f'{prefix}{start}号')
                continue
            start_num = int(start)
            end_num = int(end)
            if end_num >= start_num and end_num - start_num <= 20:
                for number in range(start_num, end_num + 1):
                    results.append(f'{prefix}{number}号')
        return results

    def extract_decision_numbers(self, text: str) -> List[str]:
        numbers = []
        numbers.extend(self.expand_decision_number_ranges(text))
        single_pattern = re.compile(r'(穗公积金中心[^\s，。；、《》]*?责字[〔\[(［【]\d{4}[〕\)\]］】]\d+(?:-\d+)?号)')
        for match in single_pattern.findall(text):
            numbers.append(self.normalize_decision_number(match))
        cleaned = []
        seen = set()
        for item in numbers:
            if item and item not in seen:
                seen.add(item)
                cleaned.append(item)
        return cleaned

    def chinese_date_to_normalized(self, text: str) -> Optional[str]:
        text = text.strip()
        chinese_map = {'〇': '0', '○': '0', 'Ｏ': '0', '一': '1', '二': '2', '三': '3', '四': '4', '五': '5', '六': '6', '七': '7', '八': '8', '九': '9'}
        match = re.search(r'([二〇○Ｏ一三四五六七八九零]{4})年([一二三四五六七八九十]{1,3})月([一二三四五六七八九十]{1,3})日', text)
        if not match:
            return None
        year_text, month_text, day_text = match.groups()
        year = ''.join(chinese_map.get(char, char) for char in year_text).replace('零', '0')
        month = self.parse_chinese_number(month_text)
        day = self.parse_chinese_number(day_text)
        if not (year.isdigit() and month and day):
            return None
        return f'{int(year)}年{month}月{day}日'

    def parse_chinese_number(self, text: str) -> Optional[int]:
        mapping = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        if text in mapping and text != '十':
            return mapping[text]
        if text == '十':
            return 10
        if text.startswith('十'):
            return 10 + mapping[text[1]]
        if text.endswith('十'):
            return mapping[text[0]] * 10
        if '十' in text:
            left, right = text.split('十')
            return mapping[left] * 10 + mapping[right]
        return mapping[text]

    def classify_notice_page(self, text: str) -> Dict[str, bool]:
        compact = re.sub(r'\s+', '', text or '')
        return {
            'is_notice_main_page': '责令限期办理决定书' in compact,
            'is_notice_revoke_page': '关于撤销《责令限期办理决定书》的决定' in compact or ('撤销' in compact and '责令限期办理决定书' in compact),
            'is_notice_delivery_page': '送达回证' in compact,
            'is_notice_logistics_page': any(keyword in compact for keyword in ['中国邮政速递物流', '邮件号', 'EMS']),
        }

    def extract_document_type(self, text: str) -> Optional[str]:
        for doc_type in ['行政裁定书', '责令限期办理决定书', '催告书', '授权委托书', '合作协议', '合同']:
            if doc_type in text:
                return doc_type
        return None

    def extract_company_candidates(self, text: str) -> List[str]:
        candidates = []
        patterns = [
            r'委托人与([\u4e00-\u9fa5A-Za-z0-9（）()·]+?(?:有限责任公司[\u4e00-\u9fa5A-Za-z0-9（）()·]*分公司|股份有限公司[\u4e00-\u9fa5A-Za-z0-9（）()·]*分公司|有限公司[\u4e00-\u9fa5A-Za-z0-9（）()·]*分公司|有限责任公司|股份有限公司|有限公司))',
            r'关于([\u4e00-\u9fa5A-Za-z0-9（）()·]+?(?:有限责任公司[\u4e00-\u9fa5A-Za-z0-9（）()·]*分公司|股份有限公司[\u4e00-\u9fa5A-Za-z0-9（）()·]*分公司|有限公司[\u4e00-\u9fa5A-Za-z0-9（）()·]*分公司|有限责任公司|股份有限公司|有限公司))',
            r'名称[:：]\s*([\u4e00-\u9fa5A-Za-z0-9（）()·]+?(?:有限责任公司[\u4e00-\u9fa5A-Za-z0-9（）()·]*分公司|股份有限公司[\u4e00-\u9fa5A-Za-z0-9（）()·]*分公司|有限公司[\u4e00-\u9fa5A-Za-z0-9（）()·]*分公司|有限责任公司|股份有限公司|有限公司))',
            r'委托单位[:：]\s*([\u4e00-\u9fa5A-Za-z0-9（）()·]+?(?:有限责任公司[\u4e00-\u9fa5A-Za-z0-9（）()·]*分公司|股份有限公司[\u4e00-\u9fa5A-Za-z0-9（）()·]*分公司|有限公司[\u4e00-\u9fa5A-Za-z0-9（）()·]*分公司|有限责任公司|股份有限公司|有限公司))',
        ]
        for pattern in patterns:
            candidates.extend(re.findall(pattern, text))
        cleaned = []
        seen = set()
        for candidate in candidates:
            value = candidate.strip()
            if value and value not in seen:
                seen.add(value)
                cleaned.append(value)
        return cleaned

    def extract_company_after_label(self, text: str, labels: List[str]) -> Optional[str]:
        for label in labels:
            match = re.search(rf'{label}[:：]\s*([^\n，。]*)', text)
            if match:
                value = match.group(1).strip()
                company = self.extract_company_name_from_text(value)
                if company:
                    return company
        return None

    def extract_company_name_from_text(self, text: str) -> Optional[str]:
        candidates = []
        for keyword in self.COMPANY_KEYWORDS:
            pattern = rf'([\u4e00-\u9fa5A-Za-z0-9（）()·]+?{keyword})'
            candidates.extend(re.findall(pattern, text))
        cleaned = []
        for candidate in candidates:
            value = re.sub(r'^(甲方|乙方|名称|申请执行人|被执行人)[:：]?', '', candidate).strip()
            value = re.sub(r'[，。；].*$', '', value)
            if len(value) >= 4:
                cleaned.append(value)
        if not cleaned:
            return None
        cleaned.sort(key=len, reverse=True)
        return cleaned[0]

    def extract_ruling_fields(self, text: str) -> Dict:
        administrative_case_no = None
        match = re.search(r'（\d{4}）粤\d+行审\d+号', text)
        if match:
            administrative_case_no = match.group(0)

        judge = None
        match = re.search(r'审判员\s*([\u4e00-\u9fa5]{2,4})', text)
        if match:
            judge = match.group(1)

        clerk = None
        match = re.search(r'书记员\s*([\u4e00-\u9fa5]{2,4})', text)
        if match:
            clerk = match.group(1)

        execution_date = self.chinese_date_to_normalized(text)
        if not execution_date:
            match = re.search(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', text)
            if match:
                execution_date = f'{int(match.group(1))}年{int(match.group(2))}月{int(match.group(3))}日'

        return {
            'document_type': '行政裁定书' if '行政裁定书' in text else None,
            'administrative_case_no': administrative_case_no,
            'decision_numbers': self.extract_decision_numbers(text),
            'judge': judge,
            'clerk': clerk,
            'execution_date': execution_date,
        }

    def extract_notice_fields(self, text: str) -> Dict:
        document_type = self.extract_document_type(text)
        company_name = self.extract_company_after_label(text, ['名称', '委托单位', '委托人'])
        company_name_candidates = self.extract_company_candidates(text)
        page_profile = self.classify_notice_page(text)
        if not company_name and company_name_candidates:
            company_name = company_name_candidates[0]
        return {
            'document_type': document_type,
            'company_name': company_name,
            'company_name_candidates': company_name_candidates,
            'decision_numbers': self.extract_decision_numbers(text),
            'page_profile': page_profile,
        }

    def extract_contract_fields(self, text: str) -> Dict:
        party_a = self.extract_company_after_label(text, ['甲方'])
        party_b = self.extract_company_after_label(text, ['乙方'])
        return {
            'document_type': '合同' if ('合同' in text or '协议' in text) else None,
            'party_a': party_a,
            'party_b': party_b,
        }

    def build_structured_output(self, text: str) -> Dict:
        return {
            'decision_numbers': self.extract_decision_numbers(text),
            'ruling': self.extract_ruling_fields(text),
            'notice': self.extract_notice_fields(text),
            'contract': self.extract_contract_fields(text),
        }
    
    def process(self, text: str) -> Dict:
        original = text
        changes = []
        text = self.normalize_brackets(text)
        changes.append('统一括号为英文格式')
        text = self.remove_extra_whitespace(text)
        changes.append('移除多余空格和换行')
        text = self.correct_common_errors(text)
        changes.append('修正常见识别错误')
        text, case_numbers = self.extract_and_format_case_numbers(text)
        if case_numbers:
            changes.append(f'识别并格式化 {len(case_numbers)} 个案号')
        text = self.optimize_company_names(text)
        changes.append('优化公司名称识别')
        structured = self.build_structured_output(text)
        changes.append('提取功能一和功能二结构化字段')
        return {
            'original': original,
            'processed': text,
            'case_numbers': case_numbers,
            'changes': changes,
            'structured': structured,
        }


def demo():
    processor = TextPostProcessor()
    test_text = """广州住房公积金管理中心
责令限期办理决定书
穗公积金中心黄埔责字[2025]594号
名称：三菱电机（广州）压缩机有限公司
统一社会信用代码：9144011661842063XT

广州铁路运输法院
行政裁定书
(2025)粤7101行审3352号
申请执行人：广州住房公积金管理中心
"""
    result = processor.process(test_text)
    print(result['processed'])
    print(result['structured'])


if __name__ == '__main__':
    demo()
