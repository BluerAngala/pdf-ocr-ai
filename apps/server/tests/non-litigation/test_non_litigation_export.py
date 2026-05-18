from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[4] / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.paths import ROOT

from non_litigation.export import (
    build_mock_ocr_results,
    ensure_non_litigation_input_structure,
    export_company_named_files,
    export_non_litigation_standard_outputs,
    get_non_litigation_input_root,
    inspect_pdf_page_count,
)


def test_export_non_litigation_standard_outputs_should_match_standard_page_counts(tmp_path: Path):
    input_dir = ensure_non_litigation_input_structure(ROOT)
    ocr_results = build_mock_ocr_results(
        ROOT / '样本材料' / '非诉组自动化样本材料',
        input_dir=input_dir,
    )
    result = export_non_litigation_standard_outputs(
        sample_root=ROOT / '样本材料' / '非诉组自动化样本材料',
        input_dir=input_dir,
        output_root=tmp_path,
        ocr_results=ocr_results,
    )

    standard_root = ROOT / '样本材料' / '非诉组自动化样本材料' / '对应输出文件（标准版）'

    assert result['created_count'] > 0
    assert input_dir == get_non_litigation_input_root(ROOT)

    pairs = []
    for folder in ['输出文件（责催）', '输出文件（申请书）', '输出文件（授权书）', '输出文件（所函）']:
        for pdf_name in (standard_root / folder).glob('*.pdf'):
            actual = tmp_path / folder / pdf_name.name
            if actual.exists():
                pairs.append((actual, pdf_name))

    for actual, expected in pairs:
        assert inspect_pdf_page_count(actual) == inspect_pdf_page_count(expected)


def test_export_company_named_files_should_skip_when_source_pdf_missing(tmp_path: Path):
    result = export_company_named_files(
        input_dir=tmp_path,
        output_dir=tmp_path / 'out',
        target_names=['a.pdf'],
        ocr_results={},
        source_name=None,
        marker='授权委托书',
    )

    assert result == 0
