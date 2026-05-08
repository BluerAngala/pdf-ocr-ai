from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import build_mock_ocr_cache, ensure_non_litigation_input_structure, get_non_litigation_input_root, get_non_litigation_ocr_cache_dir, get_non_litigation_result_root
from project_evaluation import run_project_evaluation


def test_project_evaluation_should_return_runtime_quality_and_code_quality():
    input_dir = ensure_non_litigation_input_structure(ROOT)
    build_mock_ocr_cache(
        ROOT / '样本材料' / '非诉组自动化样本材料',
        get_non_litigation_ocr_cache_dir(ROOT),
        input_dir=input_dir,
    )
    report = run_project_evaluation(ROOT)

    assert 'non_litigation' in report
    assert 'ocr_speed' in report
    assert 'code_quality' in report
    assert 'runtime_seconds' in report['non_litigation']
    assert 'quality' in report['non_litigation']
    assert 'items' in report['ocr_speed']
    assert report['non_litigation']['input_root'] == str(get_non_litigation_input_root(ROOT))
    assert report['non_litigation']['result_root'] == str(get_non_litigation_result_root(ROOT))
    assert report['non_litigation']['ocr_cache_dir'] == str(get_non_litigation_ocr_cache_dir(ROOT))
