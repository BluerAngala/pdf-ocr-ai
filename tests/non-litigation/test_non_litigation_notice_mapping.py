from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import build_mock_ocr_cache, detect_notice_source_mapping_from_ocr, discover_notice_files, ensure_non_litigation_input_structure, get_non_litigation_ocr_cache_dir


def test_detect_notice_source_mapping_from_ocr_should_map_three_notice_pdfs_to_three_notice_numbers():
    input_dir = ensure_non_litigation_input_structure(ROOT)
    ocr_cache_dir = build_mock_ocr_cache(
        ROOT / '样本材料' / '非诉组自动化样本材料',
        get_non_litigation_ocr_cache_dir(ROOT),
        input_dir=input_dir,
    )
    notice_files = discover_notice_files(input_dir)
    mapping = detect_notice_source_mapping_from_ocr(ocr_cache_dir, notice_files)
    assert len(mapping) == 3
    for source_name, notice in mapping.items():
        assert '责字' in notice
