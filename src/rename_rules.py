#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, List


class RenameService:
    def __init__(self, processor):
        self.processor = processor

    def build_notice_rename_result(self, original_filename: str, ocr_text: str, ledger_map: Dict[str, str]) -> Dict:
        process_result = self.processor.process(ocr_text)
        decision_numbers = process_result['structured']['notice']['decision_numbers']
        decision_number = decision_numbers[0] if decision_numbers else None
        sequence = ledger_map.get(decision_number) if decision_number else None
        matched = bool(decision_number and sequence)
        new_filename = f'{sequence}-责催-{decision_number}.pdf' if matched else original_filename
        return {
            'matched': matched,
            'original_filename': original_filename,
            'decision_number': decision_number,
            'sequence': sequence,
            'new_filename': new_filename,
        }

    def build_company_rename_result(self, original_filename: str, ocr_text: str) -> Dict:
        process_result = self.processor.process(ocr_text)
        company_name = process_result['structured']['notice']['company_name']
        matched = bool(company_name)
        new_filename = f'{company_name}.pdf' if matched else original_filename
        return {
            'matched': matched,
            'original_filename': original_filename,
            'company_name': company_name,
            'new_filename': new_filename,
        }


def build_notice_rename_plan(samples: List[Dict], ledger_map: Dict[str, str], service: RenameService) -> Dict:
    items = []
    matched = 0
    unmatched = 0

    for sample in samples:
        item = service.build_notice_rename_result(
            original_filename=sample['filename'],
            ocr_text=sample['ocr_text'],
            ledger_map=ledger_map,
        )
        items.append(item)
        if item['matched']:
            matched += 1
        else:
            unmatched += 1

    return {
        'total': len(samples),
        'matched': matched,
        'unmatched': unmatched,
        'items': items,
    }
