#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能区域识别模块

核心功能：
1. 基于百分比定义页面区域
2. 从PDF提取指定区域
3. 多区域尝试策略
4. 结果验证和回退机制
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, List, Optional, Dict
from PIL import Image

try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


@dataclass
class Region:
    """页面区域定义（基于百分比）"""
    name: str
    top: float      # 顶部位置（0-1）
    bottom: float   # 底部位置（0-1）
    left: float     # 左侧位置（0-1）
    right: float    # 右侧位置（0-1）
    
    def to_pixels(self, page_width: int, page_height: int) -> Tuple[int, int, int, int]:
        """转换为像素坐标"""
        x1 = int(self.left * page_width)
        y1 = int(self.top * page_height)
        x2 = int(self.right * page_width)
        y2 = int(self.bottom * page_height)
        return (x1, y1, x2, y2)


# 预定义区域
REGIONS = {
    # 责令号通常在页面前25%
    'notice_header': Region(
        name='责令号区域',
        top=0.0,
        bottom=0.25,
        left=0.0,
        right=1.0
    ),
    
    # 申请书标题通常在页面前20%
    'application_title': Region(
        name='申请书标题',
        top=0.0,
        bottom=0.2,
        left=0.0,
        right=1.0
    ),
    
    # 公司名称通常在页面中间
    'company_middle': Region(
        name='公司名称（中间）',
        top=0.3,
        bottom=0.7,
        left=0.1,
        right=0.9
    ),
    
    # 公司名称也可能在页眉
    'company_top': Region(
        name='公司名称（页眉）',
        top=0.0,
        bottom=0.3,
        left=0.0,
        right=1.0
    ),
    
    # 公司名称也可能在页脚
    'company_bottom': Region(
        name='公司名称（页脚）',
        top=0.7,
        bottom=1.0,
        left=0.0,
        right=1.0
    ),
}


class RegionExtractor:
    """区域提取器"""

    def __init__(self, dpi: int = 200, poppler_path: Optional[str] = None):
        """
        Args:
            dpi: PDF转图片的DPI
        """
        self.dpi = dpi
        self.poppler_path = poppler_path
        self._page_cache: Dict[Tuple[str, int], Image.Image] = {}

        if not HAS_PDF2IMAGE:
            raise ImportError("pdf2image 未安装，请运行: pip install pdf2image")

    def _render_page(self, pdf_path: Path, page_num: int) -> Image.Image:
        cache_key = (str(pdf_path), page_num)
        cached = self._page_cache.get(cache_key)
        if cached is not None:
            return cached

        images = convert_from_path(
            str(pdf_path),
            dpi=self.dpi,
            first_page=page_num,
            last_page=page_num,
            poppler_path=self.poppler_path,
        )

        if not images:
            raise ValueError(f"无法提取页面 {page_num}")

        full_image = images[0]
        self._page_cache[cache_key] = full_image
        return full_image

    def crop_regions_from_image(self, full_image: Image.Image, regions: List[Region]) -> List[Image.Image]:
        width, height = full_image.size
        region_images = []
        for region in regions:
            x1, y1, x2, y2 = region.to_pixels(width, height)
            region_images.append(full_image.crop((x1, y1, x2, y2)))
        return region_images

    def crop_region_from_image(self, full_image: Image.Image, region: Region) -> Image.Image:
        return self.crop_regions_from_image(full_image, [region])[0]

    def extract_region_from_pdf(
        self,
        pdf_path: Path,
        page_num: int,
        region: Region
    ) -> Image.Image:
        """从PDF提取指定区域的图片"""
        full_image = self._render_page(pdf_path, page_num)
        return self.crop_region_from_image(full_image, region)

    def extract_multiple_regions(
        self,
        pdf_path: Path,
        page_num: int,
        regions: List[Region]
    ) -> List[Image.Image]:
        """提取多个区域（性能优化：只转换一次PDF）"""
        if not regions:
            return []
        full_image = self._render_page(pdf_path, page_num)
        return self.crop_regions_from_image(full_image, regions)

    def extract_full_page(self, pdf_path: Path, page_num: int) -> Image.Image:
        """提取完整页面"""
        return self._render_page(pdf_path, page_num)
    
    def get_page_count(self, pdf_path: Path) -> int:
        """获取PDF页数"""
        if HAS_PDFPLUMBER:
            with pdfplumber.open(str(pdf_path)) as pdf:
                return len(pdf.pages)
        else:
            # 使用pdf2image获取页数
            images = convert_from_path(str(pdf_path), dpi=50, poppler_path=self.poppler_path)
            return len(images)
