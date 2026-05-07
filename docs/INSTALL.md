# 安装指南

## 快速开始

### 1. 克隆仓库

```bash
git clone https://gitcode.com/BluerAngala/pdf-ocr-ai.git
cd pdf-ocr-ai
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 Poppler（Windows）

**方式一：自动配置（推荐）**

运行自动配置脚本：

```bash
python scripts/setup_poppler.py
```

脚本会自动下载并配置 poppler 工具（约 50MB）。

**方式二：手动配置**

如果自动配置失败，可以手动下载：

1. 下载 Poppler for Windows: https://github.com/oschwartz10612/poppler-windows/releases
2. 解压到 `tools/poppler/` 目录
3. 确保目录结构为：`tools/poppler/poppler-24.08.0/Library/bin/`

### 4. 验证安装

```bash
python src/pdf_ocr_ultra.py input/example.pdf
```

## 系统要求

- **Windows**: Windows 10 或更高版本
- **Python**: 3.8 或更高版本
- **内存**: 建议 4GB 以上（OCR 需要较多内存）

## Linux/Mac 用户

对于 Linux/Mac 系统，使用包管理器安装 poppler：

```bash
# Ubuntu/Debian
sudo apt-get install poppler-utils

# macOS
brew install poppler
```

安装后无需额外配置，系统会自动找到 poppler 工具。

## 常见问题

### Q: 为什么需要 poppler？

Poppler 是一个 PDF 渲染库，用于将 PDF 页面转换为图片，这是 OCR 识别扫描版 PDF 的必要步骤。

### Q: 下载速度慢怎么办？

如果自动下载速度慢，可以：
1. 使用代理/VPN
2. 手动从 [GitHub Releases](https://github.com/oschwartz10612/poppler-windows/releases) 下载
3. 将下载的文件放入 `tools/poppler/` 目录并解压

### Q: 可以离线使用吗？

可以。首次配置需要下载 poppler（约 50MB），之后可以完全离线使用。

## 目录结构

```
pdf-ocr-ai/
├── src/                    # 源代码
│   └── pdf_ocr_ultra.py   # 主程序
├── scripts/               # 工具脚本
│   └── setup_poppler.py   # 环境配置脚本
├── tools/                 # 外部工具（git 忽略）
│   └── poppler/          # Poppler 工具（自动下载）
├── input/                 # 输入文件（git 忽略）
├── output/                # 输出结果（git 忽略）
├── requirements.txt       # Python 依赖
└── README.md             # 使用说明
```
