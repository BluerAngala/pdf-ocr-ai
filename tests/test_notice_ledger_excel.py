from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notice_rename_workflow import load_ledger_map_from_excel


def test_load_ledger_map_from_real_excel_should_contain_expected_notice_number():
    excel_path = ROOT / '样本材料' / '非诉组自动化样本材料' / '台账及命名规则.xlsx'

    ledger_map = load_ledger_map_from_excel(excel_path)

    assert '穗公积金中心越秀责字〔2024〕914-1号' in ledger_map
    assert ledger_map['穗公积金中心越秀责字〔2024〕914-1号'] == '7'
    assert '穗公积金中心越秀责字〔2025〕856号' in ledger_map
    assert ledger_map['穗公积金中心越秀责字〔2025〕856号'] == '8'
