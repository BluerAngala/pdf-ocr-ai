# 非诉组 PDF 处理 - 用户自测指南

本文档指导你如何自行测试非诉组的 PDF 处理流程。

---

## 快速开始

### 1. 环境检查

确保已安装依赖：

```bash
# 检查 Python 版本（需要 3.12+）
python --version

# 检查 pytest
pytest --version

# 检查 OCR 依赖
python -c "from rapidocr import RapidOCR; print('✅ RapidOCR 已安装')"
```

### 2. 运行测试

#### 方式一：Mock 模式（推荐，快速）

使用预生成的 OCR 缓存，快速验证流程逻辑：

```bash
python scripts/run_non_litigation_flow.py
```

预期输出：
- 运行耗时约 0.3 秒
- 生成 12 个文件
- 页数匹配率 100%

#### 方式二：真实 OCR 模式

调用 RapidOCR 进行真实识别（较慢，但更真实）：

```bash
# 首次运行（需要几分钟）
python scripts/run_non_litigation_flow.py --real

# 强制重新识别（删除缓存后重新 OCR）
python scripts/run_non_litigation_flow.py --real --force
```

预期输出：
- 运行耗时约 30-60 秒（取决于 PDF 页数）
- 生成 12 个文件
- 页数匹配率 100%

#### 方式三：运行 pytest 测试套件

```bash
# 运行所有非诉组测试
pytest tests/non-litigation/ -v

# 运行特定测试
pytest tests/non-litigation/test_non_litigation_export.py -v

# 生成覆盖率报告
pytest tests/non-litigation/ --cov=src --cov-report=html
```

---

## 测试场景

### 场景 1：验证输出文件命名

运行后检查 `output/non-litigation-results/` 目录：

```bash
# 查看输出目录结构
tree output/non-litigation-results/

# 或使用 Python
python -c "
from pathlib import Path
root = Path('output/non-litigation-results')
for folder in sorted(root.iterdir()):
    if folder.is_dir():
        print(f'{folder.name}: {len(list(folder.glob(\"*.pdf\")))} 个文件')
        for f in sorted(folder.glob('*.pdf')):
            print(f'  - {f.name}')
"
```

**预期结果：**
- 输出文件（责催）：`{序号}-责催-{责令号}.pdf`
- 输出文件（申请书）：`{序号}-申请书pdf-{责令号}.pdf`
- 输出文件（授权书）：`{公司名称}.pdf`
- 输出文件（所函）：`{公司名称}.pdf`

### 场景 2：验证文件页数

```bash
python -c "
import sys
sys.path.insert(0, 'src')
from pypdf import PdfReader
from pathlib import Path

output_root = Path('output/non-litigation-results')
standard_root = Path('样本材料/非诉组自动化样本材料/对应输出文件（标准版）')

for folder in sorted(output_root.iterdir()):
    if not folder.is_dir():
        continue
    standard_folder = standard_root / folder.name
    for pdf_file in sorted(folder.glob('*.pdf')):
        actual = len(PdfReader(pdf_file).pages)
        standard_file = standard_folder / pdf_file.name
        if standard_file.exists():
            expected = len(PdfReader(standard_file).pages)
            match = '✅' if actual == expected else '❌'
            print(f'{match} {pdf_file.name}: {actual}/{expected} 页')
"
```

**预期结果：** 所有文件页数与标准样本一致

### 场景 3：验证 OCR 识别准确性

```bash
# 查看 OCR 缓存内容
cat temp/non-litigation/ocr-cache/所函_ultra_result.json

# 或使用 Python 查看提取的文本
python -c "
import json
from pathlib import Path

cache_dir = Path('temp/non-litigation/ocr-cache')
for cache_file in sorted(cache_dir.glob('*_ultra_result.json')):
    data = json.loads(cache_file.read_text(encoding='utf-8'))
    print(f'\\n📄 {data[\"filename\"]} ({data[\"total_pages\"]} 页)')
    for page in data['pages'][:2]:  # 只显示前2页
        text = page['text'][:200].replace('\\n', ' ')
        print(f'  第{page[\"page\"]}页: {text}...')
"
```

