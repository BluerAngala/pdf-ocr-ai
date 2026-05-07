#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from typing import Dict, List

from non_litigation_product import build_non_litigation_standard_plan


DIRECTORY_MAPPING = {
    '责催': '输出文件（责催）',
    '申请书': '输出文件（申请书）',
    '授权书': '输出文件（授权书）',
    '所函': '输出文件（所函）',
}


def build_expected_output_tree(sample_root: Path) -> Dict[str, List[str]]:
    plan = build_non_litigation_standard_plan(sample_root)
    result: Dict[str, List[str]] = {}
    for doc_type, items in plan.items():
        result[DIRECTORY_MAPPING[doc_type]] = [item['target_filename'] for item in items]
    return result
