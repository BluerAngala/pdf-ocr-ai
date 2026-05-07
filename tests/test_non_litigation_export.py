from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import export_non_litigation_standard_outputs, inspect_pdf_page_count


def test_export_non_litigation_standard_outputs_should_split_application_and_notice_into_single_case_files(tmp_path: Path):
    result = export_non_litigation_standard_outputs(
        sample_root=ROOT / '样本材料' / '非诉组自动化样本材料',
        input_dir=ROOT / 'input',
        output_root=tmp_path,
    )

    app_pages = inspect_pdf_page_count(tmp_path / '输出文件（申请书）' / '7-申请书pdf-穗公积金中心越秀责字（2024）914-1号.pdf')
    notice_pages = inspect_pdf_page_count(tmp_path / '输出文件（责催）' / '7-责催-穗公积金中心越秀责字（2024）914-1号.pdf')

    assert result['created_count'] == 12
    assert app_pages < inspect_pdf_page_count(ROOT / 'input' / '申请书.pdf')
    assert notice_pages < inspect_pdf_page_count(ROOT / 'input' / '1.pdf')
