#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML 报告生成器

生成美观的 HTML 格式验证报告
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ReportData:
    """报告数据"""
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
    """HTML 报告生成器"""
    
    def __init__(self, data: ReportData):
        self.data = data
    
    def generate(self) -> str:
        """生成完整 HTML 报告"""
        html_parts = [
            self._generate_header(),
            self._generate_styles(),
            self._generate_body(),
            self._generate_footer(),
        ]
        return '\n'.join(html_parts)
    
    def _generate_header(self) -> str:
        """生成 HTML 头部"""
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.data.title}</title>
</head>'''
    
    def _generate_styles(self) -> str:
        """生成 CSS 样式"""
        return '''
<style>
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
        padding: 20px;
        line-height: 1.6;
    }
    
    .container {
        max-width: 1200px;
        margin: 0 auto;
        background: white;
        border-radius: 16px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        overflow: hidden;
    }
    
    .header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 40px;
        text-align: center;
    }
    
    .header h1 {
        font-size: 2.5em;
        margin-bottom: 10px;
        font-weight: 700;
    }
    
    .header .subtitle {
        opacity: 0.9;
        font-size: 1.1em;
    }
    
    .meta-info {
        display: flex;
        justify-content: center;
        gap: 30px;
        margin-top: 20px;
        flex-wrap: wrap;
    }
    
    .meta-item {
        background: rgba(255,255,255,0.2);
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 0.9em;
    }
    
    .summary-section {
        padding: 40px;
        background: #f8f9fa;
    }
    
    .summary-cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 20px;
        margin-bottom: 30px;
    }
    
    .summary-card {
        background: white;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        text-align: center;
        transition: transform 0.2s;
    }
    
    .summary-card:hover {
        transform: translateY(-5px);
    }
    
    .summary-card .number {
        font-size: 3em;
        font-weight: 700;
        margin-bottom: 5px;
    }
    
    .summary-card .label {
        color: #666;
        font-size: 0.95em;
    }
    
    .summary-card.pass .number { color: #28a745; }
    .summary-card.warning .number { color: #ffc107; }
    .summary-card.fail .number { color: #dc3545; }
    .summary-card.total .number { color: #667eea; }
    
    .progress-bar {
        background: #e9ecef;
        height: 30px;
        border-radius: 15px;
        overflow: hidden;
        margin-top: 20px;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #28a745 0%, #20c997 100%);
        border-radius: 15px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 600;
        transition: width 0.5s ease;
    }
    
    .content-section {
        padding: 40px;
    }
    
    .section-title {
        font-size: 1.5em;
        color: #333;
        margin-bottom: 20px;
        padding-bottom: 10px;
        border-bottom: 3px solid #667eea;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .file-list {
        display: flex;
        flex-direction: column;
        gap: 15px;
    }
    
    .file-item {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        border-left: 4px solid #ddd;
        transition: all 0.2s;
    }
    
    .file-item:hover {
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .file-item.pass {
        border-left-color: #28a745;
        background: linear-gradient(90deg, rgba(40,167,69,0.05) 0%, white 100%);
    }
    
    .file-item.warning {
        border-left-color: #ffc107;
        background: linear-gradient(90deg, rgba(255,193,7,0.05) 0%, white 100%);
    }
    
    .file-item.fail {
        border-left-color: #dc3545;
        background: linear-gradient(90deg, rgba(220,53,69,0.05) 0%, white 100%);
    }
    
    .file-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    
    .file-name {
        font-weight: 600;
        font-size: 1.1em;
        color: #333;
    }
    
    .status-badge {
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 600;
        text-transform: uppercase;
    }
    
    .status-badge.pass {
        background: #d4edda;
        color: #155724;
    }
    
    .status-badge.warning {
        background: #fff3cd;
        color: #856404;
    }
    
    .status-badge.fail {
        background: #f8d7da;
        color: #721c24;
    }
    
    .file-message {
        color: #666;
        margin-bottom: 10px;
    }
    
    .file-details {
        background: #f8f9fa;
        padding: 12px;
        border-radius: 8px;
        font-size: 0.9em;
        color: #555;
    }
    
    .suggestions {
        margin-top: 12px;
        padding: 12px;
        background: #fff3cd;
        border-radius: 8px;
        border-left: 3px solid #ffc107;
    }
    
    .suggestions-title {
        font-weight: 600;
        color: #856404;
        margin-bottom: 8px;
    }
    
    .suggestions ul {
        margin-left: 20px;
        color: #856404;
    }
    
    .suggestions li {
        margin-bottom: 5px;
    }
    
    .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: #666;
    }
    
    .empty-state-icon {
        font-size: 4em;
        margin-bottom: 20px;
    }
    
    .footer {
        background: #f8f9fa;
        padding: 20px;
        text-align: center;
        color: #666;
        font-size: 0.9em;
        border-top: 1px solid #e9ecef;
    }
    
    .timing-table-container {
        overflow-x: auto;
        margin: 20px 0;
    }
    
    .timing-table {
        width: 100%;
        border-collapse: collapse;
        background: white;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    
    .timing-table th {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px;
        text-align: left;
        font-weight: 600;
    }
    
    .timing-table td {
        padding: 12px 15px;
        border-bottom: 1px solid #e9ecef;
    }
    
    .timing-table tr:last-child td {
        border-bottom: none;
    }
    
    .timing-table tr:hover {
        background: #f8f9fa;
    }
    
    .timing-note {
        background: #e7f3ff;
        border-left: 4px solid #0066cc;
        padding: 15px 20px;
        border-radius: 8px;
        margin-top: 20px;
    }
    
    .timing-note p {
        margin-bottom: 10px;
        color: #333;
    }
    
    .timing-note ul {
        margin-left: 20px;
        color: #555;
    }
    
    .timing-note li {
        margin-bottom: 5px;
    }
    
    .accuracy-info {
        display: flex;
        gap: 15px;
        flex-wrap: wrap;
        margin-top: 10px;
    }
    
    .accuracy-badge {
        background: #e9ecef;
        padding: 5px 12px;
        border-radius: 15px;
        font-size: 0.85em;
        color: #555;
    }
    
    .accuracy-badge.good {
        background: #d4edda;
        color: #155724;
    }
    
    .accuracy-badge.fair {
        background: #fff3cd;
        color: #856404;
    }
    
    .accuracy-badge.poor {
        background: #f8d7da;
        color: #721c24;
    }
    
    @media (max-width: 768px) {
        .header h1 {
            font-size: 1.8em;
        }
        
        .meta-info {
            flex-direction: column;
            gap: 10px;
        }
        
        .summary-cards {
            grid-template-columns: repeat(2, 1fr);
        }
        
        .file-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 10px;
        }
    }
</style>'''
    
    def _generate_body(self) -> str:
        """生成 HTML 主体"""
        summary = self.data.summary
        pass_rate = summary.get('pass_rate', 0) * 100
        
        body = f'''
<body>
    <div class="container">
        <div class="header">
            <h1>📋 {self.data.title}</h1>
            <div class="subtitle">OCR 识别结果验证报告</div>
            <div class="meta-info">
                <div class="meta-item">🕐 生成时间: {self.data.generated_at}</div>
                <div class="meta-item">⚡ 运行模式: {self.data.mode}</div>
                <div class="meta-item">⏱️ 总耗时: {self.data.runtime_seconds:.2f}s</div>
            </div>
        </div>
        
        <div class="summary-section">
            <div class="summary-cards">
                <div class="summary-card total">
                    <div class="number">{summary['total']}</div>
                    <div class="label">总文件数</div>
                </div>
                <div class="summary-card pass">
                    <div class="number">{summary['passed']}</div>
                    <div class="label">✅ 通过</div>
                </div>
                <div class="summary-card warning">
                    <div class="number">{summary['warnings']}</div>
                    <div class="label">⚠️ 警告</div>
                </div>
                <div class="summary-card fail">
                    <div class="number">{summary['failed']}</div>
                    <div class="label">❌ 失败</div>
                </div>
            </div>
            
            <div class="progress-bar">
                <div class="progress-fill" style="width: {pass_rate}%">
                    通过率: {pass_rate:.1f}%
                </div>
            </div>
            
            {self._generate_timing_section()}
        </div>
        
        <div class="content-section">
            {self._generate_failed_section()}
            {self._generate_warning_section()}
            {self._generate_details_section()}
        </div>
        
        <div class="footer">
            <p>由 非诉组 PDF 处理系统自动生成</p>
        </div>
    </div>
</body>'''
        return body
    
    def _generate_timing_section(self) -> str:
        """生成耗时统计部分"""
        timing_stats = self.data.timing_statistics
        
        # 计算并行处理后的实际耗时
        # 责催文件：串行处理（累加）
        # 申请书/授权书/所函：并行处理（取最大值）
        notice_total = timing_stats.get('notice', {}).get('total', 0)
        application_max = timing_stats.get('application', {}).get('max', 0)
        authorization_max = timing_stats.get('authorization', {}).get('max', 0)
        letter_max = timing_stats.get('letter', {}).get('max', 0)
        
        # 并行部分取最大值
        parallel_time = max(application_max, authorization_max, letter_max)
        # 实际总耗时 = 串行部分 + 并行部分
        actual_total_time = notice_total + parallel_time
        
        html = '''
            <div style="margin-top: 30px;">
                <div class="section-title">⏱️ OCR 识别耗时统计</div>
                <div class="timing-table-container">
                    <table class="timing-table">
                        <thead>
                            <tr>
                                <th>文件类型</th>
                                <th>文件数</th>
                                <th>累加耗时</th>
                                <th>平均耗时</th>
                                <th>最短</th>
                                <th>最长</th>
                                <th>处理方式</th>
                            </tr>
                        </thead>
                        <tbody>'''
        
        type_names = {
            'notice': '责催文件',
            'application': '申请书',
            'authorization': '授权书',
            'letter': '所函'
        }
        
        processing_modes = {
            'notice': '串行（逐页识别）',
            'application': '并行（3并发）',
            'authorization': '并行（3并发）',
            'letter': '并行（3并发）'
        }
        
        for file_type, stats in timing_stats.items():
            if stats['count'] > 0:
                html += f'''
                            <tr>
                                <td><strong>{type_names.get(file_type, file_type)}</strong></td>
                                <td>{stats['count']} 个</td>
                                <td>{stats['total']:.2f}s</td>
                                <td>{stats['avg']:.2f}s</td>
                                <td>{stats['min']:.2f}s</td>
                                <td>{stats['max']:.2f}s</td>
                                <td><span class="accuracy-badge {'good' if '并行' in processing_modes.get(file_type, '') else 'fair'}">{processing_modes.get(file_type, '未知')}</span></td>
                            </tr>'''
        
        html += f'''
                        </tbody>
                    </table>
                </div>
                
                <div style="background: linear-gradient(90deg, #d4edda 0%, #fff3cd 100%); border-left: 4px solid #28a745; padding: 15px 20px; border-radius: 8px; margin: 20px 0;">
                    <p style="font-weight: 600; color: #155724; margin-bottom: 10px;">🚀 并行优化效果</p>
                    <div style="display: flex; gap: 30px; flex-wrap: wrap;">
                        <div>
                            <span style="color: #666;">累加总耗时：</span>
                            <span style="text-decoration: line-through; color: #999;">{notice_total + application_max + authorization_max + letter_max:.2f}s</span>
                        </div>
                        <div>
                            <span style="color: #666;">并行优化后：</span>
                            <span style="font-weight: 600; color: #28a745;">{actual_total_time:.2f}s</span>
                        </div>
                        <div>
                            <span style="color: #666;">节省时间：</span>
                            <span style="font-weight: 600; color: #28a745;">{application_max + authorization_max + letter_max - parallel_time:.2f}s</span>
                        </div>
                    </div>
                </div>
                
                <div class="timing-note">
                    <p>💡 <strong>耗时说明：</strong></p>
                    <ul>
                        <li><strong>责催文件</strong>：串行处理（必须逐页识别，找到责令号即停）</li>
                        <li><strong>申请书/授权书/所函</strong>：并行处理（3个并发线程同时处理）</li>
                        <li>可编辑 PDF 使用 pdfplumber 直接提取（0.1s/页）</li>
                        <li>扫描件使用 RapidOCR 识别（3-5s/页）</li>
                    </ul>
                </div>
            </div>'''
        
        return html
    
    def _generate_failed_section(self) -> str:
        """生成失败项部分"""
        if not self.data.failed_items:
            return '''
            <div class="section-title">❌ 失败项</div>
            <div class="empty-state">
                <div class="empty-state-icon">🎉</div>
                <p>太棒了！没有失败的文件</p>
            </div>'''
        
        items_html = ''
        for item in self.data.failed_items:
            items_html += self._generate_file_item(item)
        
        return f'''
            <div class="section-title">❌ 失败项 ({len(self.data.failed_items)})</div>
            <div class="file-list">
                {items_html}
            </div>'''
    
    def _generate_warning_section(self) -> str:
        """生成警告项部分"""
        if not self.data.warning_items:
            return '''
            <div class="section-title" style="margin-top: 30px;">⚠️ 警告项</div>
            <div class="empty-state">
                <div class="empty-state-icon">✨</div>
                <p>没有警告项</p>
            </div>'''
        
        items_html = ''
        for item in self.data.warning_items:
            items_html += self._generate_file_item(item)
        
        return f'''
            <div class="section-title" style="margin-top: 30px;">⚠️ 警告项 ({len(self.data.warning_items)})</div>
            <div class="file-list">
                {items_html}
            </div>'''
    
    def _generate_details_section(self) -> str:
        """生成详细列表部分"""
        items_html = ''
        for item in self.data.details:
            items_html += self._generate_file_item(item)
        
        return f'''
            <div class="section-title" style="margin-top: 30px;">📑 详细列表</div>
            <div class="file-list">
                {items_html}
            </div>'''
    
    def _generate_file_item(self, item: Dict) -> str:
        """生成单个文件项 HTML"""
        status = item['status']
        status_text = {'pass': '通过', 'warning': '警告', 'fail': '失败'}.get(status, status)
        
        suggestions_html = ''
        if item.get('suggestions'):
            suggestions_list = ''.join([f'<li>{s}</li>' for s in item['suggestions']])
            suggestions_html = f'''
                <div class="suggestions">
                    <div class="suggestions-title">💡 处理建议</div>
                    <ul>{suggestions_list}</ul>
                </div>'''
        
        # 生成详情信息
        details = item.get('details', {})
        details_html = ''
        details_parts = []
        if details:
            if 'total_pages' in details:
                details_parts.append(f"页数: {details['total_pages']}")
            if 'detected_cases' in details:
                details_parts.append(f"识别案件: {details['detected_cases']}")
            if 'detected_notices' in details and details['detected_notices']:
                details_parts.append(f"责令号: {', '.join(details['detected_notices'][:2])}")
            if 'keywords_found' in details and details['keywords_found']:
                details_parts.append(f"关键字: {', '.join(details['keywords_found'][:3])}")
        
        # 添加耗时信息
        timing = item.get('timing', {})
        if timing.get('total_duration', 0) > 0:
            method = timing.get('method', 'unknown')
            method_display = {'pdfplumber': 'PDF提取', 'rapidocr': 'OCR识别', 'pdfplumber_sequential': 'PDF提取'}.get(method, method)
            details_parts.append(f"识别方式: {method_display}")
            details_parts.append(f"耗时: {timing['total_duration']:.2f}s")
            if timing.get('avg_time_per_page', 0) > 0:
                details_parts.append(f"平均: {timing['avg_time_per_page']:.2f}s/页")
        
        if details_parts:
            details_html = f'<div class="file-details">{" | ".join(details_parts)}</div>'
        
        # 生成准确度信息
        accuracy = item.get('accuracy', {})
        accuracy_html = ''
        accuracy_badges = []
        
        if accuracy.get('text_quality'):
            quality = accuracy['text_quality']
            quality_text = {'good': '文本质量好', 'fair': '文本质量一般', 'poor': '文本质量差', 'empty': '无文本'}.get(quality, quality)
            accuracy_badges.append(f'<span class="accuracy-badge {quality}">{quality_text}</span>')
        
        if accuracy.get('match_confidence', 0) > 0:
            confidence = accuracy['match_confidence']
            accuracy_badges.append(f'<span class="accuracy-badge">匹配度: {confidence}%</span>')
        
        if accuracy.get('keyword_detection_rate', 0) > 0:
            rate = accuracy['keyword_detection_rate']
            accuracy_badges.append(f'<span class="accuracy-badge">关键字检出: {rate:.0f}%</span>')
        
        if accuracy.get('case_detection_accuracy', 0) > 0:
            acc = accuracy['case_detection_accuracy']
            accuracy_badges.append(f'<span class="accuracy-badge">案件识别: {acc:.0f}%</span>')
        
        if accuracy_badges:
            accuracy_html = f'<div class="accuracy-info">{"".join(accuracy_badges)}</div>'
        
        return f'''
            <div class="file-item {status}">
                <div class="file-header">
                    <div class="file-name">{item['file_name']}</div>
                    <div class="status-badge {status}">{status_text}</div>
                </div>
                <div class="file-message">{item['message']}</div>
                {details_html}
                {accuracy_html}
                {suggestions_html}
            </div>'''
    
    def _generate_footer(self) -> str:
        """生成 HTML 尾部"""
        return '\n</html>'
    
    def save(self, output_path: Path):
        """保存 HTML 报告"""
        html = self.generate()
        output_path.write_text(html, encoding='utf-8')
        print(f"HTML 报告已保存: {output_path}")


def generate_html_report(validation_result: Dict, output_path: Path, 
                         mode: str = 'mock', runtime_seconds: float = 0):
    """
    生成 HTML 报告的便捷函数
    
    Args:
        validation_result: 验证结果字典
        output_path: 输出 HTML 文件路径
        mode: 运行模式
        runtime_seconds: 运行耗时
    """
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
