#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试智能区域识别效果

测试内容：
1. 责令号提取（区域OCR vs 全页OCR）
2. 申请书识别
3. 公司名称提取
4. 性能对比
"""

import sys
import time
from pathlib import Path

# 添加 src 到路径
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))

from smart_extractor import (
    NoticeNumberExtractor,
    ApplicationExtractor,
    CompanyNameExtractor,
    ExtractionResult
)
from pdf_ocr_ultra import UltraFastOCR


def test_notice_number_extraction():
    """测试责令号提取"""
    print("\n" + "="*60)
    print("📋 测试责令号提取（智能区域识别 vs 全页OCR）")
    print("="*60)
    
    # 测试文件
    test_files = [
        ROOT / 'input' / 'non-litigation' / '1.pdf',
        ROOT / 'input' / 'non-litigation' / '2.pdf',
        ROOT / 'input' / 'non-litigation' / '3.pdf',
    ]
    
    # 方法1：智能区域识别
    print("\n🔹 方法1：智能区域识别（带回退）")
    smart_extractor = NoticeNumberExtractor(dpi=200)
    
    smart_results = []
    smart_total_time = 0
    
    for pdf_path in test_files:
        if not pdf_path.exists():
            print(f"  ⚠️ 文件不存在: {pdf_path}")
            continue
        
        print(f"\n📄 处理: {pdf_path.name}")
        
        start = time.time()
        result = smart_extractor.extract_robust(pdf_path, max_pages=3)
        duration = time.time() - start
        smart_total_time += duration
        
        smart_results.append({
            'file': pdf_path.name,
            'result': result,
            'duration': duration
        })
        
        if result.success:
            print(f"  ✅ 成功: {result.value}")
            print(f"  📍 方法: {result.method}, 页码: {result.page}")
            if result.region:
                print(f"  📐 区域: {result.region}")
            if result.fallback:
                print(f"  ⚠️ 使用了回退机制")
            print(f"  ⏱️ 耗时: {duration:.2f}s")
        else:
            print(f"  ❌ 失败: {result.error}")
    
    # 方法2：全页OCR（对比）
    print("\n\n🔹 方法2：全页OCR（对比）")
    ocr = UltraFastOCR()
    
    full_results = []
    full_total_time = 0
    
    for pdf_path in test_files:
        if not pdf_path.exists():
            continue
        
        print(f"\n📄 处理: {pdf_path.name}")
        
        start = time.time()
        ocr_result = ocr.process_pdf(str(pdf_path))
        duration = time.time() - start
        full_total_time += duration
        
        # 从OCR结果中提取责令号
        notice = None
        for page in ocr_result.pages:
            import re
            NOTICE_PATTERN = re.compile(r'穗公积金中心[^\s，。；、《》]*?责字[〔\[(]\d{4}[〕\])]\d+(?:-\d+)?号')
            match = NOTICE_PATTERN.search(page.text)
            if match:
                notice = match.group()
                break
        
        full_results.append({
            'file': pdf_path.name,
            'notice': notice,
            'duration': duration
        })
        
        if notice:
            print(f"  ✅ 找到: {notice}")
            print(f"  ⏱️ 耗时: {duration:.2f}s")
        else:
            print(f"  ❌ 未找到责令号")
    
    # 对比结果
    print("\n" + "="*60)
    print("📊 性能对比")
    print("="*60)
    print(f"智能区域识别总耗时: {smart_total_time:.2f}s")
    print(f"全页OCR总耗时: {full_total_time:.2f}s")
    
    if full_total_time > 0:
        speedup = full_total_time / smart_total_time
        print(f"提速: {speedup:.2f}x")
    
    # 准确度对比
    print("\n📋 准确度对比:")
    for i, (smart, full) in enumerate(zip(smart_results, full_results)):
        print(f"\n  文件: {smart['file']}")
        print(f"    智能识别: {smart['result'].value if smart['result'].success else '失败'}")
        print(f"    全页OCR: {full['notice'] if full['notice'] else '未找到'}")
        
        # 检查是否一致
        smart_value = smart['result'].value if smart['result'].success else None
        full_value = full['notice']
        
        if smart_value == full_value:
            print(f"    ✅ 结果一致")
        else:
            print(f"    ⚠️ 结果不一致")


def test_application_extraction():
    """测试申请书识别"""
    print("\n" + "="*60)
    print("📋 测试申请书识别")
    print("="*60)
    
    pdf_path = ROOT / 'input' / 'non-litigation' / '申请书.pdf'
    
    if not pdf_path.exists():
        print(f"  ⚠️ 文件不存在: {pdf_path}")
        return
    
    print(f"\n📄 处理: {pdf_path.name}")
    
    extractor = ApplicationExtractor(dpi=200)
    
    start = time.time()
    start_pages, info = extractor.extract_robust(pdf_path)
    duration = time.time() - start
    
    print(f"\n  ✅ 找到 {len(start_pages)} 个申请书")
    print(f"  📍 起始页: {start_pages}")
    print(f"  📊 处理信息:")
    print(f"     - 方法: {info['method']}")
    print(f"     - 检查页数: {info['pages_checked']}")
    print(f"     - 回退次数: {info['fallback_count']}")
    print(f"  ⏱️ 耗时: {duration:.2f}s")


def test_company_name_extraction():
    """测试公司名称提取"""
    print("\n" + "="*60)
    print("📋 测试公司名称提取")
    print("="*60)
    
    test_files = [
        ('授权书.pdf', [1, 2, 3]),
        ('所函.pdf', [1, 2, 3]),
    ]
    
    extractor = CompanyNameExtractor(dpi=200)
    
    for filename, pages in test_files:
        pdf_path = ROOT / 'input' / 'non-litigation' / filename
        
        if not pdf_path.exists():
            print(f"  ⚠️ 文件不存在: {pdf_path}")
            continue
        
        print(f"\n📄 处理: {filename}")
        
        for page_num in pages:
            print(f"\n  第 {page_num} 页:")
            
            start = time.time()
            result = extractor.extract_robust(pdf_path, page_num)
            duration = time.time() - start
            
            if result.success:
                print(f"    ✅ 公司: {result.value}")
                print(f"    📍 方法: {result.method}")
                if result.region:
                    print(f"    📐 区域: {result.region}")
                if result.fallback:
                    print(f"    ⚠️ 使用了回退机制")
                print(f"    ⏱️ 耗时: {duration:.2f}s")
            else:
                print(f"    ❌ 失败: {result.error}")


def main():
    """主测试流程"""
    print("\n" + "="*60)
    print("🚀 智能区域识别测试")
    print("="*60)
    
    # 测试责令号提取
    test_notice_number_extraction()
    
    # 测试申请书识别
    test_application_extraction()
    
    # 测试公司名称提取
    test_company_name_extraction()
    
    print("\n" + "="*60)
    print("✅ 测试完成")
    print("="*60)


if __name__ == '__main__':
    main()
