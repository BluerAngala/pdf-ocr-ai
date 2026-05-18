#!/usr/bin/env python3
"""分析样本 PDF 中关键字段的精确位置，用于优化区域裁剪配置。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdf2image import convert_from_path

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    from rapidocr import RapidOCR

from core.pdf_ocr_ultra import OCRConfig
from core.region_extractor import RegionExtractor, REGIONS

_poppler_path = OCRConfig().poppler_path


def analyze_pdf_layout(pdf_path: str, doc_type: str, max_pages: int = 3):
    """分析 PDF 布局，输出每页 OCR 结果及坐标信息。"""
    print(f"\n{'='*80}")
    print(f"  文书类型: {doc_type}")
    print(f"  文件: {pdf_path}")
    print(f"{'='*80}")

    ocr = RapidOCR()
    extractor = RegionExtractor(dpi=150, poppler_path=_poppler_path)

    total_pages = extractor.get_page_count(Path(pdf_path))
    print(f"  总页数: {total_pages}")

    for page_num in range(1, min(total_pages + 1, max_pages + 1)):
        full_image = extractor.extract_full_page(Path(pdf_path), page_num)
        width, height = full_image.size
        print(f"\n--- 第 {page_num} 页 (尺寸: {width}x{height}) ---")

        result = ocr(full_image)
        if not result or not result[0]:
            print("  (无 OCR 结果)")
            continue

        for line_info in result[0]:
            bbox = line_info[0]
            text_val = line_info[1]
            if isinstance(text_val, (list, tuple)):
                text = text_val[0] if len(text_val) > 0 else ""
                confidence = text_val[1] if len(text_val) > 1 else "?"
            else:
                text = str(text_val)
                confidence = line_info[2] if len(line_info) > 2 else "?"

            x1, y1 = bbox[0]
            x2, y2 = bbox[2]

            pct_top = y1 / height
            pct_bottom = y2 / height
            pct_left = x1 / width
            pct_right = x2 / width

            print(f"  [{pct_top:.2f}-{pct_bottom:.2f}, {pct_left:.2f}-{pct_right:.2f}] "
                  f"({confidence}) {text}")

    print()


def analyze_region_effectiveness(pdf_path: str, doc_type: str, region_names: list, max_pages: int = 3):
    """测试指定区域的 OCR 效果，对比区域 OCR vs 全页 OCR。"""
    print(f"\n{'='*80}")
    print(f"  区域效果测试: {doc_type}")
    print(f"  区域: {region_names}")
    print(f"{'='*80}")

    ocr = RapidOCR()
    extractor = RegionExtractor(dpi=150, poppler_path=_poppler_path)

    total_pages = extractor.get_page_count(Path(pdf_path))
    print(f"  总页数: {total_pages}")

    for page_num in range(1, min(total_pages + 1, max_pages + 1)):
        full_image = extractor.extract_full_page(Path(pdf_path), page_num)
        width, height = full_image.size

        print(f"\n--- 第 {page_num} 页 ---")

        for region_name in region_names:
            if region_name not in REGIONS:
                print(f"  区域 '{region_name}' 未定义，跳过")
                continue

            region = REGIONS[region_name]
            region_image = extractor.crop_region_from_image(full_image, region)
            rw, rh = region_image.size

            result = ocr(region_image)
            if result and result[0]:
                texts = [line[1][0] for line in result[0]]
                combined = "\n".join(texts)
                print(f"  [{region_name}] ({rw}x{rh}, "
                      f"top={region.top:.0%}-{region.bottom:.0%}, "
                      f"left={region.left:.0%}-{region.right:.0%})")
                print(f"    文本: {combined[:200]}")
            else:
                print(f"  [{region_name}] 无识别结果")

    print()


if __name__ == "__main__":
    sample_dir = Path(r"c:\Users\11071\Documents\trae_projects\pdf识别\样本材料\非诉组自动化样本材料\原始文件")

    pdfs = {
        "申请书": sample_dir / "申请书.pdf",
        "授权书": sample_dir / "授权书.pdf",
        "所函": sample_dir / "所函.pdf",
    }

    for doc_type, pdf_path in pdfs.items():
        if pdf_path.exists():
            analyze_pdf_layout(str(pdf_path), doc_type, max_pages=2)
        else:
            print(f"文件不存在: {pdf_path}")

    print("\n" + "="*80)
    print("  当前区域配置效果测试")
    print("="*80)

    region_map = {
        "申请书": ["application_title"],
        "授权书": ["company_top", "company_middle"],
        "所函": ["company_middle"],
    }

    for doc_type, pdf_path in pdfs.items():
        if pdf_path.exists():
            analyze_region_effectiveness(
                str(pdf_path), doc_type, region_map.get(doc_type, []), max_pages=2
            )
