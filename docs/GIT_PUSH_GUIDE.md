# Git 推送指南

## 项目信息

- **本地路径**: `c:\Users\11071\Documents\trae_projects\pdf识别`
- **远程仓库**: `https://gitcode.com/BluerAngala/pdf-ocr-ai.git`

## 推送步骤

在你已经全局安装 Git 的情况下，按以下步骤操作：

### 1. 打开命令行

按 `Win + R`，输入 `cmd`，回车打开命令提示符。

### 2. 进入项目目录

```bash
cd "c:\Users\11071\Documents\trae_projects\pdf识别"
```

### 3. 初始化 Git 仓库

```bash
git init
```

### 4. 添加所有文件到暂存区

```bash
git add .
```

> 注意：`.gitignore` 已配置好，会自动排除 DLL 文件和 poppler 工具。

### 5. 提交更改

```bash
git commit -m "Initial commit: PDF OCR tool with RapidOCR"
```

### 6. 添加远程仓库

```bash
git remote add origin https://gitcode.com/BluerAngala/pdf-ocr-ai.git
```

### 7. 推送到远程

```bash
git push -u origin master
```

> 如果遇到分支名问题，尝试：`git push -u origin main`

## 验证推送成功

推送完成后，访问 `https://gitcode.com/BluerAngala/pdf-ocr-ai` 查看代码是否已上传。

## 项目文件清单

以下文件会被推送到仓库：

```
.gitignore              # Git 忽略配置
GIT_PUSH_GUIDE.md       # 本文件
INSTALL.md              # 安装指南
README.md               # 项目说明
requirements.txt        # Python 依赖
scripts/
  └── setup_poppler.py  # Poppler 自动配置脚本
src/
  └── pdf_ocr_ultra.py  # 主程序
```

## 被排除的文件（不推送）

以下文件/目录被 `.gitignore` 排除：

- `tools/poppler/` - Poppler 工具（约 50MB，用户自行下载）
- `*.dll`, `*.exe` - Windows 可执行文件
- `input/`, `output/` - 输入输出文件
- `__pycache__/`, `*.pyc` - Python 缓存
- `*.pdf` - PDF 文件

## 其他人使用流程

其他人克隆仓库后需要：

```bash
# 1. 克隆仓库
git clone https://gitcode.com/BluerAngala/pdf-ocr-ai.git
cd pdf-ocr-ai

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 配置 Poppler（自动下载）
python scripts/setup_poppler.py

# 4. 开始使用
python src/pdf_ocr_ultra.py input/your.pdf
```

## 常见问题

### Q: 推送时提示权限错误

确保你已在 GitCode 上登录，并有该仓库的写入权限。

### Q: 如何更新已推送的代码

```bash
git add .
git commit -m "更新说明"
git push
```

### Q: 如何查看当前状态

```bash
git status
```
