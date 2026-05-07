#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from typing import Dict

from rename_rules import build_notice_rename_plan, RenameService


def build_notice_plan_from_paths(input_dir: Path, output_dir: Path, ledger_map: Dict[str, str], service: RenameService) -> Dict:
    samples = []
    for pdf_path in sorted(input_dir.glob('*.pdf')):
        text_path = output_dir / f'{pdf_path.stem}_ultra_result.txt'
        if text_path.exists():
            samples.append({
                'filename': pdf_path.name,
                'ocr_text': text_path.read_text(encoding='utf-8'),
            })
        else:
            samples.append({
                'filename': pdf_path.name,
                'ocr_text': '',
            })
    return build_notice_rename_plan(samples=samples, ledger_map=ledger_map, service=service)


def summarize_plan(plan: Dict) -> Dict:
    matched_items = [item for item in plan['items'] if item['matched']]
    unmatched_items = [item for item in plan['items'] if not item['matched']]
    return {
        'total': plan['total'],
        'matched': plan['matched'],
        'unmatched': plan['unmatched'],
        'matched_items': matched_items,
        'unmatched_items': unmatched_items,
    }
