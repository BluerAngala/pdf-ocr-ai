from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import detect_page_ranges


def test_detect_page_ranges_should_group_three_cases_from_six_pages():
    ranges = detect_page_ranges(6, 3, '申请书')
    assert ranges == [(0, 2), (2, 4), (4, 6)]
