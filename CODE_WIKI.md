# 公积金 OCR 工具 — Code Wiki

> 版本：1.0.0 | 开发者：陈恒律师 | Python 3.12 | Tauri 1.5 + React 19

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [技术栈与依赖](#3-技术栈与依赖)
4. [目录结构](#4-目录结构)
5. [Python 后端模块详解](#5-python-后端模块详解)
6. [Tauri + React 前端详解](#6-tauri--react-前端详解)
7. [模块依赖关系](#7-模块依赖关系)
8. [配置系统 (config.yaml)](#8-配置系统-configyaml)
9. [核心业务流程](#9-核心业务流程)
10. [项目运行方式](#10-项目运行方式)
11. [测试体系](#11-测试体系)
12. [开发注意事项](#12-开发注意事项)

---

## 1. 项目概述

公积金业务辅助工具，基于 **RapidOCR + pdfplumber** 的 PDF/图片 OCR 识别系统。服务两个核心业务组：

| 业务组 | 核心功能 | 输入 | 输出 |
|--------|---------|------|------|
| **非诉审查组** | PDF 批量切割与重命名 | 台账 Excel + 多个 PDF | 按案件分类、按规则命名的 PDF 文件 |
| **强制执行组** | 裁定信息识别与归纳 | 裁定 PDF + 非诉表格 Excel | 合并识别结果的 Excel |

技术架构为 **Tauri 桌面应用**：Rust 管理进程 + React 前端 UI + Python 后端 OCR 引擎，通过 JSON-RPC over stdin/stdout 通信。

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Tauri 桌面应用                         │
│  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │   React 前端 (TSX)    │  │   Rust 后端 (main.rs)     │ │
│  │                      │  │                          │ │
│  │  App.tsx             │  │  init_python_service()   │ │
│  │  ├─ HomeView         │  │  ├─ stdin writer task    │ │
│  │  ├─ ConfigPanel      │  │  ├─ stdout reader task   │ │
│  │  ├─ DetailView       │  │  └─ stderr reader task   │ │
│  │  ├─ PreviewPanel     │  │                          │ │
│  │  ├─ LogsPanel        │  │  Tauri Commands:         │ │
│  │  └─ StatusBar        │  │  ├─ send_jsonrpc_request │ │
│  │                      │  │  ├─ select_folder        │ │
│  │  Services:           │  │  ├─ select_files         │ │
│  │  ├─ jsonrpc.ts       │  │  ├─ open_path            │ │
│  │  ├─ system.ts        │  │  └─ get_project_root_cmd │ │
│  │  ├─ presets.ts       │  │                          │ │
│  │  └─ types.ts         │  │                          │ │
│  └──────────┬───────────┘  └────────────┬─────────────┘ │
│             │ Tauri invoke               │ stdin/stdout  │
│             └────────────┬───────────────┘              │
└──────────────────────────┼──────────────────────────────┘
                           │ JSON-RPC
┌──────────────────────────┼──────────────────────────────┐
│               Python 后端 (server.py)                    │
│                          │                               │
│  ┌───────────────────────┴──────────────────────────┐   │
│  │              JsonRpcServer                        │   │
│  │  注册方法:                                        │   │
│  │  ├─ ocr.recognize          (OCR 识别)            │   │
│  │  ├─ non_litigation.process (非诉组处理)           │   │
│  │  ├─ enforcement.extract    (强制执行提取)         │   │
│  │  ├─ company_query.process  (企业查询)             │   │
│  │  ├─ print.process          (打印)                 │   │
│  │  ├─ system.get_status      (系统状态)             │   │
│  │  └─ config.get             (获取配置)             │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │  OCR 引擎层      │  │  业务逻辑层                   │  │
│  │                 │  │                              │  │
│  │  pdf_ocr_ultra  │  │  non_litigation_* (4模块)    │  │
│  │  region_extractor│  │  enforcement_* (3模块)      │  │
│  │  smart_extractor │  │  company_query              │  │
│  │  text_postprocessor│ │  print_service             │  │
│  └─────────────────┘  └──────────────────────────────┘  │
│                                                          │
│  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │  基础设施层      │  │  评估与报告层                  │  │
│  │                 │  │                              │  │
│  │  config_loader  │  │  project_evaluation          │  │
│  │  paths          │  │  report_generator            │  │
│  │  system_resource│  │  non_litigation_validator    │  │
│  └─────────────────┘  └──────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 通信机制

```
React 前端 ──Tauri invoke──▶ Rust 后端 ──stdin──▶ Python 进程
                                        ◀──stdout──  (JSON-RPC Response)
                                        ◀──stderr──  (Progress Notification)
```

- **请求通道**：React → `invoke('send_jsonrpc_request', { request })` → Rust → Python stdin
- **响应通道**：Python stdout → Rust → Tauri Event `jsonrpc-response` → React
- **通知通道**：Python stderr → Rust → Tauri Event `jsonrpc-notification` → React

---

## 3. 技术栈与依赖

### Python 后端

| 依赖 | 版本 | 用途 |
|------|------|------|
| rapidocr-onnxruntime | ≥1.3.0 | 轻量级 ONNX 推理 OCR 引擎 |
| pdfplumber | ≥0.9.0 | 可编辑 PDF 文本直接提取 |
| pdf2image | ≥1.16.0 | PDF 转图片（需 Poppler） |
| pypdf | ≥4.0.0 | PDF 切割与操作 |
| openpyxl | ≥3.1.0 | Excel 读写 |
| pandas | (间接) | 数据处理（enforcement 模块） |
| Pillow | ≥9.0.0 | 图像处理 |
| numpy | ≥1.21.0 | 数值计算 |
| requests | ≥2.28.0 | HTTP 请求（企业查询 API） |
| pytest | ≥8.0.0 | 测试框架 |

### 前端

| 依赖 | 版本 | 用途 |
|------|------|------|
| React | ^19.2.6 | UI 框架 |
| @tauri-apps/api | ^1.5.3 | Tauri JS API |
| Tailwind CSS | ^3.4.19 | 样式框架 |
| Vite | ^5.0.0 | 构建工具 |
| TypeScript | ^5.3.0 | 类型系统 |

### Rust 后端

| 依赖 | 版本 | 用途 |
|------|------|------|
| tauri | 1.5.4 | 桌面应用框架 |
| serde / serde_json | 1.0 | 序列化 |
| tokio | 1.35 | 异步运行时 |

---

## 4. 目录结构

```
pdf识别/
├── config.yaml                      # 统一业务配置
├── AGENTS.md                        # 项目开发规范
├── 样本材料/                        # 测试样本 PDF 和标准输出
│
├── apps/
│   ├── desktop/                     # Tauri + React 前端
│   │   ├── src/
│   │   │   ├── App.tsx              # 主应用组件
│   │   │   ├── main.tsx             # 入口
│   │   │   ├── types.ts             # TypeScript 类型定义
│   │   │   ├── constants.ts         # 常量与模块配置
│   │   │   ├── presets.ts           # 预设配置
│   │   │   ├── style.css            # 全局样式
│   │   │   ├── components/
│   │   │   │   ├── configs/         # 各模块配置面板
│   │   │   │   │   ├── NonLitigationConfig.tsx
│   │   │   │   │   ├── EnforcementConfig.tsx
│   │   │   │   │   ├── CompanyQueryConfig.tsx
│   │   │   │   │   └── PrintConfig.tsx
│   │   │   │   ├── results/         # 各模块结果展示
│   │   │   │   │   ├── NonLitigationResult.tsx
│   │   │   │   │   ├── EnforcementResult.tsx
│   │   │   │   │   ├── CompanyQueryResult.tsx
│   │   │   │   │   └── PrintCardGrid.tsx
│   │   │   │   ├── ConfigPanel.tsx   # 配置面板容器
│   │   │   │   ├── DetailView.tsx    # 详情视图
│   │   │   │   ├── HomeView.tsx      # 首页视图
│   │   │   │   ├── LogsPanel.tsx     # 日志面板
│   │   │   │   ├── PreviewPanel.tsx  # 预览面板
│   │   │   │   ├── StatusBar.tsx     # 状态栏
│   │   │   │   └── SystemStatusModal.tsx # 系统状态弹窗
│   │   │   └── services/
│   │   │       ├── jsonrpc.ts        # JSON-RPC 客户端
│   │   │       └── system.ts         # 系统状态服务
│   │   ├── src-tauri/
│   │   │   ├── src/
│   │   │   │   └── main.rs           # Rust 后端入口
│   │   │   └── Cargo.toml
│   │   └── package.json
│   │
│   └── server/                      # Python 后端
│       ├── src/
│       │   ├── server.py            # JSON-RPC 服务端
│       │   ├── config_loader.py     # 配置加载器
│       │   ├── pdf_ocr_ultra.py     # OCR 核心引擎
│       │   ├── text_postprocessor.py # 文本后处理器
│       │   ├── region_extractor.py  # 区域提取器
│       │   ├── smart_extractor.py   # 智能提取器
│       │   ├── non_litigation_product.py   # 非诉组：案件加载
│       │   ├── non_litigation_output_plan.py # 非诉组：输出规划
│       │   ├── non_litigation_export.py     # 非诉组：导出核心
│       │   ├── non_litigation_validator.py  # 非诉组：验证器
│       │   ├── enforcement_product.py   # 强制执行组：台账
│       │   ├── enforcement_extractor.py # 强制执行组：信息提取
│       │   ├── enforcement_export.py    # 强制执行组：导出
│       │   ├── company_query.py     # 企业查询服务
│       │   ├── print_service.py     # 打印服务
│       │   ├── system_resource.py   # 系统资源检测
│       │   ├── paths.py             # 路径管理
│       │   ├── project_evaluation.py # 项目质量评估
│       │   └── report_generator.py  # 报告生成器
│       ├── scripts/                 # 工具脚本
│       │   ├── run_non_litigation_flow.py  # 非诉组流程脚本
│       │   └── setup_poppler.py     # Poppler 安装脚本
│       ├── tests/                   # 测试用例
│       │   ├── non-litigation/      # 非诉组测试
│       │   └── test_coze_company_query.py
│       ├── tools/                   # 外部工具（Poppler 二进制）
│       └── requirements.txt
│
├── output/                          # 运行输出（git 忽略）
└── temp/                            # 临时文件（git 忽略）
```

---

## 5. Python 后端模块详解

### 5.1 server.py — JSON-RPC 服务端

**职责**：作为 Python 进程的入口，通过 stdin/stdout 接收和返回 JSON-RPC 消息，通过 stderr 发送进度通知，是前后端通信的桥梁。

#### 关键类

| 类名 | 说明 |
|------|------|
| `JsonRpcServer` | JSON-RPC 服务端核心，管理方法注册与请求分发 |
| `ProgressEmitter` | 进度通知发射器，通过 stderr 向前端推送进度 |

#### JsonRpcServer 关键方法

| 方法 | 说明 |
|------|------|
| `register_method(name, handler)` | 注册 RPC 方法 |
| `handle_request(request)` | 处理单个 JSON-RPC 请求 |
| `run()` | 主循环，从 stdin 读取请求并处理 |

#### 注册的 RPC 方法

| 方法名 | 功能 | 参数 |
|--------|------|------|
| `ocr.recognize` | 单文件 OCR 识别 | `file_path` |
| `non_litigation.process` | 非诉组完整处理流程 | `sample_dir`, `excel_path`, `output_dir`, `use_mock`, `preset_id` |
| `enforcement.extract` | 强制执行组信息提取 | `input_dir`, `excel_path`, `output_dir` |
| `company_query.process` | 企业信息查询 | `excel_path`, `output_dir` |
| `print.process` | PDF 批量打印 | `folder_path`, `printer_name`, `copies` |
| `system.get_status` | 获取系统状态与依赖检查 | 无 |
| `config.get` | 获取当前配置 | 无 |

#### ProgressEmitter

```python
emitter.progress(phase, current, total, message)
# 输出到 stderr: {"jsonrpc": "2.0", "method": "progress", "params": {...}}
```

#### 预设路径系统

`server.py` 内置了预设路径映射，支持通过 `preset_id` 快速选择批次材料：

- `PRESET_SAMPLE_PATHS`：预设样本目录路径
- `PRESET_EXCEL_PATHS`：预设台账文件路径

---

### 5.2 pdf_ocr_ultra.py — OCR 核心引擎

**职责**：提供双引擎 OCR 能力，支持 PDF 和图片的文本识别，是整个系统的 OCR 基础设施。

#### 关键数据类

| 类名 | 字段 | 说明 |
|------|------|------|
| `OCRConfig` | `dpi`, `max_image_size`, `parallel_workers`, `small_pdf_page_threshold` | OCR 配置参数 |
| `PageResult` | `page_num`, `text`, `confidence`, `method`, `duration` | 单页识别结果 |

#### 关键类

##### `UltraFastOCR`

核心 OCR 引擎类，封装了双引擎策略和并行处理逻辑。

| 方法 | 说明 |
|------|------|
| `process_pdf(pdf_path, stop_condition)` | 处理整个 PDF，支持停止条件回调 |
| `process_pdf_pages_sequential(pdf_path, stop_condition)` | 逐页顺序处理（用于责催停止条件） |
| `process_image(image_path)` | 处理单张图片 |
| `_try_pdfplumber(pdf_path)` | 尝试 pdfplumber 直接提取（可编辑 PDF） |
| `_process_single_image(image, page_num)` | 单页图片 OCR 识别 |

**双引擎策略**：

```
输入 PDF
  │
  ├─ 尝试 pdfplumber 直接提取（可编辑 PDF，速度快）
  │   └─ 成功 → 返回文本
  │
  └─ 失败 → PDF 转图片 → RapidOCR 识别
      ├─ 页数 ≤ threshold → 顺序处理
      └─ 页数 > threshold → 多进程 Pool 并行处理
```

##### `ImagePreprocessor`

图像预处理器，提升 OCR 识别率。

| 方法 | 说明 |
|------|------|
| `preprocess(image)` | 执行预处理流水线（缩放、灰度等） |

**停止条件机制**：`process_pdf_pages_sequential()` 接受 `stop_condition` 回调函数，每页识别后调用，返回 `True` 时停止后续页面识别。用于责催文书的"命中即停"逻辑。

---

### 5.3 config_loader.py — 配置加载器

**职责**：加载 `config.yaml` 并提供结构化的配置对象，是所有业务模块的配置来源。

#### 关键数据类

##### `DocTypeConfig`

| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | str | 文书类型标识（如 "责催"、"申请书"） |
| `source_pdf` | Optional[str] | 来源 PDF 文件名 |
| `output_dir` | str | 输出目录名 |
| `pages_per_case` | Optional[int] | 每案件页数 |
| `boundary_keywords` | List[str] | 边界识别关键词 |
| `validation_keywords` | List[str] | 验证关键词 |
| `filename_pattern` | str | 输出文件名模式 |
| `is_notice` | bool | 是否为责催类文书 |
| `content_marker` | Optional[str] | 内容标记关键词 |

##### `NonLitigationConfig`

包含 50+ 配置字段的结构化配置对象，主要分组：

| 配置组 | 字段示例 | 说明 |
|--------|---------|------|
| 路径配置 | `result_dirname`, `temp_dirname`, `excel_filename` | 输入输出路径 |
| 文书类型 | `doc_types: List[DocTypeConfig]` | 文书类型列表 |
| 正则模式 | `notice_pattern`, `court_case_pattern` | 匹配正则 |
| OCR 纠错 | `ocr_corrections`, `company_name_corrections` | 纠错词表 |
| Excel 解析 | `column_original_notice`, `filter_keywords` | 台账列映射 |
| 验证配置 | `fuzzy_match_threshold`, `text_quality` | 验证参数 |
| OCR 引擎 | `dpi`, `max_image_size`, `parallel_workers` | 引擎参数 |
| 优化配置 | `enable_region_first`, `notice_scan_window_pages` | 区域优先策略 |
| 并行配置 | `auto_detect_resources`, `max_parallel_workers` | 并行参数 |

#### 关键函数

| 函数 | 返回值 | 说明 |
|------|--------|------|
| `load_config()` | `NonLitigationConfig` | 加载配置并返回结构化对象 |
| `_load_config()` | dict | 加载原始 YAML 字典（内部使用） |

---

### 5.4 text_postprocessor.py — 文本后处理器

**职责**：对 OCR 识别出的原始文本进行后处理，包括括号统一、常见错误纠错、案号提取与规范化、公司名称优化等。

#### 关键类：`TextPostProcessor`

| 方法 | 说明 |
|------|------|
| `normalize_brackets(text)` | 统一括号格式（6 种括号 → 标准格式） |
| `correct_common_errors(text)` | 通用 OCR 纠错 |
| `extract_and_format_case_numbers(text)` | 提取并格式化案号 |
| `optimize_company_names(text)` | 优化公司名称（去除多余空格等） |
| `extract_decision_numbers(text)` | 提取决定书编号 |
| `expand_decision_number_ranges(text)` | 展开决定书编号范围（如 "3360号至3365号"） |
| `extract_ruling_fields(text)` | 提取裁定书字段（案号、当事人、金额等） |
| `extract_notice_fields(text)` | 提取责催字段（责令号、公司名等） |
| `extract_contract_fields(text)` | 提取合同字段 |
| `build_structured_output(text, doc_type)` | 构建结构化输出 |
| `process(text)` | 完整处理流水线 |

**处理流水线**：

```
原始 OCR 文本
  → normalize_brackets()     括号统一
  → correct_common_errors()  通用纠错
  → extract_and_format_case_numbers()  案号提取
  → optimize_company_names() 公司名称优化
  → build_structured_output() 结构化输出
```

**支持的括号格式**：`〔〕` `()` `[]` `［］` `【】` 及混合格式，统一后比较。

---

### 5.5 region_extractor.py — 区域提取器

**职责**：从 PDF 页面中提取指定区域（如页眉、页中、页脚）的图片，用于区域优先 OCR 策略。

#### 关键数据类

##### `Region`

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 区域名称 |
| `x_percent` | float | 左上角 X 百分比 |
| `y_percent` | float | 左上角 Y 百分比 |
| `width_percent` | float | 宽度百分比 |
| `height_percent` | float | 高度百分比 |

#### 预定义区域

| 区域名 | 位置 | 用途 |
|--------|------|------|
| `notice_header` | 页面顶部 | 责催文书责令号提取 |
| `application_title` | 页面上部 | 申请书标题识别 |
| `company_middle` | 页面中部 | 公司名称识别 |
| `company_top` | 页面上部 | 授权书/所函顶部信息 |
| `company_bottom` | 页面底部 | 授权书/所函底部信息 |

#### 关键类：`RegionExtractor`

| 方法 | 说明 |
|------|------|
| `extract_region(pdf_path, page_num, region)` | 从 PDF 指定页提取区域图片 |
| `extract_regions(pdf_path, page_num, regions)` | 批量提取多个区域 |

---

### 5.6 smart_extractor.py — 智能提取器

**职责**：实现带回退机制的智能区域识别，提供责令号、申请书信息、公司名称的鲁棒提取。

#### 关键数据类

##### `ExtractionResult`

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 是否成功 |
| `value` | Optional[str] | 提取值 |
| `method` | str | 使用的方法（如 "pdfplumber", "region_ocr", "full_page_ocr"） |
| `page` | Optional[int] | 所在页码 |
| `region` | Optional[str] | 区域名称 |
| `fallback` | bool | 是否使用了回退方案 |
| `duration` | float | 耗时（秒） |

#### 关键类

| 类名 | 说明 |
|------|------|
| `NoticeNumberExtractor` | 责令号提取器，三级回退：pdfplumber → 区域 OCR → 全页 OCR |
| `ApplicationInfoExtractor` | 申请书信息提取器 |
| `CompanyNameExtractor` | 公司名称提取器 |

**三级回退策略**：

```
1. pdfplumber 直接提取（最快，适用于可编辑 PDF）
   ↓ 失败
2. 区域 OCR（只识别页眉/标题区域，速度快）
   ↓ 失败
3. 全页 OCR（最慢，但最可靠）
```

---

### 5.7 non_litigation_product.py — 非诉组案件加载

**职责**：从台账 Excel 加载案件数据，构建案件列表，是非诉组流程的数据入口。

#### 关键函数

| 函数 | 说明 |
|------|------|
| `load_non_litigation_cases(excel_path, config)` | 从 Excel 加载案件，返回案件列表 |
| `build_non_litigation_standard_plan(cases, config)` | 构建期望输出目录结构 |

#### 案例数据结构

每个案件包含：
- `original_notice`：原始责令号
- `renamed_notice`：重命名后责令号
- `company_name`：公司名称
- `sequence`：序号

---

### 5.8 non_litigation_output_plan.py — 非诉组输出规划

**职责**：根据案件数据和文书类型配置，构建期望的输出文件名列表。

#### 关键函数

| 函数 | 说明 |
|------|------|
| `build_expected_output_tree(cases, config)` | 构建期望输出树，映射文书类型到文件名列表 |

输出示例：
```
输出文件（责催）/
  1-责催-穗公积金中心越秀责字〔2024〕3360号.pdf
  2-责催-穗公积金中心越秀责字〔2024〕3361号.pdf
输出文件（申请书）/
  1-申请书pdf-穗公积金中心越秀责字〔2024〕3360号.pdf
```

---

### 5.9 non_litigation_export.py — 非诉组导出核心

**职责**：非诉组最核心的模块（约 1590 行），实现完整的 PDF 切割、重命名、导出流水线。

#### 核心函数

| 函数 | 说明 |
|------|------|
| `export_non_litigation_standard_outputs(...)` | 主入口，编排完整导出流程 |
| `build_real_ocr_cache(sample_dir, config, emitter)` | 构建真实 OCR 缓存（多进程） |
| `build_mock_ocr_cache(sample_dir, config, emitter)` | 构建 Mock OCR 缓存（测试用） |
| `run_real_ocr_on_pdf(pdf_path, config)` | 对单个 PDF 执行区域优先 OCR |
| `export_notice_files(cases, ocr_cache, config, output_dir, emitter)` | 导出责催文件（按责令号切割重命名） |
| `export_application_files(cases, ocr_cache, config, output_dir, emitter)` | 导出申请书文件（按边界切割） |
| `export_company_named_files(doc_type, cases, ocr_cache, config, output_dir, emitter)` | 导出授权书/所函（按固定页数切割） |

#### OCR 纠错函数

| 函数 | 说明 |
|------|------|
| `apply_ocr_corrections(text, config)` | 应用业务 OCR 纠错词表 |

#### 责令号匹配函数

| 函数 | 说明 |
|------|------|
| `fuzzy_match_notice(ocr_text, expected_notice, threshold)` | 模糊匹配责令号 |
| `normalize_notice_number(notice)` | 规范化责令号（统一括号格式） |
| `_score_notice_candidate(candidate, expected)` | 计算责令号候选匹配分数 |
| `_select_notice_candidate(candidates, expected)` | 选择最佳责令号候选 |

#### 回退决策函数

| 函数 | 说明 |
|------|------|
| `_should_fallback_notice(ocr_text, config)` | 判断责催是否需要回退到全页 OCR |
| `_should_fallback_application(ocr_text, config)` | 判断申请书是否需要回退 |
| `_should_fallback_company_doc(ocr_text, config)` | 判断授权书/所函是否需要回退 |

#### 区域优先 OCR 流程

```
PDF 文件
  │
  ├─ 1. 检查 OCR 缓存（已存在则跳过）
  │
  ├─ 2. 区域优先 OCR
  │   ├─ 提取指定区域图片
  │   ├─ 区域 OCR 识别
  │   └─ 匹配目标模式（责令号/标题/公司名）
  │
  ├─ 3. 回退判断
  │   ├─ 区域结果文本过短 → 全页 OCR
  │   └─ 区域结果未匹配 → 全页 OCR
  │
  └─ 4. 缓存结果（JSON 文件）
```

---

### 5.10 non_litigation_validator.py — 非诉组验证器

**职责**：验证非诉组导出结果的正确性，包括文件完整性、内容关键词、文本质量等。

#### 关键函数

| 函数 | 说明 |
|------|------|
| `validate_export_results(output_dir, cases, config)` | 验证导出结果 |
| `check_file_completeness(output_dir, expected_files)` | 检查文件完整性 |
| `check_content_keywords(file_path, keywords)` | 检查内容关键词 |
| `assess_text_quality(text, doc_type, config)` | 评估文本质量 |

---

### 5.11 enforcement_product.py — 强制执行组台账

**职责**：从非诉表格 Excel 加载强制执行案件数据，提供案件查询和匹配功能。

#### 关键数据类

##### `EnforcementCase`

| 字段 | 类型 | 说明 |
|------|------|------|
| `region` | str | 区域 |
| `notice_number` | str | 责令号 |
| `respondent` | str | 被执行人 |
| `employee` | str | 职工 |
| `amount` | Optional[float] | 金额 |
| `due_date` | str | 到期日 |
| `court_case_number` | str | 受理案号（待填充） |
| `judge` | str | 法官（待填充） |
| `ruling_result` | str | 裁定结果（待填充） |
| `applicants` | List[Dict] | 申请执行人 |
| `ruling_date` | Optional[str] | 裁定日期 |
| `clerk` | str | 书记员 |
| `execution_amount` | Optional[float] | 执行标的金额 |

##### `EnforcementCaseRegistry`

案件登记簿，维护三个索引：

| 索引 | 类型 | 说明 |
|------|------|------|
| `_notice_index` | Dict[str, EnforcementCase] | 责令号索引 |
| `_respondent_index` | Dict[str, List[EnforcementCase]] | 被执行人索引 |
| `_court_case_index` | Dict[str, EnforcementCase] | 法院案号索引 |

#### 关键函数

| 函数 | 说明 |
|------|------|
| `load_enforcement_cases(excel_path)` | 从 Excel 加载案件到 Registry |

---

### 5.12 enforcement_extractor.py — 强制执行组信息提取

**职责**：从裁定 PDF 中提取关键信息，包括案号、当事人、执行标的、日期、审判员等。

#### 关键工具函数

| 函数 | 说明 |
|------|------|
| `remove_cjk_spacing(text)` | 移除中文字符间排版间距（多轮替换直至稳定） |
| `chinese_digits_to_int(text)` | 中文数字转整数（如 "二〇二五" → 2025） |
| `chinese_date_to_arabic(text)` | 中文日期转阿拉伯数字日期 |

#### 关键数据类

##### `RulingInfo`

| 字段 | 类型 | 说明 |
|------|------|------|
| `court_case_number` | Optional[str] | 法院案号 |
| `notice_numbers` | List[str] | 责令号列表 |
| `applicants` | List[Dict] | 申请执行人 |
| `respondents` | List[Dict] | 被执行人 |
| `execution_amount` | Optional[float] | 执行标的金额 |
| `ruling_date` | Optional[str] | 裁定日期 |
| `judge` | Optional[str] | 审判员 |
| `clerk` | Optional[str] | 书记员 |
| `ruling_result` | Optional[str] | 裁定结果 |
| `is_withdrawn` | bool | 是否撤回执行 |

#### 关键类：`RulingPDFExtractor`

| 方法 | 说明 |
|------|------|
| `extract(pdf_path)` | 从裁定 PDF 提取完整信息 |
| `_extract_amount(text)` | 提取执行标的金额 |
| `_extract_date(text)` | 提取裁定日期 |
| `_extract_judge(text)` | 提取审判员 |
| `_extract_court_case_number(text)` | 提取法院案号 |
| `_extract_notice_numbers(text)` | 提取责令号（支持范围展开） |
| `_detect_withdrawal(text)` | 检测撤回执行 |

#### 便捷函数

| 函数 | 说明 |
|------|------|
| `extract_ruling_from_pdf(pdf_path)` | 便捷函数，创建提取器并提取 |

---

### 5.13 enforcement_export.py — 强制执行组导出

**职责**：批量处理裁定 PDF，提取信息并与台账匹配，导出合并后的 Excel。

#### 关键函数

| 函数 | 说明 |
|------|------|
| `build_output_excel(registry, pdf_results, output_path)` | 构建输出 Excel（台账字段 + OCR 字段） |
| `_match_case_to_pdf(case, pdf_results)` | 将台账案件与 PDF 提取结果匹配 |
| `_sort_rows_by_region(rows)` | 按区域排序输出行 |

**输出 Excel 列**：区号 | 行政审查案号 | 责令号 | 被执行人 | 职工姓名 | 金额 | 法官/法官助理 | 执行时间 | 裁定结果 | 备注

---

### 5.14 company_query.py — 企业查询服务

**职责**：通过 Coze API 查询企业信息，支持批量查询、缓存和取消操作。

#### 关键函数

| 函数 | 说明 |
|------|------|
| `query_company_info(company_name, config)` | 查询单个企业信息 |
| `process_company_query(excel_path, output_dir, emitter)` | 批量处理企业查询 |
| `request_cancel(task_id)` | 请求取消查询任务 |
| `is_cancelled(task_id)` | 检查任务是否已取消 |

#### 特性

- **Coze API 集成**：通过配置的 API URL、Token、Workflow ID 调用
- **本地缓存**：查询结果缓存到 `output/company_query_cache_*.json`
- **取消机制**：基于线程安全的 `_cancel_flags` 字典
- **请求延迟**：可配置的请求间隔（默认 0.5 秒）

---

### 5.15 print_service.py — 打印服务

**职责**：提供 PDF 批量打印功能，基于 Windows Shell API。

#### 关键函数

| 函数 | 说明 |
|------|------|
| `list_printers()` | 列出可用打印机 |
| `_print_pdf(pdf_path, printer_name, copies)` | 打印单个 PDF |
| `process_print(folder_path, printer_name, copies, emitter)` | 批量打印文件夹内 PDF |

#### 特性

- 依赖 `win32print` / `win32api`（Windows 专属）
- 自动枚举本地和网络打印机
- 支持指定打印份数

---

### 5.16 system_resource.py — 系统资源检测

**职责**：自动检测系统 CPU 和内存资源，计算推荐的并行 Worker 数量和安全级别。

#### 关键数据类

##### `ResourceProfile`

| 字段 | 类型 | 说明 |
|------|------|------|
| `cpu_count` | int | CPU 核心数 |
| `memory_gb` | float | 可用内存（GB） |
| `recommended_workers` | int | 推荐并行 Worker 数 |
| `safety_level` | str | 安全级别（"safe"/"moderate"/"aggressive"） |

#### 关键函数

| 函数 | 说明 |
|------|------|
| `detect_system_resources()` | 检测系统资源并返回 ResourceProfile |

**安全级别计算**：

| 级别 | 条件 | 推荐 Workers |
|------|------|-------------|
| safe | 内存 ≥ 8GB | min(cpu_count, max_workers) |
| moderate | 内存 ≥ 4GB | min(cpu_count - 1, max_workers) |
| aggressive | 内存 < 4GB | min(cpu_count - 2, 2) |

---

### 5.17 paths.py — 路径管理

**职责**：统一管理项目路径，支持开发模式和打包（frozen）模式。

#### 关键常量

| 常量 | 说明 |
|------|------|
| `ROOT` | 项目根目录 |
| `SERVER_SRC` | Python 后端源码目录 |
| `RESOURCES_DIR` | 资源目录 |
| `USER_DATA_DIR` | 用户数据目录 |

#### 环境变量覆盖

| 环境变量 | 覆盖目标 |
|----------|---------|
| `GJJ_OCR_ROOT` | 项目根目录 |
| `GJJ_OCR_RESOURCES` | 资源目录 |
| `GJJ_OCR_USER_DATA` | 用户数据目录 |

**模式检测**：通过 `getattr(sys, 'frozen', False)` 判断是否为打包模式，打包模式下路径指向 `_internal` 目录。

---

### 5.18 project_evaluation.py — 项目质量评估

**职责**：评估非诉组输出质量，与标准输出对比，收集 OCR 性能指标。

#### 关键函数

| 函数 | 说明 |
|------|------|
| `evaluate_non_litigation_quality(output_dir, standard_dir, config)` | 评估输出质量（按页数对比） |
| `collect_ocr_speed_metrics(ocr_cache_dir)` | 收集 OCR 速度指标 |
| `run_project_evaluation(output_dir, standard_dir, ocr_cache_dir, config)` | 完整评估流水线 |

---

### 5.19 report_generator.py — 报告生成器

**职责**：生成 HTML 格式的验证报告，包含摘要卡片、计时表格、文件详情等。

#### 关键数据类

##### `ReportData`

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | str | 报告标题 |
| `summary` | dict | 摘要信息 |
| `timing` | dict | 计时信息 |
| `file_details` | List[dict] | 文件详情列表 |

#### 关键类：`HTMLReportGenerator`

| 方法 | 说明 |
|------|------|
| `generate(report_data)` | 生成 HTML 报告字符串 |

#### 便捷函数

| 函数 | 说明 |
|------|------|
| `generate_html_report(report_data, output_path)` | 生成并保存 HTML 报告 |

---

## 6. Tauri + React 前端详解

### 6.1 Rust 后端 (main.rs)

**职责**：管理 Python 子进程的生命周期，作为 React 前端与 Python 后端之间的桥梁。

#### 关键函数

| 函数 | 说明 |
|------|------|
| `init_python_service()` | 启动 Python 子进程，建立 stdin/stdout/stderr 管道 |
| `send_jsonrpc_request(request)` | Tauri Command：发送 JSON-RPC 请求到 Python |
| `select_folder()` | Tauri Command：打开文件夹选择对话框 |
| `select_files()` | Tauri Command：打开文件选择对话框 |
| `open_path(path)` | Tauri Command：在系统文件管理器中打开路径 |
| `get_project_root_cmd()` | Tauri Command：获取项目根目录 |

#### Python 进程管理

```
init_python_service()
  │
  ├─ 检测运行模式（bundled vs development）
  │   ├─ bundled: 使用内置 Python 路径
  │   └─ development: 使用 .venv312/Scripts/python.exe
  │
  ├─ 启动 Python 子进程（server.py）
  │   ├─ stdin pipe  ← 写入请求
  │   ├─ stdout pipe → 读取响应
  │   └─ stderr pipe → 读取通知
  │
  └─ 启动三个异步任务
      ├─ stdin writer task:  发送 JSON-RPC 请求
      ├─ stdout reader task: 接收 JSON-RPC 响应 → emit event
      └─ stderr reader task: 接收进度通知 → emit event
```

#### 事件系统

| 事件名 | 方向 | 数据 |
|--------|------|------|
| `jsonrpc-response` | Rust → React | JSON-RPC 响应对象 |
| `jsonrpc-notification` | Rust → React | 进度通知对象 |

---

### 6.2 React 前端

#### App.tsx — 主应用组件

**职责**：管理应用状态、模块切换、处理流程编排。

**状态管理**：

| 状态 | 类型 | 说明 |
|------|------|------|
| `currentModule` | ModuleType | 当前活动模块 |
| `isProcessing` | boolean | 是否正在处理 |
| `progress` | object | 进度信息 |
| `result` | ProcessingResult | 处理结果 |
| `systemStatus` | SystemStatus | 系统状态 |

**模块类型**：

| 模块 | key | 说明 |
|------|-----|------|
| 非诉审查 | `non-litigation` | PDF 批量重命名 |
| 强制执行 | `enforcement` | 裁定信息提取 |
| 企业查询 | `company-query` | 企业信息查询 |
| 打印 | `print` | PDF 批量打印 |

#### types.ts — 类型定义

核心 TypeScript 接口：

| 接口 | 说明 |
|------|------|
| `ModuleType` | 模块类型联合 |
| `ProcessingResult` | 处理结果（含各模块子类型） |
| `EnforcementExtracted` | 强制执行提取结果 |
| `CompanyQueryItem` | 企业查询结果项 |
| `PrintFileItem` | 打印文件项 |
| `SystemStatus` | 系统状态 |
| `ProgressInfo` | 进度信息 |

#### constants.ts — 常量配置

| 常量 | 说明 |
|------|------|
| `MODULE_CONFIG` | 模块配置映射（标题、预设 ID） |
| `PHASE_NAMES` | 阶段名称映射（中文显示名） |

#### presets.ts — 预设配置

5 个预设定义，每个包含：
- `id`：预设标识
- `name`：预设名称
- `samplePath`：样本目录相对路径
- `excelPath`：台账文件相对路径

| 函数 | 说明 |
|------|------|
| `buildPresets(projectRoot)` | 从项目根目录构建完整预设路径 |
| `getPresets()` | 异步加载预设（通过 Tauri 获取项目根目录） |

#### services/jsonrpc.ts — JSON-RPC 客户端

| 函数 | 说明 |
|------|------|
| `sendRequest(method, params)` | 发送 JSON-RPC 请求（Tauri invoke，浏览器环境回退到 mock） |
| `setupJsonRpcListeners()` | 设置 Tauri 事件监听（响应 + 通知） |
| `mockResponse(method)` | 浏览器环境的 Mock 响应 |

**请求流程**：

```
sendRequest(method, params)
  │
  ├─ Tauri 环境
  │   └─ invoke('send_jsonrpc_request', { request })
  │       → Rust → Python stdin
  │       → Python stdout → Rust → event → callback
  │
  └─ 浏览器环境
      └─ mockResponse(method)  // 返回模拟数据
```

#### services/system.ts — 系统状态服务

| 函数 | 说明 |
|------|------|
| `fetchSystemStatus()` | 获取系统状态和依赖检查结果 |

#### 组件结构

```
App.tsx
  ├─ HomeView          首页：模块选择卡片
  ├─ ConfigPanel       配置面板：根据模块渲染对应配置组件
  │   ├─ NonLitigationConfig   非诉组配置
  │   ├─ EnforcementConfig     强制执行组配置
  │   ├─ CompanyQueryConfig    企业查询配置
  │   └─ PrintConfig           打印配置
  ├─ DetailView        详情视图：处理进度与结果
  ├─ PreviewPanel      预览面板：文件预览
  ├─ LogsPanel         日志面板：实时日志
  ├─ StatusBar         状态栏：系统状态
  └─ SystemStatusModal 系统状态弹窗
```

---

## 7. 模块依赖关系

### Python 后端依赖图

```
config_loader ←──────────────────── 所有业务模块
     │
     ├─→ non_litigation_product
     │       │
     │       ├─→ non_litigation_output_plan
     │       │       │
     │       │       └─→ non_litigation_export ──→ text_postprocessor
     │       │               │
     │       │               ├─→ pdf_ocr_ultra
     │       │               ├─→ region_extractor
     │       │               └─→ smart_extractor
     │       │                       │
     │       │                       └─→ region_extractor
     │       │
     │       └─→ non_litigation_validator
     │               │
     │               └─→ report_generator
     │
     ├─→ enforcement_product
     │       │
     │       └─→ enforcement_export ──→ enforcement_extractor
     │
     ├─→ company_query
     │
     ├─→ print_service
     │
     ├─→ pdf_ocr_ultra
     │
     ├─→ project_evaluation
     │
     └─→ server.py ──→ 所有上述模块
```

### 核心依赖链

**非诉组**：
```
config_loader → non_litigation_product → non_litigation_output_plan
    → non_litigation_export → non_litigation_validator → report_generator
```

**强制执行组**：
```
config_loader → enforcement_product → enforcement_export → enforcement_extractor
```

### 跨模块依赖

| 模块 | 依赖 |
|------|------|
| `non_litigation_export` | `pdf_ocr_ultra`, `region_extractor`, `smart_extractor`, `text_postprocessor`, `config_loader` |
| `smart_extractor` | `region_extractor`, `config_loader` |
| `enforcement_export` | `enforcement_extractor`, `enforcement_product`, `config_loader` |
| `server.py` | 所有业务模块 |

### 前端依赖

```
App.tsx
  ├─→ services/jsonrpc.ts ──→ @tauri-apps/api
  ├─→ services/system.ts  ──→ jsonrpc.ts
  ├─→ presets.ts          ──→ @tauri-apps/api
  ├─→ types.ts            (纯类型，无依赖)
  ├─→ constants.ts        ──→ types.ts
  └─→ components/*        ──→ types.ts, jsonrpc.ts, constants.ts
```

---

## 8. 配置系统 (config.yaml)

`config.yaml` 是项目的统一业务配置文件，通过 `config_loader.py` 加载。**换案件材料只需修改此文件，不需改代码**。

### 配置结构概览

```yaml
version: "1.0.0"
developer: "陈恒律师"

paths:                    # 路径配置
  directories:            # 目录名
  files:                  # 文件名
  standard_output_subdirs: # 标准输出子目录

doc_types:                # 文书类型列表（4种）
  - key / source_pdf / output_dir / pages_per_case
  - boundary_keywords / validation_keywords
  - filename_pattern / is_notice / content_marker

excel_parsing:            # 台账 Excel 解析配置
  min_columns / column_* / filter_keywords

regex_patterns:           # 正则表达式
  notice_number           # 责令号
  court_case_number       # 法院案号
  decision_case_number    # 决定书编号
  decision_number_range   # 编号范围

ocr_corrections:          # OCR 纠错词表
  non_litigation:         # 通用纠错（20+ 条）
  company_name_corrections: # 公司名称纠错（正则替换）

validation:               # 验证配置
  fuzzy_match_threshold   # 模糊匹配阈值
  text_quality            # 文本质量分级

ocr:                      # OCR 引擎配置
  engine:                 # 引擎参数（DPI、并行数等）
  optimization:           # 优化策略（区域优先、回退等）
  parallelism:            # 并行配置（自动检测、最大 Worker 数）

text_processing:          # 文本处理配置
  company_keywords        # 公司关键词
  document_types          # 文书类型
  noise_prefixes          # 噪声前缀

enforcement:              # 强制执行组配置
  paths / excel_parsing / extraction / ocr_corrections

company_query:            # 企业查询配置
  coze_api_url / coze_api_token / coze_workflow_id

print:                    # 打印配置
  default_copies / file_extensions
```

### 四种文书类型

| 类型 | key | source_pdf | pages_per_case | is_notice | 识别方式 |
|------|-----|-----------|----------------|-----------|---------|
| 责催 | 责催 | null (合并PDF) | null | true | 责令号匹配切割 |
| 申请书 | 申请书 | 申请书.pdf | 2 | false | 边界关键词切割 |
| 授权书 | 授权书 | 授权书.pdf | 1 | false | 固定页数切割 |
| 所函 | 所函 | 所函.pdf | 1 | false | 固定页数切割 |

---

## 9. 核心业务流程

### 9.1 非诉审查组流程

```
1. 加载台账
   load_non_litigation_cases(excel_path)
   → 从 Excel 读取案件列表（责令号、公司名、序号）

2. 构建 OCR 缓存
   build_real_ocr_cache(sample_dir)
   ├─ 遍历样本目录下所有 PDF
   ├─ 对每个 PDF 执行区域优先 OCR
   │   ├─ 提取区域图片 → OCR 识别
   │   ├─ 匹配目标模式（责令号/标题/公司名）
   │   └─ 回退判断 → 必要时全页 OCR
   └─ 缓存结果到 JSON 文件

3. 导出责催文件
   export_notice_files()
   ├─ 从合并 PDF 中按责令号定位页面
   ├─ 模糊匹配责令号（SequenceMatcher）
   └─ 切割并重命名为 "{序号}-责催-{责令号}.pdf"

4. 导出申请书文件
   export_application_files()
   ├─ 按边界关键词（"强制执行申请书"）定位切割点
   └─ 切割并重命名为 "{序号}-申请书pdf-{责令号}.pdf"

5. 导出授权书/所函文件
   export_company_named_files()
   ├─ 按固定页数切割（授权书1页、所函1页）
   ├─ OCR 识别公司名称
   └─ 重命名为 "{公司名称}.pdf"

6. 验证结果
   validate_export_results()
   ├─ 文件完整性检查
   ├─ 内容关键词验证
   └─ 文本质量评估

7. 生成报告
   generate_html_report()
   └─ 输出 HTML 验证报告
```

### 9.2 强制执行组流程

```
1. 加载台账
   load_enforcement_cases(excel_path)
   → 从非诉表格.xlsx读取案件（责令号、被执行人、金额等）
   → 构建 EnforcementCaseRegistry（三个索引）

2. 批量提取裁定 PDF 信息
   for each PDF in input_dir:
     extract_ruling_from_pdf(pdf_path)
     ├─ OCR 识别裁定 PDF 全文
     ├─ 移除 CJK 间距
     ├─ 提取法院案号
     ├─ 提取责令号（支持范围展开）
     ├─ 提取申请执行人/被执行人
     ├─ 提取执行标的金额
     ├─ 提取裁定日期
     ├─ 提取审判员/书记员
     └─ 检测是否撤回执行

3. 匹配台账与 PDF 结果
   _match_case_to_pdf(case, pdf_results)
   → 通过责令号或法院案号关联

4. 导出合并 Excel
   build_output_excel(registry, pdf_results, output_path)
   → 输出列：区号|案号|责令号|被执行人|职工|金额|法官|时间|结果|备注
```

---

## 10. 项目运行方式

### 环境准备

```bash
# 1. 确保 Python 3.12 已安装（.python-version 指定）

# 2. 创建并激活虚拟环境
python -m venv .venv312
.venv312\Scripts\activate

# 3. 安装 Python 依赖
pip install -r apps/server/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 配置 Poppler（PDF 转图片依赖）
python apps/server/scripts/setup_poppler.py

# 5. 安装前端依赖
cd apps/desktop
npm install
```

### 运行命令

| 场景 | 命令 |
|------|------|
| **OCR 单文件识别** | `python apps/server/src/pdf_ocr_ultra.py input/document.pdf` |
| **非诉组流程（Mock 模式）** | `python apps/server/scripts/run_non_litigation_flow.py` |
| **非诉组流程（真实 OCR）** | `python apps/server/scripts/run_non_litigation_flow.py --real` |
| **前端开发** | `npm run desktop:dev` |
| **Tauri 桌面版开发** | `npm run desktop:tauri dev` |
| **运行测试** | `pytest apps/server/tests/non-litigation/` |
| **覆盖率测试** | `pytest apps/server/tests/ --cov=apps/server/src --cov-report=html` |
| **前端代码检查** | `npm run lint` |
| **前端代码修复** | `npm run lint:fix` |
| **前端格式化** | `npm run format` |
| **前端格式检查** | `npm run format:check` |

### Tauri 桌面应用启动流程

```
npm run desktop:tauri dev
  │
  ├─ Vite 启动前端开发服务器
  ├─ Cargo 编译 Rust 后端
  └─ Tauri 窗口启动
      │
      ├─ Rust init_python_service()
      │   └─ 启动 Python 子进程 (server.py)
      │
      └─ React 前端加载
          └─ setupJsonRpcListeners()
              └─ 等待用户操作 → sendRequest()
```

---

## 11. 测试体系

### 测试目录结构

```
apps/server/tests/
├── non-litigation/
│   ├── conftest.py                          # 测试配置（sys.path 设置）
│   ├── test_batch2_input_structure.py       # 批次2输入结构测试
│   ├── test_company_name_matching.py        # 公司名称匹配测试
│   ├── test_non_litigation_company_split.py # 公司文档切割测试
│   ├── test_non_litigation_export.py        # 导出流程测试
│   ├── test_non_litigation_notice_mapping.py # 责令号映射测试
│   ├── test_non_litigation_output_plan.py   # 输出规划测试
│   ├── test_non_litigation_product.py       # 案件加载测试
│   ├── test_non_litigation_splitting.py     # PDF 切割测试
│   ├── test_non_litigation_validator.py     # 验证器测试
│   ├── test_ocr_optimization_behaviors.py   # OCR 优化行为测试
│   ├── test_project_evaluation.py           # 项目评估测试
│   ├── test_run_non_litigation_flow.py      # 完整流程测试
│   └── test_system_resource.py              # 系统资源检测测试
└── test_coze_company_query.py               # 企业查询测试
```

### 测试运行

```bash
# 激活环境
.venv312\Scripts\activate

# 运行非诉组测试
pytest apps/server/tests/non-litigation/

# 运行全部测试
pytest apps/server/tests/

# 带覆盖率
pytest apps/server/tests/ --cov=apps/server/src --cov-report=html
```

### 测试依赖

- `样本材料/` 目录下的真实样本 PDF 和标准输出
- `conftest.py` 手动将 `apps/server/src` 添加到 `sys.path`

---

## 12. 开发注意事项

### 模块导入

- `apps/server/src/` 下的模块使用 `sys.path.insert` 方式互相导入
- 无 `__init__.py`、无包安装
- 测试通过 `conftest.py` 手动加路径到 `sys.path`

### 配置驱动

- **所有业务配置集中在根目录 `config.yaml`**
- 通过 `config_loader.py` 的 `load_config()` 加载
- 换案件材料只需改 `config.yaml`，不需改代码

### OCR 纠错双层机制

1. **通用层**（`text_postprocessor.py`）：括号归一化、间距修复
2. **业务层**（`config.yaml` 的 `ocr_corrections`）：特定案件材料的纠错词表

### 责催停止条件机制

逐页 OCR → `apply_ocr_corrections` 纠错 → `NOTICE_PATTERN` 匹配 → 命中即停

### 断点续跑

- 已存在的文件/缓存自动跳过
- 不会清空重跑

### 路径约定

- Rust 侧将 Python cwd 设为项目根目录
- Python 中 `ROOT` 变量也指向项目根
- 输出到 `output/` 和 `temp/`，均已被 git 忽略

### 换案件材料检查清单

更换案件材料时，需修改 `config.yaml` 中以下配置项：

1. `regex_patterns.notice_number` — 责令号正则（城市名、文书类别字）
2. `doc_types` — 文书类型列表（关键词、页数、文件名模式、输出目录名）
3. `ocr_corrections.non_litigation` — OCR 常见误识纠错词表
4. `ocr_corrections.company_name_corrections` — 公司名称纠错（替换为本批次公司）
5. `excel_parsing` — 台账 Excel 列索引、过滤关键词
6. `validation.keywords` — 各文书类型校验关键词（所函关键词应改为对应律所名）
7. `paths.files.excel_filename` — 台账文件名（若不同）
