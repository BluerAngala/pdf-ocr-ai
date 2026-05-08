# PDF/图片 OCR 工具

基于 RapidOCR + pdfplumber 的 PDF/图片文字识别工具，支持可编辑 PDF 直接提取、扫描件 OCR 识别和图片文字识别。

## 特性

- ✅ **智能识别策略**: 优先提取可编辑文本，扫描件自动 fallback 到 OCR
- ✅ **多格式支持**: PDF + PNG/JPG/JPEG 图片
- ✅ **超极速处理**: 多进程并行 + 图像预处理优化
- ✅ **轻量快速**: 使用 RapidOCR，启动快、识别准
- ✅ **批量处理**: 支持多文件批量识别
- ✅ **多种输出**: TXT + JSON 双格式输出
- ✅ **命令行工具**: 完整的 CLI 接口
- ✅ **错误重试**: 自动重试失败的处理任务

## 快速开始

### 1. 克隆仓库

```bash
git clone https://gitcode.com/BluerAngala/pdf-ocr-ai.git
cd pdf-ocr-ai
```

### 2. 准备 Python 环境

本项目使用 **Python 3.12**（见 `.python-version` 文件）。

#### 方式一：使用 uv（推荐，最快）

```bash
# 安装 uv（如未安装）
pip install uv

# 创建虚拟环境并安装依赖
uv venv --python 3.12
uv pip install -r requirements.txt
```

#### 方式二：使用 venv（标准库）

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### IDE 配置

- **Trae / VS Code**: 选择 `.venv\Scripts\python.exe`（Windows）或 `.venv/bin/python`（macOS/Linux）
- **PyCharm**: 设置 Project Interpreter 为 `.venv` 目录下的 Python

### 3. 配置 Poppler（Windows 必需）

```bash
# 自动下载配置（推荐）
python scripts/setup_poppler.py
```

> Linux/macOS 用户请查看 [INSTALL.md](INSTALL.md)

### 4. 开始使用

```bash
# 识别 PDF
python src/pdf_ocr_ultra.py input/document.pdf

# 识别图片
python src/pdf_ocr_ultra.py input/scanned.png

# 批量识别
python src/pdf_ocr_ultra.py input/*.pdf input/*.png
```

## 详细安装说明

请参阅 [INSTALL.md](INSTALL.md) 获取完整的安装指南，包括：
- Windows 自动/手动配置
- Linux/macOS 安装
- 常见问题解答

## 使用方法

### 基本用法

```bash
# 自动选择最佳识别方式
python src/pdf_ocr_ultra.py document.pdf

# 识别图片
python src/pdf_ocr_ultra.py image.png
```

### 高级选项

```bash
# 强制使用 OCR（适用于扫描件）
python src/pdf_ocr_ultra.py document.pdf --force-ocr

# 调整 DPI（默认 250，范围 150-300）
python src/pdf_ocr_ultra.py document.pdf --dpi 200

# 指定输出目录
python src/pdf_ocr_ultra.py document.pdf -o ./results

# 调整并行进程数（默认 4）
python src/pdf_ocr_ultra.py document.pdf --workers 6

# 批量处理
python src/pdf_ocr_ultra.py doc1.pdf doc2.png doc3.pdf
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--dpi` | 图像分辨率，越高越清晰但越慢 | 250 |
| `--max-size` | 最大图像尺寸（像素） | 1024 |
| `--workers` | 并行处理进程数 | 4 |
| `--force-ocr` | 强制使用 OCR 识别 | False |
| `-o, --output` | 输出目录 | ./output |

## 输出文件

识别结果保存到 `output/` 目录：

- `{filename}_ultra_result.txt` - 纯文本格式
- `{filename}_ultra_result.json` - JSON 格式（包含每页详细信息）

## 项目结构

```
pdf-ocr-ai/
├── src/
│   └── pdf_ocr_ultra.py      # 主程序（超极速版）
├── scripts/
│   └── setup_poppler.py      # Poppler 自动配置脚本
├── tools/                     # 外部工具（git 忽略）
│   └── poppler/              # Poppler 工具（自动下载）
├── input/                     # 输入文件（git 忽略）
├── output/                    # 识别结果（git 忽略）
├── requirements.txt           # Python 依赖
├── INSTALL.md                # 详细安装指南
└── README.md                 # 本文件
```

## 技术方案

| 方案 | 适用场景 | 速度 | 准确率 |
|------|----------|------|--------|
| pdfplumber | 可编辑 PDF | 极快 (~0.1s) | ⭐⭐⭐⭐⭐ |
| RapidOCR | 扫描件/图片 PDF/图片 | 快 (~10s/页) | ⭐⭐⭐⭐⭐ |

## 性能优化

本工具采用多种优化策略：

1. **智能策略**: 可编辑 PDF 直接提取文本，跳过 OCR
2. **图像预处理**: 压缩、对比度增强、锐化
3. **多进程并行**: 多页同时处理，子进程预加载模型
4. **模型预热**: 预加载避免冷启动
5. **250 DPI 默认**: 平衡质量与速度
6. **错误重试**: 失败自动重试，提高成功率

## 常见问题

### Q: 提示 "Poppler 未安装"

运行自动配置脚本：
```bash
python scripts/setup_poppler.py
```

### Q: 中文乱码

脚本已内置 UTF-8 编码处理，如仍有问题请确保终端支持 UTF-8。

### Q: 识别速度慢

- 降低 DPI: `--dpi 200`
- 减少进程数: `--workers 2`（内存不足时）
- 确保使用 pdfplumber 处理可编辑 PDF（不要加 `--force-ocr`）

### Q: 内存不足

对于大 PDF，可以降低 DPI 或减少并行进程数：
```bash
python src/pdf_ocr_ultra.py large.pdf --dpi 200 --workers 2
```

### Q: 支持哪些图片格式？

支持 PNG、JPG、JPEG 格式的图片直接识别。

## 开发

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定模块测试
pytest tests/non-litigation/

# 运行测试并生成覆盖率报告
pytest tests/ --cov=src --cov-report=html
```

## 许可证

MIT License
