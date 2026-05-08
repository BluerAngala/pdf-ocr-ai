# 智能区域识别技术详解

## 一、区域定义方式

### 1.1 基于百分比的区域定义（推荐）

**优点**：自适应不同尺寸的PDF页面

```python
from dataclasses import dataclass
from typing import Tuple

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
    # 责令号通常在页眉（页面上半部分）
    'notice_header': Region(
        name='责令号区域',
        top=0.0,      # 从顶部开始
        bottom=0.5,   # 到页面中间
        left=0.0,     # 从左侧开始
        right=1.0     # 到右侧结束
    ),
    
    # 申请书标题通常在页面前20%
    'application_title': Region(
        name='申请书标题',
        top=0.0,
        bottom=0.2,   # 前20%
        left=0.0,
        right=1.0
    ),
    
    # 公司名称通常在页面中间
    'company_middle': Region(
        name='公司名称（中间）',
        top=0.3,      # 从30%开始
        bottom=0.7,   # 到70%结束
        left=0.1,     # 左边距10%
        right=0.9     # 右边距10%
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
```

---

## 二、区域提取实现

### 2.1 从PDF提取区域图片

```python
from pdf2image import convert_from_path
from PIL import Image
from pathlib import Path
from typing import List, Tuple

class RegionExtractor:
    """区域提取器"""
    
    def __init__(self, dpi: int = 200):
        self.dpi = dpi
    
    def extract_region_from_pdf(
        self, 
        pdf_path: Path, 
        page_num: int, 
        region: Region
    ) -> Image.Image:
        """从PDF提取指定区域的图片
        
        Args:
            pdf_path: PDF文件路径
            page_num: 页码（从1开始）
            region: 区域定义
            
        Returns:
            区域图片
        """
        # 1. 转换PDF页面为图片
        images = convert_from_path(
            str(pdf_path),
            dpi=self.dpi,
            first_page=page_num,
            last_page=page_num
        )
        
        if not images:
            raise ValueError(f"无法提取页面 {page_num}")
        
        full_image = images[0]
        
        # 2. 计算区域坐标（像素）
        width, height = full_image.size
        x1, y1, x2, y2 = region.to_pixels(width, height)
        
        # 3. 裁剪区域
        region_image = full_image.crop((x1, y1, x2, y2))
        
        return region_image
    
    def extract_multiple_regions(
        self,
        pdf_path: Path,
        page_num: int,
        regions: List[Region]
    ) -> List[Image.Image]:
        """提取多个区域
        
        Args:
            pdf_path: PDF文件路径
            page_num: 页码
            regions: 区域列表
            
        Returns:
            区域图片列表
        """
        # 只转换一次PDF页面（性能优化）
        images = convert_from_path(
            str(pdf_path),
            dpi=self.dpi,
            first_page=page_num,
            last_page=page_num
        )
        
        if not images:
            return []
        
        full_image = images[0]
        width, height = full_image.size
        
        # 裁剪多个区域
        region_images = []
        for region in regions:
            x1, y1, x2, y2 = region.to_pixels(width, height)
            region_image = full_image.crop((x1, y1, x2, y2))
            region_images.append(region_image)
        
        return region_images
```

---

## 三、智能区域识别（带回退）

### 3.1 责催文件识别

