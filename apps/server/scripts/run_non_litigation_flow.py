#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
非诉组 PDF 处理流程运行脚本

支持两种模式：
1. Mock 模式（默认）：使用预生成的 OCR 缓存，快速测试流程
2. 真实 OCR 模式：调用 RapidOCR 进行真实识别

用法：
    python scripts/run_non_litigation_flow.py                    # Mock 模式
    python scripts/run_non_litigation_flow.py --real             # 真实 OCR 模式
    python scripts/run_non_litigation_flow.py --all-batches      # 顺序运行第一批和第二批
    python scripts/run_non_litigation_flow.py --help             # 查看帮助
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List

SRC = Path(__file__).resolve().parent.parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.paths import ROOT, USER_DATA_DIR

from non_litigation.export import (
    build_mock_ocr_results,
    run_real_ocr,
    ensure_non_litigation_input_structure,
    export_non_litigation_standard_outputs,
    get_non_litigation_result_root,
)
from non_litigation.product import load_non_litigation_cases
from non_litigation.validator import validate_ocr_results
from non_litigation.report import generate_html_report
from non_litigation.evaluation import evaluate_non_litigation_quality


SAMPLE_ROOT = ROOT / '样本材料' / '非诉组自动化样本材料'
BATCH2_SAMPLE_ROOT = ROOT / '样本材料' / '非诉组自动化样本材料（第2批）'
DEFAULT_SUMMARY_PATH = USER_DATA_DIR / 'output' / 'non-litigation-run-summary.json'
DEFAULT_HTML_REPORT_PATH = USER_DATA_DIR / 'output' / 'ocr-validation-report.html'
ALL_BATCH_SUMMARY_PATH = USER_DATA_DIR / 'output' / 'non-litigation-run-summary-all-batches.json'

BATCH_CONFIGS = {
    'batch1': {
        'label': '第一批',
        'sample_root': SAMPLE_ROOT,
        'result_root': get_non_litigation_result_root(ROOT),
        'summary_path': DEFAULT_SUMMARY_PATH,
        'html_report_path': DEFAULT_HTML_REPORT_PATH,
    },
    'batch2': {
        'label': '第二批',
        'sample_root': BATCH2_SAMPLE_ROOT,
        'result_root': USER_DATA_DIR / 'output' / 'non-litigation-results-batch2',
        'summary_path': USER_DATA_DIR / 'output' / 'non-litigation-run-summary-batch2.json',
        'html_report_path': USER_DATA_DIR / 'output' / 'ocr-validation-report-batch2.html',
    },
}

REBUILDABLE_PATHS = [
    BATCH_CONFIGS['batch1']['result_root'],
    BATCH_CONFIGS['batch2']['result_root'],
    BATCH_CONFIGS['batch1']['summary_path'],
    BATCH_CONFIGS['batch2']['summary_path'],
    ALL_BATCH_SUMMARY_PATH,
    BATCH_CONFIGS['batch1']['html_report_path'],
    BATCH_CONFIGS['batch2']['html_report_path'],
    ROOT / 'temp' / 'non-litigation' / 'batch2-flat-input',
]


def resolve_sample_root(sample_root_arg: str | None) -> Path:
    if not sample_root_arg:
        return SAMPLE_ROOT
    sample_root = Path(sample_root_arg)
    if not sample_root.is_absolute():
        sample_root = ROOT / sample_root
    return sample_root


def list_pdf_names(folder: Path) -> List[str]:
    if not folder.exists():
        return []
    return sorted(path.name for path in folder.glob('*.pdf'))


def build_batch_config(batch_name: str) -> Dict:
    return dict(BATCH_CONFIGS[batch_name])


def infer_paths_for_sample_root(sample_root: Path) -> Dict:
    sample_root_str = str(sample_root)
    if sample_root == BATCH2_SAMPLE_ROOT or '第2批' in sample_root_str or 'batch2' in sample_root_str.lower():
        return build_batch_config('batch2')
    return build_batch_config('batch1')


