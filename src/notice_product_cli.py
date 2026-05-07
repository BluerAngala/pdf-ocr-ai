#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

from notice_product import build_notice_product_payload


def main() -> int:
    parser = argparse.ArgumentParser(description='功能一成品入口：非诉 PDF 批量重命名预览')
    parser.add_argument('--ledger-excel', required=True, help='台账 Excel 路径')
    parser.add_argument('--input-dir', required=True, help='PDF 输入目录')
    parser.add_argument('--output-dir', required=True, help='OCR 输出目录')
    parser.add_argument('--result-json', required=False, help='结果 JSON 输出路径')
    args = parser.parse_args()

    payload = build_notice_product_payload(
        ledger_excel_path=Path(args.ledger_excel),
        input_dir=Path(args.input_dir),
        output_dir=Path(args.output_dir),
    )

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.result_json:
        Path(args.result_json).write_text(text, encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