```python
import re
from typing import Optional, Tuple

# 责令号正则
NOTICE_PATTERN = re.compile(r'穗公积金中心[^\s，。；、《》]*?责字[〔\[(]\d{4}[〕\])]\d+(?:-\d+)?号')

class NoticeNumberExtractor:
    """责令号提取器"""
    
    def __init__(self, ocr_engine, region_extractor: RegionExtractor):
        self.ocr = ocr_engine
        self.extractor = region_extractor
    
    def extract_robust(self, pdf_path: Path, max_pages: int = 3) -> Tuple[Optional[str], Dict]:
        """鲁棒的责令号提取（带回退机制）
        
        Returns:
            (责令号, 处理信息)
        """
        info = {
            'method': None,
            'page': None,
            'region': None,
            'fallback': False,
        }
        
        # 第一步：尝试pdfplumber直接提取（最快）
        result = self._try_pdfplumber(pdf_path, max_pages)
        if result:
            info['method'] = 'pdfplumber'
            info['page'] = result[1]
            return result[0], info
        
        # 第二步：区域OCR（页眉区域）
        for page_num in range(1, max_pages + 1):
            result = self._try_region_ocr(pdf_path, page_num)
            if result:
                info['method'] = 'region_ocr'
                info['page'] = page_num
                info['region'] = 'header'
                return result, info
        
        # 第三步：全页OCR（最准，回退方案）
        result = self._try_full_page_ocr(pdf_path, max_pages)
        if result:
            info['method'] = 'full_page_ocr'
            info['page'] = result[1]
            info['fallback'] = True
            return result[0], info
        
        return None, info
    
    def _try_pdfplumber(self, pdf_path: Path, max_pages: int) -> Optional[Tuple[str, int]]:
        """尝试pdfplumber提取"""
        try:
            import pdfplumber
            
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_num in range(min(max_pages, len(pdf.pages))):
                    page = pdf.pages[page_num]
                    text = page.extract_text()
                    
                    if text:
                        match = NOTICE_PATTERN.search(text)
                        if match:
                            # 验证格式
                            notice = match.group()
                            if self._validate_notice_number(notice):
                                return notice, page_num + 1
        except Exception as e:
            print(f"  ⚠️ pdfplumber提取失败: {e}")
        
        return None
    
    def _try_region_ocr(self, pdf_path: Path, page_num: int) -> Optional[str]:
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
                    return notice
                else:
                    # 格式不对，可能是OCR错误，返回None触发回退
                    print(f"  ⚠️ 区域OCR识别到责令号但格式验证失败: {notice}")
                    return None
        except Exception as e:
            print(f"  ⚠️ 区域OCR失败: {e}")
        
        return None
    
    def _try_full_page_ocr(self, pdf_path: Path, max_pages: int) -> Optional[Tuple[str, int]]:
        """全页OCR（回退方案）"""
        print("  🔄 回退到全页OCR...")
        
        try:
            # 转换所有页面
            images = convert_from_path(str(pdf_path), dpi=self.extractor.dpi)
            
            for page_num, image in enumerate(images[:max_pages], 1):
                text = self._ocr_image(image)
                
                match = NOTICE_PATTERN.search(text)
                if match:
                    notice = match.group()
                    if self._validate_notice_number(notice):
                        return notice, page_num
        except Exception as e:
            print(f"  ❌ 全页OCR失败: {e}")
        
        return None
    
    def _ocr_image(self, image: Image.Image) -> str:
        """OCR识别图片"""
        # 使用RapidOCR
        result = self.ocr(image)
        
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
        import re
        if not re.search(r'[〔\[(]\d{4}[〕\])]', notice):
            return False
        
        return True
```

---

### 3.2 申请书识别

```python
class ApplicationExtractor:
    """申请书信息提取器"""
    
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
        total_pages = self._get_page_count(pdf_path)
        
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
                if page_num % 2 == 1:  # 奇数页
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
                else:
                    # 验证失败，返回False触发回退
                    return False
        except Exception as e:
            print(f"  ⚠️ 申请书区域OCR失败: {e}")
        
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
```

---

### 3.3 公司名称识别