def clean_rebuildable_outputs() -> List[str]:
    removed = []
    for path in REBUILDABLE_PATHS:
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(str(path))
            print(f"[OK] 已清理目录: {path}")
        elif path.is_file():
            path.unlink()
            removed.append(str(path))
            print(f"[OK] 已清理文件: {path}")
    if not removed:
        print('[INFO] 未发现需要清理的可重建产物')
    return removed





def build_run_summary(
    root_dir: Path,
    use_real_ocr: bool = False,
    sample_root: Path | None = None,
    result_root: Path | None = None,
    html_report_path: Path | None = None,
) -> Dict:
    sample_root = sample_root or SAMPLE_ROOT
    path_config = infer_paths_for_sample_root(sample_root)
    input_root = ensure_non_litigation_input_structure(root_dir)
    if (sample_root / '原始文件').exists():
        input_root = sample_root / '原始文件'
    result_root = result_root or path_config['result_root']
    html_report_path = html_report_path or path_config['html_report_path']

    result_root.mkdir(parents=True, exist_ok=True)
    html_report_path.parent.mkdir(parents=True, exist_ok=True)

    total_start = time.perf_counter()
    phase_timings = {}

    ocr_start = time.perf_counter()
    if use_real_ocr:
        print('=' * 60)
        print('[INFO] 真实 OCR 模式')
        print('=' * 60)
        ocr_results = run_real_ocr(input_root, use_mock=False)
    else:
        print('=' * 60)
        print('[INFO] Mock 模式（使用预生成缓存）')
        print('=' * 60)
        ocr_results = build_mock_ocr_results(sample_root, input_dir=input_root)
    ocr_duration = time.perf_counter() - ocr_start
    phase_timings['ocr_seconds'] = round(ocr_duration, 4)
    print(f'\n[INFO] OCR 阶段完成: {ocr_duration:.2f}s')

    print('\n[INFO] 开始导出文件...')
    export_start = time.perf_counter()
    export_result = export_non_litigation_standard_outputs(
        sample_root=sample_root,
        input_dir=input_root,
        output_root=result_root,
        ocr_results=ocr_results,
    )
    export_duration = time.perf_counter() - export_start
    export_runtime_seconds = round(export_duration, 4)
    phase_timings['export_seconds'] = export_runtime_seconds
    print(f'[INFO] 导出阶段完成: {export_duration:.2f}s')

    evaluation_start = time.perf_counter()
    quality = evaluate_non_litigation_quality(root_dir, result_root, sample_root=sample_root)
    evaluation_duration = time.perf_counter() - evaluation_start
    phase_timings['evaluation_seconds'] = round(evaluation_duration, 4)
    print(f'[INFO] 质量评估完成: {evaluation_duration:.2f}s')

    print('\n[INFO] 验证 OCR 识别结果...')
    validation_start = time.perf_counter()
    cases = load_non_litigation_cases(sample_root)
    validation_result = validate_ocr_results(cases, ocr_results, input_dir=input_root)
    validation_duration = time.perf_counter() - validation_start
    phase_timings['validation_seconds'] = round(validation_duration, 4)
    print(f'[INFO] 验证阶段完成: {validation_duration:.2f}s')

    report_start = time.perf_counter()
    runtime_seconds = round(time.perf_counter() - total_start, 4)
    generate_html_report(
        validation_result,
        html_report_path,
        mode='real_ocr' if use_real_ocr else 'mock',
        runtime_seconds=runtime_seconds,
    )
    report_duration = time.perf_counter() - report_start
    phase_timings['report_seconds'] = round(report_duration, 4)
    print(f'[INFO] 报告生成完成: {report_duration:.2f}s')

    runtime_seconds = round(time.perf_counter() - total_start, 4)
    print(f'\n' + '=' * 60)
    print(f'[INFO] 总运行时间: {runtime_seconds:.2f}s')
    print('=' * 60)

    folder_items = {
        folder.name: list_pdf_names(folder)
        for folder in sorted(result_root.iterdir())
        if folder.is_dir()
    }

    ocr_run_kind = 'real' if use_real_ocr else 'mock'

    return {
        'sample_root': str(sample_root),
        'input_root': str(input_root),
        'result_root': str(result_root),
        'html_report_path': str(html_report_path),
        'runtime_seconds': runtime_seconds,
        'export_runtime_seconds': export_runtime_seconds,
        'phase_timings': phase_timings,
        'ocr_run_kind': ocr_run_kind,
        'ocr_files_count': len(ocr_results),
        'created_count': export_result['created_count'],
        'quality': quality,
        'validation': validation_result,
        'output_folders': folder_items,
        'mode': 'real_ocr' if use_real_ocr else 'mock',
    }


