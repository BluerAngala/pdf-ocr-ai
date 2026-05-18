#!/usr/bin/env python3
"""验证新区域配置的 OCR 效果和性能，对比新旧区域。"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    from rapidocr import RapidOCR

from core.pdf_ocr_ultra import OCRConfig
from core.region_extractor import RegionExtractor, Region, REGIONS

_poppler_path = OCRConfig().poppler_path

OLD_REGIONS = {
    "申请书": [
        Region(name="申请书标题(旧)", top=0.0, bottom=0.2, left=0.0, right=1.0),
    ],
    "授权书": [
        Region(name="公司名称-页眉(旧)", top=0.0, bottom=0.3, left=0.0, right=1.0),
        Region(name="公司名称-中间(旧)", top=0.3, bottom=0.7, left=0.1, right=0.9),
    ],
    "所函": [
        Region(name="公司名称-中间(旧)", top=0.3, bottom=0.7, left=0.1, right=0.9),
    ],
}

NEW_REGIONS = {
    "申请书": [
        REGIONS.get("application_title"),
        REGIONS.get("application_respondent"),
    ],
    "授权书": [
        REGIONS.get("auth_title"),
        REGIONS.get("auth_company"),
    ],
    "所函": [
        REGIONS.get("letter_company"),
    ],
}

KEYWORDS = {
    "申请书": ["强制执行申请书", "名称", "被执行人"],
    "授权书": ["委托人", "有限公司", "授权委托书"],
    "所函": ["律师事务所函", "有限公司", "管理中心"],
}


def calc_area_pct(region: Region) -> float:
    return (region.bottom - region.top) * (region.right - region.left) * 100


def test_regions(pdf_path: str, doc_type: str, regions: list, label: str):
    ocr = RapidOCR()
    extractor = RegionExtractor(dpi=150, poppler_path=_poppler_path)
    total_pages = extractor.get_page_count(Path(pdf_path))

    total_area = sum(calc_area_pct(r) for r in regions if r)
    print(f"\n  [{label}] 区域数: {len(regions)}, 总面积: {total_area:.1f}%")

    all_texts = []
    total_ocr_time = 0.0

    for page_num in range(1, min(total_pages + 1, 4)):
        full_image = extractor.extract_full_page(Path(pdf_path), page_num)
        for region in regions:
            if region is None:
                continue
            region_image = extractor.crop_region_from_image(full_image, region)
            start = time.perf_counter()
            result = ocr(region_image)
            elapsed = time.perf_counter() - start
            total_ocr_time += elapsed

            if result and result[0]:
                texts = []
                for line in result[0]:
                    text_val = line[1]
                    if isinstance(text_val, (list, tuple)):
                        texts.append(text_val[0] if len(text_val) > 0 else "")
                    else:
                        texts.append(str(text_val))
                combined = " ".join(texts)
                all_texts.append(combined)
                print(f"    P{page_num} [{region.name}] ({elapsed:.2f}s): {combined[:120]}")
            else:
                print(f"    P{page_num} [{region.name}] ({elapsed:.2f}s): (无结果)")

    full_text = "\n".join(all_texts)
    keywords = KEYWORDS.get(doc_type, [])
    hits = [kw for kw in keywords if kw in full_text]
    print(f"  [{label}] OCR总耗时: {total_ocr_time:.2f}s, 关键词命中: {hits}/{keywords}")

    return total_ocr_time, hits, full_text


if __name__ == "__main__":
    sample_dir = Path(r"c:\Users\11071\Documents\trae_projects\pdf识别\样本材料\非诉组自动化样本材料\原始文件")

    pdfs = {
        "申请书": sample_dir / "申请书.pdf",
        "授权书": sample_dir / "授权书.pdf",
        "所函": sample_dir / "所函.pdf",
    }

    print("=" * 80)
    print("  新旧区域配置对比测试")
    print("=" * 80)

    for doc_type, pdf_path in pdfs.items():
        if not pdf_path.exists():
            print(f"\n文件不存在: {pdf_path}")
            continue

        print(f"\n{'='*60}")
        print(f"  {doc_type}: {pdf_path.name}")
        print(f"{'='*60}")

        old_time, old_hits, old_text = test_regions(
            str(pdf_path), doc_type, OLD_REGIONS[doc_type], "旧区域"
        )
        new_time, new_hits, new_text = test_regions(
            str(pdf_path), doc_type, [r for r in NEW_REGIONS[doc_type] if r], "新区域"
        )

        speedup = old_time / new_time if new_time > 0 else float("inf")
        print(f"\n  >>> 对比: 旧={old_time:.2f}s, 新={new_time:.2f}s, 提速={speedup:.1f}x")
        print(f"  >>> 关键词: 旧命中={old_hits}, 新命中={new_hits}")

        missing = set(old_hits) - set(new_hits)
        if missing:
            print(f"  ⚠️ 新区域遗漏关键词: {missing}")
        else:
            print(f"  ✅ 新区域关键词覆盖完整")
