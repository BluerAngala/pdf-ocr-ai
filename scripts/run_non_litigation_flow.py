#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
非诉组 PDF 处理流程运行脚本

支持两种模式：
1. Mock 模式（默认）：使用预生成的 OCR 缓存，快速测试流程
2. 真实 OCR 模式：调用 RapidOCR 进行真实识别

用法：
    python scripts/run_non_litigation_flow.py           # Mock 模式
    python scripts/run_non_litigation_flow.py --real    # 真实 OCR 模式
    python scripts/run_non_litigation_flow.py --help    # 查看帮助
"""

import argparse
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
    build_real_ocr_cache,
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


def build_run_summary(root_dir: Path, use_real_ocr: bool = False) -> Dict:
    """
    构建运行摘要

    Args:
        root_dir: 项目根目录
        use_real_ocr: 是否使用真实 OCR（否则使用 Mock）
    """
    input_root = ensure_non_litigation_input_structure(root_dir)
    result_root = get_non_litigation_result_root(root_dir)
    ocr_cache_dir = get_non_litigation_ocr_cache_dir(root_dir)

    # 清理旧输出
    if result_root.exists():
        shutil.rmtree(result_root)
    result_root.mkdir(parents=True, exist_ok=True)

    # 构建 OCR 缓存
    if use_real_ocr:
        print("=" * 60)
        print("🚀 真实 OCR 模式")
        print("=" * 60)
        build_real_ocr_cache(input_root, ocr_cache_dir, use_mock=False)
    else:
        print("=" * 60)
        print("📝 Mock 模式（使用预生成缓存）")
        print("=" * 60)
        build_mock_ocr_cache(SAMPLE_ROOT, ocr_cache_dir)

    # 执行导出
    print("\n📦 开始导出文件...")
    start = time.perf_counter()
    export_result = export_non_litigation_standard_outputs(
        sample_root=SAMPLE_ROOT,
        input_dir=input_root,
        output_root=result_root,
        ocr_cache_dir=ocr_cache_dir,
    )
    runtime_seconds = round(time.perf_counter() - start, 4)

    # 质量评估
    quality = evaluate_non_litigation_quality(root_dir, result_root)

    # 收集输出文件
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
        'mode': 'real_ocr' if use_real_ocr else 'mock',
    }


def format_summary(summary: Dict) -> str:
    lines = [
        "",
        "=" * 60,
        "📊 处理结果汇总",
        "=" * 60,
        f"运行模式: {summary.get('mode', 'unknown')}",
        f"非诉输入目录: {summary['input_root']}",
        f"非诉输出目录: {summary['result_root']}",
        f"非诉临时目录: {summary['ocr_cache_dir']}",
        f"运行耗时: {summary['runtime_seconds']} 秒",
        f"生成文件数: {summary['created_count']}",
        f"页数匹配: {summary['quality']['page_count_matched']}/{summary['quality']['total_files']}",
        f"页数匹配率: {summary['quality']['page_count_match_rate']:.2%}",
        "",
        "📁 输出文件列表:",
    ]
    for folder_name, file_names in summary['output_folders'].items():
        lines.append(f"\n  {folder_name}: {len(file_names)} 个文件")
        for file_name in file_names:
            lines.append(f"    - {file_name}")
    lines.extend([
        "",
        "=" * 60,
    ])
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='非诉组 PDF 处理流程',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # Mock 模式（快速测试，使用预生成 OCR 缓存）
  python scripts/run_non_litigation_flow.py

  # 真实 OCR 模式（调用 RapidOCR 识别，较慢但更真实）
  python scripts/run_non_litigation_flow.py --real

  # 强制重新 OCR（删除缓存后重新识别）
  python scripts/run_non_litigation_flow.py --real --force
        """
    )
    parser.add_argument(
        '--real', action='store_true',
        help='使用真实 OCR 模式（否则使用 Mock 缓存）'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='强制重新 OCR（删除现有缓存）'
    )
    parser.add_argument(
        '--clean', action='store_true',
        help='仅清理输出和缓存目录，不运行处理'
    )

    args = parser.parse_args()

    # 清理模式
    if args.clean:
        result_root = get_non_litigation_result_root(ROOT)
        ocr_cache_dir = get_non_litigation_ocr_cache_dir(ROOT)
        if result_root.exists():
            shutil.rmtree(result_root)
            print(f"✅ 已清理: {result_root}")
        if ocr_cache_dir.exists():
            shutil.rmtree(ocr_cache_dir)
            print(f"✅ 已清理: {ocr_cache_dir}")
        return 0

    # 强制重新 OCR
    if args.force and args.real:
        ocr_cache_dir = get_non_litigation_ocr_cache_dir(ROOT)
        if ocr_cache_dir.exists():
            shutil.rmtree(ocr_cache_dir)
            print(f"🗑️  已删除旧缓存: {ocr_cache_dir}")

    # 运行处理
    summary = build_run_summary(ROOT, use_real_ocr=args.real)

    # 保存报告
    report_path = ROOT / 'output' / 'non-litigation-run-summary.json'
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    # 输出结果
    print(format_summary(summary))
    print(f"\n📄 详细报告已保存: {report_path}")

    # 返回状态码
    if summary['quality']['page_count_match_rate'] >= 1.0:
        print("✅ 所有文件页数匹配，测试通过！")
        return 0
    else:
        print("⚠️  部分文件页数不匹配，请检查输出")
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
