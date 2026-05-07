#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from typing import Dict, List, Tuple

from pypdf import PdfReader, PdfWriter

from non_litigation_output_plan import build_expected_output_tree


PAGE_SPLITS = {
    '授权书.pdf': [(0, 1), (1, 2), (2, 3)],
    '所函.pdf': [(0, 1), (1, 2), (2, 3)],
    '申请书.pdf': [(0, 29), (29, 56), (56, 79)],
    '1.pdf': [(0, 26)],
    '2.pdf': [(0, 22)],
    '3.pdf': [(0, 22)],
}

SOURCE_MAPPING = {
    '输出文件（责催）': ['1.pdf', '2.pdf', '3.pdf'],
    '输出文件（申请书）': '申请书.pdf',
    '输出文件（授权书）': '授权书.pdf',
    '输出文件（所函）': '所函.pdf',
}


def inspect_pdf_page_count(pdf_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    return len(reader.pages)


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


def export_notice_files(input_dir: Path, output_dir: Path, target_names: List[str]) -> int:
    created = 0
    for source_name, target_name in zip(SOURCE_MAPPING['输出文件（责催）'], target_names):
        source_pdf = input_dir / source_name
        ranges = PAGE_SPLITS[source_name]
        created += export_pdf_ranges(source_pdf, ranges, output_dir, [target_name])
    return created


def export_non_litigation_standard_outputs(sample_root: Path, input_dir: Path, output_root: Path) -> Dict:
    output_root.mkdir(parents=True, exist_ok=True)
    tree = build_expected_output_tree(sample_root)
    created_count = 0

    for folder_name, target_names in tree.items():
        folder_path = output_root / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        if folder_name == '输出文件（责催）':
            created_count += export_notice_files(input_dir, folder_path, target_names)
            continue

        source_name = SOURCE_MAPPING[folder_name]
        source_pdf = input_dir / source_name
        created_count += export_pdf_ranges(source_pdf, PAGE_SPLITS[source_name], folder_path, target_names)

    return {
        'created_count': created_count,
        'output_root': str(output_root),
        'tree': tree,
    }
