from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import detect_single_page_case_ranges_from_ocr


def test_detect_single_page_case_ranges_from_ocr_should_find_three_case_pages_for_letters():
    auth_ranges = detect_single_page_case_ranges_from_ocr(ROOT / 'output' / '授权书_ultra_result.json', '授权委托书')
    letter_ranges = detect_single_page_case_ranges_from_ocr(ROOT / 'output' / '所函_ultra_result.json', '广东岭南律师事务所函')

    assert auth_ranges == [(0, 1), (1, 2), (2, 3)]
    assert letter_ranges == [(0, 1), (1, 2), (2, 3)]
