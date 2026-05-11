import sys
import os
from pathlib import Path


def get_project_root() -> Path:
    env = os.environ.get("GJJ_OCR_ROOT")
    if env:
        return Path(env).resolve()

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name == "gjj-ocr-server":
            return exe_dir.parent
        return exe_dir

    return Path(__file__).resolve().parents[3]


def get_server_src() -> Path:
    env = os.environ.get("GJJ_OCR_RESOURCES")
    if env:
        return Path(env).resolve() / "server_src"
    
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name == "gjj-ocr-server":
            return exe_dir.parent / "server_src"
        return exe_dir / "server_src"
    
    return Path(__file__).resolve().parent


def get_resources_dir() -> Path:
    env = os.environ.get("GJJ_OCR_RESOURCES")
    if env:
        return Path(env).resolve()
    
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name == "gjj-ocr-server":
            return exe_dir.parent
        return exe_dir
    
    return Path(__file__).resolve().parents[1]


def get_user_data_dir() -> Path:
    env = os.environ.get("GJJ_OCR_USER_DATA")
    if env:
        return Path(env).resolve()

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "gjj-ocr-tool"

    home = Path.home()
    if home.exists():
        return home / "AppData" / "Local" / "gjj-ocr-tool"

    return Path.cwd() / "user-data"


ROOT = get_project_root()
SERVER_SRC = get_server_src()
RESOURCES_DIR = get_resources_dir()
USER_DATA_DIR = get_user_data_dir()