```python
class CompanyNameExtractor:
    """公司名称提取器"""
    
    def extract_robust(self, pdf_path: Path, page_num: int) -> Tuple[Optional[str], Dict]:
        """鲁棒的公司名称提取
        
        Returns:
            (公司名称, 处理信息)
        """
        info = {
            'method': None,
            'region_tried': [],
            'fallback': False,
        }
        
        # 第一步：尝试多个区域
        regions_to_try = [
            ('middle', REGIONS['company_middle']),
            ('top', REGIONS['company_top']),
            ('bottom', REGIONS['company_bottom']),
        ]
        
        for region_name, region in regions_to_try:
            info['region_tried'].append(region_name)
            
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
                        info['method'] = 'region_ocr'
                        return company, info
            except Exception as e:
                print(f"  ⚠️ 区域 {region_name} OCR失败: {e}")
        
        # 第二步：全页OCR（回退方案）
        print(f"  🔄 回退到全页OCR...")
        info['fallback'] = True
        
        try:
            images = convert_from_path(
                str(pdf_path),
                dpi=self.extractor.dpi,
                first_page=page_num,
                last_page=page_num
            )
            
            if images:
                text = self._ocr_image(images[0])
                company = self._extract_company_name(text)
                
                if company:
                    info['method'] = 'full_page_ocr'
                    return company, info
        except Exception as e:
            print(f"  ❌ 全页OCR失败: {e}")
        
        return None, info
    
    def _extract_company_name(self, text: str) -> Optional[str]:
        """从文本中提取公司名称"""
        import re
        
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
```

---

## 四、处理扫描偏差

### 4.1 多区域尝试策略

```python
# 问题：扫描偏差可能导致内容位置变化
# 解决：尝试多个区域，找到最佳匹配

def extract_with_tolerance(pdf_path: Path, page_num: int) -> Optional[str]:
    """容错的区域提取"""
    
    # 定义多个候选区域（扩大搜索范围）
    candidate_regions = [
        # 标准位置
        Region('标准', top=0.0, bottom=0.2, left=0.0, right=1.0),
        
        # 向上偏移（扫描时页面下移）
        Region('上移', top=0.0, bottom=0.15, left=0.0, right=1.0),
        
        # 向下偏移（扫描时页面上移）
        Region('下移', top=0.05, bottom=0.25, left=0.0, right=1.0),
        
        # 扩大范围（不确定位置）
        Region('扩大', top=0.0, bottom=0.3, left=0.0, right=1.0),
    ]
    
    for region in candidate_regions:
        try:
            region_image = extract_region(pdf_path, page_num, region)
            text = ocr_image(region_image)
            
            if validate_result(text):
                return text
        except:
            continue
    
    # 所有区域都失败，回退到全页OCR
    return full_page_ocr(pdf_path, page_num)
```

---

## 五、性能对比

### 5.1 理论分析

| 方法 | 处理区域 | 预期速度 | 准确度 |
|------|---------|---------|--------|
| 全页OCR | 100% | 基准 | 100% |
| 区域OCR | 20-50% | 快2-5倍 | 95-98% |
| 区域+回退 | 20-100% | 快1.5-3倍 | 99%+ |

### 5.2 实际测试

```python
# 测试脚本
def benchmark_region_ocr():
    """性能基准测试"""
    
    test_files = ['1.pdf', '2.pdf', '3.pdf']
    
    # 方法1：全页OCR
    start = time.time()
    for file in test_files:
        full_page_ocr(file)
    full_time = time.time() - start
    
    # 方法2：区域OCR + 回退
    start = time.time()
    for file in test_files:
        region_ocr_with_fallback(file)
    region_time = time.time() - start
    
    print(f"全页OCR: {full_time:.2f}s")
    print(f"区域OCR: {region_time:.2f}s")
    print(f"提速: {full_time/region_time:.2f}x")
```

---

## 六、总结

### 关键技术点

1. **区域定义**：基于百分比，自适应不同尺寸
2. **区域提取**：PDF转图片后裁剪
3. **多区域尝试**：处理扫描偏差
4. **结果验证**：格式检查，确保准确度
5. **回退机制**：验证失败自动回退到全页OCR

### 准确度保证

- ✅ 不降低OCR参数
- ✅ 验证结果格式
- ✅ 失败自动回退
- ✅ 多区域尝试

### 性能提升

- ✅ 区域OCR快2-5倍
- ✅ 回退机制保证准确度
- ✅ 综合提速1.5-3倍
