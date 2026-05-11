#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强制执行组 - 裁定信息识别与导出流程脚本

功能：
1. 从裁定PDF中识别：行审案号、责令号、法官与法官助理、责令作出时间
2. 与台账（非诉表格.xlsx）按责令号匹配
3. 导出合并后Excel

用法:
    python scripts/run_enforcement_flow.py
    python scripts/run_enforcement_flow.py --use-ocr
    python scripts/run_enforcement_flow.py --input-dir "自定义路径" --excel "非诉表格.xlsx"
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'apps' / 'server' / 'src'))

from enforcement_export import run_enforcement_extraction


def main():
    parser = argparse.ArgumentParser(description='强制执行组 - 裁定信息识别与导出')
    parser.add_argument(
        '--input-dir',
        type=str,
        default='样本材料/强制组-自动化/提取信息',
        help='裁定PDF所在目录 (默认: 样本材料/强制组-自动化/提取信息)'
    )
    parser.add_argument(
        '--excel',
        type=str,
        default='样本材料/强制组-自动化/提取信息/非诉表格.xlsx',
        help='非诉表格.xlsx路径'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output/enforcement',
        help='输出目录 (默认: output/enforcement)'
    )
    parser.add_argument(
        '--use-ocr',
        action='store_true',
        help='强制使用OCR引擎（当pdfplumber无法提取文本时启用）'
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    excel_path = Path(args.excel)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"[ERROR] 输入目录不存在: {input_dir}")
        return 1

    if not excel_path.exists():
        print(f"[ERROR] Excel文件不存在: {excel_path}")
        return 1

    result = run_enforcement_extraction(
        input_dir=input_dir,
        excel_path=excel_path,
        output_dir=output_dir,
        use_ocr=args.use_ocr,
    )

    print("\n[OK] 处理完成!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
