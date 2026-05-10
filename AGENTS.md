# AGENTS.md

## 项目概述

公积金业务辅助工具，基于 RapidOCR + pdfplumber 的 PDF/图片 OCR 识别工具。服务两个业务组：非诉审查组（PDF 批量重命名）和强制执行组（裁定信息识别与归纳）。

## 环境

- **Python 3.12**（`.python-version` 指定，非 3.13）
- 虚拟环境：`.venv312/`（VS Code 已配置该路径）
- Windows 专属项目，Poppler 必须本地配置：`python apps/server/scripts/setup_poppler.py`
- pip 源：`https://pypi.tuna.tsinghua.edu.cn/simple`

## 关键命令

```bash
# 激活环境
.venv312\Scripts\activate

# 安装依赖
pip install -r apps/server/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 运行主程序（OCR 识别）
python apps/server/src/pdf_ocr_ultra.py input/document.pdf

# 非诉组流程（Mock 模式，推荐先跑）
python apps/server/scripts/run_non_litigation_flow.py

# 非诉组流程（真实 OCR）
python apps/server/scripts/run_non_litigation_flow.py --real

# 测试
pytest apps/server/tests/non-litigation/

# 覆盖率
pytest apps/server/tests/ --cov=apps/server/src --cov-report=html

# 前端开发
npm run desktop:dev

# Tauri 桌面版开发
npm run desktop:tauri dev
```

## 架构

```
config.yaml                      # 统一业务配置（文书类型、正则、纠错词表、页数等）
样本材料/                        # 测试样本 PDF 和标准输出
apps/
├── desktop/                     # Tauri + React 前端
│   ├── src/                     # React 组件
│   └── src-tauri/               # Rust 后端（Python 进程管理）
└── server/                      # Python 后端
    ├── src/
    │   ├── server.py            # JSON-RPC 服务端（与 Tauri 通信）
    │   ├── config_loader.py     # 配置加载器，提供 NonLitigationConfig 对象
    │   ├── pdf_ocr_ultra.py     # 主程序入口，OCR 核心逻辑
    │   ├── text_postprocessor.py # OCR 文本后处理（括号统一、纠错、案号规范化）
    │   ├── non_litigation_product.py  # 非诉组：从台账 Excel 加载案件数据
    │   ├── non_litigation_output_plan.py # 非诉组：构建期望输出目录结构
    │   ├── non_litigation_export.py    # 非诉组：PDF 切割/重命名/导出
    │   ├── non_litigation_validator.py # 非诉组：识别结果验证
    │   ├── project_evaluation.py       # 项目质量评估
    │   └── report_generator.py         # HTML 验证报告生成
    ├── scripts/                 # 工具脚本（Poppler 安装、模型下载等）
    ├── tests/                   # 测试用例
    ├── tools/                   # 外部工具（Poppler 二进制）
    └── requirements.txt         # Python 依赖
```

**模块依赖链**：`config_loader` ← 所有非诉组模块；`non_litigation_product` → `non_litigation_output_plan` → `non_litigation_export` → `non_litigation_validator` → `report_generator`

`text_postprocessor` 被 `non_litigation_export` 直接引用。

## 已知问题

无

## 开发注意事项

- `apps/server/src/` 下的模块用 `sys.path.insert` 方式互相导入（无 `__init__.py`、无包安装），测试也靠 `conftest.py` 手动加路径到 `sys.path`
- **所有业务配置集中在根目录 `config.yaml`**，通过 `config_loader.py` 的 `load_config()` 加载。换案件材料只需改 config.yaml，不需改代码
- OCR 纠错词库分两层：通用（`text_postprocessor.py` 中的括号归一化、间距修复）+ 业务特定（`config.yaml` 的 `ocr_corrections`）
- 责催 stop_condition 机制：逐页 OCR → `apply_ocr_corrections` 纠错 → `NOTICE_PATTERN` 匹配 → 命中即停
- `NOTICE_PATTERN` 支持 6 种括号格式：`〔〕` `()` `[]` `［］` `【】` 及混合
- 括号格式：业务默认中文括号 `（）`，匹配时统一后再比较
- `样本材料/` 含测试用的真实样本 PDF 和标准输出，测试依赖这些文件
- 输出到 `output/` 和 `temp/`，均已被 git 忽略
- 断点续跑：已存在的文件/缓存自动跳过，不会清空重跑
- Rust 侧将 Python cwd 设为项目根目录，Python 中 `ROOT` 变量也指向项目根

## 换案件材料检查清单

更换案件材料时，需修改 `config.yaml` 中以下配置项：

1. `regex_patterns.notice_number` — 责令号正则（城市名、文书类别字）
2. `doc_types` — 文书类型列表（关键词、页数、文件名模式、输出目录名）
3. `ocr_corrections.non_litigation` — OCR 常见误识纠错词表
4. `ocr_corrections.company_name_corrections` — 公司名称纠错（替换为本批次公司）
5. `excel_parsing` — 台账 Excel 列索引、过滤关键词
6. `validation.keywords` — 各文书类型校验关键词（所函关键词应改为对应律所名）
7. `paths.files.excel_filename` — 台账文件名（若不同）
