from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import detect_application_page_ranges_from_ocr


def test_detect_application_page_ranges_from_ocr_should_group_three_cases_from_six_pages():
    ranges = detect_application_page_ranges_from_ocr(ROOT / 'output' / '申请书_ultra_result.json')
    assert ranges == [(0, 2), (2, 4), (4, 6)]
