import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from text_postprocessor import TextPostProcessor


def test_extract_case_numbers_filters_noise_prefixes_and_expands_ranges():
    processor = TextPostProcessor()
    text = (
        '准予强制执行穗公积金中心番禺责字〔2024〕595号至596号《责令限期办理决定书》。\n'
        '附：穗公积金中心番禺责字〔2024〕595号至596号清单\n'
        '1 穗公积金中心番禺责字〔2024〕595号 李洪惠\n'
        '2 穗公积金中心番禺责字〔2024〕596号 李玉颜\n'
    )

    result = processor.process(text)
    decision_numbers = result['structured']['decision_numbers']

    assert decision_numbers == [
        '穗公积金中心番禺责字〔2024〕595号',
        '穗公积金中心番禺责字〔2024〕596号',
    ]


def test_extract_ruling_fields_from_judgment_text():
    processor = TextPostProcessor()
    sample_path = ROOT / 'output' / '（2025）粤7101行审3352号_ultra_result.txt'
    text = sample_path.read_text(encoding='utf-8')

    result = processor.process(text)
    ruling = result['structured']['ruling']

    assert ruling['document_type'] == '行政裁定书'
    assert ruling['administrative_case_no'] == '（2025）粤7101行审3352号'
    assert ruling['decision_numbers'] == [
        '穗公积金中心番禺责字〔2024〕595号',
        '穗公积金中心番禺责字〔2024〕596号',
    ]
    assert ruling['judge'] == '向宏'
    assert ruling['clerk'] == '梅文静'
    assert ruling['execution_date'] == '2025年4月28日'


def test_extract_notice_company_name_from_notice_text():
    processor = TextPostProcessor()
    sample_path = ROOT / 'output' / '1-责催-穗公积金中心黄埔责字（2025）594号_ultra_result.txt'
    text = sample_path.read_text(encoding='utf-8')

    result = processor.process(text)
    notice = result['structured']['notice']

    assert notice['document_type'] == '责令限期办理决定书'
    assert notice['company_name'] == '三菱电机（广州）压缩机有限公司'
    assert notice['decision_numbers'] == ['穗公积金中心黄埔责字〔2025〕594号']


def test_extract_contract_company_names_from_contract_text():
    processor = TextPostProcessor()
    sample_path = ROOT / 'output' / '广东省新闻工作者协会法律服务定点采购合同_ultra_result.txt'
    text = sample_path.read_text(encoding='utf-8')

    result = processor.process(text)
    contract = result['structured']['contract']

    assert contract['document_type'] == '合同'
    assert contract['party_a'] == '广东省新闻工作者协会'
    assert contract['party_b'] == '广东岭南律师事务所'
