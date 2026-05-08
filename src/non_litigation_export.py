#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

from pypdf import PdfReader, PdfWriter

from non_litigation_output_plan import build_expected_output_tree
from non_litigation_product import load_non_litigation_cases


SOURCE_MAPPING = {
    '输出文件（责催）': ['1.pdf', '2.pdf', '3.pdf'],
    '输出文件（申请书）': '申请书.pdf',
    '输出文件（授权书）': '授权书.pdf',
    '输出文件（所函）': '所函.pdf',
}


def inspect_pdf_page_count(pdf_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    return len(reader.pages)


def normalize_company_name_for_matching(value: str) -> str:
    text = str(value).strip()
    text = text.replace('\n', '').replace('\r', '').replace(' ', '')
    text = text.replace('（', '(').replace('）', ')')
    text = text.replace('股份有限公司广东分公司', '股份有限公司广东分公司')
    return text


def detect_application_page_ranges_from_ocr(ocr_json_path: Path) -> List[Tuple[int, int]]:
    data = json.loads(ocr_json_path.read_text(encoding='utf-8'))
    start_pages = []
    for page in data['pages']:
        text = page['text']
        if '强制执行申请书' in text and ('名称：' in text or '名称:' in text):
            start_pages.append(page['page'] - 1)
    ranges: List[Tuple[int, int]] = []
    for index, start in enumerate(start_pages):
        end = start_pages[index + 1] if index + 1 < len(start_pages) else len(data['pages'])
        ranges.append((start, end))
    return ranges


def detect_single_page_case_ranges_from_ocr(ocr_json_path: Path, marker: str) -> List[Tuple[int, int]]:
    data = json.loads(ocr_json_path.read_text(encoding='utf-8'))
    ranges: List[Tuple[int, int]] = []
    for page in data['pages']:
        text = page['text']
        if marker in text:
            page_index = page['page'] - 1
            ranges.append((page_index, page_index + 1))
    return ranges


def detect_notice_source_mapping_from_ocr(output_cache_dir: Path) -> Dict[str, str]:
    pattern = re.compile(r'穗公积金中心[^\s，。；、《》]*?责字[〔\[]\d{4}[〕\]]\d+(?:-\d+)?号')
    mapping: Dict[str, str] = {}
    for source_name in SOURCE_MAPPING['输出文件（责催）']:
        stem = source_name.replace('.pdf', '')
        json_path = output_cache_dir / f'{stem}_ultra_result.json'
        data = json.loads(json_path.read_text(encoding='utf-8'))
        numbers = []
        for page in data['pages']:
            matches = pattern.findall(page['text'].replace('\n', ' '))
            numbers.extend(matches)
        if numbers:
            mapping[source_name] = numbers[0]
    return mapping


def detect_company_page_ranges_from_ocr(ocr_json_path: Path, expected_company_names: List[str]) -> List[Tuple[int, int]]:
    data = json.loads(ocr_json_path.read_text(encoding='utf-8'))
    normalized_targets = [normalize_company_name_for_matching(name) for name in expected_company_names]
    ranges: List[Tuple[int, int]] = []
    for page in data['pages']:
        text = normalize_company_name_for_matching(page['text'])
        for company_name in normalized_targets:
            if company_name in text:
                page_index = page['page'] - 1
                ranges.append((page_index, page_index + 1))
                break
    return ranges


def export_pdf_ranges(source_pdf: Path, ranges: List[Tuple[int, int]], output_dir: Path, target_names: List[str]) -> int:
    reader = PdfReader(str(source_pdf))
    created = 0
    for (start, end), target_name in zip(ranges, target_names):
        writer = PdfWriter()
        for page_index in range(start, min(end, len(reader.pages))):
            writer.add_page(reader.pages[page_index])
        target_path = output_dir / target_name
        with target_path.open('wb') as file_obj:
            writer.write(file_obj)
        created += 1
    return created


def export_notice_files(sample_root: Path, input_dir: Path, output_dir: Path, output_cache_dir: Path) -> int:
    cases = load_non_litigation_cases(sample_root)
    target_map = {case['notice_number'].replace('（', '〔').replace('）', '〕'): f"{case['sequence']}-责催-{case['notice_number']}.pdf" for case in cases}
    source_map = detect_notice_source_mapping_from_ocr(output_cache_dir)
    created = 0
    for source_name, detected_notice in source_map.items():
        target_name = target_map.get(detected_notice)
        if not target_name:
            continue
        src = input_dir / source_name
        dst = output_dir / target_name
        shutil.copy2(src, dst)
        created += 1
    return created


def export_application_files(input_dir: Path, output_dir: Path, target_names: List[str], output_cache_dir: Path) -> int:
    source_pdf = input_dir / SOURCE_MAPPING['输出文件（申请书）']
    ocr_json_path = output_cache_dir / '申请书_ultra_result.json'
    ranges = detect_application_page_ranges_from_ocr(ocr_json_path)
    return export_pdf_ranges(source_pdf, ranges, output_dir, target_names)


def export_company_named_files(input_dir: Path, output_dir: Path, target_names: List[str], output_cache_dir: Path, source_name: str, marker: str) -> int:
    source_pdf = input_dir / source_name
    stem = source_name.replace('.pdf', '')
    ocr_json_path = output_cache_dir / f'{stem}_ultra_result.json'
    marker_ranges = detect_single_page_case_ranges_from_ocr(ocr_json_path, marker)
    company_ranges = detect_company_page_ranges_from_ocr(ocr_json_path, [name.replace('.pdf', '') for name in target_names])
    ranges = company_ranges if len(company_ranges) == len(target_names) else marker_ranges
    return export_pdf_ranges(source_pdf, ranges, output_dir, target_names)


def export_non_litigation_standard_outputs(sample_root: Path, input_dir: Path, output_root: Path) -> Dict:
    output_root.mkdir(parents=True, exist_ok=True)
    tree = build_expected_output_tree(sample_root)
    created_count = 0
    output_cache_dir = input_dir.parent / 'output'

    for folder_name, target_names in tree.items():
        folder_path = output_root / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        if folder_name == '输出文件（责催）':
            created_count += export_notice_files(sample_root, input_dir, folder_path, output_cache_dir)
            continue

        if folder_name == '输出文件（申请书）':
            created_count += export_application_files(input_dir, folder_path, target_names, output_cache_dir)
            continue

        if folder_name == '输出文件（授权书）':
            created_count += export_company_named_files(input_dir, folder_path, target_names, output_cache_dir, '授权书.pdf', '授权委托书')
            continue

        if folder_name == '输出文件（所函）':
            created_count += export_company_named_files(input_dir, folder_path, target_names, output_cache_dir, '所函.pdf', '广东岭南律师事务所函')
            continue

    return {
        'created_count': created_count,
        'output_root': str(output_root),
        'tree': tree,
    }
