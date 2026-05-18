#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断脚本：只跑授权书 + 所函的真实 OCR，输出 JSON 文件
"""

import sys
import json
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.paths import ROOT, USER_DATA_DIR
from core.pdf_ocr_ultra import UltraFastOCR, OCRConfig
from core.region_extractor import RegionExtractor, REGIONS
from core.text_postprocessor import TextPostProcessor
from non_litigation.export import (
    apply_ocr_corrections,
    inspect_pdf_page_count,
    _extract_target_company,
    normalize_company_name_for_matching,
    _collect_region_texts,
    _build_ocr_processors,
)
from core.config_loader import load_config

_cfg = load_config()
input_dir = ROOT / 'input' / 'non-litigation'


def diagnose_doc(doc_type: str, pdf_name: str):
    pdf_path = input_dir / pdf_name
    if not pdf_path.exists():
        return None

    total_pages = inspect_pdf_page_count(pdf_path)
    ocr, region_extractor = _build_ocr_processors()
    post_processor = TextPostProcessor()

    pages = []
    for page_num in range(1, total_pages + 1):
        full_image = region_extractor.extract_full_page(pdf_path, page_num)

        region_text, page_logs = _collect_region_texts(
            ocr, region_extractor, pdf_path, page_num, doc_type, full_image=full_image
        )
        region_text_corrected = apply_ocr_corrections(region_text)

        full_result = ocr.recognize_full_page_image(
            full_image, page_num=page_num, method='full_page', optimize_output=True
        )
        full_text_corrected = apply_ocr_corrections(full_result.text)

        detected_from_region = _extract_target_company(region_text_corrected, fallback_fn=post_processor.extract_company_name_from_text)
        detected_from_full = _extract_target_company(full_text_corrected, fallback_fn=post_processor.extract_company_name_from_text)

        pages.append({
            'page': page_num,
            'region_ocr_raw': region_text,
            'region_ocr_corrected': region_text_corrected,
            'full_ocr_corrected': full_text_corrected,
            'company_from_region': detected_from_region,
            'company_from_full': detected_from_full,
        })

    return {
        'doc_type': doc_type,
        'pdf_name': pdf_name,
        'total_pages': total_pages,
        'pages': pages,
    }


if __name__ == '__main__':
    results = {}
    results['授权书'] = diagnose_doc('授权书', '授权书.pdf')
    results['所函'] = diagnose_doc('所函', '所函.pdf')

    output_path = ROOT / 'temp' / 'diagnose_ocr_company.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"诊断结果已保存: {output_path}")
