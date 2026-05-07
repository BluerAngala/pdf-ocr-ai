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
    
    # 常见 OCR 识别错误映射
    COMMON_ERRORS = {
        # 括号类
        '【': '[',
        '】': ']',
        '（': '(',
        '）': ')',
        '〔': '[',
        '〕': ']',
        '［': '[',
        '］': ']',
        
        # 数字类（全角转半角）
        '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
        '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
        
        # 字母类（全角转半角）
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
        
        # 常见错别字
        '住': '住',  # 防止"住房公积金"被误识别
        '房公积金': '住房公积金',
        '限公司': '有限公司',
        '责字': '责字',
        '行审': '行审',
        '粤': '粤',
        '穗': '穗',
    }
    
    # 案号正则表达式模式
    CASE_NUMBER_PATTERNS = [
        # 法院案号：如 (2025)粤7101行审3352号
        r'[(\[（〔](\d{4})[)\]）〕]([^号]{1,10})号',
        # 决定书编号：如 穗公积金中心黄埔责字[2025]594号
        r'(.{2,10}字)[(\[（〔](\d{4})[)\]）〕](\d+)号',
        # 一般编号：如 [2025]第1号
        r'[(\[（〔](\d{4})[)\]）〕]第(\d+)号',
    ]
    
    # 公司名称关键词
    COMPANY_KEYWORDS = [
        '有限公司', '有限责任公司', '股份有限公司', '股份公司',
        '集团有限公司', '集团公司', '实业有限公司', '投资公司',
        '科技有限公司', '技术有限公司', '开发有限公司',
        '管理中心', '服务中心', '事务所', '研究院',
    ]
    
    def __init__(self):
        self.corrections: List[TextCorrection] = []
        self._init_corrections()
    
    def _init_corrections(self):
        """初始化修正规则"""
        # 案号标准化：统一使用中文括号
        self.corrections.append(TextCorrection(
            pattern=r'[(\[]?(\d{4})[)\]]?([粤穗])',
            replacement=r'（\1）\2',
            description='年份括号标准化'
        ))
        
        # 决定书编号标准化
        self.corrections.append(TextCorrection(
            pattern=r'(责字|行审|民初|刑初|执字)[（\[〔]?(\d{4})[）\]〕]?(\d+)号',
            replacement=r'\1〔\2〕\3号',
            description='决定书编号标准化'
        ))
    
    def normalize_brackets(self, text: str) -> str:
        """
        统一括号格式为英文括号
        同时处理全角字符
        """
        # 先替换全角括号为半角
        bracket_map = {
            '（': '(',
            '）': ')',
            '【': '[',
            '】': ']',
            '〔': '[',
            '〕': ']',
            '［': '[',
            '］': ']',
        }
        
        for full, half in bracket_map.items():
            text = text.replace(full, half)
        
        return text
    
    def remove_extra_whitespace(self, text: str) -> str:
        """
        移除多余空格和换行
        保留段落结构
        """
        # 将多个连续换行合并为两个
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 将行内多个空格合并为一个
        text = re.sub(r' +', ' ', text)
        # 移除行首行尾空格
        text = '\n'.join(line.strip() for line in text.split('\n'))
        return text
    
    def correct_common_errors(self, text: str) -> str:
        """修正常见识别错误"""
        # 全角转半角（数字和字母）
        fullwidth = '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
        halfwidth = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        
        for f, h in zip(fullwidth, halfwidth):
            text = text.replace(f, h)
        
        # 修正常见错误词汇
        corrections = {
            r'住\s*房\s*公\s*积\s*金': '住房公积金',
            r'有\s*限\s*公\s*司': '有限公司',
            r'统\s*一\s*社\s*会\s*信\s*用\s*代\s*码': '统一社会信用代码',
            r'法\s*定\s*代\s*表\s*人': '法定代表人',
            r'委\s*托\s*代\s*理\s*人': '委托代理人',
            r'申\s*请\s*执\s*行\s*人': '申请执行人',
            r'被\s*执\s*行\s*人': '被执行人',
        }
        
        for pattern, replacement in corrections.items():
            text = re.sub(pattern, replacement, text)
        
        return text
    
    def extract_and_format_case_numbers(self, text: str) -> Tuple[str, List[Dict]]:
        """
        识别案号并格式化
        返回：(格式化后的文本, 案号列表)
        """
        case_numbers = []
        
        # 法院案号模式（支持空格）：(2025)粤 7101 行审 3352 号 -> （2025）粤7101行审3352号
        # 匹配格式：(2025)粤7101行审3352号 或 (2025)粤 7101 行审 3352 号
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
        
        # 决定书编号模式（支持空格）：穗公积金中心黄埔责字[2025]594号 -> 穗公积金中心黄埔责字〔2025〕594号
        # 匹配格式：责字[2025]594号 或 责字 [2025] 594 号
        decision_pattern = r'(.{2,20}字)\s*[\[(]\s*(\d{4})\s*[\])]\s*(\d+)\s*号'
        
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
        """
        优化公司名称识别
        修复常见的公司名称识别错误
        """
        # 修复 "XX 有限公司" 中间有空格的情况
        for keyword in self.COMPANY_KEYWORDS:
            pattern = rf'(\S+)\s+{keyword}'
            replacement = rf'\1{keyword}'
            text = re.sub(pattern, replacement, text)
        
        # 修复统一社会信用代码格式
        # 统一社会信用代码：18位，格式为 xxxxxxxxxxxxxxxxxx
        uscc_pattern = r'统一社会信用代码[:：]?\s*([0-9A-Za-z]{18})'
        
        def format_uscc(match):
            code = match.group(1).upper()
            return f'统一社会信用代码：{code}'
        
        text = re.sub(uscc_pattern, format_uscc, text, flags=re.IGNORECASE)
        
        # 常见公司名称纠错
        company_corrections = {
            r'广东\s*润生\s*箱包\s*制造\s*有限公司': '广东润生箱包制造有限公司',
            r'三菱\s*电机\s*[(（]\s*广州\s*[)）]\s*压缩机\s*有限公司': '三菱电机（广州）压缩机有限公司',
            r'广州\s*住房\s*公积金\s*管理\s*中心': '广州住房公积金管理中心',
        }
        
        for pattern, replacement in company_corrections.items():
            text = re.sub(pattern, replacement, text)
        
        return text
    
    def process(self, text: str) -> Dict:
        """
        完整的后处理流程
        
        返回：{
            'original': 原始文本,
            'processed': 处理后文本,
            'case_numbers': 识别的案号列表,
            'changes': 修改记录
        }
        """
        original = text
        changes = []
        
        # 1. 统一括号格式（先转为英文括号便于处理）
        text = self.normalize_brackets(text)
        changes.append('统一括号为英文格式')
        
        # 2. 移除多余空格换行
        text = self.remove_extra_whitespace(text)
        changes.append('移除多余空格和换行')
        
        # 3. 修正常见识别错误
        text = self.correct_common_errors(text)
        changes.append('修正常见识别错误')
        
        # 4. 识别并格式化案号（转为中文括号输出）
        text, case_numbers = self.extract_and_format_case_numbers(text)
        if case_numbers:
            changes.append(f'识别并格式化 {len(case_numbers)} 个案号')
        
        # 5. 优化公司名称
        text = self.optimize_company_names(text)
        changes.append('优化公司名称识别')
        
        return {
            'original': original,
            'processed': text,
            'case_numbers': case_numbers,
            'changes': changes
        }


def demo():
    """演示后处理功能"""
    processor = TextPostProcessor()
    
    # 测试文本
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
    
    print("=" * 60)
    print("原始文本：")
    print("=" * 60)
    print(result['original'])
    
    print("\n" + "=" * 60)
    print("处理后文本：")
    print("=" * 60)
    print(result['processed'])
    
    print("\n" + "=" * 60)
    print("识别的案号：")
    print("=" * 60)
    for case in result['case_numbers']:
        print(f"  - {case['type']}: {case['original']} -> {case['formatted']}")
    
    print("\n" + "=" * 60)
    print("修改记录：")
    print("=" * 60)
    for change in result['changes']:
        print(f"  ✓ {change}")


if __name__ == '__main__':
    demo()
