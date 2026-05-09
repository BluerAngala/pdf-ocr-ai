from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import json

from non_litigation_export import build_mock_ocr_cache, detect_notice_source_mapping_from_ocr, discover_notice_files, ensure_non_litigation_input_structure, export_notice_files, get_non_litigation_ocr_cache_dir


def test_detect_notice_source_mapping_from_ocr_should_map_three_notice_pdfs_to_three_notice_numbers():
    input_dir = ensure_non_litigation_input_structure(ROOT)
    ocr_cache_dir = build_mock_ocr_cache(
        ROOT / '样本材料' / '非诉组自动化样本材料',
        get_non_litigation_ocr_cache_dir(ROOT),
        input_dir=input_dir,
    )
    notice_files = discover_notice_files(input_dir)
    mapping = detect_notice_source_mapping_from_ocr(ocr_cache_dir, notice_files)
    assert len(mapping) == 3
    for source_name, notice in mapping.items():
        assert '责字' in notice


def test_detect_notice_source_mapping_from_ocr_should_prefer_main_number_over_sub_number(tmp_path):
    cache_dir = tmp_path / 'ocr-cache'
    cache_dir.mkdir()
    (cache_dir / '5_ultra_result.json').write_text(json.dumps({
        'pages': [
            {'page': 1, 'text': '中国邮政速递物流 EMS 穗公积金中心南沙责字〔2025〕1971-2号'},
            {'page': 2, 'text': '穗公积金中心南沙责字〔2025〕1971-1号'},
            {'page': 3, 'text': '责令限期办理决定书\n名称：甲公司\n统一社会信用代码：123\n责令你单位履行以下义务\n穗公积金中心南沙责字〔2025〕1971号'},
        ],
        'total_pages': 3,
        'filename': '5.pdf',
    }, ensure_ascii=False), encoding='utf-8')

    mapping = detect_notice_source_mapping_from_ocr(cache_dir, ['5.pdf'])
    assert mapping['5.pdf'] == '穗公积金中心南沙责字〔2025〕1971号'


def test_detect_notice_source_mapping_from_ocr_should_keep_sub_number_when_only_sub_number_exists(tmp_path):
    cache_dir = tmp_path / 'ocr-cache'
    cache_dir.mkdir()
    (cache_dir / '6_ultra_result.json').write_text(json.dumps({
        'pages': [
            {'page': 1, 'text': '责令限期办理决定书\n名称：甲公司\n穗公积金中心南沙责字〔2025〕1971-2号'},
        ],
        'total_pages': 1,
        'filename': '6.pdf',
    }, ensure_ascii=False), encoding='utf-8')

    mapping = detect_notice_source_mapping_from_ocr(cache_dir, ['6.pdf'])
    assert mapping['6.pdf'] == '穗公积金中心南沙责字〔2025〕1971-2号'


def test_detect_notice_source_mapping_from_ocr_should_downrank_logistics_and_revoke_pages(tmp_path):
    cache_dir = tmp_path / 'ocr-cache'
    cache_dir.mkdir()
    (cache_dir / '7_ultra_result.json').write_text(json.dumps({
        'pages': [
            {'page': 1, 'text': '关于撤销《责令限期办理决定书》的决定\n穗公积金中心南沙责字〔2025〕1175-1号'},
            {'page': 2, 'text': '送达回证\n穗公积金中心南沙责字〔2025〕1175-2号'},
            {'page': 3, 'text': '责令限期办理决定书\n名称：乙公司\n统一社会信用代码：123\n责令你单位履行以下义务\n穗公积金中心南沙责字〔2025〕1175号'},
        ],
        'total_pages': 3,
        'filename': '7.pdf',
    }, ensure_ascii=False), encoding='utf-8')

    mapping = detect_notice_source_mapping_from_ocr(cache_dir, ['7.pdf'])
    assert mapping['7.pdf'] == '穗公积金中心南沙责字〔2025〕1175号'


def test_export_notice_files_should_keep_base_number_without_fuzzy_back_to_subnumber(tmp_path, monkeypatch):
    sample_root = tmp_path / 'sample'
    input_dir = tmp_path / 'input'
    output_dir = tmp_path / 'output'
    cache_dir = tmp_path / 'cache'
    input_dir.mkdir()
    output_dir.mkdir()
    cache_dir.mkdir()

    (input_dir / '5.pdf').write_text('pdf', encoding='utf-8')
    cache_file = cache_dir / '5_ultra_result.json'
    cache_file.write_text(json.dumps({
        'pages': [
            {'page': 1, 'text': '责令限期办理决定书\n名称：甲公司\n统一社会信用代码：123\n责令你单位履行以下义务\n穗公积金中心番禺责字〔2025〕1971号'}
        ],
        'total_pages': 1,
        'filename': '5.pdf',
        'selected_notice': '穗公积金中心番禺责字〔2025〕1971号',
        'selected_page': 1,
        'candidate_notices': [],
    }, ensure_ascii=False), encoding='utf-8')

    monkeypatch.setattr('non_litigation_export.load_non_litigation_cases', lambda _: [
        {'sequence': '918', 'notice_number': '穗公积金中心番禺责字（2025）1971-2号', 'company_name': '甲公司'}
    ])

    copied = []
    monkeypatch.setattr('non_litigation_export.shutil.copy2', lambda src, dst: copied.append((str(src), str(dst))))

    created = export_notice_files(sample_root, input_dir, output_dir, cache_dir)
    assert created == 1
    assert copied
    assert copied[0][1].endswith('918-责催-穗公积金中心番禺责字（2025）1971-2号.pdf')

    updated_cache = json.loads(cache_file.read_text(encoding='utf-8'))
    assert updated_cache['matched_target_notice'] == '穗公积金中心番禺责字〔2025〕1971-2号'
    assert updated_cache['same_root_remap'] is True
