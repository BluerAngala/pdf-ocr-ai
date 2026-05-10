from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / 'apps' / 'server' / 'src'
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
            input_dir=input_dir,
        ),
    )

    standard_root = ROOT / '样本材料' / '非诉组自动化样本材料' / '对应输出文件（标准版）'

    assert result['created_count'] > 0
    assert Path(result['ocr_cache_dir']).samefile(get_non_litigation_ocr_cache_dir(ROOT))
    assert input_dir == get_non_litigation_input_root(ROOT)

    pairs = []
    for folder in ['输出文件（责催）', '输出文件（申请书）', '输出文件（授权书）', '输出文件（所函）']:
        for pdf_name in (standard_root / folder).glob('*.pdf'):
            actual = tmp_path / folder / pdf_name.name
            if actual.exists():
                pairs.append((actual, pdf_name))

    for actual, expected in pairs:
        assert inspect_pdf_page_count(actual) == inspect_pdf_page_count(expected)
