#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地 LLM 管理器
支持多种本地模型：Gemma、Qwen、Llama、Phi 等
使用 llama-cpp-python 或 transformers 后端
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Generator, Any
from dataclasses import dataclass, asdict
import warnings

# 忽略警告
warnings.filterwarnings('ignore')


@dataclass
class LLMConfig:
    """LLM 配置"""
    model_path: str = ""  # 模型文件路径
    model_type: str = "auto"  # auto, gemma, qwen, llama, phi
    context_length: int = 8192
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    threads: int = 4  # CPU 线程数
    batch_size: int = 512
    gpu_layers: int = 0  # 0 = 纯CPU
    
    # 系统提示词
    system_prompt: str = """你是一个专业的法律文档分析助手。
你的任务是：
1. 检查OCR识别文本的准确性和完整性
2. 提取关键信息（案号、当事人、日期、金额等）
3. 识别文档类型和用途
4. 指出可能存在的错误或遗漏

请用中文回答，保持专业、准确的语气。"""


class LocalLLM:
    """本地大语言模型管理器"""
    
    # 推荐的模型列表
    RECOMMENDED_MODELS = {
        "gemma-3-4b": {
            "name": "Gemma 3 4B IT",
            "description": "Google最新模型，4B参数，128K上下文，中文强",
            "size": "约2.6GB (Q4量化)",
            "url": "https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF",
            "filename": "google_gemma-3-4b-it-Q4_K_M.gguf",
            "memory_required": "3-4GB",
            "recommended": True
        },
        "qwen2.5-1.5b": {
            "name": "Qwen2.5 1.5B Instruct",
            "description": "阿里最新模型，中文法律文档处理优秀",
            "size": "约1GB (Q4量化)",
            "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF",
            "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
            "memory_required": "2GB",
            "recommended": True
        },
        "qwen2.5-3b": {
            "name": "Qwen2.5 3B Instruct",
            "description": "阿里3B模型，性能更强",
            "size": "约1.9GB (Q4量化)",
            "url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF",
            "filename": "qwen2.5-3b-instruct-q4_k_m.gguf",
            "memory_required": "3GB",
            "recommended": False
        },
        "llama-3.2-3b": {
            "name": "Llama 3.2 3B Instruct",
            "description": "Meta官方，多语言支持好",
            "size": "约1.9GB (Q4量化)",
            "url": "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF",
            "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
            "memory_required": "3GB",
            "recommended": False
        },
        "phi-4": {
            "name": "Phi 4 14B (Q4量化)",
            "description": "微软推理王，量化后可在CPU运行",
            "size": "约8GB (Q4量化)",
            "url": "https://huggingface.co/bartowski/phi-4-GGUF",
            "filename": "phi-4-Q4_K_M.gguf",
            "memory_required": "10GB",
            "recommended": False
        }
    }
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self.llm = None
        self.tokenizer = None
        self._backend = None  # 'llama_cpp' or 'transformers'
        
    def list_recommended_models(self) -> Dict:
        """列出推荐的模型"""
        print("\n" + "=" * 70)
        print("🤖 推荐的本地模型（按优先级排序）")
        print("=" * 70)
        
        for key, info in self.RECOMMENDED_MODELS.items():
            rec_mark = "⭐ 推荐" if info.get('recommended') else ""
            print(f"\n📦 {info['name']} {rec_mark}")
            print(f"   描述: {info['description']}")
            print(f"   大小: {info['size']}")
            print(f"   内存需求: {info['memory_required']}")
            print(f"   下载: {info['url']}")
            print(f"   文件名: {info['filename']}")
        
        print("\n" + "=" * 70)
        print("💡 提示：建议下载 Q4_K_M 或 Q4_K_S 量化版本，平衡质量和速度")
        print("=" * 70 + "\n")
        
        return self.RECOMMENDED_MODELS
    
    def load_model(self, model_path: Optional[str] = None) -> bool:
        """
        加载模型
        支持 llama-cpp-python 和 transformers 两种后端
        """
        if model_path:
            self.config.model_path = model_path
        
        if not self.config.model_path:
            print("❌ 错误：未指定模型路径")
            print("请使用 list_recommended_models() 查看推荐模型")
            return False
        
        model_path = Path(self.config.model_path)
        if not model_path.exists():
            print(f"❌ 错误：模型文件不存在: {model_path}")
            print("\n请下载模型并放到正确位置，或运行：")
            print(f"  python scripts/download_model.py --model {model_path.name}")
            return False
        
        # 根据文件扩展名选择后端
        if model_path.suffix == '.gguf':
            return self._load_llama_cpp(str(model_path))
        else:
            return self._load_transformers(str(model_path))
    
    def _load_llama_cpp(self, model_path: str) -> bool:
        """使用 llama-cpp-python 加载 GGUF 模型"""
        try:
            from llama_cpp import Llama
            
            print(f"🔄 正在加载模型 (llama-cpp): {Path(model_path).name}")
            print(f"   上下文长度: {self.config.context_length}")
            print(f"   CPU线程: {self.config.threads}")
            print(f"   GPU层数: {self.config.gpu_layers}")
            
            self.llm = Llama(
                model_path=model_path,
                n_ctx=self.config.context_length,
                n_threads=self.config.threads,
                n_batch=self.config.batch_size,
                n_gpu_layers=self.config.gpu_layers,
                verbose=False
            )
            
            self._backend = 'llama_cpp'
            print(f"✅ 模型加载成功！")
            print(f"   词汇表大小: {self.llm.n_vocab()}")
            print(f"   上下文长度: {self.llm.n_ctx()}")
            return True
            
        except ImportError:
            print("❌ 错误：未安装 llama-cpp-python")
            print("\n请运行以下命令安装：")
            print("  pip install llama-cpp-python --no-cache-dir")
            return False
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            return False
    
    def _load_transformers(self, model_path: str) -> bool:
        """使用 transformers 加载 HuggingFace 模型"""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            
            print(f"🔄 正在加载模型 (transformers): {Path(model_path).name}")
            
            # 自动选择设备
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"   使用设备: {device}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                trust_remote_code=True
            )
            
            self.llm = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto" if device == "cuda" else None,
                trust_remote_code=True
            )
            
            if device == "cpu":
                self.llm = self.llm.to("cpu")
            
            self._backend = 'transformers'
            print(f"✅ 模型加载成功！")
            return True
            
        except ImportError:
            print("❌ 错误：未安装 transformers")
            print("\n请运行以下命令安装：")
            print("  pip install transformers torch")
            return False
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            return False
    
    def chat(self, message: str, system_prompt: Optional[str] = None) -> str:
        """
        单轮对话
        """
        if self.llm is None:
            return "错误：模型未加载"
        
        system = system_prompt or self.config.system_prompt
        
        if self._backend == 'llama_cpp':
            return self._chat_llama_cpp(message, system)
        else:
            return self._chat_transformers(message, system)
    
    def _chat_llama_cpp(self, message: str, system_prompt: str) -> str:
        """使用 llama-cpp 进行对话"""
        try:
            # 构建对话格式
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
            
            response = self.llm.create_chat_completion(
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                top_p=self.config.top_p,
                repeat_penalty=self.config.repeat_penalty
            )
            
            return response['choices'][0]['message']['content']
            
        except Exception as e:
            return f"生成失败: {e}"
    
    def _chat_transformers(self, message: str, system_prompt: str) -> str:
        """使用 transformers 进行对话"""
        try:
            # 构建对话格式（根据模型类型调整）
            if "qwen" in self.config.model_path.lower():
                # Qwen 格式
                prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{message}<|im_end|>\n<|im_start|>assistant\n"
            elif "gemma" in self.config.model_path.lower():
                # Gemma 格式
                prompt = f"<start_of_turn>user\n{message}<end_of_turn>\n<start_of_turn>model\n"
            else:
                # 通用格式
                prompt = f"System: {system_prompt}\n\nUser: {message}\n\nAssistant:"
            
            inputs = self.tokenizer(prompt, return_tensors="pt")
            if self.llm.device.type == "cuda":
                inputs = inputs.to("cuda")
            
            outputs = self.llm.generate(
                **inputs,
                max_new_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                do_sample=True
            )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            # 提取助手回复部分
            return response[len(prompt):].strip()
            
        except Exception as e:
            return f"生成失败: {e}"
    
    def analyze_ocr_text(self, text: str, task: str = "check") -> Dict:
        """
        分析 OCR 识别文本
        
        task: check(检查错误), extract(提取信息), classify(分类)
        """
        prompts = {
            "check": """请仔细检查以下OCR识别文本，完成以下任务：
1. 找出可能的识别错误（错别字、格式错误等）
2. 检查关键信息是否完整（案号、当事人、日期、金额等）
3. 指出格式不一致的地方
4. 给出修正建议

请用JSON格式返回结果：
{
  "errors": [{"original": "错误内容", "suggestion": "修正建议", "type": "错误类型"}],
  "missing_info": ["缺失的信息"],
  "format_issues": ["格式问题"],
  "overall_quality": "优秀/良好/一般/较差"
}""",
            "extract": """请从以下文本中提取关键信息，用JSON格式返回：
{
  "document_type": "文档类型",
  "case_numbers": ["案号列表"],
  "parties": {
    "applicant": "申请人",
    "respondent": "被申请人"
  },
  "dates": ["日期列表"],
  "amounts": ["金额列表"],
  "key_points": ["关键要点"]
}""",
            "classify": """请分析以下文本，判断文档类型和用途：
{
  "document_type": "裁定书/决定书/通知书/合同/其他",
  "category": "行政/民事/刑事/商事",
  "urgency": "高/中/低",
  "keywords": ["关键词列表"],
  "summary": "一句话摘要"
}"""
        }
        
        prompt = prompts.get(task, prompts["check"])
        full_prompt = f"{prompt}\n\n文本内容：\n{text[:3000]}"  # 限制长度
        
        response = self.chat(full_prompt)
        
        # 尝试解析 JSON
        try:
            # 提取 JSON 部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
        except:
            pass
        
        # 返回原始文本
        return {"raw_response": response}
    
    def get_model_info(self) -> Dict:
        """获取模型信息"""
        if self.llm is None:
            return {"status": "未加载"}
        
        info = {
            "backend": self._backend,
            "model_path": self.config.model_path,
            "status": "已加载"
        }
        
        if self._backend == 'llama_cpp':
            info.update({
                "vocab_size": self.llm.n_vocab(),
                "context_length": self.llm.n_ctx(),
                "embedding_size": self.llm.n_embd()
            })
        
        return info


def demo():
    """演示用法"""
    llm = LocalLLM()
    
    # 显示推荐模型
    llm.list_recommended_models()
    
    print("\n💡 使用示例：")
    print("""
# 1. 下载模型（手动或使用脚本）
# 推荐：Gemma 3 4B Q4_K_M 版本
# 下载地址：https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF

# 2. 加载模型
llm = LocalLLM()
llm.load_model("models/google_gemma-3-4b-it-Q4_K_M.gguf")

# 3. 分析OCR文本
result = llm.analyze_ocr_text(ocr_text, task="check")
print(json.dumps(result, ensure_ascii=False, indent=2))

# 4. 自定义对话
response = llm.chat("请总结这段文本的主要内容")
print(response)
""")


if __name__ == '__main__':
    demo()
