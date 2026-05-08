# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 环境与依赖

- **Python 3.12**（见 `.python-version`）。仓库里已有 `.venv312/`，默认按这个环境运行。
- 安装依赖：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`
- Windows 需要 Poppler；仓库已包含 `tools/poppler/poppler-24.08.0/`，初始化命令：`python scripts/setup_poppler.py`
- OCR 依赖以 `rapidocr-onnxruntime` 为主，但代码同时兼容 `rapidocr` 的新导入路径。

## 常用命令

```bash
# 通用 PDF/图片 OCR
python src/pdf_ocr_ultra.py input/document.pdf
python src/pdf_ocr_ultra.py input/scanned.png --force-ocr --dpi 200
python src/pdf_ocr_ultra.py input/*.pdf input/*.png -o output

# 项目评估：跑非诉组导出并生成 output/project-evaluation.json
python src/project_evaluation.py

# 运行所有测试
pytest tests/

# 运行非诉组测试
pytest tests/non-litigation/

# 运行单个测试文件
pytest tests/non-litigation/test_non_litigation_export.py

# 运行单个测试用例
pytest tests/non-litigation/test_non_litigation_export.py -k application

# 测试覆盖率
pytest tests/ --cov=src --cov-report=html
```

## 代码架构

### 两条主线

**1. 通用 OCR（`src/pdf_ocr_ultra.py`）**
独立 CLI 工具。核心策略是“先提取、后识别”：优先用 `pdfplumber` 直接抽取可编辑 PDF 文本，只有提取失败、内容不足，或显式传入 `--force-ocr` 时才走 RapidOCR。页级处理支持并行，子进程通过 `init_worker()` 预热 OCR 模型；结果保存为文本预览 + 结构化 JSON。

**2. 非诉组自动化流水线（`src/non_litigation_export.py` 为核心）**
这是仓库里更重要的业务流，面向广州住房公积金非诉材料批处理。输入不是任意 PDF 集，而是带固定目录结构、固定命名约束和 Excel 台账的材料包。处理逻辑：
- **责催证据文件**：每个 PDF 视为单独案件，按责令号识别并重命名，不切页
- **申请书**：优先通过 OCR 识别“强制执行申请书”等标题定位案件边界，失败时回退到固定页数切分
- **授权书 / 所函**：按公司顺序固定一页一份切分
- **审计日志**：导出结果会额外生成 `audit-log.json`，记录映射和处理痕迹

### src/ 模块关系

```
non_litigation_export.py       ← 主流水线入口（切割/重命名 PDF）
    ├── non_litigation_product.py   ← 读取 Excel《台账及命名规则.xlsx》获取案件元数据
    ├── non_litigation_output_plan.py ← 构建预期输出目录树
    ├── text_postprocessor.py        ← OCR 文本后处理（括号统一、常见错别字修正）
    └── pdf_ocr_ultra.py             ← OCR 引擎（按需调用）

smart_extractor.py             ← 带回退机制的字段提取（责令号、申请书信息、公司名）
    └── region_extractor.py    ← 按百分比坐标裁剪页面区域

non_litigation_validator.py    ← 验证 OCR 识别结果质量
report_generator.py            ← 生成 HTML 验证报告
project_evaluation.py          ← 与标准样本对比评估（页数匹配率）
```

### 关键数据路径（非诉组）

- 业务输入目录：`<root>/non-litigation/`，通常包含 `申请书.pdf`、`授权书.pdf`、`所函.pdf` 和多份责催 PDF
- 台账来源：`<sample_root>/台账及命名规则.xlsx`，由 `src/non_litigation_product.py` 读取并转换为案件列表
- 期望输出结构：由 `src/non_litigation_output_plan.py` 基于台账生成
- 实际输出目录：默认 `<root>/non-litigation-results/`，并附带 `audit-log.json`
- 评估基准：`<root>/样本材料/非诉组自动化样本材料/对应输出文件（标准版）/`
- 评估结果：`python src/project_evaluation.py` 会写入 `output/project-evaluation.json`

### 测试说明

- 测试主要集中在 `tests/non-litigation/`
- `tests/non-litigation/conftest.py` 会把 `src/` 注入 `sys.path`，因此源码模块之间大量使用直接导入而不是包导入
- 很多测试依赖真实样本目录和 PDF/Excel 材料，不是纯单元测试；改动非诉流程时，优先跑对应测试文件而不是只看静态代码

### 代码约定与易踩点

- `src/` 目前不是安装型 package，模块通过 `sys.path` 注入和同级直接导入协作，改文件名或导入方式时要连同测试一起检查
- `non_litigation_export.py` 是流程编排中心，里面同时承担路径发现、OCR 缓存、切页、重命名、导出和审计记录，改动这里会波及大部分业务测试
- `text_postprocessor.py` 负责把 OCR 噪声规范化；很多匹配逻辑依赖这里统一括号、数字和常见错字后的文本，不要只看原始 OCR 输出
- `smart_extractor.py` + `region_extractor.py` 是“区域裁剪 + 多轮回退识别”体系，适合处理版式相对固定的字段提取，不是通用 NLP 抽取器

### OCR 与案号匹配

- 代码兼容 `rapidocr_onnxruntime.RapidOCR` 和 `rapidocr.RapidOCR` 两种导入方式
- `src/pdf_ocr_ultra.py` 会优先避免 OCR，只在必要时才识别图片/扫描件；性能问题优先检查是否错误地强制走了 `--force-ocr`
- `NOTICE_PATTERN` / 案号匹配逻辑是整个非诉流程的关键约束，格式围绕“穗公积金中心…责字[年份]编号”展开；如果案号识别异常，先排查后处理和括号归一化，再排查正则
- `project_evaluation.py` 当前核心评估指标是**页数匹配率**，不是逐页内容 diff；它更适合验证切分/命名是否整体正确
