from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from text_postprocessor import TextPostProcessor
from rename_rules import RenameService, build_notice_rename_plan


def test_build_notice_rename_plan_for_real_files_preview_mode():
    processor = TextPostProcessor()
    service = RenameService(processor)
    ledger_map = {
        '穗公积金中心黄埔责字〔2025〕594号': '1',
    }
    samples = [
        {
            'filename': '原始责催.pdf',
            'ocr_text': (ROOT / 'output' / '1-责催-穗公积金中心黄埔责字（2025）594号_ultra_result.txt').read_text(encoding='utf-8'),
        }
    ]

    plan = build_notice_rename_plan(samples=samples, ledger_map=ledger_map, service=service)

    assert plan['total'] == 1
    assert plan['matched'] == 1
    assert plan['unmatched'] == 0
    assert plan['items'][0]['new_filename'] == '1-责催-穗公积金中心黄埔责字〔2025〕594号.pdf'
