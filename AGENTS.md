# AGENTS.md

公积金业务辅助工具，基于 RapidOCR + pdfplumber 的 PDF/图片 OCR 识别。

## 环境

- **Python 3.12**（`.python-version` 指定，非 3.13）
- 虚拟环境：`.venv312/`（VS Code 已配置该解释器路径）
- Windows 专属，Poppler 需本地配置：`python apps/server/scripts/setup_poppler.py`
- pip 源：`https://pypi.tuna.tsinghua.edu.cn/simple`

## 关键命令

```bash
.venv312\Scripts\activate                          # 激活环境
pip install -r apps/server/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

python apps/server/src/pdf_ocr_ultra.py input/document.pdf          # 通用 OCR
python apps/server/src/pdf_ocr_ultra.py doc.pdf --force-ocr         # 强制 OCR（跳过文本提取）

python apps/server/scripts/run_non_litigation_flow.py               # 非诉组 Mock 模式
python apps/server/scripts/run_non_litigation_flow.py --real        # 非诉组真实 OCR
python apps/server/scripts/run_non_litigation_flow.py --real --force # 删缓存重跑

pytest apps/server/tests/non-litigation/                             # 非诉组测试
pytest apps/server/tests/non-litigation/test_non_litigation_export.py      # 单文件
pytest apps/server/tests/non-litigation/test_non_litigation_export.py -k application  # 单用例
pytest apps/server/tests/ --cov=apps/server/src --cov-report=html   # 覆盖率

npm run desktop:dev          # 前端开发
npm run desktop:tauri dev    # Tauri 桌面版开发
npm run lint                 # 前端 lint
npm run lint:fix             # 前端 lint 自动修复
npm run format               # 前端格式化
npm run format:check         # 前端格式检查
```

## 架构

```
config.yaml                          # 所有业务配置（正则、纠错词表、页数、enforcement 等）
apps/
├── desktop/                         # Tauri 1.x + React 19 + Vite + Tailwind
│   ├── src/                         # React 组件及 JSON-RPC 服务层
│   └── src-tauri/src/main.rs        # Rust 侧启动 Python 进程，通过 stdin/stdout JSON-RPC 通信
└── server/                          # Python 后端
    ├── src/
    │   ├── paths.py                 # ROOT/SERVER_SRC 常量，所有模块的第一个依赖
    │   ├── config_loader.py         # 加载 config.yaml → NonLitigationConfig（全局缓存）
    │   ├── server.py                # JSON-RPC 服务端（与 Tauri 通信，启动时设 UTF-8 + surrogate 清理）
    │   ├── pdf_ocr_ultra.py         # 通用 OCR CLI（先提取文本，失败/不足才走 OCR）
    │   ├── text_postprocessor.py    # 括号统一、纠错、案号规范化
    │   ├── smart_extractor.py       # 区域裁剪 + 多轮回退字段提取
    │   ├── region_extractor.py      # 按百分比坐标裁剪页面区域
    │   │
    │   │─── 非诉组流水线 ───
    │   ├── non_litigation_product.py      # 从台账 Excel 加载案件元数据
    │   ├── non_litigation_output_plan.py  # 构建期望输出目录结构
    │   ├── non_litigation_export.py       # 核心编排：PDF 切割/重命名/导出/审计
    │   ├── non_litigation_validator.py    # 识别结果验证
    │   │
    │   │─── 强制执行组 ───
    │   ├── enforcement_product.py         # 从非诉表格 Excel 加载执行案件
    │   ├── enforcement_extractor.py       # 裁定 PDF 信息提取（RulingInfo 数据类）
    │   ├── enforcement_export.py          # 裁定信息与台账匹配 → 导出 Excel
    │   │
    │   ├── company_query.py               # Coze API 查询公司信息
    │   ├── print_service.py               # 打印服务
    │   ├── project_evaluation.py          # 页数匹配率评估（非逐页内容 diff）
    │   ├── report_generator.py            # HTML 验证报告
    │   └── system_resource.py             # 系统资源检测
    └── tests/non-litigation/conftest.py   # 把 src/ 注入 sys.path
```

**依赖链**：
- 非诉组：`paths` ← `config_loader` ← `non_litigation_product` → `non_litigation_output_plan` → `non_litigation_export`（中心编排）→ `non_litigation_validator` → `report_generator`
- 强制执行组：`paths` ← `config_loader` ← `enforcement_product` → `enforcement_extractor` → `enforcement_export`
- 通用：`paths` ← `pdf_ocr_ultra`；`smart_extractor` → `region_extractor`；`text_postprocessor` 被 `non_litigation_export` 直接引用

## 开发注意事项

- **无包安装**：`apps/server/src/` 无 `__init__.py`，模块通过 `sys.path.insert` 互相导入。测试靠 `conftest.py` 注入 `sys.path`。改文件名或导入方式时要连带检查测试
- **paths.py 是基石**：所有模块 `from paths import ROOT`。ROOT 解析顺序：环境变量 `GJJ_OCR_ROOT` → PyInstaller frozen 路径 → `Path(__file__).parents[3]`（项目根目录）
- **config_loader 全局缓存**：`_CONFIG_CACHE` 首次加载后不变，改了 `config.yaml` 需调 `reload_config()` 或重启进程才生效
- **业务配置全在 config.yaml**：换案件材料只改配置不改代码。强力执行组配置在 `enforcement:` 键下
- OCR 纠错分两层：通用（`text_postprocessor.py` 括号归一化、间距修复）+ 业务特定（`config.yaml` 的 `ocr_corrections`）
- 责催 stop_condition：逐页 OCR → `apply_ocr_corrections` → `NOTICE_PATTERN` 匹配 → 命中即停
- `NOTICE_PATTERN` 支持 6 种括号：`〔〕` `()` `[]` `［］` `【】` 及混合；业务默认中文 `（）`，匹配时统一后比较
- Rust 侧将 Python cwd 设为项目根目录
- 输出到 `output/` 和 `temp/`，已被 git 忽略；断点续跑，已有缓存自动跳过
- `样本材料/` 含真实样本 PDF 和标准输出，测试依赖这些文件

## 换案件材料检查清单

修改 `config.yaml` 中以下配置项：

1. `regex_patterns.notice_number` — 责令号正则（城市名、文书类别字）
2. `doc_types` — 文书类型列表（关键词、页数、文件名模式、输出目录名）
3. `ocr_corrections.non_litigation` — OCR 常见误识纠错词表
4. `ocr_corrections.company_name_corrections` — 公司名称纠错（替换为本批次公司）
5. `excel_parsing` — 台账 Excel 列索引、过滤关键词
6. `validation.keywords` — 各文书类型校验关键词（所函关键词应改为对应律所名）
7. `paths.files.excel_filename` — 台账文件名（若不同）
