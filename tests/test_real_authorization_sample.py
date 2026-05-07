from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from text_postprocessor import TextPostProcessor


def test_real_authorization_sample_should_extract_multiple_company_candidates():
    processor = TextPostProcessor()
    text = (ROOT / 'output' / '授权书_ultra_result.txt').read_text(encoding='utf-8')

    result = processor.process(text)
    notice = result['structured']['notice']

    assert notice['document_type'] == '授权委托书'
    assert notice['company_name_candidates'] == [
        '北京华图宏阳教育文化发展股份有限公司广东分公司',
        '广州市严静殡葬服务有限公司',
        '广州吾能学网络科技有限公司',
    ]
