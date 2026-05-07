from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_output_plan import build_expected_output_tree


def test_build_expected_output_tree_should_match_standard_directory_structure():
    tree = build_expected_output_tree(
        sample_root=ROOT / '样本材料' / '非诉组自动化样本材料'
    )

    assert set(tree.keys()) == {'输出文件（责催）', '输出文件（申请书）', '输出文件（授权书）', '输出文件（所函）'}
    assert len(tree['输出文件（责催）']) == 3
    assert len(tree['输出文件（申请书）']) == 3
    assert len(tree['输出文件（授权书）']) == 3
    assert len(tree['输出文件（所函）']) == 3
    assert '7-责催-穗公积金中心越秀责字（2024）914-1号.pdf' in tree['输出文件（责催）']
    assert '北京华图宏阳教育文化发展股份有限公司广东分公司.pdf' in tree['输出文件（授权书）']
