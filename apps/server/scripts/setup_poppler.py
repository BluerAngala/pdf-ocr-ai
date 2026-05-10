#!/usr/bin/env python3
"""
Poppler 自动下载和配置脚本
首次运行项目时自动下载并配置 poppler 工具
"""

import os
import sys
import zipfile
import urllib.request
from pathlib import Path
from typing import Optional

# Poppler Windows 版本下载链接
POPPLER_URL = "https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip"
POPPLER_VERSION = "24.08.0"


def get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).resolve().parents[3]


def get_poppler_dir() -> Path:
    """获取 poppler 安装目录"""
    return get_project_root() / "tools" / "poppler"


def check_poppler_exists() -> bool:
    """检查 poppler 是否已安装"""
    poppler_dir = get_poppler_dir()
    if not poppler_dir.exists():
        return False

    # 检查关键可执行文件是否存在
    pdftoppm = poppler_dir / f"poppler-{POPPLER_VERSION}" / "Library" / "bin" / "pdftoppm.exe"
    return pdftoppm.exists()


def download_file(url: str, dest: Path, chunk_size: int = 8192) -> None:
    """下载文件并显示进度"""
    print(f"正在下载 poppler ({POPPLER_VERSION})...")
    print(f"来源: {url}")
    print(f"目标: {dest}")
    print()

    def report_progress(block_num: int, block_size: int, total_size: int) -> None:
        downloaded = block_num * block_size
        percent = min(100, int(downloaded * 100 / total_size))
        bar_length = 40
        filled = int(bar_length * percent / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        print(f"\r进度: [{bar}] {percent}% ({downloaded // 1024 // 1024}MB / {total_size // 1024 // 1024}MB)", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, dest, reporthook=report_progress)
        print("\n下载完成！")
    except Exception as e:
        if dest.exists():
            dest.unlink()
        raise RuntimeError(f"下载失败: {e}")


def extract_zip(zip_path: Path, extract_to: Path) -> None:
    """解压 zip 文件"""
    print(f"\n正在解压到 {extract_to}...")
    extract_to.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

    print("解压完成！")


def setup_poppler() -> Optional[Path]:
    """
    设置 poppler 环境
    返回 poppler bin 目录路径，如果设置失败返回 None
    """
    # 检查是否已存在
    if check_poppler_exists():
        poppler_bin = get_poppler_dir() / f"poppler-{POPPLER_VERSION}" / "Library" / "bin"
        print(f"✓ Poppler 已安装: {poppler_bin}")
        return poppler_bin

    print("=" * 60)
    print("首次运行配置 - 下载 Poppler")
    print("=" * 60)
    print()

    poppler_dir = get_poppler_dir()
    zip_path = poppler_dir / "poppler.zip"

    try:
        # 创建目录
        poppler_dir.mkdir(parents=True, exist_ok=True)

        # 下载
        download_file(POPPLER_URL, zip_path)

        # 解压
        extract_zip(zip_path, poppler_dir)

        # 清理 zip 文件
        zip_path.unlink()
        print(f"✓ 清理临时文件: {zip_path.name}")

        # 验证安装
        if check_poppler_exists():
            poppler_bin = poppler_dir / f"poppler-{POPPLER_VERSION}" / "Library" / "bin"
            print(f"\n✅ Poppler 安装成功！")
            print(f"   路径: {poppler_bin}")
            return poppler_bin
        else:
            print("\n❌ 安装验证失败")
            return None

    except Exception as e:
        print(f"\n❌ 安装失败: {e}")
        # 清理
        if zip_path.exists():
            zip_path.unlink()
        return None


def main() -> int:
    """主函数"""
    print("PDF OCR - Poppler 环境配置工具\n")

    if sys.platform != "win32":
        print("⚠️  非 Windows 系统检测到")
        print("   Linux/Mac 用户请使用包管理器安装 poppler:")
        print("   - Ubuntu/Debian: sudo apt-get install poppler-utils")
        print("   - macOS: brew install poppler")
        return 0

    poppler_bin = setup_poppler()

    if poppler_bin:
        print("\n" + "=" * 60)
        print("配置完成！可以开始使用 PDF OCR 工具了。")
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print("配置失败。请手动安装 poppler 并配置环境变量。")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
