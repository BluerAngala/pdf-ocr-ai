#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试脚本：测试强制执行组匹配逻辑
"""

import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from enforcement.product import (
    EnforcementCaseRegistry,
    normalize_notice_for_match,
    load_enforcement_cases,
)
from enforcement.extractor import RulingInfo


def test_normalize():
    """测试标准化函数"""
    test_cases = [
        "穗公积金中心萝岗责字〔2023〕3360号",
        "穗公积金中心萝岗责字[2023]3360号",
        "穗公积金中心萝岗责字(2023)3360号",
        "穗公积金中心萝岗责字（2023）3360号",
        " 穗公积金中心萝岗责字〔2023〕3360号 ",
    ]

    print("=== 标准化测试 ===")
    for tc in test_cases:
        norm = normalize_notice_for_match(tc)
        print(f"  原始: '{tc}'")
        print(f"  标准化: '{norm}'")
        print()


def test_match_logic():
    """测试匹配逻辑"""
    registry = EnforcementCaseRegistry()

    # 模拟台账数据
    test_notices = [
        "穗公积金中心萝岗责字〔2023〕3360号",
        "穗公积金中心萝岗责字〔2023〕3361号",
        "穗公积金中心越秀责字〔2024〕562号",
    ]

    for i, notice in enumerate(test_notices):
        from enforcement.product import EnforcementCase
        case = EnforcementCase()
        case.notice_number = notice
        case.region = "测试"
        case.respondent = f"公司{i}"
        registry.cases.append(case)

        # 建立索引
        normalized = registry._normalize_notice_number(notice)
        registry._notice_index[normalized] = case

    print("=== 台账索引 ===")
    for k, v in registry._notice_index.items():
        print(f"  key='{k}' -> notice='{v.notice_number}'")

    # 模拟 PDF 提取结果
    test_pdf_notices = [
        ["穗公积金中心萝岗责字〔2023〕3360号", "穗公积金中心萝岗责字〔2023〕3361号"],
        ["穗公积金中心越秀责字〔2024〕562号"],
    ]

    print("\n=== 匹配测试 ===")
    for i, notices in enumerate(test_pdf_notices):
        info = RulingInfo()
        info.notice_numbers = notices
        info.court_case_number = f"(2025)粤7101行审{3355+i}号"

        matched = registry.match_ruling_info(info)
        print(f"\nPDF {i+1}:")
        print(f"  提取责令号: {notices}")
        print(f"  匹配结果: {len(matched)} 条")
        for m in matched:
            print(f"    - {m.notice_number}")


def test_edge_cases():
    """测试边界情况"""
    print("\n=== 边界情况测试 ===")

    # 测试1: 短格式 vs 长格式
    short = "责字〔2023〕3360号"
    long = "穗公积金中心萝岗责字〔2023〕3360号"
    norm_short = normalize_notice_for_match(short)
    norm_long = normalize_notice_for_match(long)
    print(f"\n短格式: '{short}' -> '{norm_short}'")
    print(f"长格式: '{long}' -> '{norm_long}'")
    print(f"短.endswith(长): {norm_short.endswith(norm_long)}")
    print(f"长.endswith(短): {norm_long.endswith(norm_short)}")

    # 测试2: 带空格的 OCR 结果
    ocr_result = "穗公积金中心萝岗责字 〔2023〕 3360 号"
    norm_ocr = normalize_notice_for_match(ocr_result)
    print(f"\nOCR带空格: '{ocr_result}' -> '{norm_ocr}'")

    # 测试3: 不同年份
    notice_2023 = "穗公积金中心萝岗责字〔2023〕3360号"
    notice_2024 = "穗公积金中心越秀责字〔2024〕562号"
    norm_2023 = normalize_notice_for_match(notice_2023)
    norm_2024 = normalize_notice_for_match(notice_2024)
    print(f"\n2023: '{norm_2023}'")
    print(f"2024: '{norm_2024}'")
    print(f"相等: {norm_2023 == norm_2024}")

    # 测试4: 模拟截图中的情况
    print("\n=== 模拟截图场景 ===")
    # 假设台账中有这些责令号
    ledger_notices = [
        "穗公积金中心萝岗责字〔2023〕3360号",
        "穗公积金中心萝岗责字〔2023〕3361号",
        "穗公积金中心越秀责字〔2024〕562号",
    ]
    # PDF 提取的责令号
    pdf_notices = [
        "穗公积金中心萝岗责字〔2023〕3360号",
        "穗公积金中心萝岗责字〔2023〕3361号",
    ]

    registry = EnforcementCaseRegistry()
    for notice in ledger_notices:
        from enforcement.product import EnforcementCase
        case = EnforcementCase()
        case.notice_number = notice
        registry.cases.append(case)
        normalized = registry._normalize_notice_number(notice)
        registry._notice_index[normalized] = case

    info = RulingInfo()
    info.notice_numbers = pdf_notices
    matched = registry.match_ruling_info(info)
    print(f"台账: {len(ledger_notices)} 条")
    print(f"PDF 提取: {pdf_notices}")
    print(f"匹配结果: {len(matched)} 条")
    for m in matched:
        print(f"  - {m.notice_number}")


if __name__ == "__main__":
    test_normalize()
    print()
    test_match_logic()
    print()
    test_edge_cases()
