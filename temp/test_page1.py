import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'src')
from pdf_ocr_ultra import UltraFastOCR, OCRConfig
from pathlib import Path

pdf_path = Path('样本材料/非诉组自动化样本材料/原始文件/责催（证据材料）/2.pdf')
config = OCRConfig()
ocr = UltraFastOCR(config)

# Only process page 1
result = ocr.process_pdf_pages_sequential(str(pdf_path), max_pages=1)
if result and result['pages']:
    text = result['pages'][0].get('text', '')
    print(f'Page 1 text ({len(text)} chars):')
    print(text[:500])
    print()
    # Check for 责
    if '责' in text:
        idx = text.index('责')
        print(f'"责" found at pos {idx}: ...{text[max(0,idx-20):idx+30]}...')
    else:
        print('"责" NOT found in text')
    
    # Check for 穗
    if '穗' in text:
        idx = text.index('穗')
        print(f'"穗" found at pos {idx}: ...{text[max(0,idx-5):idx+40]}...')
    else:
        print('"穗" NOT found in text')
