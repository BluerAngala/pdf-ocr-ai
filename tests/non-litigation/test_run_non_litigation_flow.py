from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_non_litigation_flow import build_run_summary, format_summary


def test_run_non_litigation_flow_should_build_summary_with_expected_paths_and_outputs():
    summary = build_run_summary(ROOT)
    text = format_summary(summary)

    assert summary['input_root'] == str(ROOT / 'input' / 'non-litigation')
    assert summary['result_root'] == str(ROOT / 'output' / 'non-litigation-results')
    assert summary['ocr_cache_dir'] == str(ROOT / 'temp' / 'non-litigation' / 'ocr-cache')
    assert summary['created_count'] == 12
    assert summary['quality']['page_count_matched'] == 12
    assert summary['quality']['total_files'] == 12
    assert '非诉输入目录:' in text
    assert '非诉输出目录:' in text
    assert '页数匹配: 12/12' in text
    assert '输出文件（申请书）' in summary['output_folders']
    assert len(summary['output_folders']['输出文件（责催）']) == 3
