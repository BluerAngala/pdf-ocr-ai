from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from text_postprocessor import TextPostProcessor
from rename_rules import RenameService
from notice_rename_workflow import build_notice_plan_from_paths, load_ledger_map_from_excel, summarize_plan


def test_notice_workflow_summary_should_include_unmatched_items():
    processor = TextPostProcessor()
    service = RenameService(processor)
    ledger_map = load_ledger_map_from_excel(ROOT / '样本材料' / '非诉组自动化样本材料' / '台账及命名规则.xlsx')

    plan = build_notice_plan_from_paths(
        input_dir=ROOT / 'input',
        output_dir=ROOT / 'output',
        ledger_map=ledger_map,
        service=service,
    )
    summary = summarize_plan(plan)

    assert 'matched_items' in summary
    assert 'unmatched_items' in summary
    assert summary['total'] == summary['matched'] + summary['unmatched']
