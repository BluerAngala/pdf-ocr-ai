#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强制执行组 - 裁定信息提取与导出模块

功能：
1. 批量处理裁定PDF，提取信息
2. 与台账进行匹配关联
3. 导出JSON和更新Excel
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from paths import ROOT

from config_loader import load_config
from enforcement_extractor import RulingPDFExtractor, RulingInfo, extract_ruling_from_pdf
from enforcement_product import EnforcementCaseRegistry, load_enforcement_cases

_cfg = load_config()
_enforcement_cfg = _cfg.raw_config.get('enforcement', {})
_paths_cfg = _enforcement_cfg.get('paths', {})


@dataclass
class ExtractionResult:
    """提取结果数据结构"""
    pdf_filename: str = ""
    court_case_number: str = ""
    matched: bool = False
    matched_notice_numbers: List[str] = field(default_factory=list)
    ruling_info: Optional[RulingInfo] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'pdf_filename': self.pdf_filename,
            'court_case_number': self.court_case_number,
            'matched': self.matched,
            'matched_notice_numbers': self.matched_notice_numbers,
            'ruling_info': self.ruling_info.to_dict() if self.ruling_info else None,
            'error': self.error,
        }


class EnforcementExtractor:
    """强制执行组裁定信息提取器"""
    
    def __init__(self, input_dir: Path, use_ocr: bool = False):
        self.input_dir = input_dir
        self.use_ocr = use_ocr
        self.pdf_extractor = RulingPDFExtractor(use_ocr=use_ocr)
        self.results: List[ExtractionResult] = []
    
    def process_all_pdfs(self) -> List[ExtractionResult]:
        """处理目录下所有裁定PDF"""
        self.results = []
        
        pdf_files = sorted(self.input_dir.glob("*.pdf"))
        print(f"[INFO] 发现 {len(pdf_files)} 个PDF文件待处理")
        
        for pdf_file in pdf_files:
            result = self._process_single_pdf(pdf_file)
            self.results.append(result)
        
        return self.results
    
    def _process_single_pdf(self, pdf_file: Path) -> ExtractionResult:
        """处理单个PDF文件"""
        result = ExtractionResult(pdf_filename=pdf_file.name)
        
        print(f"[INFO] 处理: {pdf_file.name}")
        
        try:
            # 提取裁定信息
            ruling_info = self.pdf_extractor.extract_from_pdf(pdf_file)
            result.ruling_info = ruling_info
            result.court_case_number = ruling_info.court_case_number
            
            if not ruling_info.court_case_number:
                result.error = "无法提取法院案号"
                print(f"  [WARN] {result.error}")
            else:
                print(f"  [OK] 案号: {ruling_info.court_case_number}")
                print(f"      责令号: {ruling_info.notice_numbers}")
                print(f"      被执行人: {[r['name'] for r in ruling_info.respondents]}")
                print(f"      金额: {ruling_info.execution_amount}")
                print(f"      日期: {ruling_info.ruling_date}")
                print(f"      审判员: {ruling_info.judge}")
        
        except Exception as e:
            result.error = str(e)
            print(f"  [ERROR] 处理失败: {e}")
        
        return result
    
    def match_with_registry(self, registry: EnforcementCaseRegistry) -> Dict[str, List[str]]:
        """
        将提取结果与案件登记簿进行匹配
        
        Returns:
            Dict[str, List[str]]: 匹配统计信息
        """
        stats = {
            'total_processed': len(self.results),
            'successfully_extracted': 0,
            'matched_cases': 0,
            'unmatched_cases': 0,
            'matched_notice_numbers': [],
        }
        
        for result in self.results:
            if result.error or not result.ruling_info:
                continue
            
            stats['successfully_extracted'] += 1
            
            # 匹配案件
            matched_cases = registry.match_ruling_info(result.ruling_info)
            
            if matched_cases:
                result.matched = True
                stats['matched_cases'] += 1
                
                # 更新案件信息
                for case in matched_cases:
                    registry.update_case_from_ruling(case, result.ruling_info)
                    result.matched_notice_numbers.append(case.notice_number)
                    stats['matched_notice_numbers'].append(case.notice_number)
                
                print(f"  [MATCHED] {result.court_case_number} -> {len(matched_cases)} 条案件")
            else:
                stats['unmatched_cases'] += 1
                print(f"  [UNMATCHED] {result.court_case_number}")
        
        return stats
    
    def export_to_json(self, output_path: Path) -> Path:
        """导出提取结果到JSON"""
        data = {
            'export_time': datetime.now().isoformat(),
            'input_dir': str(self.input_dir),
            'total_files': len(self.results),
            'results': [r.to_dict() for r in self.results]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] 已导出JSON到: {output_path}")
        return output_path


