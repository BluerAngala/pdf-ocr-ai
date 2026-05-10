#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能提取器模块

实现带回退机制的智能区域识别：
1. 责令号提取器
2. 申请书信息提取器
3. 公司名称提取器
"""

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Dict, List

from PIL import Image

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from rapidocr import RapidOCR
    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False

from region_extractor import RegionExtractor, REGIONS

from config_loader import load_config

_cfg = load_config()


NOTICE_PATTERN = _cfg.notice_pattern


@dataclass
class ExtractionResult:
    """提取结果"""
    success: bool
    value: Optional[str]
    method: str
    page: Optional[int] = None
    region: Optional[str] = None
    fallback: bool = False
    duration: float = 0.0
    error: Optional[str] = None


class NoticeNumberExtractor:
    """责令号提取器（带回退机制）"""
    
    def __init__(self, dpi: int = 200):
        """
        Args:
            dpi: PDF转图片的DPI
        """
        self.dpi = dpi
        self.extractor = RegionExtractor(dpi=dpi)
        
        if not HAS_RAPIDOCR:
            raise ImportError("RapidOCR 未安装，请运行: pip install rapidocr-onnxruntime")
        
        self.ocr_engine = RapidOCR()
    
    def extract_robust(self, pdf_path: Path, max_pages: int = 3) -> ExtractionResult:
        """鲁棒的责令号提取（带回退机制）
        
        流程：
        1. pdfplumber直接提取（最快）
        2. 区域OCR（页眉区域）
        3. 全页OCR（回退方案）
        
        Args:
            pdf_path: PDF文件路径
            max_pages: 最多检查的页数
            
        Returns:
            提取结果
        """
        start_time = time.time()
        
        # 第一步：尝试pdfplumber直接提取（最快）
        result = self._try_pdfplumber(pdf_path, max_pages)
        if result.success:
            result.duration = time.time() - start_time
            return result
        
        # 第二步：区域OCR（页眉区域）
        for page_num in range(1, max_pages + 1):
            result = self._try_region_ocr(pdf_path, page_num)
            if result.success:
                result.duration = time.time() - start_time
                return result
        
        # 第三步：全页OCR（最准，回退方案）
        result = self._try_full_page_ocr(pdf_path, max_pages)
        result.duration = time.time() - start_time
        return result
    
    def _try_pdfplumber(self, pdf_path: Path, max_pages: int) -> ExtractionResult:
        """尝试pdfplumber提取"""
        if not HAS_PDFPLUMBER:
            return ExtractionResult(
                success=False,
                value=None,
                method='pdfplumber',
                error='pdfplumber 未安装'
            )
        
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_num in range(min(max_pages, len(pdf.pages))):
                    page = pdf.pages[page_num]
                    text = page.extract_text()
                    
                    if text:
                        match = NOTICE_PATTERN.search(text)
                        if match:
                            notice = match.group()
                            # 验证格式
                            if self._validate_notice_number(notice):
                                return ExtractionResult(
                                    success=True,
                                    value=notice,
                                    method='pdfplumber',
                                    page=page_num + 1
                                )
        except Exception as e:
            return ExtractionResult(
                success=False,
                value=None,
                method='pdfplumber',
                error=str(e)
            )
        
        return ExtractionResult(
            success=False,
            value=None,
            method='pdfplumber',
            error='未找到责令号'
        )
    
    def _try_region_ocr(self, pdf_path: Path, page_num: int) -> ExtractionResult:
        """尝试区域OCR"""
        try:
            # 提取页眉区域
            region_image = self.extractor.extract_region_from_pdf(
                pdf_path, 
                page_num, 
                REGIONS['notice_header']
            )
            
            # OCR识别
            text = self._ocr_image(region_image)
            
            # 查找责令号
            match = NOTICE_PATTERN.search(text)
            if match:
                notice = match.group()
                # 验证格式
                if self._validate_notice_number(notice):
                    return ExtractionResult(
                        success=True,
                        value=notice,
                        method='region_ocr',
                        page=page_num,
                        region='notice_header'
                    )
                else:
                    # 格式不对，可能是OCR错误
                    return ExtractionResult(
                        success=False,
                        value=None,
                        method='region_ocr',
                        page=page_num,
                        region='notice_header',
                        error=f'格式验证失败: {notice}'
                    )
        except Exception as e:
            return ExtractionResult(
                success=False,
                value=None,
                method='region_ocr',
                page=page_num,
                error=str(e)
            )
        
        return ExtractionResult(
            success=False,
            value=None,
            method='region_ocr',
            page=page_num,
            error='未找到责令号'
        )
    
    def _try_full_page_ocr(self, pdf_path: Path, max_pages: int) -> ExtractionResult:
        """全页OCR（回退方案）"""
        print("  🔄 回退到全页OCR...")
        
        try:
            for page_num in range(1, max_pages + 1):
                # 提取完整页面
                full_image = self.extractor.extract_full_page(pdf_path, page_num)
                
                # OCR识别
                text = self._ocr_image(full_image)
                
                # 查找责令号
                match = NOTICE_PATTERN.search(text)
                if match:
                    notice = match.group()
                    if self._validate_notice_number(notice):
                        return ExtractionResult(
                            success=True,
                            value=notice,
                            method='full_page_ocr',
                            page=page_num,
                            fallback=True
                        )
        except Exception as e:
            return ExtractionResult(
                success=False,
                value=None,
                method='full_page_ocr',
                fallback=True,
                error=str(e)
            )
        
        return ExtractionResult(
            success=False,
            value=None,
            method='full_page_ocr',
            fallback=True,
            error='未找到责令号'
        )
    
    def _ocr_image(self, image: Image.Image) -> str:
        """OCR识别图片"""
        result = self.ocr_engine(image)
        
        # 提取文本
        if result and result[0]:
            texts = [line[1][0] for line in result[0]]
            return '\n'.join(texts)
        
        return ""
    
    def _validate_notice_number(self, notice: str) -> bool:
        """验证责令号格式"""
        # 基本格式检查
        if not notice:
            return False
        
        # 长度检查
        if len(notice) < 15 or len(notice) > 50:
            return False
        
        # 必须包含的关键字
        if '穗公积金中心' not in notice:
            return False
        
        if '责字' not in notice:
            return False
        
        # 年份检查（必须包含4位年份）
        if not re.search(r'[〔\[(]\d{4}[〕\])]', notice):
            return False
        
        return True


class ApplicationExtractor:
    """申请书信息提取器（带回退机制）"""
    
    def __init__(self, dpi: int = 200):
        self.dpi = dpi
        self.extractor = RegionExtractor(dpi=dpi)
        self.ocr_engine = RapidOCR()
    
    def extract_robust(self, pdf_path: Path) -> Tuple[List[int], Dict]:
        """鲁棒的申请书信息提取
        
        Returns:
            (申请书起始页列表, 处理信息)
        """
        info = {
            'method': None,
            'pages_checked': 0,
            'fallback_count': 0,
        }
        
        # 获取总页数
        total_pages = self.extractor.get_page_count(pdf_path)
        
        # 申请书通常从奇数页开始
        start_pages = []
        
        for page_num in range(1, total_pages + 1):
            # 第一步：区域OCR（标题区域）
            found = self._try_region_ocr(pdf_path, page_num)
            
            if found:
                start_pages.append(page_num)
                info['method'] = 'region_ocr'
            else:
                # 第二步：奇数页检查（回退到全页OCR）
                if page_num % _cfg.pages_per_case['申请书'] == 1:
                    found = self._try_full_page_ocr(pdf_path, page_num)
                    if found:
                        start_pages.append(page_num)
                        info['fallback_count'] += 1
            
            info['pages_checked'] += 1
        
        if info['fallback_count'] > 0:
            info['method'] = 'full_page_ocr'
        
        return start_pages, info
    
    def _try_region_ocr(self, pdf_path: Path, page_num: int) -> bool:
        """尝试区域OCR识别申请书标题"""
        try:
            # 提取标题区域（页面前20%）
            region_image = self.extractor.extract_region_from_pdf(
                pdf_path,
                page_num,
                REGIONS['application_title']
            )
            
            # OCR识别
            text = self._ocr_image(region_image)
            
            # 检查关键字
            if '强制执行申请书' in text:
                # 验证：检查是否还有其他关键字
                if self._validate_application_title(text):
                    return True
        except Exception as e:
            print(f"  ⚠️ 申请书区域OCR失败: {e}")
        
        return False
    
    def _try_full_page_ocr(self, pdf_path: Path, page_num: int) -> bool:
        """全页OCR（回退方案）"""
        try:
            # 提取完整页面
            full_image = self.extractor.extract_full_page(pdf_path, page_num)
            
            # OCR识别
            text = self._ocr_image(full_image)
            
            # 检查关键字
            if '强制执行申请书' in text:
                return True
        except Exception as e:
            print(f"  ⚠️ 申请书全页OCR失败: {e}")
        
        return False
    
    def _validate_application_title(self, text: str) -> bool:
        """验证申请书标题"""
        # 必须包含关键字
        if '强制执行申请书' not in text:
            return False
        
        # 可能包含的其他关键字
        keywords = ['申请人', '被申请人', '执行']
        keyword_count = sum(1 for kw in keywords if kw in text)
        
        # 至少包含1个其他关键字
        return keyword_count >= 1
    
    def _ocr_image(self, image: Image.Image) -> str:
        """OCR识别图片"""
        result = self.ocr_engine(image)
        
        if result and result[0]:
            texts = [line[1][0] for line in result[0]]
            return '\n'.join(texts)
        
        return ""


class CompanyNameExtractor:
    """公司名称提取器（带回退机制）"""
    
    def __init__(self, dpi: int = 200):
        self.dpi = dpi
        self.extractor = RegionExtractor(dpi=dpi)
        self.ocr_engine = RapidOCR()
    
    def extract_robust(self, pdf_path: Path, page_num: int) -> ExtractionResult:
        """鲁棒的公司名称提取
        
        Returns:
            提取结果
        """
        start_time = time.time()
        
        # 第一步：尝试多个区域
        regions_to_try = [
            ('middle', REGIONS['company_middle']),
            ('top', REGIONS['company_top']),
            ('bottom', REGIONS['company_bottom']),
        ]
        
        for region_name, region in regions_to_try:
            result = self._try_region_ocr(pdf_path, page_num, region_name, region)
            if result.success:
                result.duration = time.time() - start_time
                return result
        
        # 第二步：全页OCR（回退方案）
        print(f"  🔄 回退到全页OCR...")
        result = self._try_full_page_ocr(pdf_path, page_num)
        result.duration = time.time() - start_time
        return result
    
    def _try_region_ocr(
        self, 
        pdf_path: Path, 
        page_num: int, 
        region_name: str, 
        region
    ) -> ExtractionResult:
        """尝试区域OCR"""
        try:
            # 提取区域
            region_image = self.extractor.extract_region_from_pdf(
                pdf_path, page_num, region
            )
            
            # OCR识别
            text = self._ocr_image(region_image)
            
            # 提取公司名称
            company = self._extract_company_name(text)
            
            if company:
                # 验证公司名称
                if self._validate_company_name(company):
                    return ExtractionResult(
                        success=True,
                        value=company,
                        method='region_ocr',
                        page=page_num,
                        region=region_name
                    )
        except Exception as e:
            return ExtractionResult(
                success=False,
                value=None,
                method='region_ocr',
                page=page_num,
                region=region_name,
                error=str(e)
            )
        
        return ExtractionResult(
            success=False,
            value=None,
            method='region_ocr',
            page=page_num,
            region=region_name,
            error='未找到公司名称'
        )
    
    def _try_full_page_ocr(self, pdf_path: Path, page_num: int) -> ExtractionResult:
        """全页OCR（回退方案）"""
        try:
            # 提取完整页面
            full_image = self.extractor.extract_full_page(pdf_path, page_num)
            
            # OCR识别
            text = self._ocr_image(full_image)
            
            # 提取公司名称
            company = self._extract_company_name(text)
            
            if company:
                return ExtractionResult(
                    success=True,
                    value=company,
                    method='full_page_ocr',
                    page=page_num,
                    fallback=True
                )
        except Exception as e:
            return ExtractionResult(
                success=False,
                value=None,
                method='full_page_ocr',
                fallback=True,
                error=str(e)
            )
        
        return ExtractionResult(
            success=False,
            value=None,
            method='full_page_ocr',
            fallback=True,
            error='未找到公司名称'
        )
    
    def _extract_company_name(self, text: str) -> Optional[str]:
        """从文本中提取公司名称"""
        # 公司名称正则
        patterns = [
            # 标准公司名称
            r'([^\s，。；、《》]+?(?:有限公司|股份有限公司|集团|公司))',
            # 分公司
            r'([^\s，。；、《》]+?分公司)',
            # 其他企业
            r'([^\s，。；、《》]+?(?:厂|店|中心|研究院))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return None
    
    def _validate_company_name(self, name: str) -> bool:
        """验证公司名称"""
        if not name:
            return False
        
        # 长度检查
        if len(name) < 4 or len(name) > 50:
            return False
        
        # 必须包含公司类型
        company_types = ['有限公司', '股份有限公司', '集团', '公司', '分公司', '厂', '店']
        if not any(ct in name for ct in company_types):
            return False
        
        # 不能包含特殊字符
        invalid_chars = ['\n', '\r', '\t', ' ']
        if any(char in name for char in invalid_chars):
            return False
        
        return True
    
    def _ocr_image(self, image: Image.Image) -> str:
        """OCR识别图片"""
        result = self.ocr_engine(image)
        
        if result and result[0]:
            texts = [line[1][0] for line in result[0]]
            return '\n'.join(texts)
        
        return ""
