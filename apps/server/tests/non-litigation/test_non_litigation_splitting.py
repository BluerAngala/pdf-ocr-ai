from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[4] / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.paths import ROOT

from non_litigation.export import detect_page_ranges


def test_detect_page_ranges_should_group_three_cases_from_six_pages():
    ranges = detect_page_ranges(6, 3, '申请书')
    assert ranges == [(0, 2), (2, 4), (4, 6)]
