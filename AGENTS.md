# AGENTS.md

## 项目概述

公积金业务辅助工具，基于 RapidOCR + pdfplumber 的 PDF/图片 OCR 识别工具。服务两个业务组：非诉审查组（PDF 批量重命名）和强制执行组（裁定信息识别与归纳）。

## 环境

- **Python 3.12**（`.python-version` 指定，非 3.13）
- 虚拟环境：`.venv312/`（VS Code 已配置该路径）
- Windows 专属项目，Poppler 必须本地配置：`python scripts/setup_poppler.py`
- pip 源：`https://pypi.tuna.tsinghua.edu.cn/simple`

## 关键命令

```bash
# 激活环境
.venv312\Scripts\activate

# 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 运行主程序（OCR 识别）
python src/pdf_ocr_ultra.py input/document.pdf

# 非诉组流程（Mock 模式，推荐先跑）
python scripts/run_non_litigation_flow.py

# 非诉组流程（真实 OCR）
python scripts/run_non_litigation_flow.py --real

# 测试
pytest tests/non-litigation/

# 覆盖率
pytest tests/ --cov=src --cov-report=html
```

## 架构

```
src/
├── pdf_ocr_ultra.py          # 主程序入口，OCR 核心逻辑
├── text_postprocessor.py     # OCR 文本后处理（括号统一、纠错、案号规范化）
├── non_litigation_product.py # 非诉组：从台账 Excel 加载案件数据
├── non_litigation_output_plan.py  # 非诉组：构建期望输出目录结构
├── non_litigation_export.py  # 非诉组：PDF 切割/重命名/导出
├── non_litigation_validator.py    # 非诉组：识别结果验证
├── project_evaluation.py     # 项目质量评估
└── report_generator.py       # HTML 验证报告生成
```

**模块依赖链**：`non_litigation_product` → `non_litigation_output_plan` → `non_litigation_export` → `non_litigation_validator` → `report_generator`

`text_postprocessor` 被 `non_litigation_export` 直接引用。

## 已知问题

无

## 开发注意事项

- `src/` 下的模块用 `sys.path.insert` 方式互相导入（无 `__init__.py`、无包安装），测试也靠 `conftest.py` 手动加 `src/` 到 `sys.path`
- 业务逻辑围绕中文法律文书，OCR 纠错词库在 `text_postprocessor.py` 中硬编码（如"责行"→"责令"、"公积全"→"公积金"）
- 括号格式：业务默认中文括号 `（）`，匹配时统一后再比较
- `样本材料/` 含测试用的真实样本 PDF 和标准输出，测试依赖这些文件
- `models/` 下有本地 GGUF 模型文件（可选 LLM 功能），已被 `.gitignore` 排除
- 输出到 `output/` 和 `temp/`，均已被 git 忽略
