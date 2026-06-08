# -*- mode: python ; coding: utf-8 -*-
# onefile：单 exe；RapidOCR 用 collect_all + 显式 datas，运行时由 pdf_ocr_ultra 指定 config_path
import importlib
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

# 优先使用 rapidocr_onnxruntime，同时打包 rapidocr 作为后备
try:
    _rapid_datas, _rapid_binaries, _rapid_hidden = collect_all("rapidocr_onnxruntime")
    datas = list(_rapid_datas)
    datas += collect_data_files("rapidocr_onnxruntime")
    _pkg = Path(importlib.import_module("rapidocr_onnxruntime").__file__).resolve().parent
    for rel in ("config.yaml",):
        src = _pkg / rel
        if src.is_file():
            datas.append((str(src), "rapidocr_onnxruntime"))
    _models = _pkg / "models"
    if _models.is_dir():
        for onnx in _models.glob("*.onnx"):
            datas.append((str(onnx), "rapidocr_onnxruntime/models"))
    binaries = list(_rapid_binaries)
    rapid_hidden = list(_rapid_hidden)
except Exception:
    datas = []
    binaries = []
    rapid_hidden = []

# 同时打包 rapidocr（后备方案）
try:
    _rapidocr_datas, _rapidocr_binaries, _rapidocr_hidden = collect_all("rapidocr")
    datas += list(_rapidocr_datas)
    datas += collect_data_files("rapidocr")
    _pkg2 = Path(importlib.import_module("rapidocr").__file__).resolve().parent
    for rel in ("default_models.yaml", "config.yaml"):
        src = _pkg2 / rel
        if src.is_file():
            datas.append((str(src), "rapidocr"))
    _models2 = _pkg2 / "models"
    if _models2.is_dir():
        for onnx in _models2.glob("*.onnx"):
            datas.append((str(onnx), "rapidocr/models"))
    binaries += list(_rapidocr_binaries)
    rapid_hidden += list(_rapidocr_hidden)
except Exception:
    pass
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
