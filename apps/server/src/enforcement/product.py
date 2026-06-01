#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强制执行组 - 台账数据加载模块

功能：
1. 从非诉表格.xlsx加载案件数据
2. 提供案件查询和匹配功能
3. 支持通过责令号或法院案号关联裁定信息
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd

from core.paths import ROOT

from core.config_loader import load_config

from enforcement.extractor import (
    _NOTICE_STRUCT_PATTERN, _KNOWN_DISTRICTS, _DISTRICT_VARIANTS,
    structural_correct_notice,
)

_cfg = load_config()
_enforcement_cfg = _cfg.raw_config.get('enforcement', {})
_excel_cfg = _enforcement_cfg.get('excel_parsing', {})


@dataclass
class EnforcementCase:
    """强制执行案件数据结构"""
    # 基本信息（来自台账）
    region: str = ""                    # 区域
    notice_number: str = ""             # 责令号
    respondent: str = ""                # 被执行人
    employee: str = ""                  # 职工
    amount: Optional[float] = None      # 金额
    due_date: str = ""                  # 到期日
    
    # 需要从裁定PDF提取的信息
    court_case_number: str = ""         # 受理案号
    judge: str = ""                     # 法官/助理/书记员
    ruling_result: str = ""             # 裁定结果/收到时间
    
    # 扩展信息（从裁定PDF提取）
    applicants: List[Dict[str, str]] = field(default_factory=list)   # 申请执行人
    ruling_date: Optional[str] = None   # 裁定日期
    clerk: str = ""                     # 书记员
    execution_amount: Optional[float] = None  # 执行标的金额（从裁定提取）
    
    # 原始行索引（用于回写Excel）
    row_index: int = -1
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'region': self.region,
            'notice_number': self.notice_number,
            'respondent': self.respondent,
            'employee': self.employee,
            'amount': self.amount,
            'due_date': self.due_date,
            'court_case_number': self.court_case_number,
            'judge': self.judge,
            'ruling_result': self.ruling_result,
            'applicants': self.applicants,
            'ruling_date': self.ruling_date,
            'clerk': self.clerk,
            'execution_amount': self.execution_amount,
        }


