import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'src')
from non_litigation_export import NOTICE_PATTERN, apply_ocr_corrections
from pdf_ocr_ultra import UltraFastOCR, OCRConfig
from pathlib import Path

pdf_path = Path('样本材料/非诉组自动化样本材料/原始文件/责催（证据材料）/2.pdf')
print(f'Testing {pdf_path.name}...')

config = OCRConfig()
print('Initializing OCR...')
ocr = UltraFastOCR(config)
print('OCR ready')

start = time.time()

def stop_condition(page_num, text):
    corrected = apply_ocr_corrections(text)
    matches = NOTICE_PATTERN.findall(corrected)
    if matches:
        print(f'  STOP at page {page_num}! Found: {matches}')
        return True
    return False

result = ocr.process_pdf_pages_sequential(str(pdf_path), stop_condition=stop_condition)
elapsed = time.time() - start

print(f'Time: {elapsed:.1f}s')
print(f'Pages: {len(result["pages"])}')
print(f'Stopped early: {result.get("stopped_early", False)}')
if result['pages']:
    p1_text = result['pages'][0].get('text', '')
    matches = NOTICE_PATTERN.findall(apply_ocr_corrections(p1_text))
    print(f'Page 1 notice: {matches[:3]}')