def build_aggregate_summary(batch_summaries: List[Dict], mode: str) -> Dict:
    total_runtime = round(sum(item['runtime_seconds'] for item in batch_summaries), 4)
    total_quality_files = sum(item['quality']['total_files'] for item in batch_summaries)
    total_quality_matched = sum(item['quality']['page_count_matched'] for item in batch_summaries)
    total_validation_files = sum(item['validation']['summary']['total'] for item in batch_summaries)
    total_validation_passed = sum(item['validation']['summary']['passed'] for item in batch_summaries)

    return {
        'mode': mode,
        'batch_count': len(batch_summaries),
        'batches': [
            {
                'batch_name': item['batch_name'],
                'label': item['label'],
                'sample_root': item['sample_root'],
                'result_root': item['result_root'],
                'html_report_path': item['html_report_path'],
                'summary_path': item['summary_path'],
                'runtime_seconds': item['runtime_seconds'],
                'export_runtime_seconds': item.get('export_runtime_seconds', item['runtime_seconds']),
                'phase_timings': item.get('phase_timings', {}),
                'ocr_run_kind': item.get('ocr_run_kind', 'unknown'),
                'ocr_files_count': item.get('ocr_files_count', 0),
                'quality': item['quality'],
                'validation_summary': item['validation']['summary'],
                'accuracy_summary': item['validation'].get('accuracy_summary', {}),
            }
            for item in batch_summaries
        ],
        'total_runtime_seconds': total_runtime,
        'phase_timings': {
            'ocr_seconds': round(sum(item.get('phase_timings', {}).get('ocr_seconds', 0) for item in batch_summaries), 4),
            'export_seconds': round(sum(item.get('phase_timings', {}).get('export_seconds', 0) for item in batch_summaries), 4),
            'validation_seconds': round(sum(item.get('phase_timings', {}).get('validation_seconds', 0) for item in batch_summaries), 4),
            'report_seconds': round(sum(item.get('phase_timings', {}).get('report_seconds', 0) for item in batch_summaries), 4),
        },
        'overall_page_count_match_rate': round(total_quality_matched / total_quality_files, 4) if total_quality_files else 0,
        'overall_validation_pass_rate': round(total_validation_passed / total_validation_files, 4) if total_validation_files else 0,
        'quality_totals': {
            'total_files': total_quality_files,
            'page_count_matched': total_quality_matched,
        },
        'validation_totals': {
            'total': total_validation_files,
            'passed': total_validation_passed,
            'warnings': sum(item['validation']['summary']['warnings'] for item in batch_summaries),
            'failed': sum(item['validation']['summary']['failed'] for item in batch_summaries),
        },
        'accuracy_summary': {
            'same_root_remap_warnings': sum(item['validation'].get('accuracy_summary', {}).get('same_root_remap_warnings', 0) for item in batch_summaries),
            'notice_failures': sum(item['validation'].get('accuracy_summary', {}).get('notice_failures', 0) for item in batch_summaries),
            'basis_mismatch_warnings': sum(item['validation'].get('accuracy_summary', {}).get('basis_mismatch_warnings', 0) for item in batch_summaries),
            'fuzzy_mapping_warnings': sum(item['validation'].get('accuracy_summary', {}).get('fuzzy_mapping_warnings', 0) for item in batch_summaries),
            'ocr_or_heuristic_failures': sum(item['validation'].get('accuracy_summary', {}).get('ocr_or_heuristic_failures', 0) for item in batch_summaries),
            'documents_with_high_fallback': sum(item['validation'].get('accuracy_summary', {}).get('documents_with_high_fallback', 0) for item in batch_summaries),
            'fallback_pages_total': sum(item['validation'].get('accuracy_summary', {}).get('fallback_pages_total', 0) for item in batch_summaries),
        },
    }


