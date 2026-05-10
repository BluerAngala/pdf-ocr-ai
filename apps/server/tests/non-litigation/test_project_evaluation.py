from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import build_mock_ocr_cache, ensure_non_litigation_input_structure, get_non_litigation_input_root, get_non_litigation_ocr_cache_dir, get_non_litigation_result_root
from project_evaluation import build_test_health, run_project_evaluation


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
    assert 'ocr_accuracy' in report
    assert 'optimization_guardrails' in report
    assert 'runtime_seconds' in report['non_litigation']
    assert 'quality' in report['non_litigation']
    assert 'items' in report['ocr_speed']
    assert 'fallback_pages_total' in report['ocr_speed']
    assert 'fallback_pages_total' in report['optimization_guardrails']
    assert report['non_litigation']['input_root'] == str(get_non_litigation_input_root(ROOT))
    assert report['non_litigation']['result_root'] == str(get_non_litigation_result_root(ROOT))
    assert report['non_litigation']['ocr_cache_dir'] == str(get_non_litigation_ocr_cache_dir(ROOT))


def test_build_test_health_should_exclude_retired_tests_and_include_current_regressions():
    health = build_test_health()

    assert 'tests/non-litigation/test_run_non_litigation_flow.py' in health['active_regression_suite']
    assert 'tests/non-litigation/test_batch2_input_structure.py' in health['active_regression_suite']
    assert 'tests/non-litigation/test_non_litigation_validator.py' in health['active_regression_suite']
    assert 'tests/non-litigation/test_ocr_optimization_behaviors.py' in health['active_regression_suite']
    assert 'tests/non-litigation/test_project_evaluation.py' in health['active_regression_suite']

    assert 'tests/non-litigation/test_non_litigation_suite_directory.py' not in health['active_regression_suite']
    assert 'tests/non-litigation/test_non_litigation_full_compare.py' not in health['active_regression_suite']
    assert 'scripts/test_smart_extraction.py' not in health['active_regression_suite']

    assert 'tests/non-litigation/test_non_litigation_suite_directory.py' in health['retired_tests']
    assert 'tests/non-litigation/test_non_litigation_full_compare.py' in health['retired_tests']
    assert 'scripts/test_smart_extraction.py' in health['retired_tests']
