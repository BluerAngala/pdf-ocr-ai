from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import export_non_litigation_standard_outputs, inspect_pdf_page_count


def test_non_litigation_exported_outputs_should_match_standard_page_counts_for_all_four_types(tmp_path: Path):
    export_non_litigation_standard_outputs(
        sample_root=ROOT / '样本材料' / '非诉组自动化样本材料',
        input_dir=ROOT / 'input',
        output_root=tmp_path,
    )

    standard_root = ROOT / '样本材料' / '非诉组自动化样本材料' / '对应输出文件（标准版）'
    folders = ['输出文件（责催）', '输出文件（申请书）', '输出文件（授权书）', '输出文件（所函）']

    for folder in folders:
        for expected_file in (standard_root / folder).glob('*.pdf'):
            actual_file = tmp_path / folder / expected_file.name
            assert actual_file.exists(), str(actual_file)
            assert inspect_pdf_page_count(actual_file) == inspect_pdf_page_count(expected_file)