def format_summary(summary: Dict) -> str:
    ocr_run_kind = summary.get('ocr_run_kind', 'unknown')
    lines = [
        '',
        '=' * 60,
        '[INFO] 处理结果汇总',
        '=' * 60,
        f"运行模式: {summary.get('mode', 'unknown')}",
        f"OCR 运行类型: {ocr_run_kind}",
        f"样本根目录: {summary.get('sample_root', 'unknown')}",
        f"非诉输入目录: {summary['input_root']}",
        f"非诉输出目录: {summary['result_root']}",
        f"HTML 报告: {summary.get('html_report_path', 'unknown')}",
        f"运行总耗时: {summary['runtime_seconds']} 秒",
        f"OCR耗时: {summary.get('phase_timings', {}).get('ocr_seconds', 0)} 秒",
        f"导出阶段耗时: {summary.get('export_runtime_seconds', summary['runtime_seconds'])} 秒",
        f"验证阶段耗时: {summary.get('phase_timings', {}).get('validation_seconds', 0)} 秒",
        f"报告阶段耗时: {summary.get('phase_timings', {}).get('report_seconds', 0)} 秒",
        f"OCR 识别文件数: {summary.get('ocr_files_count', 0)}",
        f"生成文件数: {summary['created_count']}",
        f"页数匹配: {summary['quality']['page_count_matched']}/{summary['quality']['total_files']}",
        f"页数匹配率: {summary['quality']['page_count_match_rate']:.2%}",
        '',
        '[INFO] 输出文件列表:',
    ]
    for folder_name, file_names in summary['output_folders'].items():
        lines.append(f"\n  {folder_name}: {len(file_names)} 个文件")
        for file_name in file_names:
            lines.append(f"    - {file_name}")

    if 'validation' in summary:
        validation = summary['validation']
        accuracy_summary = validation.get('accuracy_summary', {})
        lines.extend([
            '',
            '[INFO] OCR 识别验证:',
            f"  总计: {validation['summary']['total']} 个文件",
            f"  [OK] 通过: {validation['summary']['passed']} 个",
            f"  [WARN] 警告: {validation['summary']['warnings']} 个",
            f"  [ERROR] 失败: {validation['summary']['failed']} 个",
            f"  通过率: {validation['summary']['pass_rate']:.1%}",
            f"  最终识别准确率: {validation['summary']['pass_rate']:.1%}",
            f"  业务导出准确率: {summary['quality']['page_count_match_rate']:.1%}",
            f"  评估口径类 warning（台账/映射）: {accuracy_summary.get('basis_mismatch_warnings', 0)}",
            f"  模糊映射 warning: {accuracy_summary.get('fuzzy_mapping_warnings', 0)}",
            f"  OCR/规则真实失败: {accuracy_summary.get('ocr_or_heuristic_failures', 0)}",
            f"  同根号重映射警告: {accuracy_summary.get('same_root_remap_warnings', 0)}",
            f"  责令号失败数: {accuracy_summary.get('notice_failures', 0)}",
            f"  高 fallback 文档数: {accuracy_summary.get('documents_with_high_fallback', 0)}",
            f"  fallback 页数总计: {accuracy_summary.get('fallback_pages_total', 0)}",
        ])

        if validation['failed_items']:
            lines.append('\n  [ERROR] 失败项:')
            for item in validation['failed_items']:
                lines.append(f"    - {item['file_name']}: {item['message']}")

        if validation['warning_items']:
            lines.append('\n  [WARN] 警告项:')
            for item in validation['warning_items']:
                lines.append(f"    - {item['file_name']}: {item['message']}")

    lines.extend([
        '',
        '=' * 60,
    ])
    return '\n'.join(lines)


