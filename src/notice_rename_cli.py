#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path
from typing import Dict

from text_postprocessor import TextPostProcessor
from rename_rules import RenameService
from notice_rename_workflow import build_notice_plan_from_paths, summarize_plan


def load_ledger_map_from_json(json_path: Path) -> Dict[str, str]:
    data = json.loads(json_path.read_text(encoding='utf-8'))
    return {str(k): str(v) for k, v in data.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description='功能一：责催文件重命名计划生成')
    parser.add_argument('--input-dir', required=True, help='PDF 输入目录')
    parser.add_argument('--output-dir', required=True, help='OCR 输出目录')
    parser.add_argument('--ledger-json', required=True, help='台账 JSON 映射文件（责令号 -> 序号）')
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    ledger_map = load_ledger_map_from_json(Path(args.ledger_json))

    processor = TextPostProcessor()
    service = RenameService(processor)
    plan = build_notice_plan_from_paths(input_dir=input_dir, output_dir=output_dir, ledger_map=ledger_map, service=service)
    summary = summarize_plan(plan)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
