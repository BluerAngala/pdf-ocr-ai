#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型下载脚本
支持从 HuggingFace 下载 GGUF 格式的量化模型
"""

import os
import sys
import argparse
import urllib.request
from pathlib import Path
from typing import Optional

# 模型仓库映射
MODEL_REPOS = {
    # ==================== 2026年最新模型（推荐）====================
    "gemma-4-e2b": {
        "repo": "bartowski/google_gemma-4-e2b-it-GGUF",
        "files": {
            "Q4_K_M": "gemma-4-e2b-it-Q4_K_M.gguf",
            "Q4_K_S": "gemma-4-e2b-it-Q4_K_S.gguf",
            "Q5_K_M": "gemma-4-e2b-it-Q5_K_M.gguf",
        },
        "recommended": "Q4_K_M",
        "description": "🆕 Google Gemma 4 E2B (2026.4) - 2B参数，手机端最优，超轻量"
    },
    "gemma-4-e4b": {
        "repo": "bartowski/google_gemma-4-e4b-it-GGUF",
        "files": {
            "Q4_K_M": "gemma-4-e4b-it-Q4_K_M.gguf",
            "Q4_K_S": "gemma-4-e4b-it-Q4_K_S.gguf",
            "Q5_K_M": "gemma-4-e4b-it-Q5_K_M.gguf",
        },
        "recommended": "Q4_K_M",
        "description": "🆕 Google Gemma 4 E4B (2026.4) - 4B参数，性能更强"
    },
    "qwen3.5-0.5b": {
        "repo": "Qwen/Qwen3.5-0.5B-Instruct-GGUF",
        "files": {
            "Q4_K_M": "qwen3.5-0.5b-instruct-q4_k_m.gguf",
            "Q4_0": "qwen3.5-0.5b-instruct-q4_0.gguf",
        },
        "recommended": "Q4_K_M",
        "description": "🆕 阿里 Qwen3.5 0.5B (2026.3) - 300MB超轻量，速度极快"
    },
    "qwen3.5-1.5b": {
        "repo": "Qwen/Qwen3.5-1.5B-Instruct-GGUF",
        "files": {
            "Q4_K_M": "qwen3.5-1.5b-instruct-q4_k_m.gguf",
            "Q4_0": "qwen3.5-1.5b-instruct-q4_0.gguf",
            "Q5_K_M": "qwen3.5-1.5b-instruct-q5_k_m.gguf",
        },
        "recommended": "Q4_K_M",
        "description": "🆕 阿里 Qwen3.5 1.5B (2026.3) - 中文OCR检查首选，900MB"
    },
    "phi-4-mini": {
        "repo": "bartowski/phi-4-mini-instruct-GGUF",
        "files": {
            "Q4_K_M": "phi-4-mini-instruct-Q4_K_M.gguf",
            "Q4_K_S": "phi-4-mini-instruct-Q4_K_S.gguf",
        },
        "recommended": "Q4_K_M",
        "description": "🆕 微软 Phi-4 Mini (2026) - 3.8B参数，推理强，200K上下文"
    },
    # ==================== 2025年模型（备选）====================
    "gemma-3-4b": {
        "repo": "bartowski/google_gemma-3-4b-it-GGUF",
        "files": {
            "Q4_K_M": "google_gemma-3-4b-it-Q4_K_M.gguf",
            "Q4_K_S": "google_gemma-3-4b-it-Q4_K_S.gguf",
            "Q5_K_M": "google_gemma-3-4b-it-Q5_K_M.gguf",
            "Q6_K": "google_gemma-3-4b-it-Q6_K.gguf",
        },
        "recommended": "Q4_K_M",
        "description": "Google Gemma 3 4B - 轻量级模型，中文优秀"
    },
    "qwen2.5-1.5b": {
        "repo": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "files": {
            "Q4_K_M": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
            "Q4_0": "qwen2.5-1.5b-instruct-q4_0.gguf",
            "Q5_K_M": "qwen2.5-1.5b-instruct-q5_k_m.gguf",
        },
        "recommended": "Q4_K_M",
        "description": "阿里 Qwen2.5 1.5B - 中文法律文档处理优秀"
    },
    "qwen2.5-3b": {
        "repo": "Qwen/Qwen2.5-3B-Instruct-GGUF",
        "files": {
            "Q4_K_M": "qwen2.5-3b-instruct-q4_k_m.gguf",
            "Q4_0": "qwen2.5-3b-instruct-q4_0.gguf",
        },
        "recommended": "Q4_K_M",
        "description": "阿里 Qwen2.5 3B - 性能更强"
    },
    "llama-3.2-3b": {
        "repo": "bartowski/Llama-3.2-3B-Instruct-GGUF",
        "files": {
            "Q4_K_M": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
            "Q4_K_S": "Llama-3.2-3B-Instruct-Q4_K_S.gguf",
        },
        "recommended": "Q4_K_M",
        "description": "Meta Llama 3.2 3B - 多语言支持好"
    },
    "phi-4": {
        "repo": "bartowski/phi-4-GGUF",
        "files": {
            "Q4_K_M": "phi-4-Q4_K_M.gguf",
            "Q4_K_S": "phi-4-Q4_K_S.gguf",
        },
        "recommended": "Q4_K_M",
        "description": "微软 Phi 4 14B - 推理能力极强（需要10GB+内存）"
    }
}


def get_hf_url(repo: str, filename: str) -> str:
    """构建 HuggingFace 下载链接"""
    return f"https://huggingface.co/{repo}/resolve/main/{filename}"


def get_mirror_url(repo: str, filename: str, mirror: str = "hf-mirror") -> str:
    """构建镜像下载链接"""
    if mirror == "hf-mirror":
        return f"https://hf-mirror.com/{repo}/resolve/main/{filename}"
    return get_hf_url(repo, filename)


def download_file(url: str, dest_path: Path, show_progress: bool = True) -> bool:
    """下载文件并显示进度"""
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        if show_progress:
            print(f"\n📥 正在下载: {url}")
            print(f"   目标: {dest_path}")
        
        # 获取文件大小
        req = urllib.request.Request(url, method='HEAD')
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                total_size = int(response.headers.get('Content-Length', 0))
        except:
            total_size = 0
        
        # 下载文件
        def report_progress(block_num: int, block_size: int, total_size: int):
            if total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, int(downloaded * 100 / total_size))
                mb_downloaded = downloaded / 1024 / 1024
                mb_total = total_size / 1024 / 1024
                print(f"\r   进度: {percent}% ({mb_downloaded:.1f}MB / {mb_total:.1f}MB)", end="", flush=True)
        
        urllib.request.urlretrieve(url, dest_path, reporthook=report_progress if show_progress else None)
        
        if show_progress:
            print("\n   ✅ 下载完成！")
        
        return True
        
    except Exception as e:
        if show_progress:
            print(f"\n   ❌ 下载失败: {e}")
        # 清理失败的文件
        if dest_path.exists():
            dest_path.unlink()
        return False


def list_models():
    """列出所有可用模型"""
    print("\n" + "=" * 70)
    print("📦 可用的模型列表")
    print("=" * 70)
    
    for key, info in MODEL_REPOS.items():
        print(f"\n🔹 {key}")
        print(f"   描述: {info['description']}")
        print(f"   推荐量化: {info['recommended']}")
        print(f"   可用版本: {', '.join(info['files'].keys())}")
        print(f"   仓库: https://huggingface.co/{info['repo']}")
    
    print("\n" + "=" * 70)
    print("💡 使用示例:")
    print("   python download_model.py --model gemma-3-4b")
    print("   python download_model.py --model qwen2.5-1.5b --quant Q4_K_M")
    print("=" * 70 + "\n")


def download_model(model_key: str, quant: Optional[str] = None, use_mirror: bool = True) -> bool:
    """下载指定模型"""
    
    if model_key not in MODEL_REPOS:
        print(f"❌ 错误：未知模型 '{model_key}'")
        print(f"可用模型: {', '.join(MODEL_REPOS.keys())}")
        return False
    
    model_info = MODEL_REPOS[model_key]
    
    # 选择量化版本
    if quant is None:
        quant = model_info['recommended']
    
    if quant not in model_info['files']:
        print(f"❌ 错误：量化版本 '{quant}' 不可用")
        print(f"可用版本: {', '.join(model_info['files'].keys())}")
        return False
    
    filename = model_info['files'][quant]
    repo = model_info['repo']
    
    # 构建下载链接
    if use_mirror:
        url = get_mirror_url(repo, filename)
    else:
        url = get_hf_url(repo, filename)
    
    # 设置保存路径
    models_dir = Path(__file__).parent.parent / "models"
    dest_path = models_dir / filename
    
    # 检查是否已存在
    if dest_path.exists():
        print(f"⚠️  模型文件已存在: {dest_path}")
        response = input("   是否重新下载? (y/N): ")
        if response.lower() != 'y':
            print("   跳过下载")
            return True
        dest_path.unlink()
    
    # 下载
    print(f"\n🚀 开始下载模型: {model_key} ({quant})")
    print(f"   描述: {model_info['description']}")
    
    success = download_file(url, dest_path)
    
    if success:
        print(f"\n✅ 模型下载成功！")
        print(f"   文件: {dest_path}")
        print(f"   大小: {dest_path.stat().st_size / 1024 / 1024:.1f} MB")
        print(f"\n💡 使用方式:")
        print(f"   python src/local_llm.py")
        print(f"   llm.load_model(\"models/{filename}\")")
    else:
        print(f"\n❌ 下载失败，尝试使用官方源...")
        url = get_hf_url(repo, filename)
        success = download_file(url, dest_path)
    
    return success


def main():
    parser = argparse.ArgumentParser(
        description="下载本地 LLM 模型",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有可用模型
  python download_model.py --list
  
  # 下载推荐的 Gemma 3 4B 模型
  python download_model.py --model gemma-3-4b
  
  # 下载指定量化版本
  python download_model.py --model qwen2.5-1.5b --quant Q4_K_M
  
  # 使用官方源下载（不使用镜像）
  python download_model.py --model gemma-3-4b --no-mirror
        """
    )
    
    parser.add_argument('--list', '-l', action='store_true', help='列出所有可用模型')
    parser.add_argument('--model', '-m', type=str, help='要下载的模型名称')
    parser.add_argument('--quant', '-q', type=str, help='量化版本 (默认使用推荐版本)')
    parser.add_argument('--no-mirror', action='store_true', help='不使用镜像，直接从HuggingFace下载')
    
    args = parser.parse_args()
    
    if args.list or (not args.model):
        list_models()
        return 0
    
    success = download_model(
        model_key=args.model,
        quant=args.quant,
        use_mirror=not args.no_mirror
    )
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
