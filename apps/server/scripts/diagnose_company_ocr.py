#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断脚本：只跑授权书 + 所函的真实 OCR，打印每页原始文字和公司名提取过程
"""

import sys
from pathlib import Path

# 当前文件在 apps/server/scripts/ 下，src 在 apps/server/src/
SRC = Path(__file__).resolve().parent.parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paths import ROOT, USER_DATA_DIR
from pdf_ocr_ultra import UltraFastOCR, OCRConfig
from region_extractor import RegionExtractor, REGIONS
from text_postprocessor import TextPostProcessor
from non_litigation_export import (
    apply_ocr_corrections,
    inspect_pdf_page_count,
    _extract_target_company,
    normalize_company_name_for_matching,
    _collect_region_texts,
    _build_ocr_processors,
)
from config_loader import load_config

_cfg = load_config()
input_dir = ROOT / 'input' / 'non-litigation'


def diagnose_doc(doc_type: str, pdf_name: str):
    pdf_path = input_dir / pdf_name
    if not pdf_path.exists():
        print(f"\n[SKIP] {pdf_name} 不存在")
        return

    print(f"\n{'=' * 60}")
    print(f"诊断: {doc_type} ({pdf_name})")
    print('=' * 60)

    total_pages = inspect_pdf_page_count(pdf_path)
    print(f"总页数: {total_pages}\n")

    ocr, region_extractor = _build_ocr_processors()
    post_processor = TextPostProcessor()

    for page_num in range(1, total_pages + 1):
        print(f"--- 第 {page_num} 页 ---")

        # 1. 提取全页图
        full_image = region_extractor.extract_full_page(pdf_path, page_num)

        # 2. 区域裁剪 OCR（和正式流程一致）
        region_text, page_logs = _collect_region_texts(
            ocr, region_extractor, pdf_path, page_num, doc_type, full_image=full_image
        )
        region_text_corrected = apply_ocr_corrections(region_text)

        # 3. 整页 OCR（用于对比）
        full_result = ocr.recognize_full_page_image(
            full_image, page_num=page_num, method='full_page', optimize_output=True
        )
        full_text_corrected = apply_ocr_corrections(full_result.text)

        # 4. 打印原始识别结果
        print(f"  [区域OCR] 原始文本:\n{region_text!r}")
        print(f"  [区域OCR] 纠错后文本:\n{region_text_corrected!r}")
        print(f"  [整页OCR] 纠错后文本:\n{full_text_corrected!r}")

        # 5. 公司名提取（两种策略）
        detected_from_region = _extract_target_company(region_text_corrected, fallback_fn=post_processor.extract_company_name_from_text)
        detected_from_full = _extract_target_company(full_text_corrected, fallback_fn=post_processor.extract_company_name_from_text)

        print(f"  [公司名提取] 从区域OCR: {detected_from_region!r}")
        print(f"  [公司名提取] 从整页OCR: {detected_from_full!r}")
        print()


if __name__ == '__main__':
    diagnose_doc('授权书', '授权书.pdf')
    diagnose_doc('所函', '所函.pdf')
