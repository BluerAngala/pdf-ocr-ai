from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ruling_product import build_ruling_product_payload


def test_ruling_product_should_build_output_payload_from_real_excel_and_ocr_text():
    payload = build_ruling_product_payload(
        excel_path=ROOT / '样本材料' / '强制组-自动化' / '提取信息' / '非诉表格.xlsx',
        ocr_texts=[(ROOT / 'output' / '（2025）粤7101行审3355号_ultra_result.txt').read_text(encoding='utf-8')],
    )

    assert 'rows' in payload
    assert 'matched_count' in payload
    assert len(payload['rows']) >= 1
