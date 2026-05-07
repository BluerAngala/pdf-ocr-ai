from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from text_postprocessor import TextPostProcessor
from rename_rules import RenameService
from notice_rename_workflow import build_notice_plan_from_paths


def test_build_notice_plan_from_real_paths_uses_output_text_and_ledger():
    processor = TextPostProcessor()
    service = RenameService(processor)

    ledger_map = {
        '穗公积金中心黄埔责字〔2025〕594号': '1',
    }

    input_dir = ROOT / 'input'
    output_dir = ROOT / 'output'

    plan = build_notice_plan_from_paths(
        input_dir=input_dir,
        output_dir=output_dir,
        ledger_map=ledger_map,
        service=service,
    )

    matched_items = [item for item in plan['items'] if item['matched']]

    assert plan['total'] >= 1
    assert len(matched_items) >= 1
    assert any(item['new_filename'] == '1-责催-穗公积金中心黄埔责字〔2025〕594号.pdf' for item in matched_items)
