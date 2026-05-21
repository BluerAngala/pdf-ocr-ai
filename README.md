# PDF/图片 OCR 工具 — 公积金业务辅助

基于 RapidOCR + pdfplumber 的 PDF/图片 OCR 识别工具，专为公积金业务定制。支持两个业务组：非诉审查组（PDF 批量重命名）和强制执行组（裁定信息识别与归纳）。

## 特性

- ✅ **智能识 别策略**: 优先提取可编辑文本，扫描件自动 fallback 到 OCR
- ✅ **找到即停**: 责催文件逐页 OCR，识别到责令号立即停止，3 案件 ~20s
- ✅ **多格式支持**: PDF + PNG/JPG/JPEG 图片
- ✅ **超极速处理**: 多进程并行 + 图像预处理优化
- ✅ **轻量快速**: 使用 RapidOCR，启动快、识别准
- ✅ **批量处理**: 支持多文件批量识别
- ✅ **配置驱动**: 换案件材料只需改 `config.yaml`，不需改代码
- ✅ **多种输出**: TXT + JSON 双格式输出 + HTML 验证报告
- ✅ **错误重试**: 自动重试失败的处理任务
- ✅ **断点续跑**: 已有缓存自动跳过，不会清空重跑

## 快速开始

### 1. 克隆仓库

```bash
git clone https://gitcode.com/BluerAngala/pdf-ocr-ai.git
cd pdf-ocr-ai
```

### 2. 准备 Python 环境

本项目使用 **Python 3.12**（见 `.python-version` 文件）。

**Windows（标准库）:**

```bash
python -m venv .venv312
.venv312\Scripts\activate
pip install -r apps/server/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### IDE 配置

- **Trae / VS Code**: 选择 `.venv312\Scripts\python.exe`
- **PyCharm**: 设置 Project Interpreter 为 `.venv312` 目录下的 Python

### 3. 配置 Poppler（Windows 必需）

```bash
python apps/server/scripts/setup_poppler.py
```

### 4. 安装前端依赖

```bash
npm install
```

### 5. 开始使用

```bash
# 通用 OCR 识别
python apps/server/src/pdf_ocr_ultra.py input/document.pdf

# 非诉组流程（Mock 模式，推荐先跑）
python apps/server/scripts/run_non_litigation_flow.py

# 非诉组流程（真实 OCR）
python apps/server/scripts/run_non_litigation_flow.py --real

# 强制重新 OCR（删缓存重跑）
python apps/server/scripts/run_non_litigation_flow.py --real --force
```

## 使用方法

### 通用 OCR

```bash
# 自动选择最佳识别方式
python apps/server/src/pdf_ocr_ultra.py document.pdf

# 识别图片
python apps/server/src/pdf_ocr_ultra.py image.png

# 强制使用 OCR（适用于扫描件）
python apps/server/src/pdf_ocr_ultra.py document.pdf --force-ocr

# 调整 DPI（默认 250，范围 150-300）
python apps/server/src/pdf_ocr_ultra.py document.pdf --dpi 200

# 指定输出目录
python apps/server/src/pdf_ocr_ultra.py document.pdf -o ./results

