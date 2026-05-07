#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, List


OUTPUT_COLUMNS = ['区号', '行政审查案号', '责令号', '被执行人', '职工姓名', '金额', '审批员/法官助理', '执行时间']


def build_ruling_output_rows(rows: List[Dict]) -> List[Dict]:
    output_rows: List[Dict] = []
    for row in rows:
        output_rows.append({column: row.get(column, '') for column in OUTPUT_COLUMNS})
    return output_rows
