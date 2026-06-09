"""
覆盖 product.py 支持多命名前缀的修复（5月台账混存责催+授权书场景）。

历史背景：
  5月台账及命名规则.xlsx 把 5月责催（1-责催-...）和 5月授权书（1-授权书-...）
  两批数据塞到同一张 Sheet。旧逻辑只认 "责催-" 前缀，导致授权书批次被过滤，
  OCR 识别到的"天河 1684"在 ledger 里查不到，触发"未匹配台账_需人工核查"。
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[4] / 'apps' / 'server' / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from openpyxl import Workbook

from non_litigation.product import (
    _extract_sequence_from_renamed,
    _matches_any_keyword,
    build_non_litigation_standard_plan,
    load_non_litigation_cases,
)


def test_extract_sequence_should_handle_zechui_prefix():
    assert _extract_sequence_from_renamed('1-责催-穗公积金中心天河责字〔2025〕1684号') == '1'
    assert _extract_sequence_from_renamed('368-责催-穗公积金中心越秀责字〔2025〕1684号') == '368'


def test_extract_sequence_should_handle_shouquanshu_prefix():
    assert _extract_sequence_from_renamed('1-授权书-穗公积金中心天河责字〔2025〕1684号') == '1'
    assert _extract_sequence_from_renamed('35-授权书-穗公积金中心天河责字〔2025〕1851号') == '35'


def test_extract_sequence_should_handle_shenqingshu_pdf_prefix():
    assert _extract_sequence_from_renamed('7-申请书pdf-穗公积金中心越秀责字（2024）914-1号') == '7'


def test_matches_any_keyword_supports_pipe_separated_pattern():
    assert _matches_any_keyword('1-责催-XXX', '责催-|授权书-')
    assert _matches_any_keyword('1-授权书-XXX', '责催-|授权书-')
    assert not _matches_any_keyword('1-XXX', '责催-|授权书-')


def test_load_non_litigation_cases_should_include_authorization_book_batch(tmp_path: Path):
    """模拟 5月台账混存场景：5月责催 + 5月授权书 都在同一张 Sheet。"""
    wb = Workbook()
    ws = wb.active
    # 跳过 7 行 header
    for _ in range(7):
        ws.append([None] * 5)
    # 5月责催批次
    ws.append([None,
               '穗公积金中心越秀责字〔2025〕1684号',
               '368-责催-穗公积金中心越秀责字〔2025〕1684号',
               '368-申请书pdf-穗公积金中心越秀责字〔2025〕1684号',
               '中路铁联保安（广州）有限公司'])
    # 5月授权书批次（关键：用户报告的 1684 在这一行）
    ws.append([None,
               '穗公积金中心天河责字〔2025〕1684号',
               '1-授权书-穗公积金中心天河责字〔2025〕1684号',
               '1-申请书pdf-穗公积金中心天河责字〔2025〕1684号',
               '广州新居网家居科技有限公司'])
    xlsx = tmp_path / 'ledger.xlsx'
    wb.save(xlsx)
    wb.close()

    cases = load_non_litigation_cases(tmp_path, excel_path=xlsx)
    assert len(cases) == 2, f'应加载 2 条（责催 1 + 授权书 1），实际 {len(cases)}'

    notices = {c['notice_number'] for c in cases}
    assert '穗公积金中心越秀责字〔2025〕1684号' in notices
    assert '穗公积金中心天河责字〔2025〕1684号' in notices, \
        '5月授权书批次的天河 1684 必须被加载（这是用户报告的核心 bug）'


def test_build_plan_should_cover_application_for_authorization_book_batch(tmp_path: Path):
    """build_non_litigation_standard_plan 应为授权书批次生成对应的申请书 target。"""
    wb = Workbook()
    ws = wb.active
    for _ in range(7):
        ws.append([None] * 5)
    ws.append([None,
               '穗公积金中心天河责字〔2025〕1684号',
               '1-授权书-穗公积金中心天河责字〔2025〕1684号',
               '1-申请书pdf-穗公积金中心天河责字〔2025〕1684号',
               '广州新居网家居科技有限公司'])
    xlsx = tmp_path / 'ledger.xlsx'
    wb.save(xlsx)
    wb.close()

    plan = build_non_litigation_standard_plan(tmp_path, excel_path=xlsx)
    app_filenames = {item['target_filename'] for item in plan['申请书']}
    assert '1-申请书pdf-穗公积金中心天河责字〔2025〕1684号.pdf' in app_filenames
