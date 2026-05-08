from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import detect_notice_source_mapping_from_ocr


def test_detect_notice_source_mapping_from_ocr_should_map_three_notice_pdfs_to_three_notice_numbers():
    mapping = detect_notice_source_mapping_from_ocr(ROOT / 'output')
    assert mapping['1.pdf'] == '穗公积金中心越秀责字〔2024〕914-1号'
    assert mapping['3.pdf'] == '穗公积金中心越秀责字〔2025〕856号'
    assert mapping['2.pdf'] == '穗公积金中心越秀责字〔2025〕1107号'
