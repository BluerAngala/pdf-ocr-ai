# -*- mode: python ; coding: utf-8 -*-
# onefile：单 exe；显式打包 rapidocr_onnxruntime 的 config 和 ONNX 模型
import importlib
from pathlib import Path

datas = []
binaries = []
rapid_hidden = []

# 显式打包 rapidocr_onnxruntime（不依赖 collect_all，因为新版 PyInstaller 对非 package 模块会失败）
try:
    _pkg = Path(importlib.import_module("rapidocr_onnxruntime").__file__).resolve().parent
    print(f"[spec] rapidocr_onnxruntime path: {_pkg}")
    for rel in ("config.yaml",):
        src = _pkg / rel
        if src.is_file():
            datas.append((str(src), "rapidocr_onnxruntime"))
            print(f"[spec] Added: {src}")
    _models = _pkg / "models"
    if _models.is_dir():
        for onnx in _models.glob("*.onnx"):
            datas.append((str(onnx), "rapidocr_onnxruntime/models"))
            print(f"[spec] Added model: {onnx.name}")
except Exception as e:
    print(f"[spec] Error collecting rapidocr_onnxruntime: {e}")

# 打包 rapidocr（fallback）
try:
    _pkg2 = Path(importlib.import_module("rapidocr").__file__).resolve().parent
    for rel in ("default_models.yaml", "config.yaml"):
        src = _pkg2 / rel
        if src.is_file():
            datas.append((str(src), "rapidocr"))
    _models2 = _pkg2 / "models"
    if _models2.is_dir():
        for onnx in _models2.glob("*.onnx"):
            datas.append((str(onnx), "rapidocr/models"))
except Exception as e:
    print(f"[spec] Error collecting rapidocr: {e}")

hiddenimports = rapid_hidden + [
    "yaml",
    "rapidocr_onnxruntime",
    "rapidocr",
    "pdfplumber",
    "pdf2image",
    "openpyxl",
    "PIL",
    "numpy",
    "pypdf",
    "onnxruntime",
    "cv2",
    "win32print",
    "win32api",
    "win32con",
    "pywintypes",
    "pythoncom",
    "psutil",
]

a = Analysis(
    ["src\\server.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["runtime_utf8_hook.py"],
    excludes=["pytest", "pygments", "IPython", "matplotlib", "tkinter", "unittest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="gjj-ocr-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
