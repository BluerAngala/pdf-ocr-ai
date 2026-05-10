#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载适合老旧电脑的GGUF格式小模型
使用国内镜像加速下载
"""

import os
import sys
import urllib.request
from pathlib import Path
from typing import Optional

# 模型配置（轻量版）- 魔搭社区
MODELS = {
    # ==================== Qwen3 系列（最新推荐）====================
    "qwen3-0.5b": {
        "name": "Qwen3 0.5B",
        "description": "🆕 阿里最新Qwen3，300MB，适合4GB内存，比Qwen2.5更强",
        "modelscope_id": "Qwen/Qwen3-0.5B-Instruct-GGUF",
        "filename": "qwen3-0.5b-instruct-q4_k_m.gguf",
        "size": "300MB"
    },
    "qwen3-1.5b": {
        "name": "Qwen3 1.5B",
        "description": "🆕 阿里最新Qwen3，900MB，适合6-8GB内存，中文最强小模型",
        "modelscope_id": "Qwen/Qwen3-1.5B-Instruct-GGUF",
        "filename": "qwen3-1.5b-instruct-q4_k_m.gguf",
        "size": "900MB"
    },
    "qwen3-4b": {
        "name": "Qwen3 4B",
        "description": "🆕 阿里最新Qwen3，2.3GB，适合8GB内存，性能接近7B模型",
        "modelscope_id": "Qwen/Qwen3-4B-Instruct-GGUF",
        "filename": "qwen3-4b-instruct-q4_k_m.gguf",
        "size": "2.3GB"
    },
    # ==================== Qwen2.5 系列（备选）====================
    "qwen2.5-0.5b": {
        "name": "Qwen2.5 0.5B",
        "description": "阿里超轻量模型，300MB，适合4GB内存",
        "modelscope_id": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "size": "300MB"
    },
    "qwen2.5-1.5b": {
        "name": "Qwen2.5 1.5B",
        "description": "阿里轻量模型，900MB，适合6-8GB内存，中文优秀",
        "modelscope_id": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "size": "900MB"
    }
}


def download_file(url: str, dest_path: Path, show_progress: bool = True) -> bool:
    """下载文件并显示进度"""
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        if show_progress:
            print(f"\n📥 正在下载: {url.split('/')[-1]}")
            print(f"   目标: {dest_path}")
        
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


def download_model(model_key: str) -> bool:
    """使用魔搭社区下载指定模型"""
    try:
        from modelscope import snapshot_download
        
        if model_key not in MODELS:
            print(f"❌ 未知模型: {model_key}")
            print(f"可用模型: {', '.join(MODELS.keys())}")
            return False
        
        model_info = MODELS[model_key]
        model_id = model_info["modelscope_id"]
        filename = model_info["filename"]
        
        print(f"\n{'='*70}")
        print(f"🚀 开始下载: {model_info['name']}")
        print(f"{'='*70}")
        print(f"模型ID: {model_id}")
        print(f"描述: {model_info['description']}")
        print(f"预计大小: {model_info['size']}")
        print(f"\n⏳ 正在从魔搭社区下载...")
        
        # 设置保存目录
        models_dir = Path(__file__).resolve().parents[3] / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用魔搭下载
        local_dir = snapshot_download(
            model_id,
            cache_dir=str(models_dir),
            local_dir=str(models_dir / model_key)
        )
        
        print(f"\n✅ 下载完成!")
        print(f"📁 保存位置: {local_dir}")
        
        # 查找GGUF文件
        local_path = Path(local_dir)
        gguf_files = list(local_path.glob("*.gguf"))
        
        if gguf_files:
            print(f"\n📄 找到GGUF文件:")
            for f in gguf_files:
                size_mb = f.stat().st_size / 1024 / 1024
                print(f"   - {f.name} ({size_mb:.1f} MB)")
                
            # 如果找到目标文件，显示使用方式
            target_file = local_path / filename
            if target_file.exists():
                print(f"\n{'='*70}")
                print(f"✅ 模型准备就绪！")
                print(f"{'='*70}")
                print(f"\n💡 使用方式:")
                print(f"   python src/local_llm.py")
                print(f"   llm.load_model(\"models/{model_key}/{filename}\")")
                return True
        else:
            print(f"\n⚠️  未找到GGUF文件，可能下载的是原始格式")
            print(f"   请检查目录: {local_dir}")
            return False
        
        return True
        
    except ImportError:
        print("❌ 错误: 未安装 modelscope")
        print("请运行: pip install modelscope")
        return False
    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def list_models():
    """列出所有可用模型"""
    print("\n" + "="*70)
    print("📦 适合老旧电脑的轻量模型")
    print("="*70)
    
    for key, info in MODELS.items():
        print(f"\n🔹 {key}")
        print(f"   名称: {info['name']}")
        print(f"   描述: {info['description']}")
        print(f"   大小: {info['size']}")
    
    print("\n" + "="*70)
    print("💡 推荐（最新Qwen3）:")
    print("   4GB内存  → qwen3-0.5b (最新，比Qwen2.5更强)")
    print("   6-8GB内存 → qwen3-1.5b (最新，中文最强小模型)")
    print("   8GB+内存 → qwen3-4b (性能接近7B模型)")
    print("\n   备选（Qwen2.5）:")
    print("   4GB内存  → qwen2.5-0.5b")
    print("   6-8GB内存 → qwen2.5-1.5b")
    print("="*70 + "\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="下载适合老旧电脑的GGUF小模型",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有模型
  python download_gguf_models.py --list
  
  # 下载 Qwen2.5 0.5B（4GB内存推荐）
  python download_gguf_models.py --model qwen2.5-0.5b
  
  # 下载 Qwen2.5 1.5B（6-8GB内存推荐）
  python download_gguf_models.py --model qwen2.5-1.5b
        """
    )
    
    parser.add_argument('--list', '-l', action='store_true', help='列出所有可用模型')
    parser.add_argument('--model', '-m', type=str, help='要下载的模型名称')
    
    args = parser.parse_args()
    
    if args.list or (not args.model):
        list_models()
        return 0
    
    success = download_model(args.model)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
