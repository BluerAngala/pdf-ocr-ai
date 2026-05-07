from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from text_postprocessor import TextPostProcessor


def test_real_notice_sample_keeps_primary_decision_number_and_company_name_stable():
    processor = TextPostProcessor()
    sample_path = ROOT / 'output' / '1-责催-穗公积金中心黄埔责字（2025）594号_ultra_result.txt'
    text = sample_path.read_text(encoding='utf-8')

    result = processor.process(text)
    structured = result['structured']

    assert structured['notice']['document_type'] == '责令限期办理决定书'
    assert structured['notice']['company_name'] == '三菱电机（广州）压缩机有限公司'
    assert structured['notice']['decision_numbers'] == ['穗公积金中心黄埔责字〔2025〕594号']
    assert '穗公积金中心黄埔催字〔2025〕667号' not in structured['notice']['decision_numbers']


def test_real_ruling_sample_expands_range_without_noise_prefixes():
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


def test_processed_text_should_not_overwrite_original_notice_signal():
    processor = TextPostProcessor()
    original_text = '名称：三菱电机（广州）压缩机有限公司\n穗公积金中心黄埔责字〔2025〕594号'

    result = processor.process(original_text)

    assert '三菱电机（广州）压缩机有限公司' in result['processed']
    assert '穗公积金中心黄埔责字〔2025〕594号' in result['processed']


def test_processed_text_should_not_overwrite_original_ruling_signal():
    processor = TextPostProcessor()
    original_text = '行 政 裁 定 书\n（2025）粤7101行审3352号\n审 判 员 向 宏'

    result = processor.process(original_text)

    assert '行政裁定书' in result['processed']
    assert '（2025）粤7101行审3352号' in result['processed']
    assert '审判员向宏' in result['processed']
