from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[4] / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.paths import ROOT

from non_litigation.export import normalize_company_name_for_matching


def test_normalize_company_name_for_matching_should_remove_spaces_and_keep_core_name():
    assert normalize_company_name_for_matching('北京华图宏阳教育文\n化发展股份有限公司广东分公司') == '北京华图宏阳教育文化发展股份有限公司广东分公司'
    assert normalize_company_name_for_matching('广州 吾能学 网络科技 有限公司') == '广州吾能学网络科技有限公司'
