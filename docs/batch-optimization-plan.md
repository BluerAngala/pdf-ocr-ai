# 大规模批量处理优化方案

## 问题分析

### 当前性能（1000案件）

| 文件类型 | 单个耗时 | 1000案件总耗时 | 瓶颈 |
|---------|---------|--------------|------|
| 责催文件 | 12s/个 | **3.3小时** | 逐页OCR |
| 申请书 | 17s/页 | **9.4小时** | 全页OCR |
| 授权书 | 20s/页 | **5.5小时** | 全页OCR |
| 所函 | 21s/页 | **5.8小时** | 全页OCR |
| **总计** | - | **~24小时** | 😱 |

### 主要瓶颈

1. **OCR处理慢**：每页3-5秒，扫描件更慢
2. **责催文件逐页识别**：必须找到责令号才能停止
3. **申请书全页OCR**：6页全部识别，但只需要关键字
4. **串行处理限制**：责催文件必须串行

---

## 优化方案

### 方案一：OCR参数优化（预期提速 40%）

```python
# 当前配置
dpi: 200
max_image_size: 800
skip_cls: True

# 优化配置
dpi: 150              # 降低DPI，速度+50%，准确度-5%
max_image_size: 600   # 更小图片，速度+30%
skip_cls: True        # 保持跳过方向分类
use_det_limit: True   # 限制检测区域
det_limit_side_len: 960  # 检测边长限制
```

**效果**：单页OCR从 3-5s 降到 1.5-2.5s

---

### 方案二：智能区域识别（预期提速 60%）

#### 责催文件优化
```python
# 当前：逐页识别，找到责令号即停
# 优化：只识别前3页的关键区域

def extract_notice_number_fast(pdf_path):
    """快速提取责令号 - 只识别关键区域"""
    # 1. 尝试pdfplumber提取前3页
    # 2. 如果失败，OCR只识别页面上半部分（责令号通常在页眉）
    # 3. 使用更简单的正则匹配
```

#### 申请书优化
```python
# 当前：全页OCR
# 优化：只识别标题区域

def extract_application_info_fast(pdf_path):
    """快速提取申请书信息 - 只识别标题"""
    # 1. 只OCR每页的前20%区域（标题位置）
    # 2. 检测"强制执行申请书"关键字
    # 3. 按固定页数切割（2页/案件）
```

#### 授权书/所函优化
```python
# 当前：全页OCR
# 优化：只识别公司名称

def extract_company_name_fast(pdf_path):
    """快速提取公司名称 - 只识别关键区域"""
    # 1. 只OCR页面中间区域（公司名称位置）
    # 2. 使用公司名称正则匹配
    # 3. 按固定页数切割（1页/公司）
```

---

### 方案三：多进程并行（预期提速 70%）

```python
# 当前：3个线程并行
# 优化：使用多进程 + 更高并发

from multiprocessing import Pool

def process_batch_parallel(input_dir, batch_size=50):
    """批量并行处理"""
    # 1. 将1000个案件分成20批，每批50个
    # 2. 每批使用独立进程处理
    # 3. 使用CPU核心数作为并发数（如8核）
    
    with Pool(processes=cpu_count()) as pool:
        results = pool.map(process_single_case, case_list)
```

**效果**：
- 8核CPU：理论提速8倍
- 实际提速：5-6倍（考虑GIL和IO）

---

### 方案四：增量处理 + 断点续传

```python
class BatchProcessor:
    """批量处理器 - 支持断点续传"""
    
    def __init__(self, checkpoint_file='checkpoint.json'):
        self.checkpoint_file = checkpoint_file
        self.processed = self.load_checkpoint()
    
    def process_batch(self, case_list):
        """批量处理，支持断点续传"""
        for case in case_list:
            if case['id'] in self.processed:
                print(f"跳过已处理: {case['id']}")
                continue
            
            try:
                result = self.process_case(case)
                self.save_checkpoint(case['id'], result)
            except Exception as e:
                print(f"处理失败: {case['id']}, 错误: {e}")
                continue
```

---

### 方案五：预处理 + 缓存优化

```python
# 1. PDF预处理缓存
def preprocess_pdf_batch(pdf_list):
    """批量预处理PDF"""
    # - 转换为图片
    # - 压缩图片
    # - 缓存到本地
    
# 2. OCR结果缓存
def get_ocr_cache(pdf_path):
    """获取OCR缓存"""
    cache_key = get_file_hash(pdf_path)
    if cache_key in cache:
        return cache[cache_key]
    
# 3. 台账数据缓存
def load_cases_with_cache(excel_path):
    """加载台账数据（带缓存）"""
    cache_file = excel_path.with_suffix('.cache.json')
    if cache_file.exists():
        return json.loads(cache_file.read_text())
```

---

## 综合优化效果预估

| 优化方案 | 提速比例 | 累计耗时 |
|---------|---------|---------|
| 基准 | - | 24小时 |
| OCR参数优化 | 40% | 14.4小时 |
| 智能区域识别 | 60% | 5.8小时 |
| 多进程并行 | 70% | **1.7小时** |
| 增量处理 | - | 支持断点续传 |

**最终预期**：1000案件从 24小时 → **1.7小时**

---

## 实施建议

### 第一阶段：快速优化（1小时实施）
1. ✅ 调整OCR参数（dpi=150, max_size=600）
2. ✅ 增加并发数（从3到CPU核心数）
3. ✅ 添加进度显示

### 第二阶段：深度优化（半天实施）
1. 实现智能区域识别
2. 实现多进程并行
3. 实现断点续传

### 第三阶段：极致优化（1天实施）
1. 实现预处理缓存
2. 实现分布式处理（可选）
3. 性能监控和调优

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 降低DPI导致识别率下降 | 中 | 测试样本验证 |
| 区域识别可能遗漏信息 | 中 | 保留全页OCR作为备选 |
| 多进程内存占用高 | 低 | 分批处理，限制并发数 |
| 断点续传可能丢失进度 | 低 | 实时保存检查点 |

---

## 下一步行动

1. **立即实施**：OCR参数优化 + 并发数提升
2. **短期实施**：智能区域识别 + 断点续传
3. **长期优化**：多进程并行 + 预处理缓存

**建议**：先实施第一阶段，验证效果后再进行深度优化。
