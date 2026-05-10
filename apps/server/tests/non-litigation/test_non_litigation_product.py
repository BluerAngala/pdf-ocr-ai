from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_product import build_non_litigation_standard_plan


def test_non_litigation_standard_plan_should_match_expected_outputs_per_document_type():
    plan = build_non_litigation_standard_plan(
        sample_root=ROOT / '样本材料' / '非诉组自动化样本材料'
    )

    assert set(plan.keys()) == {'责催', '申请书', '授权书', '所函'}
    assert len(plan['责催']) > 0
    assert len(plan['申请书']) == len(plan['责催'])
    assert len(plan['授权书']) == len(plan['责催'])
    assert len(plan['所函']) == len(plan['责催'])
    assert plan['责催'][0]['target_filename'] == '7-责催-穗公积金中心越秀责字（2024）914-1号.pdf'
    assert plan['申请书'][1]['target_filename'] == '8-申请书pdf-穗公积金中心越秀责字（2025）856号.pdf'
