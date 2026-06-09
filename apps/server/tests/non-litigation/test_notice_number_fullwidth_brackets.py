# -*- coding: utf-8 -*-
r"""回归测试：全角圆括号文号匹配。

背景：台账里 99% 的责令号是全角圆括号格式
（如 `穗公积金中心南沙责字（2025）1240号`），但旧版
`config.regex_patterns.notice_number` 字符类 `[〔\[(［【]` 不含全角圆括号
`（` (U+FF08)，导致全角圆括号文号全部漏识别 → 全部走"人工核查"。

本测试覆盖修复后的所有相关正则，断言台账 100% 真实数据可匹配。
"""
from pathlib import Path
import re

import pytest

from core.config_loader import load_config
from non_litigation.smart_extractor import NoticeNumberExtractor
from non_litigation.export import (
    _RELAXED_NOTICE_PATTERN,
    _NOTICE_STRUCT_PATTERN,
)


_REAL_SAMPLES = [
    "穗公积金中心南沙责字（2025）1240号",
    "穗公积金中心白云责字（2025）1698号",
    "穗公积金中心越秀责字（2024）914-1号",
    "穗公积金中心越秀责字（2025）1007号",
    "穗公积金中心越秀责字（2025）1107号",
]

_ALL_BRACKET_SAMPLES = [
    ("穗公积金中心南沙责字（2025）1240号", "fullwidth_round"),
    ("穗公积金中心越秀责字（2024）914-1号", "fullwidth_round_with_dash"),
    ("穗公积金中心越秀责字〔2025〕1007号", "tortoise"),
    ("穗公积金中心越秀责字[2025]1007号", "halfwidth_square"),
    ("穗公积金中心越秀责字(2025)1007号", "halfwidth_round"),
    ("穗公积金中心越秀责字［2025］1007号", "fullwidth_square"),
    ("穗公积金中心越秀责字【2025】1007号", "blacklenticular"),
]


def test_config_notice_pattern_matches_fullwidth_round_brackets():
    """主正则（config.yaml:336）必须匹配全角圆括号。"""
    cfg = load_config()
    for sample, _label in _ALL_BRACKET_SAMPLES:
        m = cfg.notice_pattern.search(sample)
        assert m, f"主正则未匹配 {sample!r}"


def test_config_decision_number_range_pattern_matches_fullwidth_round_brackets():
    """区间正则（config.yaml:340）必须支持全角圆括号。"""
    cfg = load_config()
    pat = cfg.notice_number_range_pattern
    text = "穗公积金中心南沙责字（2025）100号至110号"
    m = pat.search(text)
    assert m, f"区间正则未匹配 {text!r}"


def test_config_single_decision_number_pattern_matches_fullwidth_round_brackets():
    """单号正则（config.yaml:341）必须支持全角圆括号。"""
    cfg = load_config()
    pat = cfg.single_decision_number_pattern
    text = "穗公积金中心南沙责字（2025）1240号"
    m = pat.search(text)
    assert m, f"单号正则未匹配 {text!r}"


def test_config_enforcement_notice_number_in_ruling_matches_fullwidth_round_brackets():
    """强制执行组文号正则（config.yaml:441）必须支持全角圆括号。"""
    cfg = load_config()
    raw_pat = cfg.raw_config['enforcement']['extraction']['notice_number_in_ruling_pattern']
    pat = re.compile(raw_pat)
    text = "穗公积金中心越秀责字（2025）1107号"
    m = pat.search(text)
    assert m, f"强制组文号正则未匹配 {text!r}"


def test_config_enforcement_notice_number_range_matches_fullwidth_round_brackets():
    """强制执行组文号区间正则（config.yaml:442）必须支持全角圆括号。"""
    cfg = load_config()
    raw_pat = cfg.raw_config['enforcement']['extraction']['notice_number_range_pattern']
    pat = re.compile(raw_pat)
    text = "责字（2025）100号至110号"
    m = pat.search(text)
    assert m, f"强制组区间正则未匹配 {text!r}"


def test_smart_extractor_validate_notice_number_accepts_fullwidth_round_brackets():
    """smart_extractor._validate_notice_number 内部正则必须支持全角圆括号。"""
    extractor = NoticeNumberExtractor.__new__(NoticeNumberExtractor)
    assert extractor._validate_notice_number("穗公积金中心南沙责字（2025）1240号")
    assert extractor._validate_notice_number("穗公积金中心越秀责字（2024）914-1号")


def test_export_relaxed_notice_pattern_matches_fullwidth_round_brackets():
    """export._RELAXED_NOTICE_PATTERN 必须支持全角圆括号。"""
    for sample, _label in _ALL_BRACKET_SAMPLES:
        m = _RELAXED_NOTICE_PATTERN.search(sample)
        assert m, f"_RELAXED_NOTICE_PATTERN 未匹配 {sample!r}"


def test_export_notice_struct_pattern_matches_fullwidth_round_brackets():
    """export._NOTICE_STRUCT_PATTERN 必须支持全角圆括号。"""
    for sample, _label in _ALL_BRACKET_SAMPLES:
        m = _NOTICE_STRUCT_PATTERN.match(sample)
        assert m, f"_NOTICE_STRUCT_PATTERN 未匹配 {sample!r}"


def test_real_ledger_notices_all_match_main_pattern(tmp_path: Path):
    """端到端：从真实台账读取所有文号，主正则必须 100% 匹配。"""
    from core.paths import ROOT as _ROOT
    cfg = load_config()
    ledger_xlsx = (
        _ROOT
        / "apps"
        / "desktop"
        / "src-tauri"
        / "resources"
        / "sample-data"
        / "non-litigation-batch1"
        / "台账及命名规则.xlsx"
    )
    if not ledger_xlsx.exists():
        pytest.skip(f"台账文件不存在: {ledger_xlsx}")
    try:
        import openpyxl
    except ImportError:
        pytest.skip("openpyxl 不可用")

    wb = openpyxl.load_workbook(ledger_xlsx, data_only=True)
    notices = set()
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if cell and isinstance(cell, str) and "公积金" in cell and "责字" in cell:
                    notices.add(cell.strip())
    assert notices, "台账中未发现任何文号"
    failed = [n for n in notices if not cfg.notice_pattern.search(n)]
    assert not failed, f"主正则漏识别 {len(failed)}/{len(notices)} 个文号；前 5 个: {failed[:5]}"


def test_bracket_class_fullwidth_round_chars_present():
    """防御性回归：未来若有人重写字符类，必须保留 `（` 和 `）`。"""
    cfg = load_config()
    pattern = cfg.notice_pattern.pattern
    assert "\uff08" in pattern, "左字符类必须含全角左圆括号 （"
    assert "\uff09" in pattern, "右字符类必须含全角右圆括号 ）"
