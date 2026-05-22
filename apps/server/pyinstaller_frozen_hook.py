"""PyInstaller 运行时：工作目录设为 exe 所在目录（onedir 布局）。"""
import os
import sys

if getattr(sys, "frozen", False) and hasattr(sys, "executable"):
    try:
        os.chdir(os.path.dirname(os.path.abspath(sys.executable)))
    except OSError:
        pass
