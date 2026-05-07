from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from text_postprocessor import TextPostProcessor
from rename_rules import RenameService
from notice_rename_workflow import build_notice_plan_from_paths, summarize_plan


def test_notice_cli_style_workflow_should_report_summary_and_items():
    processor = TextPostProcessor()
    service = RenameService(processor)
    ledger_map = {
        '穗公积金中心黄埔责字〔2025〕594号': '1',
    }

    plan = build_notice_plan_from_paths(
        input_dir=ROOT / 'input',
        output_dir=ROOT / 'output',
        ledger_map=ledger_map,
        service=service,
    )
    summary = summarize_plan(plan)

    assert summary['total'] >= 1
    assert summary['matched'] >= 1
    assert summary['unmatched'] >= 0
    assert any(item['new_filename'] == '1-责催-穗公积金中心黄埔责字〔2025〕594号.pdf' for item in summary['matched_items'])
