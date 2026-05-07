from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from project_evaluation import run_project_evaluation


def test_project_evaluation_should_return_runtime_quality_and_code_quality():
    report = run_project_evaluation(ROOT)

    assert 'notice' in report
    assert 'ruling' in report
    assert 'code_quality' in report
    assert 'runtime_seconds' in report['notice']
    assert 'quality' in report['notice']
    assert 'runtime_seconds' in report['ruling']
