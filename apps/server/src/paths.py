import sys
import os
from pathlib import Path


def get_project_root() -> Path:
    env = os.environ.get("GJJ_OCR_ROOT")
    if env:
        return Path(env).resolve()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[3]


def get_server_src() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "server_src"
    return Path(__file__).resolve().parent


def get_resources_dir() -> Path:
    env = os.environ.get("GJJ_OCR_RESOURCES")
    if env:
        return Path(env).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


ROOT = get_project_root()
SERVER_SRC = get_server_src()
RESOURCES_DIR = get_resources_dir()