**预期结果：**
- 所函：识别到 "广东岭南律师事务所函" 和公司名称
- 授权书：识别到 "授权委托书" 和公司名称
- 申请书：识别到 "强制执行申请书" 和 "名称："
- 责催：识别到责令号（如 "穗公积金中心越秀责字〔2024〕914-1号"）

### 场景 4：自定义样本测试

如果你想用自己的 PDF 文件测试：

```bash
# 1. 准备输入文件
# 将文件放入 input/non-litigation/ 目录：
# - 1.pdf, 2.pdf, 3.pdf（责催文件）
# - 申请书.pdf
# - 授权书.pdf
# - 所函.pdf

# 2. 准备台账
# 修改 样本材料/非诉组自动化样本材料/台账及命名规则.xlsx
# 确保包含序号、责令号、公司名称的对应关系

# 3. 清理缓存（强制重新识别）
python scripts/run_non_litigation_flow.py --clean

# 4. 运行真实 OCR 测试
python scripts/run_non_litigation_flow.py --real --force
```

---

## 常见问题排查

### 问题 1：OCR 识别失败

**现象：**
```
[ERROR] OCR 识别失败: xxx.pdf
```

**排查步骤：**
1. 检查 Poppler 是否安装：
   ```bash
   python scripts/setup_poppler.py
   ```

2. 检查 PDF 文件是否损坏：
   ```bash
   python -c "from pypdf import PdfReader; PdfReader('input/non-litigation/xxx.pdf')"
   ```

3. 尝试降低 DPI：
   ```python
   # 修改 src/non_litigation_export.py
   config = OCRConfig(dpi=200)  # 默认 250
   ```

### 问题 2：页数不匹配

**现象：**
```
页数匹配率: 83.33% (10/12)
```

**排查步骤：**
1. 检查 OCR 缓存是否完整：
   ```bash
   ls temp/non-litigation/ocr-cache/
   # 应该有 6 个 json 文件
   ```

2. 检查输入文件是否存在：
   ```bash
   ls input/non-litigation/
   # 应该有 6 个 pdf 文件
   ```

3. 强制重新 OCR：
   ```bash
   python scripts/run_non_litigation_flow.py --real --force
   ```

### 问题 3：公司名称识别错误

**现象：** 授权书/所函命名错误

**排查步骤：**
1. 查看 OCR 识别结果：
   ```bash
   cat temp/non-litigation/ocr-cache/授权书_ultra_result.json
   ```

2. 检查纠错词库：
   ```python
   # 修改 src/non_litigation_export.py 中的 NON_LITIGATION_CORRECTIONS
   NON_LITIGATION_CORRECTIONS = {
       '错误词': '正确词',
       # ...
   }
   ```

---

## 性能测试

### 测试 OCR 速度

```bash
# 单文件 OCR 速度测试
python -c "
import time
from pathlib import Path
from src.pdf_ocr_ultra import UltraFastOCR, OCRConfig

pdf_path = Path('input/non-litigation/所函.pdf')
config = OCRConfig(dpi=250)
ocr = UltraFastOCR(config)

start = time.time()
result = ocr.process_pdf(str(pdf_path))
elapsed = time.time() - start

print(f'文件: {pdf_path.name}')
print(f'页数: {result[\"total_pages\"]}')
print(f'耗时: {elapsed:.2f} 秒')
print(f'平均每页: {elapsed/result[\"total_pages\"]:.2f} 秒')
"
```

**预期性能：**
- 单页扫描件：3-5 秒/页
- 可编辑 PDF：0.1 秒/页（使用 pdfplumber）

---

## 测试 checklist

- [ ] Mock 模式运行成功（0.3 秒，12 文件）
- [ ] 真实 OCR 模式运行成功（30-60 秒）
- [ ] 所有输出文件命名正确
- [ ] 所有输出文件页数与标准样本一致
- [ ] OCR 识别文本包含关键信息（公司名称、责令号）
- [ ] pytest 测试全部通过

---

## 进阶：批量测试

```bash
# 运行 10 次测试并统计
for i in {1..10}; do
    python scripts/run_non_litigation_flow.py 2>&1 | grep "运行耗时"
done
```

---

如有问题，请检查：
1. `output/non-litigation-run-summary.json` 中的详细报告
2. `temp/non-litigation/ocr-cache/` 中的 OCR 识别结果
3. 运行 `pytest tests/non-litigation/ -v` 查看具体测试失败原因