class EnforcementCaseRegistry:
    """强制执行案件登记簿"""
    
    def __init__(self):
        self.cases: List[EnforcementCase] = []
        self._notice_index: Dict[str, EnforcementCase] = {}      # 责令号索引
        self._respondent_index: Dict[str, List[EnforcementCase]] = {}  # 被执行人索引
        self._court_case_index: Dict[str, EnforcementCase] = {}  # 法院案号索引
        self._df: Optional[pd.DataFrame] = None                   # 原始DataFrame
        self._excel_path: Optional[Path] = None
    
    def load_from_excel(self, excel_path: Path) -> 'EnforcementCaseRegistry':
        """从Excel文件加载案件数据"""
        self._excel_path = excel_path
        
        # 读取Excel
        df = pd.read_excel(excel_path)
        self._df = df
        
        # 获取列索引配置
        col_cfg = _excel_cfg.get('columns', {})
        min_cols = _excel_cfg.get('min_columns', 3)
        filter_keyword = _excel_cfg.get('filter_keywords', {}).get('notice_number', '责字')
        
        # 遍历行数据
        for idx, row in df.iterrows():
            # 检查最小列数
            if len(row) < min_cols:
                continue
            
            # 获取责令号
            notice_number = self._get_cell_value(row, col_cfg.get('notice_number', 1))
            if not notice_number or filter_keyword not in str(notice_number):
                continue
            
            case = EnforcementCase(row_index=idx)
            case.region = self._get_cell_value(row, col_cfg.get('region', 0))
            case.notice_number = str(notice_number).strip()
            case.respondent = self._get_cell_value(row, col_cfg.get('respondent', 2))
            case.employee = self._get_cell_value(row, col_cfg.get('employee', 3))
            case.amount = self._parse_amount(self._get_cell_value(row, col_cfg.get('amount', 4)))
            case.due_date = self._get_cell_value(row, col_cfg.get('due_date', 5))
            
            # 已存在的法院案号（如果有）
            case.court_case_number = self._get_cell_value(row, col_cfg.get('case_number', 13))
            case.judge = self._get_cell_value(row, col_cfg.get('judge', 14))
            case.ruling_result = self._get_cell_value(row, col_cfg.get('ruling_result', 15))
            
            self.cases.append(case)
            
            # 建立索引（使用标准化后的责令号作为键）
            normalized_notice = self._normalize_notice_number(case.notice_number)
            self._notice_index[normalized_notice] = case
            
            if case.respondent:
                if case.respondent not in self._respondent_index:
                    self._respondent_index[case.respondent] = []
                self._respondent_index[case.respondent].append(case)
            
            if case.court_case_number:
                self._court_case_index[case.court_case_number] = case
        
        print(f"INFO: 从 {excel_path.name} 加载了 {len(self.cases)} 条案件记录")
        return self
    
    def _get_cell_value(self, row: pd.Series, col_idx: int) -> str:
        """安全获取单元格值"""
        try:
            if col_idx < len(row):
                val = row.iloc[col_idx]
                if pd.isna(val):
                    return ""
                return str(val).strip()
        except:
            pass
        return ""
    
    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """解析金额"""
        if not amount_str:
            return None
        try:
            # 移除逗号和空格
            cleaned = amount_str.replace(',', '').replace(' ', '').strip()
            return float(cleaned)
        except:
            return None
    
    def find_by_notice_number(self, notice_number: str) -> Optional[EnforcementCase]:
        """通过责令号查找案件（支持长短格式 + 同根主号 + 结构化模糊匹配）"""
        normalized = self._normalize_notice_number(notice_number)
        if normalized in self._notice_index:
            return self._notice_index[normalized]

        # 长短格式匹配
        for excel_notice, case in self._notice_index.items():
            excel_norm = self._normalize_notice_number(excel_notice)
            if normalized.endswith(excel_norm) or excel_norm.endswith(normalized):
                return case

        # 同根主号匹配（如 1234-1号 匹配 1234号）
        candidate_root = self._get_notice_root_number(notice_number)
        for excel_notice, case in self._notice_index.items():
            excel_root = self._get_notice_root_number(excel_notice)
            if candidate_root == excel_root:
                return case

        # 结构化模糊匹配
        match = self._structured_match_notice(notice_number)
        if match:
            return match
        return None
    
    def find_all_by_notice_number(self, notice_number: str) -> List[EnforcementCase]:
        """通过责令号查找所有匹配案件（支持长短格式 + 同根主号 + 结构化模糊匹配）"""
        normalized = self._normalize_notice_number(notice_number)
        results = []
        if normalized in self._notice_index:
            results.append(self._notice_index[normalized])

        # 长短格式匹配
        for excel_notice, case in self._notice_index.items():
            excel_norm = self._normalize_notice_number(excel_notice)
            if excel_norm != normalized:
                if normalized.endswith(excel_norm) or excel_norm.endswith(normalized):
                    if case not in results:
                        results.append(case)

        # 同根主号匹配（如 1234-1号 匹配 1234号）
        if not results:
            candidate_root = self._get_notice_root_number(notice_number)
            for excel_notice, case in self._notice_index.items():
                excel_root = self._get_notice_root_number(excel_notice)
                if candidate_root == excel_root:
                    if case not in results:
                        results.append(case)

        # 结构化模糊匹配
        if not results:
            match = self._structured_match_notice(notice_number)
            if match and match not in results:
                results.append(match)

        return results

    @staticmethod
    def _get_notice_root_number(notice_number: str) -> str:
        """获取责令号的主号（去掉 -N 后缀）"""
        normalized = normalize_notice_for_match(notice_number)
        import re
        return re.sub(r'(\d+)-\d+号$', r'\1号', normalized)
    
    def _structured_match_notice(self, candidate: str) -> Optional[EnforcementCase]:
        """
        结构化责令号匹配：解析年+编号+区名，按组件比对台账。
        纠正 OCR 误识后与台账精确比对，保证匹配准确性。
        """
        corrected = structural_correct_notice(candidate)
        cand_parts = self._parse_notice_components(corrected)
        if not cand_parts:
            return None

        cand_district = self._resolve_district(cand_parts['district'])
        cand_year = cand_parts['year']
        cand_number = cand_parts['number']

        for excel_notice, case in self._notice_index.items():
            excel_parts = self._parse_notice_components(excel_notice)
            if not excel_parts:
                continue
            if excel_parts['year'] != cand_year:
                continue
            if excel_parts['number'] != cand_number:
                continue
            if cand_district and excel_parts['district'] != cand_district:
                continue
            return case

        return None

    @staticmethod
    def _parse_notice_components(notice: str) -> Optional[Dict[str, str]]:
        m = _NOTICE_STRUCT_PATTERN.match(notice)
        if not m:
            return None
        return {
            'prefix': m.group(1),
            'district': m.group(2),
            'year': m.group(4),
            'number': m.group(6),
        }

    @staticmethod
    def _resolve_district(raw_district: str) -> Optional[str]:
        if raw_district in _DISTRICT_VARIANTS:
            return _DISTRICT_VARIANTS[raw_district]
        if raw_district in _KNOWN_DISTRICTS:
            return raw_district
        try:
            from rapidfuzz import fuzz as rf_fuzz
            for district in _KNOWN_DISTRICTS:
                if rf_fuzz.ratio(raw_district, district, score_cutoff=70.0):
                    return district
        except ImportError:
            pass
        return None
    
    def find_by_court_case_number(self, case_number: str) -> Optional[EnforcementCase]:
        """通过法院案号查找案件"""
        normalized = self._normalize_court_case_number(case_number)
        return self._court_case_index.get(normalized)
    
    @staticmethod
    def _normalize_respondent_name(name: str) -> str:
        return re.sub(r'[\s\u3000]+', '', str(name).strip())

    def find_by_respondent(self, respondent: str) -> List[EnforcementCase]:
        norm = self._normalize_respondent_name(respondent)
        cases = self._respondent_index.get(respondent, [])
        if cases:
            return cases
        if norm != respondent:
            cases = self._respondent_index.get(norm, [])
            if cases:
                return cases
        for key, val in self._respondent_index.items():
            if self._normalize_respondent_name(key) == norm:
                return val
        return []

    def find_by_respondent_fuzzy(self, respondent: str, threshold: float = 0.8) -> List[EnforcementCase]:
        from difflib import SequenceMatcher
        norm_query = self._normalize_respondent_name(respondent)
        results = []
        for name, cases in self._respondent_index.items():
            norm_name = self._normalize_respondent_name(name)
            similarity = SequenceMatcher(None, norm_query, norm_name).ratio()
            if similarity >= threshold:
                results.extend(cases)
        return results

    def match_ruling_info(self, ruling_info) -> List[EnforcementCase]:
        matched_by_notice = []
        for notice_number in getattr(ruling_info, 'notice_numbers', []):
            cases = self.find_all_by_notice_number(notice_number)
            for case in cases:
                if case not in matched_by_notice:
                    matched_by_notice.append(case)

        if matched_by_notice:
            ocr_respondents = [
                r.get('name', '')
                for r in getattr(ruling_info, 'respondents', [])
                if r.get('name')
            ]
            if ocr_respondents:
                filtered = []
                for case in matched_by_notice:
                    for resp_name in ocr_respondents:
                        if self._respondent_name_matches(case.respondent, resp_name):
                            filtered.append(case)
                            break
                if filtered:
                    return filtered
            return matched_by_notice

        respondent_matches = []
        for respondent in getattr(ruling_info, 'respondents', []):
            name = respondent.get('name', '')
            if not name:
                continue
            cases = self.find_by_respondent(name)
            if not cases:
                cases = self.find_by_respondent_fuzzy(name)
            if cases:
                respondent_matches.extend(cases)
        seen = set()
        deduped = []
        for c in respondent_matches:
            if id(c) not in seen:
                seen.add(id(c))
                deduped.append(c)
        respondent_matches = deduped

        if respondent_matches:
            court_case = getattr(ruling_info, 'court_case_number', '')
            if court_case:
                court_matched = self.find_by_court_case_number(court_case)
                if court_matched and court_matched in respondent_matches:
                    return [court_matched]
            if len(respondent_matches) <= 3:
                return respondent_matches
            return []

        court_case = getattr(ruling_info, 'court_case_number', '')
        if court_case:
            case = self.find_by_court_case_number(court_case)
            if case:
                return [case]

        return []

    @staticmethod
    def _respondent_name_matches(ledger_name: str, ocr_name: str) -> bool:
        norm_ledger = EnforcementCaseRegistry._normalize_respondent_name(ledger_name)
        norm_ocr = EnforcementCaseRegistry._normalize_respondent_name(ocr_name)
        if norm_ledger == norm_ocr:
            return True
        if norm_ledger in norm_ocr or norm_ocr in norm_ledger:
            return True
        from difflib import SequenceMatcher
        return SequenceMatcher(None, norm_ledger, norm_ocr).ratio() >= 0.85
    
    def update_case_from_ruling(self, case: EnforcementCase, ruling_info) -> None:
        """用裁定信息更新案件数据"""
        # 更新法院案号
        if getattr(ruling_info, 'court_case_number', ''):
            case.court_case_number = ruling_info.court_case_number
            self._court_case_index[case.court_case_number] = case
        
        # 更新法官/书记员
        if getattr(ruling_info, 'judge', ''):
            case.judge = ruling_info.judge
        
        if getattr(ruling_info, 'clerk', ''):
            if case.judge:
                case.judge = f"{case.judge}/{ruling_info.clerk}"
            else:
                case.judge = ruling_info.clerk
        
        # 更新裁定日期到裁定结果字段
        if getattr(ruling_info, 'ruling_date', ''):
            case.ruling_result = ruling_info.ruling_date
        
        # 保存扩展信息
        case.applicants = getattr(ruling_info, 'applicants', [])
        case.ruling_date = getattr(ruling_info, 'ruling_date', None)
        case.clerk = getattr(ruling_info, 'clerk', '')
        case.execution_amount = getattr(ruling_info, 'execution_amount', None)
    
    def save_to_excel(self, output_path: Optional[Path] = None) -> Path:
        """将更新后的数据保存回Excel"""
        if self._df is None:
            raise ValueError("未加载Excel数据")
        
        save_path = output_path or self._excel_path
        if not save_path:
            raise ValueError("未指定保存路径")
        
        # 获取列索引配置
        col_cfg = _excel_cfg.get('columns', {})
        
        # 创建副本以避免修改原始DataFrame的类型
        import numpy as np
        df_copy = self._df.copy()
        
        # 确保目标列是object类型（可以存储字符串）
        for col_key in ['case_number', 'judge', 'ruling_result']:
            col_idx = col_cfg.get(col_key, 0)
            if col_idx < len(df_copy.columns):
                # 使用loc列选择并转换为object类型
                col_name = df_copy.columns[col_idx]
                df_copy[col_name] = df_copy[col_name].astype(object)
                # 将NaN替换为None以便可以存储字符串
                df_copy[col_name] = df_copy[col_name].where(df_copy[col_name].notna(), None)
        
        # 更新DataFrame
        for case in self.cases:
            if case.row_index < 0 or case.row_index >= len(df_copy):
                continue
            
            # 更新法院案号
            if case.court_case_number:
                col_idx = col_cfg.get('case_number', 13)
                if col_idx < len(df_copy.columns):
                    df_copy.iat[case.row_index, col_idx] = case.court_case_number
            
            # 更新法官/书记员
            if case.judge:
                col_idx = col_cfg.get('judge', 14)
                if col_idx < len(df_copy.columns):
                    df_copy.iat[case.row_index, col_idx] = case.judge
            
            # 更新裁定结果
            if case.ruling_result:
                col_idx = col_cfg.get('ruling_result', 15)
                if col_idx < len(df_copy.columns):
                    df_copy.iat[case.row_index, col_idx] = case.ruling_result
        
        # 保存
        df_copy.to_excel(save_path, index=False)
        print(f"INFO: 已保存到: {save_path}")
        return save_path
    
    def export_to_json(self, output_path: Path) -> Path:
        """导出所有案件数据到JSON"""
        import json
        
        data = {
            'total_cases': len(self.cases),
            'cases': [case.to_dict() for case in self.cases]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"INFO: 已导出JSON到: {output_path}")
        return output_path
    
    def _normalize_notice_number(self, notice_number: str) -> str:
        """标准化责令号格式（与 export / 统计共用，含去空格）"""
        return normalize_notice_for_match(notice_number)

    def _normalize_court_case_number(self, case_number: str) -> str:
        """标准化法院案号格式"""
        normalized = str(case_number).strip()
        normalized = normalized.replace('(', '（').replace(')', '）')
        normalized = normalized.replace('[', '（').replace(']', '）')
        return normalized


