import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'src')
from non_litigation_export import NOTICE_PATTERN, apply_ocr_corrections
from pdf_ocr_ultra import UltraFastOCR, OCRConfig
from pathlib import Path

notice_dir = Path('样本材料/非诉组自动化样本材料/原始文件/责催（证据材料）')
notice_files = sorted(notice_dir.glob('*.pdf'))

config = OCRConfig()
ocr = UltraFastOCR(config)

total_start = time.time()

for pdf_path in notice_files:
    print(f'\n{"="*60}')
    print(f'Processing {pdf_path.name}...')
    start = time.time()
    
    def make_stop_condition():
        def stop_condition(page_num, text):
            corrected = apply_ocr_corrections(text)
            matches = NOTICE_PATTERN.findall(corrected)
            if matches:
                print(f'  STOP at page {page_num}! Found: {matches}')
                return True
            return False
        return stop_condition
    
    result = ocr.process_pdf_pages_sequential(str(pdf_path), stop_condition=make_stop_condition())
    elapsed = time.time() - start
    
    print(f'Time: {elapsed:.1f}s | Pages: {len(result["pages"])} | Stopped: {result.get("stopped_early", False)}')
    if result['pages']:
        p1_text = result['pages'][0].get('text', '')
        matches = NOTICE_PATTERN.findall(apply_ocr_corrections(p1_text))
        print(f'Notice: {matches[:3]}')

total_elapsed = time.time() - total_start
print(f'\nTotal: {total_elapsed:.1f}s for {len(notice_files)} files')
