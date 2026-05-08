import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'src')

from pathlib import Path
from non_litigation_product import load_non_litigation_cases
from non_litigation_export import (
    ensure_non_litigation_input_structure,
    discover_notice_files,
    run_real_ocr_on_pdf,
    detect_notice_source_mapping_from_ocr,
    get_non_litigation_ocr_cache_dir,
    NOTICE_PATTERN,
)
from non_litigation_output_plan import build_expected_output_tree
from non_litigation_validator import validate_ocr_results

ROOT = Path('.')
sample_root = ROOT / '样本材料' / '非诉组自动化样本材料'

total_start = time.time()

# Step 1: Setup input
print('=' * 60)
print('Step 1: Setting up input directory')
input_dir = ensure_non_litigation_input_structure(sample_root)
print(f'Input dir: {input_dir}')

# Step 2: Load cases
print('\n' + '=' * 60)
print('Step 2: Loading cases from ledger')
ledger_path = sample_root / '台账.xlsx'
cases = load_non_litigation_cases(ledger_path)
print(f'Loaded {len(cases)} cases')

# Step 3: OCR on notice files
print('\n' + '=' * 60)
print('Step 3: OCR on notice files')
notice_files = discover_notice_files(input_dir)
ocr_cache_dir = get_non_litigation_ocr_cache_dir(ROOT)
ocr_cache_dir.mkdir(parents=True, exist_ok=True)

notice_times = []
for nf in notice_files:
    pdf_path = input_dir / nf
    start = time.time()
    result = run_real_ocr_on_pdf(pdf_path, ocr_cache_dir, is_notice=True, stop_pattern=NOTICE_PATTERN)
    elapsed = time.time() - start
    notice_times.append(elapsed)
    cached = (ocr_cache_dir / f'{Path(nf).stem}_ultra_result.json').exists()
    print(f'  {nf}: {elapsed:.1f}s (cached={cached})')

# Step 4: OCR on other files
print('\n' + '=' * 60)
print('Step 4: OCR on application/authorization/letter files')
from non_litigation_export import SOURCE_MAPPING

other_files = {k: v for k, v in SOURCE_MAPPING.items() if '责催' not in k}
other_times = []
for label, filename in other_files.items():
    pdf_path = input_dir / filename
    if pdf_path.exists():
        start = time.time()
        result = run_real_ocr_on_pdf(pdf_path, ocr_cache_dir, is_notice=False)
        elapsed = time.time() - start
        other_times.append(elapsed)
        print(f'  {filename} ({label}): {elapsed:.1f}s')

# Step 5: Detect notice mapping
print('\n' + '=' * 60)
print('Step 5: Detecting notice-to-file mapping')
mapping = detect_notice_source_mapping_from_ocr(ocr_cache_dir, notice_files)
print(f'Mapping: {mapping}')

# Step 6: Validate
print('\n' + '=' * 60)
print('Step 6: Validation')
validation = validate_ocr_results(ocr_cache_dir, cases, input_dir=input_dir)
print(f'Result: {validation.get("status", "unknown")}')

total_elapsed = time.time() - total_start
print(f'\n{"="*60}')
print(f'Total time: {total_elapsed:.1f}s')
print(f'Notice files: {sum(notice_times):.1f}s ({notice_times})')
print(f'Other files: {sum(other_times):.1f}s ({other_times})')