def run_enforcement_extraction(
    input_dir: Path,
    excel_path: Path,
    output_dir: Path,
    use_ocr: bool = False,
) -> Dict[str, Any]:
    """
    运行强制执行组完整提取流程
    
    Args:
        input_dir: 裁定PDF所在目录
        excel_path: 非诉表格.xlsx 路径
        output_dir: 输出目录
        use_ocr: 是否使用OCR
    
    Returns:
        Dict[str, Any]: 处理结果统计
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("强制执行组 - 裁定信息提取")
    print("=" * 60)
    
    # 1. 加载台账
    print("\n[1/4] 加载台账数据...")
    registry = load_enforcement_cases(excel_path)
    
    # 2. 处理裁定PDF
    print("\n[2/4] 处理裁定PDF...")
    extractor = EnforcementExtractor(input_dir, use_ocr=use_ocr)
    results = extractor.process_all_pdfs()
    
    # 3. 匹配并更新
    print("\n[3/4] 匹配案件并更新数据...")
    stats = extractor.match_with_registry(registry)
    
    # 4. 导出结果
    print("\n[4/4] 导出结果...")
    
    # 导出JSON（提取详情）
    json_path = output_dir / _paths_cfg.get('json_output_filename', 'enforcement_extracted.json')
    extractor.export_to_json(json_path)
    
    # 导出JSON（案件完整数据）
    cases_json_path = output_dir / 'enforcement_cases.json'
    registry.export_to_json(cases_json_path)
    
    # 保存更新后的Excel
    excel_output_path = output_dir / excel_path.name
    registry.save_to_excel(excel_output_path)
    
    # 打印统计
    print("\n" + "=" * 60)
    print("处理统计")
    print("=" * 60)
    print(f"  处理PDF文件: {stats['total_processed']}")
    print(f"  成功提取: {stats['successfully_extracted']}")
    print(f"  匹配成功: {stats['matched_cases']}")
    print(f"  未匹配: {stats['unmatched_cases']}")
    print(f"\n输出文件:")
    print(f"  - {json_path}")
    print(f"  - {cases_json_path}")
    print(f"  - {excel_output_path}")
    
    return {
        'stats': stats,
        'output_files': {
            'json': str(json_path),
            'cases_json': str(cases_json_path),
            'excel': str(excel_output_path),
        }
    }


if __name__ == "__main__":
    # 测试运行
    input_dir = Path("样本材料/强制组-自动化/提取信息")
    excel_path = Path("样本材料/强制组-自动化/提取信息/非诉表格.xlsx")
    output_dir = Path("output/enforcement")
    
    if input_dir.exists() and excel_path.exists():
        result = run_enforcement_extraction(input_dir, excel_path, output_dir, use_ocr=False)
        print("\n[OK] 处理完成!")
    else:
        print(f"[ERROR] 输入路径不存在")
        print(f"  输入目录: {input_dir} (存在: {input_dir.exists()})")
        print(f"  Excel文件: {excel_path} (存在: {excel_path.exists()})")
