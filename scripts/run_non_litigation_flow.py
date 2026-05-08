#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from non_litigation_export import (
    build_mock_ocr_cache,
    ensure_non_litigation_input_structure,
    export_non_litigation_standard_outputs,
    get_non_litigation_input_root,
    get_non_litigation_ocr_cache_dir,
    get_non_litigation_result_root,
)
from project_evaluation import evaluate_non_litigation_quality


SAMPLE_ROOT = ROOT / '样本材料' / '非诉组自动化样本材料'


def list_pdf_names(folder: Path) -> List[str]:
    if not folder.exists():
        return []
    return sorted(path.name for path in folder.glob('*.pdf'))


def build_run_summary(root_dir: Path) -> Dict:
    input_root = ensure_non_litigation_input_structure(root_dir)
    result_root = get_non_litigation_result_root(root_dir)
    ocr_cache_dir = get_non_litigation_ocr_cache_dir(root_dir)

    if result_root.exists():
        shutil.rmtree(result_root)
    result_root.mkdir(parents=True, exist_ok=True)

    build_mock_ocr_cache(SAMPLE_ROOT, ocr_cache_dir)

    start = time.perf_counter()
    export_result = export_non_litigation_standard_outputs(
        sample_root=SAMPLE_ROOT,
        input_dir=input_root,
        output_root=result_root,
        ocr_cache_dir=ocr_cache_dir,
    )
    runtime_seconds = round(time.perf_counter() - start, 4)
    quality = evaluate_non_litigation_quality(root_dir, result_root)

    folder_items = {
        folder.name: list_pdf_names(folder)
        for folder in sorted(result_root.iterdir())
        if folder.is_dir()
    }

    return {
        'input_root': str(get_non_litigation_input_root(root_dir)),
        'result_root': str(result_root),
        'ocr_cache_dir': str(ocr_cache_dir),
        'runtime_seconds': runtime_seconds,
        'created_count': export_result['created_count'],
        'quality': quality,
        'output_folders': folder_items,
    }


def format_summary(summary: Dict) -> str:
    lines = [
        f"非诉输入目录: {summary['input_root']}",
        f"非诉输出目录: {summary['result_root']}",
        f"非诉临时目录: {summary['ocr_cache_dir']}",
        f"运行耗时: {summary['runtime_seconds']} 秒",
        f"生成文件数: {summary['created_count']}",
        f"页数匹配: {summary['quality']['page_count_matched']}/{summary['quality']['total_files']}",
        f"页数匹配率: {summary['quality']['page_count_match_rate']}",
    ]
    for folder_name, file_names in summary['output_folders'].items():
        lines.append(f"{folder_name}: {len(file_names)} 个文件")
        for file_name in file_names:
            lines.append(f"  - {file_name}")
    return '\n'.join(lines)


def main() -> int:
    summary = build_run_summary(ROOT)
    report_path = ROOT / 'output' / 'non-litigation-run-summary.json'
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(format_summary(summary))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