def format_all_batches_summary(summary: Dict) -> str:
    lines = [
        '',
        '=' * 60,
        '[INFO] 双批次处理汇总',
        '=' * 60,
        f"运行模式: {summary.get('mode', 'unknown')}",
    ]

    for batch in summary['batches']:
        lines.extend([
            '',
            f"{batch['label']}（{batch['batch_name']}）",
            f"  样本目录: {batch['sample_root']}",
            f"  输出目录: {batch['result_root']}",
            f"  HTML 报告: {batch['html_report_path']}",
            f"  Summary JSON: {batch['summary_path']}",
            f"  总耗时: {batch['runtime_seconds']} 秒",
            f"  OCR耗时: {batch.get('phase_timings', {}).get('ocr_seconds', 0)} 秒",
            f"  OCR 运行类型: {batch.get('ocr_run_kind', 'unknown')}",
            f"  OCR 识别文件数: {batch.get('ocr_files_count', 0)}",
            f"  导出阶段耗时: {batch.get('export_runtime_seconds', batch['runtime_seconds'])} 秒",
            f"  最终识别准确率: {batch['validation_summary']['pass_rate']:.1%}",
            f"  业务导出准确率: {batch['quality']['page_count_match_rate']:.1%}",
            f"  评估口径类 warning（台账/映射）: {batch['accuracy_summary'].get('basis_mismatch_warnings', 0)}",
            f"  模糊映射 warning: {batch['accuracy_summary'].get('fuzzy_mapping_warnings', 0)}",
            f"  OCR/规则真实失败: {batch['accuracy_summary'].get('ocr_or_heuristic_failures', 0)}",
            f"  同根号重映射警告: {batch['accuracy_summary'].get('same_root_remap_warnings', 0)}",
            f"  责令号失败数: {batch['accuracy_summary'].get('notice_failures', 0)}",
            f"  fallback 页数总计: {batch['accuracy_summary'].get('fallback_pages_total', 0)}",
        ])

    lines.extend([
        '',
        '总体统计',
        f"  两批合计总耗时: {summary['total_runtime_seconds']} 秒",
        f"  两批OCR耗时: {summary.get('phase_timings', {}).get('ocr_seconds', 0)} 秒",
        f"  总体识别准确率: {summary['overall_validation_pass_rate']:.1%}",
        f"  总体业务导出准确率: {summary['overall_page_count_match_rate']:.1%}",
        f"  评估口径类 warning（台账/映射）: {summary['accuracy_summary']['basis_mismatch_warnings']}",
        f"  模糊映射 warning: {summary['accuracy_summary']['fuzzy_mapping_warnings']}",
        f"  OCR/规则真实失败: {summary['accuracy_summary']['ocr_or_heuristic_failures']}",
        f"  高 fallback 文档数: {summary['accuracy_summary']['documents_with_high_fallback']}",
        f"  同根号重映射警告: {summary['accuracy_summary']['same_root_remap_warnings']}",
        f"  责令号失败数: {summary['accuracy_summary']['notice_failures']}",
        f"  fallback 页数总计: {summary['accuracy_summary']['fallback_pages_total']}",
        '',
        '=' * 60,
    ])
    return '\n'.join(lines)


