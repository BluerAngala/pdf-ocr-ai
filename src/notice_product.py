#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from typing import Dict

from text_postprocessor import TextPostProcessor
from rename_rules import RenameService
from notice_rename_workflow import build_notice_plan_from_paths, load_ledger_map_from_excel, summarize_plan


def build_notice_product_payload(ledger_excel_path: Path, input_dir: Path, output_dir: Path) -> Dict:
    processor = TextPostProcessor()
    service = RenameService(processor)
    ledger_map = load_ledger_map_from_excel(ledger_excel_path)
    plan = build_notice_plan_from_paths(input_dir=input_dir, output_dir=output_dir, ledger_map=ledger_map, service=service)
    summary = summarize_plan(plan)
    return {
        'summary': {
            'total': summary['total'],
            'matched': summary['matched'],
            'unmatched': summary['unmatched'],
        },
        'items': plan['items'],
        'matched_items': summary['matched_items'],
        'unmatched_items': summary['unmatched_items'],
    }
