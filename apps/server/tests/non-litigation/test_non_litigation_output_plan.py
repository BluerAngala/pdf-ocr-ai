from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[4] / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.paths import ROOT

from non_litigation.output_plan import build_expected_output_tree


def test_build_expected_output_tree_should_match_standard_directory_structure():
    tree = build_expected_output_tree(
        sample_root=ROOT / '样本材料' / '非诉组自动化样本材料'
    )

    assert set(tree.keys()) == {'输出文件（责催）', '输出文件（申请书）', '输出文件（授权书）', '输出文件（所函）'}
    for folder_name, names in tree.items():
        assert len(names) > 0
    assert len(tree['输出文件（申请书）']) == len(tree['输出文件（责催）'])
    assert len(tree['输出文件（授权书）']) == len(tree['输出文件（责催）'])
    assert len(tree['输出文件（所函）']) == len(tree['输出文件（责催）'])
    assert '7-责催-穗公积金中心越秀责字（2024）914-1号.pdf' in tree['输出文件（责催）']
