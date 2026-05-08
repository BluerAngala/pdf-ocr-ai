from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import detect_application_page_ranges_fixed


def test_detect_application_page_ranges_fixed_should_group_three_cases_from_six_pages():
    ranges = detect_application_page_ranges_fixed(6, 3)
    assert ranges == [(0, 2), (2, 4), (4, 6)]
