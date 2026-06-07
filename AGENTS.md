# Repository Guidelines

> 公积金业务辅助工具。基于 RapidOCR + pdfplumber 的 PDF/图片 OCR 识别，分**非诉组**（责催/申请书/授权书/所函）和**强制执行组**（裁定信息）两条业务主线。前端是 Tauri 1.x 桌面壳，后端是 Python 3.12，通过 stdin/stdout JSON-RPC（`server.py`）通信，可选 Flask HTTP（`http_server.py`）并存。

## 1. Project Overview

- **业务目标**：批量处理公积金案件 PDF（页数切割、字段提取、案号匹配、Excel 导出），覆盖两个组的真实办公场景。
- **核心策略**：
  - pdfplumber 优先抽取可编辑文本，失败/内容不足时回退 RapidOCR。
  - 责催类型**逐页 OCR → 命中 `NOTICE_PATTERN` 即停**。
  - 配置驱动：所有业务规则（正则、纠错词表、文书类型、强制组正则）均在 `config.yaml`，**换案件只改配置不改代码**。
  - 断点续跑：OCR 结果 pickle 缓存 + 流式任务 SQLite (`streaming_*.db`)。
- **部署形态**：开发期 `tauri dev` 直接拉 Python 子进程；发布期 `build.rs` 用 PyInstaller 打成 `gjj-ocr-server.exe`（onefile）随 Tauri NSIS 安装包分发。

## 2. Architecture & Data Flow

### 后端分层（`apps/server/src/`）

```
src/
├── server.py                # JSON-RPC 入口（stdin/stdout, 1343 行，30+ RPC 方法）
├── http_server.py           # Flask + CORS HTTP 入口（641 行，RESTful 替代/并存）
├── core/                    # 基础设施层（无业务规则）
│   ├── paths.py             # 唯一路径入口（环境变量 GJJ_OCR_ROOT/RESOURCES/USER_DATA）
│   ├── config_loader.py     # yaml → NonLitigationConfig（带 _CONFIG_CACHE 缓存）
│   ├── pdf_ocr_ultra.py     # OCR 引擎（RapidOCR + GPU 探测 + 多进程 Pool + ImagePreprocessor）
│   ├── text_postprocessor.py# 文本后处理（括号归一/全角/案号/公司名）
│   ├── region_extractor.py  # 按百分比坐标裁剪页面区域
│   ├── smart_corrector.py   # 智能纠错引擎（L1=自动 / L2=需核查 / L3=禁用）
│   ├── task_state.py        # SQLite 任务状态（断点续跑/失败重试）
│   ├── task_cancel.py       # 跨模块取消注册表（threading.Event 字典）
│   ├── preset_paths.py      # 预设样本/台账路径解析（5 个 PRESET_DEFINITIONS）
│   └── system_resource.py   # CPU/内存/GPU 探测
├── non_litigation/          # 非诉组业务
│   ├── export.py            # 中心编排（3216 行，build_mock_ocr_results / run_real_ocr / export_*）
│   ├── streaming.py         # StreamingBatchProcessor（SQLite 拉批 + 批渲染 5/20 页）
│   ├── product.py           # 台账 Excel 加载
│   ├── output_plan.py       # 期望输出目录结构
│   ├── smart_extractor.py   # 三步回退抽取（pdfplumber→区域 OCR→全页 OCR）
│   ├── validator.py         # 校验（PASS/WARNING/FAIL）
│   ├── evaluation.py        # 质量评估（项目评估 JSON + active/retired 12/3 项）
│   └── report.py            # HTML 报告生成
├── enforcement/             # 强制执行组业务
│   ├── product.py           # EnforcementCaseRegistry（台账加载 + 匹配）
│   ├── extractor.py         # RulingInfo 数据类 + RuleBasedExtractor（927 行）
│   ├── export.py            # 双 Sheet Excel（匹配 + PDF 独有）
│   └── debug_match.py       # 台账匹配调试工具
└── infra/                   # 外部服务
    ├── company_query.py     # Unicloud HTTP API（缓存 + 线程池并发）
    └── print_service.py     # Windows 打印（PrintTaskManager 单例）
```

### 数据流