def normalize_notice_for_match(text: str) -> str:
    """责令号匹配用归一化：去空格、统一括号（与 enforcement/export 一致）。"""
    if not text:
        return ""
    normalized = str(text).strip().replace(" ", "")
    for old, new in [
        ("(", "〔"),
        (")", "〕"),
        ("（", "〔"),
        ("）", "〕"),
        ("[", "〔"),
        ("]", "〕"),
        ("［", "〔"),
        ("］", "〕"),
        ("【", "〔"),
        ("】", "〕"),
    ]:
        normalized = normalized.replace(old, new)
    return normalized


def load_enforcement_cases(excel_path: Path) -> EnforcementCaseRegistry:
    """
    加载强制执行案件的便捷函数
    
    Args:
        excel_path: 非诉表格.xlsx 文件路径
    
    Returns:
        EnforcementCaseRegistry: 案件登记簿
    """
    registry = EnforcementCaseRegistry()
    return registry.load_from_excel(excel_path)


if __name__ == "__main__":
    # 测试代码
    test_excel = Path("样本材料/强制组-自动化/提取信息/非诉表格.xlsx")
    if test_excel.exists():
        registry = load_enforcement_cases(test_excel)
        print(f"\n加载了 {len(registry.cases)} 条案件")
        for case in registry.cases[:3]:
            print(f"  - {case.notice_number}: {case.respondent} ({case.employee})")
    else:
        print(f"测试文件不存在: {test_excel}")
