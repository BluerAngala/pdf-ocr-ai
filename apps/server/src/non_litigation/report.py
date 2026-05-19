#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML 报告生成器
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ReportData:
    title: str
    summary: Dict
    timing_statistics: Dict
    details: List[Dict]
    failed_items: List[Dict]
    warning_items: List[Dict]
    generated_at: str
    mode: str
    runtime_seconds: float


class HTMLReportGenerator:

    def __init__(self, data: ReportData):
        self.data = data

    def generate(self) -> str:
        return '\n'.join([
            self._header(),
            self._styles(),
            self._body(),
            '</html>',
        ])

    def _header(self) -> str:
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self.data.title}</title>
</head>'''

    def _styles(self) -> str:
        return '''
<style>
body {
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
    margin: 0;
    padding: 24px;
    background: #f5f5f5;
    color: #333;
    font-size: 14px;
    line-height: 1.6;
}
.wrap {
    max-width: 960px;
    margin: 0 auto;
    background: #fff;
    border: 1px solid #ddd;
}
.head {
    padding: 24px 32px;
    border-bottom: 2px solid #333;
}
.head h1 {
    font-size: 18px;
    font-weight: 600;
    margin: 0 0 8px;
}
.head .meta {
    font-size: 12px;
    color: #888;
}
.head .meta span {
    margin-right: 16px;
}
.sec {
    padding: 20px 32px;
    border-bottom: 1px solid #eee;
}
.sec-title {
    font-size: 14px;
    font-weight: 600;
    margin: 0 0 12px;
    padding-left: 8px;
    border-left: 3px solid #333;
}
.row {
    display: flex;
    gap: 0;
    margin-bottom: 12px;
}
.cell {
    flex: 1;
    padding: 10px 16px;
    text-align: center;
    border: 1px solid #eee;
    border-right: none;
}
.cell:last-child { border-right: 1px solid #eee; }
.cell .val {
    font-size: 22px;
    font-weight: 700;
    line-height: 1.2;
}
.cell .lbl {
    font-size: 11px;
    color: #888;
    margin-top: 2px;
}
.c-pass .val { color: #2e7d32; }
.c-warn .val { color: #e65100; }
.c-fail .val { color: #c62828; }
.c-rate .val { color: #1565c0; }
.bar-bg {
    height: 6px;
    background: #eee;
    margin-top: 8px;
}
.bar-fg {
    height: 6px;
    background: #2e7d32;
}
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}
th {
    background: #fafafa;
    font-weight: 600;
    text-align: left;
    padding: 8px 12px;
    border-bottom: 2px solid #ddd;
    white-space: nowrap;
}
td {
    padding: 7px 12px;
    border-bottom: 1px solid #eee;
}
tr:last-child td { border-bottom: none; }
tr:hover { background: #fafafa; }
.tag {
    display: inline-block;
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 2px;
    background: #f0f0f0;
    color: #555;
}
.tag-ok { background: #e8f5e9; color: #2e7d32; }
.tag-warn { background: #fff3e0; color: #e65100; }
.tag-err { background: #ffebee; color: #c62828; }
.note {
    font-size: 12px;
    color: #777;
    padding: 10px 12px;
    background: #fafafa;
    border-left: 3px solid #aaa;
    margin-top: 12px;
}
.note ul {
    margin: 6px 0 0 18px;
}
.note li { margin-bottom: 2px; }
.file-list { display: flex; flex-direction: column; gap: 0; }
.file-row {
    padding: 10px 12px;
    border-left: 3px solid #ccc;
    border-bottom: 1px solid #f0f0f0;
}
.file-row.pass { border-left-color: #2e7d32; }
.file-row.warning { border-left-color: #e65100; }
.file-row.fail { border-left-color: #c62828; }
.file-row .top {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.file-row .name {
    font-weight: 600;
    font-size: 13px;
}
.file-row .msg {
    font-size: 12px;
    color: #666;
    margin-top: 2px;
}
.file-row .info {
    font-size: 11px;
    color: #999;
    margin-top: 3px;
}
.file-row .tags {
    margin-top: 4px;
}
.file-row .tags .tag { margin-right: 4px; }
.sug {
    font-size: 11px;
    color: #e65100;
    margin-top: 4px;
    padding-left: 8px;
    border-left: 2px solid #e65100;
}
.empty {
    padding: 24px;
    text-align: center;
    color: #aaa;
    font-size: 13px;
}
.foot {
    padding: 12px 32px;
    font-size: 11px;
    color: #bbb;
    text-align: right;
}
@media (max-width: 640px) {
    body { padding: 0; }
    .wrap { border: none; }
    .sec { padding: 16px; }
    .row { flex-wrap: wrap; }
    .cell { min-width: 30%; border-right: 1px solid #eee; }
}
</style>'''

    def _body(self) -> str:
        s = self.data.summary
        pr = s.get('pass_rate', 0) * 100
        mode_label = '真实 OCR' if self.data.mode == 'real_ocr' else 'Mock'
        rt = self.data.runtime_seconds
        rt_str = f'{rt:.1f}s' if rt < 60 else f'{int(rt // 60)}m{rt % 60:.0f}s'

        return f'''
<body>
<div class="wrap">
<div class="head">
    <h1>{self.data.title}</h1>
    <div class="meta">
        <span>{self.data.generated_at}</span>
        <span>模式: {mode_label}</span>
        <span>耗时: {rt_str}</span>
    </div>
</div>

<div class="sec">
    <div class="row">
        <div class="cell"><div class="val">{s['total']}</div><div class="lbl">总文件</div></div>
        <div class="cell c-pass"><div class="val">{s['passed']}</div><div class="lbl">通过</div></div>
        <div class="cell c-warn"><div class="val">{s['warnings']}</div><div class="lbl">警告</div></div>
        <div class="cell c-fail"><div class="val">{s['failed']}</div><div class="lbl">失败</div></div>
        <div class="cell c-rate"><div class="val">{pr:.0f}%</div><div class="lbl">通过率</div></div>
    </div>
    <div class="bar-bg"><div class="bar-fg" style="width:{pr:.1f}%"></div></div>
</div>

{self._timing_section()}

{self._failed_section()}
{self._warning_section()}
{self._details_section()}

<div class="foot">非诉组 PDF 处理系统自动生成</div>
</div>
</body>'''

    def _timing_section(self) -> str:
        ts = self.data.timing_statistics
        if not ts:
            return ''

        type_names = {'notice': '责催', 'application': '申请书', 'authorization': '授权书', 'letter': '所函'}
        modes = {'notice': '逐页识别, 命中即停', 'application': '区域裁剪 + OCR', 'authorization': '区域裁剪 + OCR', 'letter': '区域裁剪 + OCR'}

        grand = sum(v.get('total', 0) for v in ts.values())

        rows = ''
        for ft, st in ts.items():
            if st['count'] == 0:
                continue
            rows += f'''<tr>
<td>{type_names.get(ft, ft)}</td>
<td>{st['count']}</td>
<td>{st['total']:.1f}s</td>
<td>{st['avg']:.1f}s</td>
<td>{st['min']:.1f}s</td>
<td>{st['max']:.1f}s</td>
<td><span class="tag">{modes.get(ft, '-')}</span></td>
</tr>'''

        return f'''
<div class="sec">
    <div class="sec-title">OCR 耗时统计</div>
    <table>
    <thead><tr>
        <th>类型</th><th>文件数</th><th>总耗时</th><th>平均</th><th>最短</th><th>最长</th><th>策略</th>
    </tr></thead>
    <tbody>{rows}</tbody>
    </table>
    <div class="note">
        <strong>OCR 累计: {grand:.1f}s</strong>
        <ul>
            <li>责催: region-first 逐页串行, 找到责令号即停</li>
            <li>申请书/授权书/所函: 区域裁剪, 仅对关键区域推理</li>
            <li>DirectML 模式下串行处理; CUDA 模式下可多线程并行</li>
        </ul>
    </div>
</div>'''

    def _failed_section(self) -> str:
        if not self.data.failed_items:
            return '<div class="sec"><div class="sec-title">失败项</div><div class="empty">无</div></div>'
        rows = ''.join(self._file_item(i) for i in self.data.failed_items)
        return f'<div class="sec"><div class="sec-title">失败项 ({len(self.data.failed_items)})</div><div class="file-list">{rows}</div></div>'

    def _warning_section(self) -> str:
        if not self.data.warning_items:
            return '<div class="sec"><div class="sec-title">警告项</div><div class="empty">无</div></div>'
        rows = ''.join(self._file_item(i) for i in self.data.warning_items)
        return f'<div class="sec"><div class="sec-title">警告项 ({len(self.data.warning_items)})</div><div class="file-list">{rows}</div></div>'

    def _details_section(self) -> str:
        rows = ''.join(self._file_item(i) for i in self.data.details)
        return f'<div class="sec"><div class="sec-title">全部明细</div><div class="file-list">{rows}</div></div>'

    def _file_item(self, item: Dict) -> str:
        status = item['status']
        label = {'pass': '通过', 'warning': '警告', 'fail': '失败'}.get(status, status)
        tag_cls = {'pass': 'tag-ok', 'warning': 'tag-warn', 'fail': 'tag-err'}.get(status, 'tag')

        d = item.get('details', {})
        parts = []
        if d.get('total_pages'):
            parts.append(f"{d['total_pages']}页")
        if d.get('detected_cases'):
            parts.append(f"{d['detected_cases']}案件")
        if d.get('detected_notices'):
            parts.append('责令号: ' + ', '.join(d['detected_notices'][:2]))
        if d.get('keywords_found'):
            parts.append('关键字: ' + ', '.join(d['keywords_found'][:3]))

        strategy = d.get('optimization_strategy', '')
        method_map = {'pdfplumber': 'PDF提取', 'pdfplumber_sequential': 'PDF提取', 'rapidocr': 'OCR', 'region_first_sequential': '区域优先', 'region_first': '区域优先', 'mixed': '混合'}
        if strategy and strategy != 'unknown':
            parts.append(method_map.get(strategy, strategy))

        timing = item.get('timing', {})
        if timing.get('total_duration', 0) > 0:
            dur = timing['total_duration']
            dur_str = f'{dur:.1f}s' if dur < 60 else f'{int(dur // 60)}m{dur % 60:.0f}s'
            parts.append(dur_str)

        info_line = ' | '.join(parts)

        tags_html = ''
        acc = item.get('accuracy', {})
        tag_parts = []
        if acc.get('region_first_hit_rate', 0) > 0:
            tag_parts.append(f'<span class="tag">区域命中{acc["region_first_hit_rate"]:.0f}%</span>')
        if acc.get('fallback_rate', 0) > 0:
            tag_parts.append(f'<span class="tag">回退{acc["fallback_rate"]:.0f}%</span>')
        if acc.get('keyword_detection_rate', 0) > 0:
            tag_parts.append(f'<span class="tag">关键字{acc["keyword_detection_rate"]:.0f}%</span>')
        if d.get('same_root_remap'):
            tag_parts.append('<span class="tag tag-warn">同根号重映射</span>')
        if tag_parts:
            tags_html = f'<div class="tags">{"".join(tag_parts)}</div>'

        sug_html = ''
        suggestions = item.get('suggestions', [])
        if suggestions:
            sug_html = '<div class="sug">' + '; '.join(suggestions[:3]) + '</div>'

        return f'''<div class="file-row {status}">
<div class="top">
    <span class="name">{item['file_name']}</span>
    <span class="tag {tag_cls}">{label}</span>
</div>
<div class="msg">{item['message']}</div>
<div class="info">{info_line}</div>
{tags_html}{sug_html}
</div>'''

    def save(self, output_path: Path):
        html = self.generate()
        output_path.write_text(html, encoding='utf-8')
        print(f"HTML 报告已保存: {output_path}")


def generate_html_report(validation_result: Dict, output_path: Path,
                         mode: str = 'mock', runtime_seconds: float = 0):
    data = ReportData(
        title='非诉组 PDF 处理报告',
        summary=validation_result['summary'],
        timing_statistics=validation_result.get('timing_statistics', {}),
        details=validation_result['details'],
        failed_items=validation_result['failed_items'],
        warning_items=validation_result['warning_items'],
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        mode=mode,
        runtime_seconds=runtime_seconds
    )
    generator = HTMLReportGenerator(data)
    generator.save(output_path)