**非诉组主线**（`server._non_litigation_process`）：
```
PDF 输入
  → resolve_input_path / ensure_non_litigation_input_structure
  → run_real_ocr
      ├─ Mock 模式：build_mock_ocr_results
      └─ 真实：total_tasks ≥ _STREAMING_THRESHOLD 且 _should_use_streaming
          → StreamingBatchProcessor + TaskStateManager (SQLite)
          → 批渲染 PDF → RapidOCR → TextPostProcessor.apply_ocr_corrections
            （注意：streaming.py 不走 smart_corrector，只走 cfg.ocr_corrections）
  → export_non_litigation_standard_outputs
      → export_notice_files（→ detect_notice_source_mapping_from_ocr → _match_notice_from_ocr_text
        → SmartCorrector.correct_notice_number，**L1 自动应用、L2/L3 标 needs_review**）
      → export_application_files / export_company_named_files / write_mapping_excel
  → validate_ocr_results + evaluate_non_litigation_quality
  → emit summary
```

**强制执行主线**（`server._enforcement_extract`）：
```
裁定 PDF
  → process_enforcement_cases
  → load_enforcement_cases（EnforcementCaseRegistry）
  → batch_extract_rulings（逐 PDF：RulingPDFExtractor 走 pdfplumber→OCR + RuleBasedExtractor）
  → compute_enforcement_match_stats（按 PDF 聚合：责令号→被执行人→法院案号）
  → enforcement.export.build_output_excel（Sheet1 匹配 + Sheet2 PDF 独有）
```

### 取消体系

- `core.task_cancel` 是全局 `threading.Event` 字典，被所有长任务共用。
- `infra.print_service.PrintTaskManager` 维护自己的 `cancel_event`。
- HTTP 入口的 `/print/cancel` 走 `cancel_print_task`，`/company-query/cancel` 直接调 `request_cancel`。

## 3. Key Directories

| 路径 | 用途 |
|---|---|
| `apps/server/src/` | Python 后端（`core/` + `non_litigation/` + `enforcement/` + `infra/`） |
| `apps/server/tests/` | pytest 测试（仅 `non-litigation/` 子目录有 conftest） |
| `apps/server/scripts/` | CLI 入口、PyInstaller 打包、诊断、下载、基准 |
| `apps/server/tools/poppler/` | Poppler 24.08.0 Windows 二进制（`setup_poppler.py` 安装） |
| `apps/server/requirements.txt` | Python 依赖 |
| `apps/desktop/src/` | React 19 + Vite 前端 |
| `apps/desktop/src-tauri/` | Tauri 1.x Rust 端 + `resources/`（含打包产物） |
| `config.yaml` | **所有业务配置**（正则、纠错词表、文书类型、强制组规则） |
| `resources/sample-data/` | 安装包携带的 5 个样本目录（non-litigation-batch1/2、enforcement/extract、enforcement/print、company-query） |
| `样本材料/` | 开发用真实样本（含第 1/2/3 批 + 番禺法院待做 + 强制组 + 企业查询） |
| `input/` | 待处理输入（`.gitkeep` 占位） |
| `output/`、`temp/` | 运行产物（`.gitignore` 忽略） |
| `docs/` | `ocr_generic_design.md`（3 层纠错设计）+ `企业查询接口api文档.md` |
| `scripts/` | 根目录工具脚本（test_fix、smart_test、bench_parallel、export_case_kb_schema） |

## 4. Development Commands

```bash
# Python 环境
.venv312\Scripts\activate
pip install -r apps/server/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python apps/server/scripts/setup_poppler.py     # Windows Poppler 一次性安装

# 非诉组
python apps/server/scripts/run_non_litigation_flow.py              # Mock 模式
python apps/server/scripts/run_non_litigation_flow.py --real        # 真实 OCR
python apps/server/scripts/run_non_litigation_flow.py --real --force # 删缓存重跑

# 强制执行组
python apps/server/scripts/run_enforcement_flow.py
python apps/server/scripts/run_enforcement_flow.py --use-ocr

# 通用 OCR CLI
python apps/server/src/pdf_ocr_ultra.py input/document.pdf
python apps/server/src/pdf_ocr_ultra.py doc.pdf --force-ocr

# 测试
pytest apps/server/tests/                                         # 全部
pytest apps/server/tests/non-litigation/test_non_litigation_export.py      # 单文件
pytest apps/server/tests/non-litigation/test_non_litigation_export.py -k application  # 单用例
pytest --cov=apps/server/src --cov-report=html apps/server/tests/   # 覆盖率

# 打包 / 一键自检
powershell apps/server/scripts/build_server_bundle.ps1             # PyInstaller onefile + 冒烟
python apps/server/scripts/e2e_verify.py                            # 端到端冒烟
python apps/server/scripts/verify_server_bundle.py <exe> --resources <res-dir>  # 单跑冒烟
python scripts/test_fix.py                  # 根目录智能自检（含 Rust 编译 + Python 测试）
python scripts/test_fix.py --full           # 包含打包
python scripts/test_fix.py --skip-build     # 跳过打包
python scripts/smart_test.py                # 智能检测+修复

# 前端
npm run desktop:dev                         # 仅 Vite 开发（不启 Tauri）
npm run desktop:tauri dev                   # Tauri 开发（启 Python 子进程）
npm run desktop:tauri build                 # Tauri release（NSIS；自动打后端 onefile）
npm run lint                                # ESLint
npm run lint:fix
npm run format                              # Prettier
npm run format:check
```

