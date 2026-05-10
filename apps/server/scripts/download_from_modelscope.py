#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从魔搭社区(ModelScope)下载模型
国内访问速度快，适合下载大模型
"""

import os
import sys
from pathlib import Path
from typing import Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# 模型配置
MODELS = {
    "gemma-4-e2b": {
        "model_id": "google/gemma-4-e2b-it",
        "files": ["gemma-4-e2b-it-Q4_K_M.gguf"],
        "description": "Google Gemma 4 E2B - 2B参数，超轻量",
        "size": "约1.3GB"
    },
    "gemma-4-e2b-assistant": {
        "model_id": "google/gemma-4-e2b-it-assistant",
        "files": ["gemma-4-e2b-it-assistant-Q4_K_M.gguf"],
        "description": "Google Gemma 4 E2B Assistant版",
        "size": "约1.3GB"
    },
    "qwen3.5-1.5b": {
        "model_id": "qwen/Qwen3.5-1.5B-Instruct-GGUF",
        "files": ["qwen3.5-1.5b-instruct-q4_k_m.gguf"],
        "description": "阿里 Qwen3.5 1.5B - 中文优秀",
        "size": "约900MB"
    },
    "qwen3.5-122b-a10b": {
        "model_id": "z-lab/Qwen3.5-122B-A10B-DFlash",
        "files": [],  # 需要查看实际文件
        "description": "z-lab Qwen3.5 122B A10B - 大模型蒸馏版",
        "size": "约?GB"
    }
}


def download_model(model_key: str, cache_dir: Optional[str] = None) -> bool:
    """从魔搭社区下载模型"""
    try:
        from modelscope import snapshot_download
        
        if model_key not in MODELS:
            print(f"❌ 未知模型: {model_key}")
            print(f"可用模型: {', '.join(MODELS.keys())}")
            return False
        
        model_info = MODELS[model_key]
        model_id = model_info["model_id"]
        
        print(f"\n{'='*70}")
        print(f"📥 下载模型: {model_key}")
        print(f"{'='*70}")
        print(f"模型ID: {model_id}")
        print(f"描述: {model_info['description']}")
        print(f"大小: {model_info['size']}")
        print(f"\n⏳ 开始下载...")
        
        # 设置缓存目录
        if cache_dir is None:
            cache_dir = str(Path(__file__).resolve().parents[3] / "models")
        
        # 下载模型
        local_dir = snapshot_download(
            model_id,
            cache_dir=cache_dir,
            local_dir=os.path.join(cache_dir, model_key)
        )
        
        print(f"\n✅ 下载完成!")
        print(f"📁 保存位置: {local_dir}")
        
        # 列出下载的文件
        local_path = Path(local_dir)
        gguf_files = list(local_path.glob("*.gguf"))
        
        if gguf_files:
            print(f"\n📄 GGUF文件:")
            for f in gguf_files:
                size_mb = f.stat().st_size / 1024 / 1024
                print(f"   - {f.name} ({size_mb:.1f} MB)")
        else:
            print(f"\n⚠️ 未找到GGUF文件，可能下载的是原始格式")
            print(f"   需要手动转换或使用transformers加载")
        
        return True
        
    except ImportError:
        print("❌ 错误: 未安装 modelscope")
        print("请运行: pip install modelscope")
        return False
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def list_models():
    """列出所有可用模型"""
    print("\n" + "="*70)
    print("📦 可用模型列表（魔搭社区）")
    print("="*70)
    
    for key, info in MODELS.items():
        print(f"\n🔹 {key}")
        print(f"   模型ID: {info['model_id']}")
        print(f"   描述: {info['description']}")
        print(f"   大小: {info['size']}")
    
    print("\n" + "="*70)
    print("💡 使用示例:")
    print("   python download_from_modelscope.py --model gemma-4-e2b")
    print("   python download_from_modelscope.py --model qwen3.5-1.5b")
    print("="*70 + "\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="从魔搭社区下载模型")
    parser.add_argument('--list', '-l', action='store_true', help='列出所有可用模型')
    parser.add_argument('--model', '-m', type=str, help='要下载的模型名称')
    parser.add_argument('--cache-dir', type=str, help='缓存目录（默认: models/）')
    
    args = parser.parse_args()
    
    if args.list or (not args.model):
        list_models()
        return 0
    
    success = download_model(args.model, args.cache_dir)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
