from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import normalize_company_name_for_matching


def test_normalize_company_name_for_matching_should_remove_spaces_and_keep_core_name():
    assert normalize_company_name_for_matching('北京华图宏阳教育文\n化发展股份有限公司广东分公司') == '北京华图宏阳教育文化发展股份有限公司广东分公司'
    assert normalize_company_name_for_matching('广州 吾能学 网络科技 有限公司') == '广州吾能学网络科技有限公司'