### 强制重打后端
- `$env:GJJ_FORCE_SERVER_BUNDLE="1"` — `build.rs` 检测到时强制 `PyInstaller` 重打
- 删除 `apps/desktop/src-tauri/resources/gjj-ocr-server.exe` — 同上
- `$env:GJJ_SKIP_SERVER_BUNDLE="1"` — 跳过自动重打

## 5. Code Conventions & Common Patterns

### 命名
- 文件：snake_case。包：单数形式（`core`、`non_litigation`）。
- 类：PascalCase（`UltraFastOCR`、`NonLitigationConfig`、`TaskStateManager`、`RulingInfo`）。
- 私有：前缀 `_`（`_execute_task`、`_match_notice_from_ocr_text`、`_safe_json_dumps`）。
- 常量：UPPER_SNAKE（`_STREAMING_THRESHOLD`、`OCR_MODEL_MEMORY_GB`、`PRESET_DEFINITIONS`）。

### 导入约定
- 后端 `src/` 下**无 `__init__.py`**——靠 `sys.path.insert` 互相引用；测试时 `conftest.py` 注入 `apps/server/src`。
- `core/__init__.py` 显式 re-export 子模块的关键符号（`paths`、`config_loader`、`UltraFastOCR` 等）。
- `non_litigation/__init__.py` 用 `from .export import *` 加显式 `from .product import ...`。
- `enforcement/__init__.py` 三个文件全 `import *`（**注**：`enforcement.product` 与 `enforcement.extractor` 都有 `normalize_*` 类函数，全 `*` 导入会互相覆盖——改动时警惕）。
- `infra/__init__.py` 显式列举。

### 错误处理
- 长任务不抛异常吞掉——用 `traceback` 写日志 + `emitter` 推前端 + `task_state.update_status(task_id, "failed", error=...)`。
- 取消抛 `core.task_cancel.CancelledError`，由 `StreamingBatchProcessor` / `process_print_v2` 抛。
- surrogate 字符：`server.py::_sanitize` 递归替换为 `\ufffd`，所有出栈响应必须走 `_safe_json_dumps`。

### 异步 / 并发模式
- **RPC 入口**：`server.py` 把长任务丢到 `threading.Thread(daemon=True)`，主线程继续读 stdin。
- **流式 OCR**：`StreamingBatchProcessor` 共享 OCR 引擎（`_ocr_engine` 单例），批渲染 5/20 页一组；`TaskStateManager` 用 SQLite WAL，每线程独立连接。
- **企业查询**：`infra.company_query.process_company_query` 用 `concurrent.futures.ThreadPoolExecutor` + 取消事件。
- **GPU 探测**：`detect_gpu_provider()` 返回 CUDA→DirectML→CPU，`get_ocr_lock()` 保护 RapidOCR 初始化（Windows DirectML 共享问题）。

### 依赖注入 / 状态管理
- 路径**唯一入口**是 `core.paths`：环境变量 `GJJ_OCR_ROOT` / `GJJ_OCR_RESOURCES` / `GJJ_OCR_USER_DATA` 驱动，回退到开发态仓库布局。**不要在业务代码里写 `Path(__file__).parents[N]`**。
- 配置**全局缓存**：`config_loader._CONFIG_CACHE` 首次加载后不变。改 `config.yaml` 需 `reload_config()` 或重启。
- 业务配置**全部在 `config.yaml`**——`enforcement.*`、`company_query.*`、`print.*` 是顶层 key。**换案件只改配置不改代码**。
- 跨模块取消用 `core.task_cancel`；不要在子模块里自己维护 Event 字典。

### 数据类优先
- 大量 `@dataclass`：`OCRConfig`、`PageResult`、`RulingInfo`、`ExtractionResult`、`ValidationResult`、`Task`、`EnforcementCase`、`PrintTask`、`ResourceProfile`。
- 持久化走 pickle（`ocr-cache.pkl`）+ SQLite（`streaming_*.db`、`temp/ocr_state.db`）。

