from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from text_postprocessor import TextPostProcessor
from ruling_match_workflow import normalize_ruling_decision_number


def test_notice_should_keep_dash_suffix_in_decision_number():
    processor = TextPostProcessor()
    text = (ROOT / 'output' / '7-责催-穗公积金中心越秀责字（2024）914-1号_ultra_result.txt').read_text(encoding='utf-8')

    result = processor.process(text)
    notice = result['structured']['notice']

    assert notice['decision_numbers'][0] == '穗公积金中心越秀责字〔2024〕914-1号'


def test_ruling_decision_number_should_match_excel_style_without_center_prefix():
    value = normalize_ruling_decision_number('穗公积金中心萝岗责字〔2023〕3360号')
    assert value == '萝岗责字〔2023〕3360号'
