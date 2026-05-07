#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from typing import Dict, List


REQUIRED_FIELDS = ['行政审查案号', '审批员/法官助理', '执行时间']


def normalize_ruling_decision_number(value: str) -> str:
    text = str(value).strip()
    text = re.sub(r'\s+', '', text)
    text = text.replace('（', '〔').replace('）', '〕').replace('(', '〔').replace(')', '〕')
    text = text.replace('穗公积金中心', '')
    return text


def match_ruling_rows(rows: List[Dict], ocr_text: str, processor) -> Dict:
    process_result = processor.process(ocr_text)
    ruling = process_result['structured']['ruling']
    decision_numbers = {normalize_ruling_decision_number(item) for item in ruling['decision_numbers']}

    matched_count = 0
    output_rows = []
    for row in rows:
        row_copy = dict(row)
        row_decision_number = normalize_ruling_decision_number(row_copy.get('责令号', ''))
        if row_decision_number in decision_numbers:
            row_copy['行政审查案号'] = ruling['administrative_case_no'] or ''
            row_copy['审批员/法官助理'] = ruling['judge'] or ''
            row_copy['执行时间'] = ruling['execution_date'] or ''
            matched_count += 1
        output_rows.append(row_copy)

    return {
        'matched_count': matched_count,
        'rows': output_rows,
        'decision_numbers': sorted(decision_numbers),
    }