### 前端
- React 19 + Vite 5 + TypeScript（strict + noUnusedLocals）+ Tailwind 3 + ESLint 10 flat config + Prettier 3。
- **TS/TSX 根目录**：`apps/desktop/src/`（由 `tsconfig.json` 的 `include: ["src"]` 锁定）。
- ESLint ignores `dist` 和 `src-tauri`；`@typescript-eslint/no-unused-vars` 允许 `_` 前缀。
- Prettier：`singleQuote: false`, `tabWidth: 2`, `printWidth: 100`, `endOfLine: "auto"`, `trailingComma: "all"`。
- **Tailwind token 体系**：`hsl(var(--…))` + primary 50..900 显式蓝阶，**颜色加在 CSS 变量里**而不是写 `bg-blue-500` 之类默认值。

## 6. Important Files

| 文件 | 角色 |
|---|---|
| `apps/server/src/server.py` | JSON-RPC 中心编排器（30+ 方法、长任务后台线程、surrogate 清理、stderr 通知通道） |
| `apps/server/src/http_server.py` | Flask REST 入口（实现**不完整**：`/non-litigation/process`、`/enforcement/extract`、`/print/start`、`/company-query/process` 多为 stub） |
| `apps/server/src/core/paths.py` | 运行时路径唯一入口 |
| `apps/server/src/core/config_loader.py` | `NonLitigationConfig` 聚合 + 缓存 |
| `apps/server/src/core/pdf_ocr_ultra.py` | OCR 引擎（GPU 探测 + 多进程 + 缓存） |
| `apps/server/src/core/smart_corrector.py` | 智能纠错（**L1/L2/L3 三级**，AdaptiveLearner 写 `learned_corrections.json`） |
| `apps/server/src/core/task_state.py` | SQLite 任务状态（`Task` + `TaskStateManager`） |
| `apps/server/src/non_litigation/export.py` | 非诉组业务核心（3216 行，**改动时先读全文件**） |
| `apps/server/src/non_litigation/streaming.py` | 流式批处理（**与 export.py 互不调用 smart_corrector**） |
| `apps/server/src/enforcement/extractor.py` | 强制组核心（927 行，配置驱动 RuleBasedExtractor） |
| `apps/desktop/src-tauri/build.rs` | 资源同步 + 自动 PyInstaller 打包（`sync_resources_release` / `sync_resources_dev`） |
| `apps/desktop/src-tauri/src/main.rs` | Tauri→Python 桥（tokio::process + JSON-RPC + 版本号→缓存清理） |
| `config.yaml` | **业务配置中心**（顶层 16 个 key） |
| `apps/server/scripts/build_server_bundle.ps1` | onefile 打包 + 冒烟 |
| `apps/server/scripts/setup_poppler.py` | Poppler Windows 安装 |
| `apps/server/runtime_utf8_hook.py` + `pyinstaller_frozen_hook.py` | PyInstaller 钩子 |

## 7. Runtime / Tooling Preferences

### 强制要求
- **Python 3.12**（`.python-version` 写 `3.12`）。不接受 3.13。
- **Windows**：Tauri 端 `CREATE_NO_WINDOW` + `pywin32`；Poppler 需本地配置（`apps/server/tools/poppler/poppler-24.08.0`）。
- **Node ≥ 18**（Vite 5 隐含）；Tauri 1.x + Rust ≥ 1.70。
- pip 源：`https://pypi.tuna.tsinghua.edu.cn/simple`。
- 包管理器：**npm**（根有 `package-lock.json` 143KB，无 `bun.lockb`/`pnpm-lock.yaml`）。
- 锁 Python 解释器到 `.venv312\Scripts\python.exe`（`.vscode/settings.json` + `build.rs::find_python`）。

### 工作区
- npm workspaces = `["apps/*"]`，所有 npm 脚本在 `apps/desktop/package.json`。
- 仓库根 `package.json` 的 `test:fix` / `test:smart` **是 Python 包装脚本**（`scripts/test_fix.py` / `smart_test.py`），不是 pytest 入口。

### Tauri Rust ↔ Python 通信
- stdin/stdout JSON-RPC。Rust 写入 `JsonRpcRequest{jsonrpc, method, params, id} + \n`。
- Python stdout 行：含 `jsonrpc` 字段 → 响应；否则 → `notify.log` 通知。
- Python stderr：行匹配 `JSON-RPC 服务已启动` → `rpc_ready=true` → emit `python-service-ready`。
- 注入环境变量：`GJJ_OCR_ROOT`、`GJJ_OCR_RESOURCES`、`GJJ_OCR_USER_DATA`、`GJJ_APP_VERSION`（= `CARGO_PKG_VERSION`）、`PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`。
- 版本号变化 → `check_and_clear_cache_on_upgrade` 清 `output/`、`temp/`、`ocr-gpu-cache.json`。

