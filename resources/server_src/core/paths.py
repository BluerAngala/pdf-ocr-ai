"""
运行时路径 — 全项目唯一入口。

环境变量（由 Tauri 启动 Python 时注入）：
  GJJ_OCR_ROOT       安装目录（exe 所在目录，只读应用根）
  GJJ_OCR_RESOURCES  内嵌资源目录（config、sample-data、poppler、server_src）
  GJJ_OCR_USER_DATA  可写用户数据（output、缓存、日志）

开发态未设置环境变量时自动推断仓库布局。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Union


def path_for_display(path: Union[Path, str]) -> str:
    """去掉 Windows 长路径前缀 \\\\?\\，供前端展示（不影响文件访问）。"""
    text = os.fspath(path)
    if os.name != "nt":
        return text
    norm = text.replace("/", "\\")
    if norm.startswith("\\\\?\\UNC\\"):
        return "\\\\" + norm[8:]
    if norm.startswith("\\\\?\\"):
        return norm[4:]
    return text


def get_app_root() -> Path:
    env = os.environ.get("GJJ_OCR_ROOT")
    if env:
        return Path(env).resolve()

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name == "gjj-ocr-server":
            return exe_dir.parent.parent
        return exe_dir.parent if exe_dir.name == "resources" else exe_dir

    return Path(__file__).resolve().parents[4]


def get_resources_dir() -> Path:
    env = os.environ.get("GJJ_OCR_RESOURCES")
    if env:
        return Path(env).resolve()

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name == "gjj-ocr-server":
            return exe_dir.parent
        return exe_dir

    root = get_app_root()
    if (root / "sample-data").is_dir():
        return root
    project_resources = root / "resources"
    if project_resources.is_dir():
        return project_resources.resolve()
    return root.resolve()


def get_user_data_dir() -> Path:
    env = os.environ.get("GJJ_OCR_USER_DATA")
    if env:
        path = Path(env).resolve()
    else:
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            path = Path(local_appdata) / "gjj-ocr-tool"
        else:
            path = Path.home() / "AppData" / "Local" / "gjj-ocr-tool"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_path() -> Path:
    """打包：resources/config.yaml；开发：仓库根 config.yaml。"""
    resources_cfg = get_resources_dir() / "config.yaml"
    app_cfg = get_app_root() / "config.yaml"
    nested_cfg = get_app_root() / "resources" / "config.yaml"
    if getattr(sys, "frozen", False):
        order = [resources_cfg, nested_cfg, app_cfg]
    else:
        order = [app_cfg, resources_cfg, nested_cfg]
    for path in order:
        if path.is_file():
            return path.resolve()
    return resources_cfg if getattr(sys, "frozen", False) else app_cfg


def get_server_src() -> Path:
    if getattr(sys, "frozen", False):
        return get_resources_dir() / "server_src"
    return Path(__file__).resolve().parents[1]


def get_data_roots() -> List[Path]:
    """解析 sample-data / 样本材料 时的搜索根（顺序 matters）。"""
    roots: List[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        try:
            key = str(path.resolve())
        except OSError:
            return
        if key in seen:
            return
        seen.add(key)
        roots.append(path.resolve())

    add(get_resources_dir())
    add(get_app_root())
    app = get_app_root()
    if (app / "resources").is_dir():
        add(app / "resources")
    if not getattr(sys, "frozen", False) and (app / "样本材料").is_dir():
        add(app)
    return roots


def resolve_input_path(
    path_arg: str | None,
    preset_id: str | None = None,
    preset_kind: str = "sample",
    default_preset_id: str | None = None,
) -> Path:
    """
    统一解析 RPC/CLI 传入的路径参数。
    - 绝对路径且存在：直接使用
    - 绝对路径不存在 + preset_id：回退预设
    - 相对路径：按 data_roots / preset_paths 搜索
    - 均未提供：default_preset_id 或 preset_id
    """
    from core.preset_paths import resolve_path_candidates, resolve_preset

    if path_arg:
        raw = str(path_arg).strip()
        if not raw:
            pass
        else:
            p = Path(raw)
            if p.is_absolute():
                if p.exists():
                    return p.resolve()
                if preset_id:
                    try:
                        return resolve_preset(preset_id, preset_kind)  # type: ignore[arg-type]
                    except (FileNotFoundError, KeyError):
                        pass
                raise FileNotFoundError(f"路径不存在: {p}")
            return resolve_path_candidates([raw])

    pid = preset_id or default_preset_id
    if pid:
        return resolve_preset(pid, preset_kind)  # type: ignore[arg-type]

    raise FileNotFoundError(
        f"未指定路径且无可用预设 (preset_id={preset_id!r}, {describe_runtime_paths()})"
    )


def describe_runtime_paths() -> str:
    cfg = get_config_path()
    return (
        f"APP_ROOT={get_app_root()}, RESOURCES={get_resources_dir()}, "
        f"USER_DATA={get_user_data_dir()}, CONFIG={cfg} (exists={cfg.is_file()})"
    )


# 向后兼容别名
ROOT = get_app_root()
SERVER_SRC = get_server_src()
RESOURCES_DIR = get_resources_dir()
USER_DATA_DIR = get_user_data_dir()
CONFIG_PATH = get_config_path()
