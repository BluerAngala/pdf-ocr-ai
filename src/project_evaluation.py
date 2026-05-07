#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from pathlib import Path
from typing import Dict, List

from notice_product import build_notice_product_payload
from ruling_product import build_ruling_product_payload


def evaluate_notice_quality(payload: Dict) -> Dict:
    total = payload['summary']['total']
    matched = payload['summary']['matched']
    rate = matched / total if total else 0
    return {
        'total': total,
        'matched': matched,
        'unmatched': payload['summary']['unmatched'],
        'match_rate': round(rate, 4),
    }


def evaluate_ruling_quality(payload: Dict) -> Dict:
    rows = payload['rows']
    filled_case_no = sum(1 for row in rows if row.get('行政审查案号'))
    filled_judge = sum(1 for row in rows if row.get('审批员/法官助理'))
    filled_date = sum(1 for row in rows if row.get('执行时间'))
    total = len(rows)
    return {
        'total_rows': total,
        'matched_count': payload['matched_count'],
        'case_no_fill_rate': round(filled_case_no / total, 4) if total else 0,
        'judge_fill_rate': round(filled_judge / total, 4) if total else 0,
        'execution_date_fill_rate': round(filled_date / total, 4) if total else 0,
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
            'test_regression_artifacts.py',
            'test_notice_ledger_excel.py',
            'test_notice_product.py',
            'test_notice_product_cli.py',
            'test_decision_number_normalization.py',
            'test_ruling_excel_workflow.py',
            'test_ruling_match_workflow.py',
            'test_ruling_product.py',
            'test_ruling_product_cli.py',
            'test_project_evaluation.py',
        ],
        'status': 'curated-current-real-samples',
    }


def run_project_evaluation(root_dir: Path) -> Dict:
    output_dir = root_dir / 'output'

    notice_start = time.perf_counter()
    notice_payload = build_notice_product_payload(
        ledger_excel_path=root_dir / '样本材料' / '非诉组自动化样本材料' / '台账及命名规则.xlsx',
        input_dir=root_dir / 'input',
        output_dir=output_dir,
    )
    notice_duration = round(time.perf_counter() - notice_start, 4)

    ruling_text_paths = sorted(output_dir.glob('（2025）粤7101行审*_ultra_result.txt'))
    ruling_texts = [path.read_text(encoding='utf-8') for path in ruling_text_paths]
    ruling_start = time.perf_counter()
    ruling_payload = build_ruling_product_payload(
        excel_path=root_dir / '样本材料' / '强制组-自动化' / '提取信息' / '非诉表格.xlsx',
        ocr_texts=ruling_texts,
    )
    ruling_duration = round(time.perf_counter() - ruling_start, 4)

    report = {
        'notice': {
            'runtime_seconds': notice_duration,
            'quality': evaluate_notice_quality(notice_payload),
        },
        'ruling': {
            'runtime_seconds': ruling_duration,
            'quality': evaluate_ruling_quality(ruling_payload),
            'ocr_text_count': len(ruling_text_paths),
        },
        'ocr_speed': collect_ocr_speed_metrics(output_dir),
        'code_quality': {
            'tests_status': 'see pytest',
            'focus': ['decision-number-normalization', 'real-sample-regression', 'workflow-payload-output'],
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
