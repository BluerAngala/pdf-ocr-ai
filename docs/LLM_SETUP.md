# 本地 LLM 部署指南

本文档介绍如何在 PDF OCR 项目中部署和使用本地 AI 模型，用于文本检查、信息提取和内容分析。

## 推荐模型

根据你的配置（CPU，4-8GB内存），推荐以下模型：

### ⭐ 首选：Gemma 3 4B IT
- **大小**：约 2.6GB (Q4_K_M量化)
- **内存需求**：3-4GB
- **特点**：Google 2025年最新模型，128K上下文，中文优秀
- **适用**：文本纠错、信息提取、内容理解

### ⭐ 备选：Qwen2.5 1.5B Instruct
- **大小**：约 1GB (Q4_K_M量化)
- **内存需求**：2GB
- **特点**：阿里最新模型，中文法律文档处理优秀
- **适用**：资源受限场景

## 快速开始

### 1. 安装依赖

```bash
# 安装 llama-cpp-python (CPU版本)
pip install llama-cpp-python --no-cache-dir

# 如果需要 GPU 加速 (需要NVIDIA显卡)
# CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python --no-cache-dir
```

### 2. 下载模型

```bash
# 列出所有可用模型
python scripts/download_model.py --list

# 下载 Gemma 3 4B (推荐)
python scripts/download_model.py --model gemma-3-4b

# 或下载 Qwen2.5 1.5B (更轻量)
python scripts/download_model.py --model qwen2.5-1.5b
```

模型将下载到 `models/` 目录。

### 3. 使用模型

```python
from src.local_llm import LocalLLM

# 创建 LLM 实例
llm = LocalLLM()

# 加载模型
llm.load_model("models/google_gemma-3-4b-it-Q4_K_M.gguf")

# 分析 OCR 文本
ocr_text = """你的OCR识别文本..."""

# 检查错误
result = llm.analyze_ocr_text(ocr_text, task="check")
print(result)

# 提取信息
result = llm.analyze_ocr_text(ocr_text, task="extract")
print(result)

# 分类文档
result = llm.analyze_ocr_text(ocr_text, task="classify")
print(result)

# 自定义对话
response = llm.chat("请总结这段文本的主要内容")
print(response)
```

## 集成到 OCR 流程

修改 `pdf_ocr_ultra.py` 中的 `save_result` 方法已集成 LLM 分析。你也可以手动调用：

```python
from src.pdf_ocr_ultra import UltraFastOCR, OCRConfig
from src.local_llm import LocalLLM

# OCR 处理
config = OCRConfig()
processor = UltraFastOCR(config)
result = processor.process_file("input/document.pdf")

# LLM 分析
llm = LocalLLM()
llm.load_model("models/google_gemma-3-4b-it-Q4_K_M.gguf")

# 分析每页内容
for page in result['pages']:
    analysis = llm.analyze_ocr_text(page['text'], task="check")
    page['llm_analysis'] = analysis
```

## 模型对比

| 模型 | 大小 | 内存需求 | 速度 | 中文 | 推理 | 推荐度 |
|------|------|----------|------|------|------|--------|
| Gemma 3 4B | 2.6GB | 3-4GB | 快 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Qwen2.5 1.5B | 1GB | 2GB | 很快 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Qwen2.5 3B | 1.9GB | 3GB | 快 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Llama 3.2 3B | 1.9GB | 3GB | 快 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Phi-4 14B | 8GB | 10GB | 慢 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |

## 性能优化

### CPU 优化
```python
config = LLMConfig(
    threads=4,          # 根据CPU核心数调整
    batch_size=512,     # 批处理大小
    context_length=4096 # 减少上下文长度可节省内存
)
llm = LocalLLM(config)
```

### 量化版本选择
- **Q4_K_M**：推荐，平衡质量和速度
- **Q4_K_S**：更快，质量略降
- **Q5_K_M**：质量更好，稍慢
- **Q6_K**：最高质量，最慢

## 常见问题

### Q: 模型加载很慢？
A: 首次加载需要读取大文件到内存，这是正常的。后续对话会很快。

### Q: 内存不足？
A: 选择更小的模型（如 Qwen2.5 1.5B），或减小 `context_length`。

### Q: 中文效果不好？
A: 确保选择中文优化的模型（Gemma 3、Qwen2.5），避免使用 Llama。

### Q: 如何更新模型？
A: 重新运行下载脚本，会提示是否覆盖。

## 手动下载模型

如果自动下载失败，可以手动下载：

1. 访问 HuggingFace 模型页面
2. 下载 `.gguf` 文件（推荐 Q4_K_M 版本）
3. 放到 `models/` 目录
4. 加载时使用正确文件名

推荐模型页面：
- Gemma 3 4B: https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF
- Qwen2.5 1.5B: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF

## 高级用法

### 自定义系统提示词
```python
config = LLMConfig(
    system_prompt="你是一个专业的合同审查助手..."
)
llm = LocalLLM(config)
```

### 调整生成参数
```python
config = LLMConfig(
    temperature=0.5,  # 降低随机性
    max_tokens=1024,  # 限制生成长度
    top_p=0.95
)
```

### 批量处理
```python
for file in pdf_files:
    result = processor.process_file(file)
    analysis = llm.analyze_ocr_text(result['full_text'])
    # 保存分析结果
```
