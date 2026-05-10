#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI模型下载脚本 - 直接下载最新可用模型
"""

import os
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path("c:/Users/11071/Documents/trae_projects/pdf识别/models")

# 2024-2025年最新可用的小模型
MODELS = [
    # SmolLM2 - 2024年9月 HuggingFace发布，360M超轻量但能力不错
    (
        "SmolLM2-360M",
        "SmolLM2-360M-Instruct-Q4_K_M.gguf",
        "https://www.modelscope.cn/models/bartowski/SmolLM2-360M-Instruct-GGUF/resolve/master/SmolLM2-360M-Instruct-Q4_K_M.gguf"
    ),
    # Qwen2.5-3B - 2024年9月发布，比1.5B更强
    (
        "Qwen2.5-3B-Instruct",
        "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
        "https://www.modelscope.cn/models/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/master/Qwen2.5-3B-Instruct-Q4_K_M.gguf"
    ),
]


def download_file(url: str, destination: Path) -> bool:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=600) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            
            with open(destination, 'wb') as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        mb = downloaded / (1024 * 1024)
                        print(f"\r  {percent:.1f}% ({mb:.1f} MB)", end='', flush=True)
        
        print()
        return True
        
    except Exception as e:
        print(f"\n失败: {e}")
        if destination.exists():
            destination.unlink()
        return False


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    
    for name, filename, url in MODELS:
        filepath = MODELS_DIR / filename
        
        if filepath.exists():
            size = filepath.stat().st_size / (1024 * 1024)
            print(f"[跳过] {name} 已存在 ({size:.1f} MB)")
            continue
        
        print(f"[下载] {name}")
        
        if download_file(url, filepath):
            size = filepath.stat().st_size / (1024 * 1024)
            print(f"[完成] {name} ({size:.1f} MB)")
        else:
            print(f"[失败] {name}")
            sys.exit(1)
    
    print("\n全部完成")


if __name__ == "__main__":
    main()
