#!/usr/bin/env python3
"""
快速测试 _execute_task 单步执行
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.paths import ROOT
from core.pdf_ocr_ultra import get_ocr_engine, UltraFastOCR
from core.region_extractor import RegionExtractor
from core.task_state import TaskStateManager, Task
from PIL import Image
import numpy as np

print("="*60)
print("单步 OCR 执行诊断")
print("="*60)

sample_root = ROOT / '样本材料' / '非诉组自动化样本材料'
input_dir = sample_root / '原始文件'
auth_pdf = input_dir / '授权书.pdf'

print(f"\n测试文件: {auth_pdf}")
print(f"文件存在: {auth_pdf.exists()}")

if not auth_pdf.exists():
    print("ERROR: 文件不存在")
    sys.exit(1)

# 1. 初始化 OCR
print("\n[1/5] 初始化 OCR 引擎...")
try:
    engine = get_ocr_engine()
    print(f"  [OK] OCR 引擎: {type(engine)}")
except Exception as e:
    print(f"  [FAIL] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 2. 初始化区域提取器
print("\n[2/5] 初始化区域提取器...")
try:
    from core.pdf_ocr_ultra import OCRConfig
    cfg = OCRConfig()
    extractor = RegionExtractor(dpi=200, poppler_path=cfg.poppler_path)
    print(f"  [OK] RegionExtractor 初始化完成, poppler_path={cfg.poppler_path}")
except Exception as e:
    print(f"  [FAIL] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. 提取全页图像
print("\n[3/5] 提取全页图像...")
try:
    full_image = extractor.extract_full_page(auth_pdf, page_num=1)
    print(f"  [OK] 图像尺寸: {full_image.size}, 模式: {full_image.mode}")
except Exception as e:
    print(f"  [FAIL] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 裁剪区域
print("\n[4/5] 裁剪区域...")
try:
    from core.region_extractor import REGIONS
    region_names = ['company_top', 'company_middle']
    regions = [REGIONS[name] for name in region_names if name in REGIONS]
    images = extractor.crop_regions_from_image(full_image, regions)
    print(f"  [OK] 裁剪了 {len(images)} 个区域")
    for i, img in enumerate(images):
        print(f"    区域 {i+1}: {img.size}")
except Exception as e:
    print(f"  [FAIL] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. OCR 识别
print("\n[5/5] OCR 识别...")
try:
        # 使用 UltraFastOCR 实例
    ufo = UltraFastOCR({}, skip_warmup=True)
    
    for i, img in enumerate(images):
        print(f"  识别区域 {i+1}...")
        texts = ufo._run_ocr(engine, img, fallback_path=None, use_lock=False)
        print(f"    [OK] 识别到 {len(texts)} 行文本")
        for j, text in enumerate(texts[:3]):
            print(f"      行{j+1}: {text[:80]}...")
        if len(texts) > 3:
            print(f"      ... 共 {len(texts)} 行")
    
    print("\n[OK] 全部测试通过！单步 OCR 正常")
except Exception as e:
    print(f"  [FAIL] {e}")
    import traceback
    traceback.print_exc()
    print("\n[DIAGNOSIS] OCR 执行失败，这是根本原因")
    sys.exit(1)
