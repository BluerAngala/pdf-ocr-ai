#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from pathlib import Path
from typing import Dict

from non_litigation_export import export_non_litigation_standard_outputs, inspect_pdf_page_count
from non_litigation_output_plan import build_expected_output_tree


def evaluate_non_litigation_quality(root_dir: Path, output_root: Path) -> Dict:
    standard_root = root_dir / '样本材料' / '非诉组自动化样本材料' / '对应输出文件（标准版）'
    tree = build_expected_output_tree(root_dir / '样本材料' / '非诉组自动化样本材料')
    total = 0
    matched = 0
    for folder, names in tree.items():
        mapped_folder = folder
        for name in names:
            total += 1
            actual = output_root / mapped_folder / name
            expected = standard_root / mapped_folder / name
            if actual.exists() and expected.exists() and inspect_pdf_page_count(actual) == inspect_pdf_page_count(expected):
                matched += 1
    return {
        'total_files': total,
        'page_count_matched': matched,
        'page_count_match_rate': round(matched / total, 4) if total else 0,
    }


def collect_ocr_speed_metrics(output_dir: Path) -> Dict:
    json_paths = sorted(output_dir.glob('*_ultra_result.json'))
    items = []
    total_duration = 0.0
    total_pages = 0
    for path in json_paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        duration = float(data.get('total_duration', 0) or 0)
        pages = int(data.get('total_pages', 0) or 0)
        total_duration += duration
        total_pages += pages
        items.append({
            'filename': data.get('filename', path.name),
            'method': data.get('method', ''),
            'pages': pages,
            'duration_seconds': round(duration, 4),
            'seconds_per_page': round(duration / pages, 4) if pages else 0,
        })
    return {
        'file_count': len(items),
        'total_pages': total_pages,
        'total_duration_seconds': round(total_duration, 4),
        'avg_seconds_per_page': round(total_duration / total_pages, 4) if total_pages else 0,
        'items': items,
    }


def build_test_health() -> Dict:
    return {
        'active_regression_suite': [
            'test_non_litigation_product.py',
            'test_non_litigation_output_plan.py',
            'test_non_litigation_export.py',
            'test_non_litigation_splitting.py',
            'test_non_litigation_company_split.py',
            'test_non_litigation_notice_mapping.py',
            'test_company_name_matching.py',
            'test_non_litigation_full_compare.py',
            'test_project_evaluation.py',
        ],
        'status': 'focused-non-litigation-suite',
    }


def run_project_evaluation(root_dir: Path) -> Dict:
    output_dir = root_dir / 'output'
    result_root = output_dir / 'non-litigation-standard'

    start = time.perf_counter()
    export_non_litigation_standard_outputs(
        sample_root=root_dir / '样本材料' / '非诉组自动化样本材料',
        input_dir=root_dir / 'input',
        output_root=result_root,
    )
    export_duration = round(time.perf_counter() - start, 4)

    report = {
        'non_litigation': {
            'runtime_seconds': export_duration,
            'quality': evaluate_non_litigation_quality(root_dir, result_root),
        },
        'ocr_speed': collect_ocr_speed_metrics(output_dir),
        'code_quality': {
            'tests_status': 'see pytest',
            'focus': ['ocr-driven-splitting', 'company-name-matching', 'notice-number-matching'],
            'test_health': build_test_health(),
        },
    }
    return report


def main() -> int:
    root_dir = Path(__file__).resolve().parent.parent
    report = run_project_evaluation(root_dir)
    output_path = root_dir / 'output' / 'project-evaluation.json'
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
