#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能纠错引擎 - 基于上下文和台账数据的OCR纠错

核心策略（三级纠错机制）：
1. L1 - 识别纠错（OCR错误）：置信度≥95%，自动应用
   - 区名纠错：番禹→番禺
   - 常见错字：有限公词→有限公司
   
2. L2 - 台账匹配纠错（模糊匹配）：置信度85%-95%，人工核查
   - 公司名相似但不完全相同
   - 责令号模糊匹配
   
3. L3 - 数字序列纠错：禁用自动，全部人工核查
   - 数字差异（如3539 vs 3519）一律不进自动纠错

安全原则：
- 数字类绝不自动纠错
- 不确定的进人工核查
- 完整审计日志
"""

import re
import json
import difflib
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CorrectionCandidate:
    """纠错候选结果"""
    original: str
    corrected: str
    confidence: float
    method: str  # 'exact', 'fuzzy', 'sequence', 'region', 'learned', 'parse_only', 'failed'
    reason: str
    level: str = 'L0'  # 'L1', 'L2', 'L3' - 纠错级别
    auto_apply: bool = False  # 是否自动应用


@dataclass
class NoticeNumberInfo:
    """解析后的责令号信息"""
    full_text: str
    prefix: str  # 穗公积金中心
    region: str  # 番禺
    suffix: str  # 责字
    year: str    # 2025
    number: str  # 3519
    
    @property
    def normalized(self) -> str:
        return f"{self.prefix}{self.region}{self.suffix}〔{self.year}〕{self.number}号"


class NoticeNumberParser:
    """责令号解析器"""
    
    # 广州公积金责令号模式（支持多种括号变体）
    PATTERN = re.compile(
        r'(穗公积金中心)'  # 前缀
        r'([\u4e00-\u9fa5]{2})'  # 区名（2个汉字）
        r'(责字|贵字|责)'  # 后缀（支持OCR错误）
        r'[〔\[(［【（]'  # 左括号（支持中文圆括号）
        r'(\d{4})'  # 年份
        r'[〕\)\]］】）]'  # 右括号（支持中文圆括号）
        r'(\d+)'  # 号码
        r'号?'
    )
    
    # 区名纠错映射（L1 - 高置信度自动纠错）
    REGION_CORRECTIONS = {
        '番禹': '番禺',
        '天何': '天河',
        '白去': '白云',
        '荔弯': '荔湾',
        '海猪': '海珠',
        '越莠': '越秀',
        '黄浦': '黄埔',
        '花者': '花都',
    }
    
    # 有效的广州区名
    VALID_REGIONS = {
        '番禺', '天河', '白云', '荔湾', '海珠', '越秀', 
        '黄埔', '花都', '萝岗', '南沙', '从化', '增城'
    }
    
    @classmethod
    def parse(cls, text: str) -> Optional[NoticeNumberInfo]:
        """解析责令号"""
        match = cls.PATTERN.search(text)
        if not match:
            return None
        
        prefix, region, suffix, year, number = match.groups()
        
        # 纠正区名（L1级别）
        region = cls.REGION_CORRECTIONS.get(region, region)
        
        # 纠正后缀
        if suffix in ('贵字', '责'):
            suffix = '责字'
        
        return NoticeNumberInfo(
            full_text=match.group(),
            prefix=prefix,
            region=region,
            suffix=suffix,
            year=year,
            number=number
        )
    
    @classmethod
    def extract_all(cls, text: str) -> List[NoticeNumberInfo]:
        """提取文本中的所有责令号"""
        results = []
        for match in cls.PATTERN.finditer(text):
            prefix, region, suffix, year, number = match.groups()
            region = cls.REGION_CORRECTIONS.get(region, region)
            if suffix in ('贵字', '责'):
                suffix = '责字'
            results.append(NoticeNumberInfo(
                full_text=match.group(),
                prefix=prefix,
                region=region,
                suffix=suffix,
                year=year,
                number=number
            ))
        return results


class LedgerBasedCorrector:
    """基于台账的纠错器"""
    
    def __init__(self, ledger_cases: List[Dict]):
        """
        Args:
            ledger_cases: 台账数据列表，每个元素包含 'notice_number', 'sequence', 'company_name'
        """
        self.ledger_cases = ledger_cases
        self._build_indices()
    
    def _build_indices(self):
        """构建索引加速查询"""
        # 按区名索引
        self.region_to_numbers: Dict[str, Set[str]] = defaultdict(set)
        # 所有号码
        self.all_numbers: Set[str] = set()
        # 号码到案件的映射
        self.number_to_cases: Dict[str, List[Dict]] = defaultdict(list)
        
        for case in self.ledger_cases:
            notice = case.get('notice_number', '')
            info = NoticeNumberParser.parse(notice)
            if info:
                self.region_to_numbers[info.region].add(info.number)
                self.all_numbers.add(info.number)
                self.number_to_cases[info.number].append(case)
    
    def correct(self, detected_text: str, context_region: Optional[str] = None) -> Optional[CorrectionCandidate]:
        """
        基于台账纠正检测到的责令号
        
        策略：
        1. L1 - 精确匹配：置信度100%，自动应用
        2. L1 - 区名纠正：高置信度区名纠错，自动应用
        3. L3 - 数字序列纠错：禁用自动，返回候选但不自动应用
        4. L2 - 模糊匹配：中等置信度，建议人工核查
        
        Returns:
            CorrectionCandidate 或 None
        """
        info = NoticeNumberParser.parse(detected_text)
        if not info:
            return None
        
        # L1: 精确匹配（100%置信度，自动应用）
        if info.number in self.all_numbers:
            return CorrectionCandidate(
                original=detected_text,
                corrected=info.normalized,
                confidence=1.0,
                method='exact',
                reason='精确匹配台账记录',
                level='L1',
                auto_apply=True
            )
        
        # L1: 区名验证和纠正（高置信度，自动应用）
        if info.region not in NoticeNumberParser.VALID_REGIONS:
            # 尝试纠正区名
            corrected_region = self._fuzzy_correct_region(info.region)
            if corrected_region:
                original_region = info.region
                info.region = corrected_region
                # 区名纠正后重新检查精确匹配
                if info.number in self.all_numbers:
                    return CorrectionCandidate(
                        original=detected_text,
                        corrected=info.normalized,
                        confidence=0.95,
                        method='region',
                        reason=f'区名纠正: {original_region} -> {corrected_region}',
                        level='L1',
                        auto_apply=True
                    )
        
        # L3: 数字序列推断（禁用自动，建议人工核查）
        # 数字差异一律不自动应用，避免错误纠正
        sequence_match = self._infer_number_by_sequence(
            info.number, 
            info.region,
            context_region
        )
        
        if sequence_match and sequence_match != info.number:
            return CorrectionCandidate(
                original=detected_text,
                corrected=info.normalized.replace(info.number, sequence_match),
                confidence=0.70,  # 较低置信度
                method='sequence',
                reason=f'数字序列推断: {info.number} -> {sequence_match}（建议人工核查）',
                level='L3',
                auto_apply=False  # 禁用自动应用
            )
        
        # L2: 模糊匹配（中等置信度，建议人工核查）
        fuzzy_match = self._fuzzy_match_number(info.number, info.region)
        if fuzzy_match:
            return CorrectionCandidate(
                original=detected_text,
                corrected=info.normalized.replace(info.number, fuzzy_match),
                confidence=0.75,
                method='fuzzy',
                reason=f'模糊匹配: {info.number} -> {fuzzy_match}（建议人工核查）',
                level='L2',
                auto_apply=False  # 不自动应用
            )
        
        return None
    
    def _fuzzy_correct_region(self, region: str) -> Optional[str]:
        """模糊纠正区名"""
        for valid_region in NoticeNumberParser.VALID_REGIONS:
            if difflib.SequenceMatcher(None, region, valid_region).ratio() > 0.7:
                return valid_region
        return None
    
    def _infer_number_by_sequence(
        self, 
        detected_number: str, 
        region: str,
        context_region: Optional[str] = None
    ) -> Optional[str]:
        """
        基于序列推断纠正号码（L3级别 - 禁用自动）
        
        仅用于提示，不自动应用！
        """
        # 使用上下文区名或检测到的区名
        target_region = context_region or region
        region_numbers = self.region_to_numbers.get(target_region, set())
        
        if not region_numbers:
            return None
        
        detected_int = int(detected_number)
        best_match = None
        best_diff = float('inf')
        
        # 找出所有单字符差异的候选
        for ledger_number in region_numbers:
            if len(detected_number) != len(ledger_number):
                continue
                
            # 计算差异字符数
            diff_count = sum(1 for a, b in zip(detected_number, ledger_number) if a != b)
            
            if diff_count == 1:
                # 只有一个字符差异，可能是OCR错误
                ledger_int = int(ledger_number)
                numeric_diff = abs(detected_int - ledger_int)
                
                if numeric_diff < best_diff:
                    best_diff = numeric_diff
                    best_match = ledger_number
        
        return best_match
    
    def _fuzzy_match_number(self, number: str, region: str) -> Optional[str]:
        """模糊匹配号码（L2级别）"""
        region_numbers = self.region_to_numbers.get(region, set())
        
        best_match = None
        best_ratio = 0.0
        
        for ledger_number in region_numbers:
            ratio = difflib.SequenceMatcher(None, number, ledger_number).ratio()
            if ratio > best_ratio and ratio > 0.8:
                best_ratio = ratio
                best_match = ledger_number
        
        return best_match


class AdaptiveLearner:
    """自适应学习器 - 从纠正中学习（仅L1级别规则）"""
    
    # L1级别允许学习的规则（区名、常见错字）
    ALLOWED_PATTERNS = [
        (r'番禹', '番禺'),
        (r'有限公词', '有限公司'),
        (r'有限责公司', '有限责任公司'),
        (r'统一社会信用代玛', '统一社会信用代码'),
    ]
    
    def __init__(self, learn_file: Optional[Path] = None):
        self.learn_file = learn_file or Path(__file__).parent / 'learned_corrections.json'
        self.corrections: Dict[str, str] = {}
        self.correction_stats: Dict[str, Dict] = defaultdict(lambda: {'count': 0, 'success': 0})
        self._load_learned()
    
    def _load_learned(self):
        """加载已学习的纠正规则"""
        if self.learn_file.exists():
            try:
                with open(self.learn_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.corrections = data.get('corrections', {})
                    self.correction_stats = defaultdict(
                        lambda: {'count': 0, 'success': 0},
                        data.get('stats', {})
                    )
            except Exception as e:
                logger.warning(f"加载学习数据失败: {e}")
    
    def save(self):
        """保存学习数据"""
        try:
            with open(self.learn_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'corrections': self.corrections,
                    'stats': dict(self.correction_stats)
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存学习数据失败: {e}")
    
    def learn(self, original: str, corrected: str, success: bool = True):
        """学习一次纠正（仅记录L1级别的规则）"""
        # 只学习允许的L1模式
        is_allowed = False
        for pattern, replacement in self.ALLOWED_PATTERNS:
            if pattern in original or replacement in corrected:
                is_allowed = True
                break
        
        if not is_allowed:
            return
        
        key = f"{original}->{corrected}"
        self.correction_stats[key]['count'] += 1
        if success:
            self.correction_stats[key]['success'] += 1
        
        # 如果成功率足够高，自动应用
        stats = self.correction_stats[key]
        if stats['count'] >= 3 and stats['success'] / stats['count'] > 0.9:
            self.corrections[original] = corrected
            logger.info(f"自动学习新规则: {original} -> {corrected}")
    
    def apply_learned(self, text: str) -> Tuple[str, Optional[CorrectionCandidate]]:
        """
        应用已学习的纠正规则
        
        Returns:
            (纠正后的文本, CorrectionCandidate或None)
        """
        result = text
        for wrong, correct in self.corrections.items():
            if wrong in result:
                result = result.replace(wrong, correct)
                return result, CorrectionCandidate(
                    original=text,
                    corrected=result,
                    confidence=0.95,
                    method='learned',
                    reason=f'应用已学习的规则: {wrong} -> {correct}',
                    level='L1',
                    auto_apply=True
                )
        return result, None


class SmartCorrector:
    """智能纠错引擎主类"""
    
    def __init__(
        self, 
        ledger_cases: Optional[List[Dict]] = None,
        enable_learning: bool = True
    ):
        self.ledger_corrector = LedgerBasedCorrector(ledger_cases) if ledger_cases else None
        self.adaptive_learner = AdaptiveLearner() if enable_learning else None
    
    def correct_notice_number(
        self, 
        detected_text: str,
        context: Optional[Dict] = None
    ) -> CorrectionCandidate:
        """
        纠正责令号
        
        三级纠错策略：
        - L1 (confidence >= 0.95): 自动应用（区名纠错、精确匹配）
        - L2 (confidence 0.75-0.95): 建议人工核查（模糊匹配）
        - L3 (confidence < 0.75): 强制人工核查（数字序列推断）
        
        Returns:
            CorrectionCandidate，包含 auto_apply 标志
        """
        context = context or {}
        
        # L1: 应用已学习的规则（高置信度）
        if self.adaptive_learner:
            learned_text, learned_candidate = self.adaptive_learner.apply_learned(detected_text)
            if learned_candidate:
                return learned_candidate
        
        # L1/L2/L3: 基于台账的纠正
        if self.ledger_corrector:
            context_region = context.get('expected_region')
            result = self.ledger_corrector.correct(detected_text, context_region)
            if result:
                # 记录学习（仅L1级别）
                if self.adaptive_learner and result.level == 'L1':
                    self.adaptive_learner.learn(detected_text, result.corrected)
                return result
        
        # 基础解析（无纠正）
        info = NoticeNumberParser.parse(detected_text)
        if info:
            return CorrectionCandidate(
                original=detected_text,
                corrected=info.normalized,
                confidence=0.6,
                method='parse_only',
                reason='仅解析，无纠正',
                level='L0',
                auto_apply=False
            )
        
        # 无法解析
        return CorrectionCandidate(
            original=detected_text,
            corrected=detected_text,
            confidence=0.0,
            method='failed',
            reason='无法解析责令号',
            level='L0',
            auto_apply=False
        )
    
    def should_auto_apply(self, candidate: CorrectionCandidate) -> bool:
        """判断是否应自动应用纠错结果"""
        # 只有L1级别且明确标记为auto_apply的才自动应用
        return candidate.level == 'L1' and candidate.auto_apply and candidate.confidence >= 0.95
    
    def needs_manual_review(self, candidate: CorrectionCandidate) -> bool:
        """判断是否需要人工核查"""
        # L2和L3级别需要人工核查
        return candidate.level in ('L2', 'L3') or not candidate.auto_apply
    
    def correct_text(self, text: str, context: Optional[Dict] = None) -> Tuple[str, List[CorrectionCandidate]]:
        """
        纠正文本中的所有责令号
        
        Returns:
            (纠正后的文本, 所有纠错候选列表)
        """
        infos = NoticeNumberParser.extract_all(text)
        result = text
        corrections = []
        
        for info in infos:
            correction = self.correct_notice_number(info.full_text, context)
            corrections.append(correction)
            
            # 只有高置信度的才自动替换
            if self.should_auto_apply(correction):
                result = result.replace(info.full_text, correction.corrected)
        
        return result, corrections
    
    def save_learning(self):
        """保存学习数据"""
        if self.adaptive_learner:
            self.adaptive_learner.save()


# 便捷函数
def create_corrector_from_ledger(ledger_cases: List[Dict]) -> SmartCorrector:
    """从台账数据创建纠错器"""
    return SmartCorrector(ledger_cases=ledger_cases, enable_learning=True)
