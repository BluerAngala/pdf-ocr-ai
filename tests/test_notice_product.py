from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notice_product import build_notice_product_payload


def test_notice_product_should_build_preview_payload_from_real_excel_and_dirs():
    payload = build_notice_product_payload(
        ledger_excel_path=ROOT / '样本材料' / '非诉组自动化样本材料' / '台账及命名规则.xlsx',
        input_dir=ROOT / 'input',
        output_dir=ROOT / 'output',
    )

    assert 'summary' in payload
    assert 'items' in payload
    assert payload['summary']['total'] >= 1
