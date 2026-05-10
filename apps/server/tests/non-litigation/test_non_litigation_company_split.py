from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import detect_page_ranges


def test_detect_page_ranges_should_find_three_single_page_ranges_for_letters():
    auth_ranges = detect_page_ranges(3, 3, '授权书')
    letter_ranges = detect_page_ranges(3, 3, '所函')

    assert auth_ranges == [(0, 1), (1, 2), (2, 3)]
    assert letter_ranges == [(0, 1), (1, 2), (2, 3)]