# 调整并行进程数（默认 4）
python apps/server/src/pdf_ocr_ultra.py document.pdf --workers 6
```


| 参数             | 说明             | 默认值      |
| -------------- | -------------- | -------- |
| `--dpi`        | 图像分辨率，越高越清晰但越慢 | 250      |
| `--max-size`   | 最大图像尺寸（像素）     | 1024     |
| `--workers`    | 并行处理进程数        | 4        |
| `--force-ocr`  | 强制使用 OCR 识别    | False    |
| `-o, --output` | 输出目录           | ./output |


### 非诉组业务流程

1. 将案件材料放入 `样本材料/非诉组自动化样本材料/原始文件/`
2. 台账 Excel 放入 `样本材料/非诉组自动化样本材料/`
3. 根据案件材料修改 `config.yaml`（见下方"换案件材料"章节）
4. 先跑 Mock 模式验证流程：`python apps/server/scripts/run_non_litigation_flow.py`
5. 再跑真实 OCR：`python apps/server/scripts/run_non_litigation_flow.py --real`
6. 查看输出：`output/non-litigation-results/`

## 项目结构

```
pdf-ocr-ai/
├── config.yaml                  # 统一业务配置（文书类型、正则、纠错词表、页数等）
├── package.json                 # Monorepo 根配置（npm workspaces）
├── apps/
│   ├── desktop/                 # Tauri + React 前端
│   │   ├── src/                 # React 组件及服务层
│   │   │   ├── App.tsx          # 主状态容器
│   │   │   ├── components/      # UI 组件（ConfigPanel, PreviewPanel, LogsPanel 等）
│   │   │   └── services/        # JSON-RPC 客户端、系统状态服务
│   │   ├── src-tauri/           # Rust 后端（Python 进程管理、系统调用）
│   │   ├── eslint.config.js     # ESLint flat config（TypeScript + React + Prettier）
│   │   ├── .prettierrc          # Prettier 格式化规则
│   │   └── package.json         # 前端依赖及脚本
│   └── server/                  # Python 后端
│       ├── src/
│       │   ├── server.py            # JSON-RPC 服务端（与 Tauri 通信）
│       │   ├── config_loader.py     # 配置加载器，提供 NonLitigationConfig 对象
│       │   ├── pdf_ocr_ultra.py     # 主程序入口，OCR 核心逻辑
│       │   ├── text_postprocessor.py # OCR 文本后处理（括号统一、纠错、案号规范化）
│       │   ├── non_litigation_product.py    # 非诉组：从台账 Excel 加载案件数据
│       │   ├── non_litigation_output_plan.py # 非诉组：构建期望输出目录结构
│       │   ├── non_litigation_export.py      # 非诉组：PDF 切割/重命名/导出
│       │   ├── non_litigation_validator.py   # 非诉组：识别结果验证
│       │   ├── project_evaluation.py         # 项目质量评估
│       │   └── report_generator.py           # HTML 验证报告生成
│       ├── scripts/                 # 工具脚本（Poppler 安装、模型下载等）
│       ├── tests/                   # 测试用例
│       ├── tools/                   # 外部工具（Poppler 二进制）
│       └── requirements.txt         # Python 依赖
├── docs/                        # 项目文档和设计资料
├── 样本材料/                     # 测试样本（git 忽略）
├── input/                       # 输入文件（git 忽略）
├── output/                      # 识别结果（git 忽略）
└── temp/                        # 临时缓存（git 忽略）
```

## 技术方案


| 方案            | 适用场景    | 速度           | 准确率  |
| ------------- | ------- | ------------ | ---- |
| pdfplumber    | 可编辑 PDF | 极快 (~0.1s)   | 文本精确 |
| RapidOCR      | 扫描件/图片  | 快 (~3-10s/页) | 高    |
| 逐页 OCR + 找到即停 | 责催文件    | ~7s/文件(1页)   | 高    |


## 性能优化

1. **智能策略**: 可编辑 PDF 直接提取文本，跳过 OCR
2. **找到即停**: 责催文件逐页 OCR，识别到责令号立即停止，避免扫描全部页面
3. **图像预处理**: 压缩、对比度增强、锐化
4. **多进程并行**: 多页同时处理，子进程预加载模型
5. **模型预热**: 预加载避免冷启动
6. **断点续跑**: 已有缓存自动跳过，不会清空重跑

## 换案件材料

更换案件材料时，只需修改 `config.yaml`，无需改代码：

1. `regex_patterns.notice_number` — 责令号正则（城市名、文书类别字）
2. `doc_types` — 文书类型列表（关键词、页数、文件名模式、输出目录名）
3. `ocr_corrections.non_litigation` — OCR 常见误识纠错词表
4. `ocr_corrections.company_name_corrections` — 公司名称纠错（替换为本批次公司）
5. `excel_parsing` — 台账 Excel 列索引、过滤关键词
6. `validation.keywords` — 各文书类型校验关键词（所函关键词应改为对应律所名）
7. `paths.files.excel_filename` — 台账文件名（若不同）

## 常见问题

### Q: 提示 "Poppler 未安装"

```bash
python apps/server/scripts/setup_poppler.py
```

### Q: 中文乱码

脚本已内置 UTF-8 编码处理，如仍有问题请确保终端支持 UTF-8。Windows 下可加 `-X utf8` 参数：

```bash
python -X utf8 apps/server/scripts/run_non_litigation_flow.py --real
```

### Q: 识别速度慢

- 责催文件已支持"找到即停"，正常情况下每个文件 ~7s
- 如仍慢，检查 `config.yaml` 中 `NOTICE_PATTERN` 是否匹配当前案件的责令号格式
- 非责催文件：降低 DPI 或减少进程数

### Q: 责催文件识别不到责令号

1. 检查 `config.yaml` 中 `regex_patterns.notice_number` 是否适配当前案件格式
2. 检查 `ocr_corrections.non_litigation` 是否包含当前 OCR 的常见误识
3. 查看 `temp/non-litigation/ocr-cache/` 中的缓存 JSON，确认 OCR 原始文本内容

### Q: 支持哪些图片格式？

支持 PNG、JPG、JPEG 格式的图片直接识别。

## 开发

```bash
# 前端开发（Vite 热更新）
npm run desktop:dev

# Tauri 桌面版开发
npm run desktop:tauri dev

# 前端代码检查
npm run lint

# 前端代码自动修复
npm run lint:fix

# 前端代码格式化
npm run format

# 前端格式检查（CI 用）
npm run format:check

# 运行所有 Python 测试
pytest apps/server/tests/

# 运行非诉组测试
pytest apps/server/tests/non-litigation/

# 运行 Python 测试并生成覆盖率报告
pytest apps/server/tests/ --cov=apps/server/src --cov-report=html
```

## 许可证

MIT License