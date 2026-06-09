# -*- mode: python ; coding: utf-8 -*-
# onefile：单 exe；显式打包 rapidocr_onnxruntime 的 config 和 ONNX 模型
import importlib
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

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

# pandas 子模块（PyInstaller 经常漏收 pandas._libs 等 C 扩展）
_pandas_hidden = collect_submodules("pandas")
_pandas_datas = collect_data_files("pandas", include_py_files=False)
datas.extend(_pandas_datas)
print(f"[spec] pandas submodules: {len(_pandas_hidden)}, datas: {len(_pandas_datas)}")

# pywin32 子模块 + DLL（打印服务依赖 win32print/win32api 等）
_win32_hidden = collect_submodules("win32") + collect_submodules("win32com")
_win32_datas = collect_data_files("win32", include_py_files=False)
datas.extend(_win32_datas)
# pywintypesXX.dll 和 pythoncomXX.dll 在 venv 根目录，collect 找不到，手动收集
for _dll_name in ("pywintypes312.dll", "pythoncom312.dll"):
    _dll = Path(importlib.import_module("pywintypes" if "pywintypes" in _dll_name else "pythoncom").__file__).resolve()
    if _dll.exists():
        binaries.append((str(_dll), "."))
        print(f"[spec] Added DLL: {_dll}")
print(f"[spec] win32 submodules: {len(_win32_hidden)}, datas: {len(_win32_datas)}")

hiddenimports = rapid_hidden + _pandas_hidden + _win32_hidden + [
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
    "requests",
    "flask",
    "flask_cors",
    "rapidfuzz",
    "winreg",
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
