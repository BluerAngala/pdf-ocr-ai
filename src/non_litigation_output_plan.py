#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from typing import Dict, List

from non_litigation_product import build_non_litigation_standard_plan

from config_loader import load_config

_cfg = load_config()


def build_expected_output_tree(sample_root: Path) -> Dict[str, List[str]]:
    plan = build_non_litigation_standard_plan(sample_root)
    result: Dict[str, List[str]] = {}
    for doc_type, items in plan.items():
        result[_cfg.directory_mapping[doc_type]] = [item['target_filename'] for item in items]
    return result
