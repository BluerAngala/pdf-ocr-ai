# 适合老旧电脑的超轻量模型（4-8GB内存）

## ⚠️ 重要说明

魔搭社区下载的是原始模型格式（safetensors），体积巨大（10-20GB），**不适合老旧电脑**。

你需要下载 **GGUF量化版本**，文件小、加载快、内存占用低。

---

## 🎯 真正适合老旧电脑的模型

### 方案一：从 HuggingFace 下载 GGUF（推荐）

#### 1. **TinyLlama 1.1B** ⭐ 最轻量
- **文件大小**：约 600MB (Q4_K_M)
- **运行内存**：约 1GB
- **下载地址**：
  ```
  https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF
  文件名：tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
  ```
- **特点**：
  - 仅1.1B参数，极致轻量
  - 适合简单文本检查
  - 英文为主，中文一般
- **适用**：内存<4GB的老旧电脑

#### 2. **Qwen2.5 0.5B** ⭐ 中文轻量
- **文件大小**：约 300MB (Q4_K_M)
- **运行内存**：约 500MB
- **下载地址**：
  ```
  https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF
  文件名：qwen2.5-0.5b-instruct-q4_k_m.gguf
  ```
- **特点**：
  - 仅0.5B参数，超轻量
  - 中文优化好
  - 阿里出品
- **适用**：纯中文简单任务

#### 3. **Qwen2.5 1.5B** ⭐ 平衡之选
- **文件大小**：约 900MB (Q4_K_M)
- **运行内存**：约 1.2GB
- **下载地址**：
  ```
  https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF
  文件名：qwen2.5-1.5b-instruct-q4_k_m.gguf
  ```
- **特点**：
  - 1.5B参数，质量较好
  - 中文优秀
  - 速度极快
- **适用**：4-6GB内存电脑

#### 4. **Phi-2 2.7B** ⭐ 推理强
- **文件大小**：约 1.6GB (Q4_K_M)
- **运行内存**：约 2GB
- **下载地址**：
  ```
  https://huggingface.co/TheBloke/phi-2-GGUF
  文件名：phi-2.Q4_K_M.gguf
  ```
- **特点**：
  - 微软出品，推理能力强
  - 2.7B参数但效果接近7B
  - 英文为主
- **适用**：需要推理能力的场景

#### 5. **Gemma 2B** ⭐ 谷歌轻量
- **文件大小**：约 1.3GB (Q4_K_M)
- **运行内存**：约 1.6GB
- **下载地址**：
  ```
  https://huggingface.co/bartowski/gemma-2-2b-it-GGUF
  文件名：gemma-2-2b-it-Q4_K_M.gguf
  ```
- **特点**：
  - Google出品
  - 2B参数，质量较好
  - 多语言支持
- **适用**：多语言简单任务

---

## 📊 对比表

| 模型 | 文件大小 | 运行内存 | 中文 | 速度 | 质量 | 推荐指数 |
|------|----------|----------|------|------|------|----------|
| **Qwen2.5 0.5B** | 300MB | 500MB | ⭐⭐⭐⭐ | ⚡⚡⚡⚡⚡ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **TinyLlama 1.1B** | 600MB | 1GB | ⭐⭐ | ⚡⚡⚡⚡⚡ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Qwen2.5 1.5B** | 900MB | 1.2GB | ⭐⭐⭐⭐⭐ | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Gemma 2B** | 1.3GB | 1.6GB | ⭐⭐⭐⭐ | ⚡⚡⚡ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Phi-2 2.7B** | 1.6GB | 2GB | ⭐⭐ | ⚡⚡⚡ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## 🚀 快速下载指南

### 方法1：使用 huggingface-cli（推荐）

```bash
# 安装 huggingface-cli
pip install huggingface-hub

# 下载 Qwen2.5 1.5B（推荐）
huggingface-cli download Qwen/Qwen2.5-1.5B-Instruct-GGUF qwen2.5-1.5b-instruct-q4_k_m.gguf --local-dir models --local-dir-use-symlinks False

# 下载 Qwen2.5 0.5B（极致轻量）
huggingface-cli download Qwen/Qwen2.5-0.5B-Instruct-GGUF qwen2.5-0.5b-instruct-q4_k_m.gguf --local-dir models --local-dir-use-symlinks False
```

### 方法2：使用 wget/curl 直接下载

```bash
# Qwen2.5 1.5B Q4_K_M
wget https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf -O models/qwen2.5-1.5b-instruct-q4_k_m.gguf

# Qwen2.5 0.5B Q4_K_M
wget https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf -O models/qwen2.5-0.5b-instruct-q4_k_m.gguf
```

### 方法3：使用国内镜像（速度快）

```bash
# 使用 hf-mirror 镜像
wget https://hf-mirror.com/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf -O models/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

---

## 💻 针对你的配置推荐

### 如果你的电脑是 4GB 内存：
**推荐：Qwen2.5 0.5B**
- 文件：300MB
- 内存：500MB
- 中文够用，速度极快

### 如果你的电脑是 6-8GB 内存：
**推荐：Qwen2.5 1.5B**
- 文件：900MB
- 内存：1.2GB
- 中文优秀，质量较好

---

## 📝 使用示例

```python
from src.local_llm import LocalLLM, LLMConfig

# 配置
config = LLMConfig(
    model_path="models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
    context_length=2048,  # 减小节省内存
    max_tokens=512,
    threads=2  # 根据CPU核心调整
)

# 加载
llm = LocalLLM(config)
llm.load_model()

# 使用
result = llm.analyze_ocr_text("你的OCR文本", task="check")
print(result)
```

---

## ⚡ 性能预期

在老旧CPU上（如Intel i5-4代）：

| 模型 | 加载时间 | 生成速度 | 检查一页 |
|------|----------|----------|----------|
| Qwen2.5 0.5B | <1秒 | 50+ tok/s | 1-2秒 |
| Qwen2.5 1.5B | 1-2秒 | 30+ tok/s | 2-3秒 |

---

## 🔧 内存优化技巧

1. **减小上下文长度**
   ```python
   config = LLMConfig(context_length=2048)  # 默认8192
   ```

2. **减少线程数**
   ```python
   config = LLMConfig(threads=2)  # 默认4
   ```

3. **使用更激进的量化**
   - Q4_K_S 比 Q4_K_M 节省 10% 内存
   - Q3_K_M 节省 25% 内存（质量稍降）

---

## ❓ 常见问题

**Q: 为什么魔搭社区下载的文件这么大？**
A: 魔搭社区默认下载原始模型（safetensors格式），需要你自己量化或找GGUF版本。

**Q: GGUF模型在哪里找？**
A: HuggingFace上搜索 "模型名 GGUF"，如 "qwen2.5 GGUF"。

**Q: 下载速度慢怎么办？**
A: 使用国内镜像 hf-mirror.com，或使用 huggingface-cli 断点续传。

**Q: 这些模型真的能在老旧电脑上运行吗？**
A: 是的！Qwen2.5 0.5B 只需要500MB内存，10年前的电脑都能跑。
