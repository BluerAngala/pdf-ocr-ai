from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import (
    build_mock_ocr_cache,
    ensure_non_litigation_input_structure,
    export_non_litigation_standard_outputs,
    get_non_litigation_input_root,
    get_non_litigation_ocr_cache_dir,
    inspect_pdf_page_count,
)


def test_export_non_litigation_standard_outputs_should_match_standard_page_counts(tmp_path: Path):
    input_dir = ensure_non_litigation_input_structure(ROOT)
    result = export_non_litigation_standard_outputs(
        sample_root=ROOT / '样本材料' / '非诉组自动化样本材料',
        input_dir=input_dir,
        output_root=tmp_path,
        ocr_cache_dir=build_mock_ocr_cache(
            ROOT / '样本材料' / '非诉组自动化样本材料',
            get_non_litigation_ocr_cache_dir(ROOT),
        ),
    )

    standard_root = ROOT / '样本材料' / '非诉组自动化样本材料' / '对应输出文件（标准版）'

    pairs = [
        (
            tmp_path / '输出文件（申请书）' / '7-申请书pdf-穗公积金中心越秀责字（2024）914-1号.pdf',
            standard_root / '输出文件（申请书）' / '7-申请书pdf-穗公积金中心越秀责字（2024）914-1号.pdf',
        ),
        (
            tmp_path / '输出文件（申请书）' / '8-申请书pdf-穗公积金中心越秀责字（2025）856号.pdf',
            standard_root / '输出文件（申请书）' / '8-申请书pdf-穗公积金中心越秀责字（2025）856号.pdf',
        ),
        (
            tmp_path / '输出文件（申请书）' / '9-申请书pdf-穗公积金中心越秀责字（2025）1107号.pdf',
            standard_root / '输出文件（申请书）' / '9-申请书pdf-穗公积金中心越秀责字（2025）1107号.pdf',
        ),
        (
            tmp_path / '输出文件（责催）' / '7-责催-穗公积金中心越秀责字（2024）914-1号.pdf',
            standard_root / '输出文件（责催）' / '7-责催-穗公积金中心越秀责字（2024）914-1号.pdf',
        ),
        (
            tmp_path / '输出文件（责催）' / '8-责催-穗公积金中心越秀责字（2025）856号.pdf',
            standard_root / '输出文件（责催）' / '8-责催-穗公积金中心越秀责字（2025）856号.pdf',
        ),
        (
            tmp_path / '输出文件（责催）' / '9-责催-穗公积金中心越秀责字（2025）1107号.pdf',
            standard_root / '输出文件（责催）' / '9-责催-穗公积金中心越秀责字（2025）1107号.pdf',
        ),
    ]

    assert result['created_count'] == 12
    assert Path(result['ocr_cache_dir']).samefile(get_non_litigation_ocr_cache_dir(ROOT))
    assert input_dir == get_non_litigation_input_root(ROOT)
    for actual, expected in pairs:
        assert inspect_pdf_page_count(actual) == inspect_pdf_page_count(expected)