def save_summary_json(summary: Dict, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')


def run_single_batch(batch_name: str, use_real_ocr: bool) -> Dict:
    config = build_batch_config(batch_name)
    summary = build_run_summary(
        ROOT,
        use_real_ocr=use_real_ocr,
        sample_root=config['sample_root'],
        result_root=config['result_root'],
        html_report_path=config['html_report_path'],
    )
    save_summary_json(summary, config['summary_path'])
    print(format_summary(summary))
    print(f"\n[INFO] 详细报告已保存: {config['summary_path']}")
    summary['batch_name'] = batch_name
    summary['label'] = config['label']
    summary['summary_path'] = str(config['summary_path'])
    return summary


def run_all_batches(use_real_ocr: bool) -> Dict:
    batch_summaries = []
    for batch_name in ('batch1', 'batch2'):
        config = build_batch_config(batch_name)
        print('\n' + '#' * 60)
        print(f"# 开始处理{config['label']}")
        print('#' * 60)
        batch_summaries.append(run_single_batch(batch_name, use_real_ocr))

    aggregate = build_aggregate_summary(
        batch_summaries,
        mode='real_ocr' if use_real_ocr else 'mock',
    )
    save_summary_json(aggregate, ALL_BATCH_SUMMARY_PATH)
    print(format_all_batches_summary(aggregate))
    print(f"\n[INFO] 双批次汇总已保存: {ALL_BATCH_SUMMARY_PATH}")
    return aggregate


def determine_exit_code(summary: Dict) -> int:
    exit_code = 0

    validation = summary.get('validation')
    if validation:
        if validation['summary']['failed'] > 0:
            print(f"\n[ERROR] OCR 验证失败: {validation['summary']['failed']} 个文件")
            print('\n[INFO] 处理建议:')
            for item in validation['failed_items']:
                print(f"\n  【{item['file_name']}】")
                for suggestion in item['suggestions']:
                    print(f"    - {suggestion}")
            exit_code = 2
        elif validation['summary']['warnings'] > 0:
            print(f"\n[WARN] OCR 验证警告: {validation['summary']['warnings']} 个文件")
        else:
            print('\n[OK] OCR 验证全部通过！')

    if exit_code == 0:
        print('\n[OK] 所有检查通过，处理成功！')

    return exit_code


def determine_all_batches_exit_code(summary: Dict) -> int:
    exit_code = 0
    if summary['overall_page_count_match_rate'] < 1.0:
        print('[WARN] 双批次结果中存在页数不匹配')
        exit_code = 1
    if summary['validation_totals']['failed'] > 0:
        print(f"\n[ERROR] 双批次 OCR 验证失败: {summary['validation_totals']['failed']} 个文件")
        exit_code = 2
    elif summary['validation_totals']['warnings'] > 0:
        print(f"\n[WARN] 双批次 OCR 验证警告: {summary['validation_totals']['warnings']} 个文件")
    else:
        print('\n[OK] 双批次 OCR 验证全部通过！')

    if exit_code == 0:
        print('\n[OK] 双批次处理成功！')

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description='非诉组 PDF 处理流程',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # Mock 模式（快速测试，使用预生成 OCR 数据）
  python scripts/run_non_litigation_flow.py

  # 真实 OCR 模式（调用 RapidOCR 识别，较慢但更真实）
  python scripts/run_non_litigation_flow.py --real

  # 顺序运行第一批与第二批
  python scripts/run_non_litigation_flow.py --clean --all-batches --real
        """
    )
    parser.add_argument(
        '--real', action='store_true',
        help='使用真实 OCR 模式（否则使用 Mock 数据）'
    )
    parser.add_argument(
        '--clean', action='store_true',
        help='清理白名单中的输出和缓存产物；若不带 --all-batches/--sample-root，则清理后直接退出'
    )
    parser.add_argument(
        '--sample-root',
        help='指定样本根目录（如 样本材料/非诉组自动化样本材料（第2批））'
    )
    parser.add_argument(
        '--all-batches', action='store_true',
        help='顺序运行第一批与第二批，并生成汇总 summary'
    )

    args = parser.parse_args()

    if args.clean:
        clean_rebuildable_outputs()
        if not args.all_batches and not args.sample_root:
            return 0

    if args.all_batches:
        aggregate = run_all_batches(use_real_ocr=args.real)
        return determine_all_batches_exit_code(aggregate)

    sample_root = resolve_sample_root(args.sample_root)
    path_config = infer_paths_for_sample_root(sample_root)

    summary = build_run_summary(
        ROOT,
        use_real_ocr=args.real,
        sample_root=sample_root,
        result_root=path_config['result_root'],
        html_report_path=path_config['html_report_path'],
    )
    save_summary_json(summary, path_config['summary_path'])

    print(format_summary(summary))
    print(f"\n[INFO] 详细报告已保存: {path_config['summary_path']}")

    return determine_exit_code(summary)


if __name__ == '__main__':
    raise SystemExit(main())
