from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import build_mock_ocr_cache, detect_application_page_ranges_from_ocr, get_non_litigation_ocr_cache_dir


def test_detect_application_page_ranges_from_ocr_should_group_three_cases_from_six_pages():
    ocr_cache_dir = build_mock_ocr_cache(
        ROOT / '样本材料' / '非诉组自动化样本材料',
        get_non_litigation_ocr_cache_dir(ROOT),
    )
    ranges = detect_application_page_ranges_from_ocr(ocr_cache_dir / '申请书_ultra_result.json')
    assert ranges == [(0, 2), (2, 4), (4, 6)]
