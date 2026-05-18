from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[4] / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.paths import ROOT

from non_litigation.export import discover_notice_files, get_notice_input_dirs
from non_litigation.evaluation import evaluate_non_litigation_quality


def test_get_notice_input_dirs_should_include_nested_batch2_notice_dir():
    input_dir = ROOT / '样本材料' / '非诉组自动化样本材料（第2批）' / '原始文件'
    dirs = get_notice_input_dirs(input_dir)
    assert input_dir in dirs
    assert input_dir / '责催（证据材料）' in dirs


def test_discover_notice_files_should_find_nested_batch2_notice_pdfs():
    input_dir = ROOT / '样本材料' / '非诉组自动化样本材料（第2批）' / '原始文件'
    files = discover_notice_files(input_dir)
    assert files == ['1.pdf', '2.pdf', '3.pdf', '4.pdf', '5.pdf']


def test_evaluate_non_litigation_quality_should_accept_custom_sample_root(tmp_path: Path):
    sample_root = ROOT / '样本材料' / '非诉组自动化样本材料（第2批）'
    standard_root = sample_root / '对应输出文件（标准版）'
    for folder in standard_root.iterdir():
        if folder.is_dir():
            target_dir = tmp_path / folder.name
            target_dir.mkdir(parents=True, exist_ok=True)
            for pdf in folder.glob('*.pdf'):
                target_path = target_dir / pdf.name
                target_path.write_bytes(pdf.read_bytes())

    report = evaluate_non_litigation_quality(ROOT, tmp_path, sample_root=sample_root)
    assert report['total_files'] == 20
    assert report['page_count_matched'] >= 19
    assert report['page_count_match_rate'] >= 0.95
