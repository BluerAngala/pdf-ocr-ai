#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

from ruling_product import build_ruling_product_payload


def main() -> int:
    parser = argparse.ArgumentParser(description='功能二成品入口：裁定信息识别与归纳')
    parser.add_argument('--excel', required=True, help='非诉表格 Excel 路径')
    parser.add_argument('--ocr-text', required=True, nargs='+', help='OCR 文本文件路径，可传多个')
    parser.add_argument('--result-json', required=False, help='结果 JSON 输出路径')
    args = parser.parse_args()

    ocr_texts = [Path(path).read_text(encoding='utf-8') for path in args.ocr_text]
    payload = build_ruling_product_payload(
        excel_path=Path(args.excel),
        ocr_texts=ocr_texts,
    )

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.result_json:
        Path(args.result_json).write_text(text, encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
