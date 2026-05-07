from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from text_postprocessor import TextPostProcessor
from rename_rules import RenameService


def test_build_notice_filename_from_real_sample_and_ledger_mapping():
    processor = TextPostProcessor()
    service = RenameService(processor)
    sample_path = ROOT / 'output' / '1-责催-穗公积金中心黄埔责字（2025）594号_ultra_result.txt'
    text = sample_path.read_text(encoding='utf-8')

    ledger_map = {
        '穗公积金中心黄埔责字〔2025〕594号': '1',
    }

    result = service.build_notice_rename_result(
        original_filename='原始责催.pdf',
        ocr_text=text,
        ledger_map=ledger_map,
    )

    assert result['matched'] is True
    assert result['decision_number'] == '穗公积金中心黄埔责字〔2025〕594号'
    assert result['sequence'] == '1'
    assert result['new_filename'] == '1-责催-穗公积金中心黄埔责字〔2025〕594号.pdf'


def test_build_authorization_filename_from_company_name():
    processor = TextPostProcessor()
    service = RenameService(processor)
    ocr_text = '授权委托书\n委托单位：三菱电机（广州）压缩机有限公司\n受托人：张三'

    result = service.build_company_rename_result(
        original_filename='授权书.pdf',
        ocr_text=ocr_text,
    )

    assert result['matched'] is True
    assert result['company_name'] == '三菱电机（广州）压缩机有限公司'
    assert result['new_filename'] == '三菱电机（广州）压缩机有限公司.pdf'
