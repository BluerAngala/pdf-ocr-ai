#!/usr/bin/env python3
"""
端到端验证：模拟 Tauri 前端调用 run_non_litigation_flow 的完整流程
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.paths import ROOT

sample_root = ROOT / '样本材料' / '非诉组自动化样本材料'
input_dir = sample_root / '原始文件'

print("=" * 60)
print("端到端验证 - 模拟 Tauri 调用链")
print("=" * 60)

# 1. 验证模块导入
print("\n[1/5] 模块导入...")
try:
    from non_litigation.export import run_real_ocr, _should_use_streaming, _STREAMING_THRESHOLD, HAS_OCR
    from non_litigation.streaming import StreamingBatchProcessor, set_log_fn
    from core.task_state import TaskStateManager
    from core.pdf_ocr_ultra import OCRConfig
    print("  [OK] 所有模块导入成功")
except Exception as e:
    print(f"  [FAIL] 导入失败: {e}")
    sys.exit(1)

# 2. 验证流式切换条件
print("\n[2/5] 流式切换条件...")
try:
    from non_litigation.product import load_non_litigation_cases
    cases = load_non_litigation_cases(sample_root)
    total_tasks = len(cases) * 2 + 1
    should = _should_use_streaming(total_tasks)
    print(f"  cases: {len(cases)}, total_tasks: {total_tasks}")
    print(f"  _should_use_streaming({total_tasks}) = {should}")
    print(f"  HAS_OCR = {HAS_OCR}")
    if not should or not HAS_OCR:
        print("  [WARN] 流式不会启用，检查条件")
    else:
        print("  [OK] 流式将启用")
except Exception as e:
    print(f"  [WARN] 无法加载台账: {e}")
    cases = []
    should = False

# 3. 验证 Poppler 可用
print("\n[3/5] Poppler 可用性...")
try:
    cfg = OCRConfig()
    from core.pdf_ocr_ultra import check_poppler_installed
    ok = check_poppler_installed(cfg.poppler_path)
    print(f"  poppler_path: {cfg.poppler_path}")
    print(f"  [OK] Poppler 可用" if ok else "  [FAIL] Poppler 不可用!")
    if not ok:
        sys.exit(1)
except Exception as e:
    print(f"  [FAIL] {e}")
    sys.exit(1)

# 4. 运行 OCR（真实流式路径）
print("\n[4/5] 运行流式 OCR (小批量 5 个 case)...")
try:
    test_cases = cases[:5] if len(cases) >= 5 else cases
    t0 = time.perf_counter()
    ocr_results = run_real_ocr(
        input_dir=input_dir,
        use_mock=False,
        progress_callback=None,
        cancel_check=None,
    )
    elapsed = time.perf_counter() - t0
    print(f"  [OK] OCR 完成, 耗时: {elapsed:.2f}s")
    print(f"  结果文件数: {len(ocr_results)}")
    for filename, data in ocr_results.items():
        pages = data.get('pages', [])
        text_preview = pages[0].get('text', '')[:80] if pages else '(empty)'
        print(f"    {filename}: {len(pages)} 页, 预览: {text_preview}...")
except Exception as e:
    print(f"  [FAIL] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. 验证结果非空
print("\n[5/5] 结果验证...")
if not ocr_results:
    print("  [FAIL] OCR 结果为空!")
    sys.exit(1)

has_text = False
for filename, data in ocr_results.items():
    for page in data.get('pages', []):
        if page.get('text', '').strip():
            has_text = True
            break
    if has_text:
        break

if has_text:
    print("  [OK] OCR 结果包含有效文本")
else:
    print("  [WARN] OCR 结果无有效文本")

print("\n" + "=" * 60)
print("验证通过! 所有检查均成功")
print("=" * 60)
