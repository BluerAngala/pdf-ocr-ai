from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from text_postprocessor import TextPostProcessor


def test_ruling_sample_should_extract_core_fields_for_module_two():
    processor = TextPostProcessor()
    text = (ROOT / 'output' / '（2025）粤7101行审3352号_ultra_result.txt').read_text(encoding='utf-8')

    result = processor.process(text)
    ruling = result['structured']['ruling']

    assert ruling['administrative_case_no'] == '（2025）粤7101行审3352号'
    assert ruling['decision_numbers'] == [
        '穗公积金中心番禺责字〔2024〕595号',
        '穗公积金中心番禺责字〔2024〕596号',
    ]
    assert ruling['judge'] == '向宏'
    assert ruling['execution_date'] == '2025年4月28日'
