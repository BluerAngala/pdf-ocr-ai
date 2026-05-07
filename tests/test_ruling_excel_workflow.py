from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ruling_excel_workflow import load_non_litigation_rows_from_excel


def test_load_non_litigation_rows_from_real_excel_should_include_required_columns():
    excel_path = ROOT / '样本材料' / '强制组-自动化' / '提取信息' / '非诉表格.xlsx'

    rows = load_non_litigation_rows_from_excel(excel_path)

    assert len(rows) >= 1
    first = rows[0]
    assert '责令号' in first
    assert '被执行人' in first
    assert '职工姓名' in first