### PyInstaller 打包规则
- onefile 命令：`python -m PyInstaller gjj-ocr-server.spec --noconfirm --clean`（CWD=`apps/server`）。
- 产物：`apps/server/dist/gjj-ocr-server.exe` → 拷到 `src-tauri/resources/gjj-ocr-server.exe`。
- 清理 `gjj-ocr-server/`（旧 onedir）和 `python-runtime/`（旧便携版）。
- 重打判定：`force` OR exe 不存在 OR `apps/server/src/**` 任一 mtime > exe mtime OR `verify_server_bundle.py` 校验失败。
- **`apps/desktop/src-tauri/resources/server_src/` 由 `build.rs` 自动同步自 `apps/server/src/`**——**禁止手编**。`tauri.conf.json` resources 必须含 `resources/server_src/**`，否则安装包没有最新源码。

## 8. Testing & QA

### 测试框架
- **pytest 9.0.3**（实际运行版本；`requirements.txt` 声明 `pytest>=8.0.0`、`pytest-cov>=4.0.0`、`pytest-asyncio>=0.21.0`）。
- 无 `pytest.ini` / `pyproject.toml` / `setup.cfg` / `tox.ini` / `.coveragerc`。
- 无 `pytest-mock`；无 `MagicMock` 任何使用；`TestCozeCompanyQuery` 是唯一 unittest.TestCase 兼容类。
- **唯一 conftest**：`apps/server/tests/non-litigation/conftest.py`（8 行，仅 `sys.path.insert` + `from core.paths import ROOT`）。顶层 4 个老测试（`test_server.py`、`test_rpc.py`、`test_unicloud_*`）自管 `sys.path`。

### 测试风格
- 平铺 `def test_…`，长描述式 snake_case（如 `test_export_non_litigation_standard_outputs_should_match_standard_page_counts`）。
- 非诉组测试用 `build_mock_ocr_results(...)` 预生成假 OCR dict + 真实样本 PDF 比对页数。
- 输出用 `tmp_path` 隔离。
- `test_coze_company_query.py` 硬编码了 Coze Bearer token——**敏感信息已泄漏进仓库**，未来应迁到环境变量。
- `test_run_non_litigation_flow.py` 用 `monkeypatch.setattr` 局部替换 `build_mock_ocr_results`，本质是逻辑测试。

### 运行命令
- 必须在**仓库根**跑（`conftest.py` 用 `parents[4]` 倒推仓库根）。
- 跑单文件：`pytest apps/server/tests/non-litigation/test_non_litigation_validator.py`
- 跑单用例：`pytest apps/server/tests/non-litigation/test_run_non_litigation_flow.py::test_format_summary_should_use_ascii_labels`
- 覆盖率：`pytest --cov=apps/server/src apps/server/tests`

### 覆盖盲点（**改动后必须补**）
已覆盖：`core.paths`、`core.system_resource`、`non_litigation.{export,evaluation,validator,product,output_plan,notice_mapping,run_non_litigation_flow}`、`infra.company_query`（但走真实 HTTP）。

**未覆盖**（按优先级）：
- `enforcement/`（整包，**零测试**）— 改前手动跑 `run_enforcement_flow.py` 验证
- `core/{pdf_ocr_ultra, text_postprocessor, region_extractor, smart_corrector, config_loader, task_state, task_cancel, preset_paths}` — 零测试
- `non_litigation/{streaming, report, smart_extractor}` — 零测试
- `infra/print_service` — 零测试
- `http_server.py`（Flask 入口）— 零测试
- `server.py` RPC 协议层 — 仅 `test_server.py` / `test_rpc.py` 两个无 assert 的 print 测试

### 自检脚本（**非 pytest**）
- `scripts/test_fix.py`（169 行，subprocess 编排：跑 pytest + Rust 编译 + 可选打包 + 修复 channel closed / OCR 引擎就绪）
- `scripts/smart_test.py`（300 行，智能检测/修复）
- `scripts/test-fix.ps1` / `test-fix-simple.ps1`（PowerShell 包装）
- `apps/server/scripts/e2e_verify.py`（在 `scripts/` 而非 `tests/`，端到端冒烟）

### 缓存约定
- 断点续跑：`cache_path.exists()` 复用 pickle，**不重跑**。
- `clear_ocr_cache` RPC（`force=true`）：清 `ocr-cache.pkl` + 所有 `streaming_*.db`。
- `output/`、`temp/`、`.app-version`、`ocr-gpu-cache.json` 全部在 `.gitignore`。
