from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from text_postprocessor import TextPostProcessor
from ruling_match_workflow import match_ruling_rows


def test_match_ruling_rows_should_fill_fields_by_decision_number():
    processor = TextPostProcessor()
    ocr_text = (ROOT / 'output' / '（2025）粤7101行审3355号_ultra_result.txt').read_text(encoding='utf-8')

    excel_rows = [
        {
            '区号': '萝岗',
            '行政审查案号': '',
            '责令号': '萝岗责字（2023）3360号',
            '被执行人': '广州敏惠汽车零部件有限公司',
            '职工姓名': '王新康',
            '金额': '31884',
            '审批员/法官助理': '',
            '执行时间': '',
        },
        {
            '区号': '萝岗',
            '行政审查案号': '',
            '责令号': '萝岗责字（2023）3361号',
            '被执行人': '广州敏惠汽车零部件有限公司',
            '职工姓名': '苑林红',
            '金额': '15926',
            '审批员/法官助理': '',
            '执行时间': '',
        },
    ]

    result = match_ruling_rows(rows=excel_rows, ocr_text=ocr_text, processor=processor)

    assert result['matched_count'] == 2
    assert result['rows'][0]['行政审查案号'] == '（2025）粤7101行审3355号'
    assert result['rows'][0]['审批员/法官助理'] == '向宏'
    assert result['rows'][0]['执行时间'] == '2025年4月28日'
    assert result['rows'][1]['行政审查案号'] == '（2025）粤7101行审3355号'
