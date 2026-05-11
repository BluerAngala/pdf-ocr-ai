#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from pathlib import Path
from typing import Dict

from non_litigation_export import (
    build_mock_ocr_results,
    ensure_non_litigation_input_structure,
    export_non_litigation_standard_outputs,
    get_non_litigation_input_root,
    get_non_litigation_result_root,
    inspect_pdf_page_count,
)
from non_litigation_output_plan import build_expected_output_tree
from non_litigation_product import load_non_litigation_cases
from non_litigation_validator import validate_ocr_results


def evaluate_non_litigation_quality(root_dir: Path, output_root: Path, sample_root: Path | None = None) -> Dict:
    sample_root = sample_root or (root_dir / '样本材料' / '非诉组自动化样本材料')
    standard_root = sample_root / '对应输出文件（标准版）'
    tree = build_expected_output_tree(sample_root)
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


def collect_ocr_speed_metrics(ocr_results: Dict[str, Dict]) -> Dict:
    items = []
    total_duration = 0.0
    total_pages = 0
    total_fallback_pages = 0
    total_region_pages = 0
    for source_name, data in ocr_results.items():
        duration = float(data.get('total_duration', 0) or 0)
        pages = int(data.get('total_pages', 0) or 0)
        fallback_pages = int(data.get('fallback_pages', 0) or 0)
        region_pages = int(data.get('region_pages', 0) or 0)
        total_duration += duration
        total_pages += pages
        total_fallback_pages += fallback_pages
        total_region_pages += region_pages
        items.append({
            'filename': data.get('filename', source_name),
            'method': data.get('method', ''),
            'optimization_strategy': data.get('optimization_strategy', data.get('method', '')),
            'pages': pages,
            'fallback_pages': fallback_pages,
            'region_pages': region_pages,
            'stopped_early': data.get('stopped_early', False),
            'duration_seconds': round(duration, 4),
            'seconds_per_page': round(duration / pages, 4) if pages else 0,
        })
    return {
        'file_count': len(items),
        'total_pages': total_pages,
        'total_duration_seconds': round(total_duration, 4),
        'avg_seconds_per_page': round(total_duration / total_pages, 4) if total_pages else 0,
        'fallback_pages_total': total_fallback_pages,
        'region_pages_total': total_region_pages,
        'items': items,
    }


def build_test_health() -> Dict:
    return {
        'active_regression_suite': [
            'tests/non-litigation/test_non_litigation_product.py',
            'tests/non-litigation/test_non_litigation_output_plan.py',
            'tests/non-litigation/test_non_litigation_export.py',
            'tests/non-litigation/test_non_litigation_splitting.py',
            'tests/non-litigation/test_non_litigation_company_split.py',
            'tests/non-litigation/test_company_name_matching.py',
            'tests/non-litigation/test_run_non_litigation_flow.py',
            'tests/non-litigation/test_batch2_input_structure.py',
            'tests/non-litigation/test_non_litigation_notice_mapping.py',
            'tests/non-litigation/test_non_litigation_validator.py',
            'tests/non-litigation/test_ocr_optimization_behaviors.py',
            'tests/non-litigation/test_project_evaluation.py',
        ],
        'retired_tests': [
            'tests/non-litigation/test_non_litigation_suite_directory.py',
            'tests/non-litigation/test_non_litigation_full_compare.py',
            'scripts/test_smart_extraction.py',
        ],
        'status': 'focused-non-litigation-suite',
    }


def run_project_evaluation(root_dir: Path, sample_root: Path | None = None, input_dir: Path | None = None) -> Dict:
    sample_root = sample_root or (root_dir / '样本材料' / '非诉组自动化样本材料')
    result_root = get_non_litigation_result_root(root_dir)
    input_dir = input_dir or ensure_non_litigation_input_structure(root_dir)

    ocr_results = build_mock_ocr_results(sample_root, input_dir=input_dir)

    start = time.perf_counter()
    export_non_litigation_standard_outputs(
        sample_root=sample_root,
        input_dir=input_dir,
        output_root=result_root,
        ocr_results=ocr_results,
    )
    export_duration = round(time.perf_counter() - start, 4)

    validation = validate_ocr_results(load_non_litigation_cases(sample_root), ocr_results, input_dir=input_dir)
    ocr_speed = collect_ocr_speed_metrics(ocr_results)

    report = {
        'non_litigation': {
            'runtime_seconds': export_duration,
            'quality': evaluate_non_litigation_quality(root_dir, result_root, sample_root=sample_root),
            'input_root': str(input_dir),
            'result_root': str(result_root),
        },
        'ocr_speed': ocr_speed,
        'ocr_accuracy': validation.get('accuracy_summary', {}),
        'optimization_guardrails': {
            **validation.get('optimization_guardrails', {}),
            'avg_seconds_per_page': ocr_speed.get('avg_seconds_per_page', 0),
            'fallback_pages_total': ocr_speed.get('fallback_pages_total', 0),
        },
        'code_quality': {
            'tests_status': 'see pytest',
            'focus': ['ocr-driven-splitting', 'company-name-matching', 'notice-number-matching'],
            'test_health': build_test_health(),
        },
    }
    return report


def main() -> int:
    from paths import ROOT
    root_dir = ROOT
    report = run_project_evaluation(root_dir)
    output_path = root_dir / 'output' / 'project-evaluation.json'
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
