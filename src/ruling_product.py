#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from typing import Dict, List

from text_postprocessor import TextPostProcessor
from ruling_excel_workflow import load_non_litigation_rows_from_excel
from ruling_match_workflow import match_ruling_rows
from ruling_output_workflow import build_ruling_output_rows


def build_ruling_product_payload(excel_path: Path, ocr_texts: List[str]) -> Dict:
    processor = TextPostProcessor()
    rows = load_non_litigation_rows_from_excel(excel_path)
    matched_count = 0

    current_rows = rows
    for ocr_text in ocr_texts:
        match_result = match_ruling_rows(rows=current_rows, ocr_text=ocr_text, processor=processor)
        current_rows = match_result['rows']
        matched_count += match_result['matched_count']

    output_rows = build_ruling_output_rows(current_rows)
    return {
        'matched_count': matched_count,
        'rows': output_rows,
    }
