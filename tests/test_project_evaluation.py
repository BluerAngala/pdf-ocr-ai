from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project_evaluation import run_project_evaluation


def test_project_evaluation_should_return_runtime_quality_and_code_quality():
    report = run_project_evaluation(ROOT)

    assert 'non_litigation' in report
    assert 'ocr_speed' in report
    assert 'code_quality' in report
    assert 'runtime_seconds' in report['non_litigation']
    assert 'quality' in report['non_litigation']
    assert 'items' in report['ocr_speed']
