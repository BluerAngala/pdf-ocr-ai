#!/usr/bin/env python3
"""校验 PyInstaller 输出：onedir 目录或 onefile exe（含 OCR 冒烟）。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _verify_onedir(bundle: Path) -> int:
    exe = bundle / "gjj-ocr-server.exe"
    if not exe.is_file():
        print(f"[verify] 缺少主程序: {exe}", file=sys.stderr)
        return 1
    cfg_candidates = [
        bundle / "_internal" / "rapidocr_onnxruntime" / "config.yaml",
        bundle / "rapidocr_onnxruntime" / "config.yaml",
    ]
    cfg = next((p for p in cfg_candidates if p.is_file()), None)
    if cfg is None:
        print("[verify] 缺少 rapidocr_onnxruntime/config.yaml", file=sys.stderr)
        return 1
    onnx = list((cfg.parent / "models").glob("*.onnx")) if (cfg.parent / "models").is_dir() else []
    if not onnx:
        print(f"[verify] 缺少 ONNX 模型: {cfg.parent / 'models'}", file=sys.stderr)
        return 1
    print(f"[verify] OK onedir cfg={cfg} onnx={len(onnx)}")
    return 0


def _verify_onefile(exe: Path, resources: Path | None) -> int:
    if not exe.is_file():
        print(f"[verify] 缺少 onefile: {exe}", file=sys.stderr)
        return 1
    env = os.environ.copy()
    if resources and resources.is_dir():
        env["GJJ_OCR_RESOURCES"] = str(resources)
        env["GJJ_OCR_ROOT"] = str(resources)
    env.setdefault("PYTHONUTF8", "1")
    req = json.dumps(
        {"jsonrpc": "2.0", "method": "ocr.warmup", "params": {"skip_gpu_probe": True}, "id": 1},
        ensure_ascii=False,
    ) + "\n"
    proc = subprocess.Popen(
        [str(exe)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(exe.parent),
        env=env,
    )
    assert proc.stdin is not None
    proc.stdin.write(req)
    proc.stdin.flush()
    proc.stdin.close()
    deadline = time.time() + 180
    err_text = ""
    out_text = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        time.sleep(0.3)
    try:
        out_text, err_text = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        print("[verify] onefile OCR 冒烟超时", file=sys.stderr)
        return 1
    combined = (out_text or "") + (err_text or "")
    if "rapidocr_onnxruntime" in combined and "config.yaml" in combined and "No such file" in combined:
        print("[verify] onefile 仍缺 rapidocr config.yaml:", file=sys.stderr)
        print(combined[-2000:], file=sys.stderr)
        return 1
    if proc.returncode not in (0, None) and "No such file" in combined:
        print(f"[verify] onefile 进程退出 {proc.returncode}", file=sys.stderr)
        print(combined[-2000:], file=sys.stderr)
        return 1
    if '"result"' in (out_text or "") or '"status"' in (out_text or ""):
        print("[verify] OK onefile ocr.warmup")
        return 0
    if "JSON-RPC" in combined and "已启动" in combined:
        print("[verify] OK onefile (RPC started, warmup may still be in background)")
        return 0
    print("[verify] onefile did not receive valid RPC response", file=sys.stderr)
    print(combined[-2000:], file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: verify_server_bundle.py <exe或目录> [--resources DIR]", file=sys.stderr)
        return 2
    target = Path(sys.argv[1]).resolve()
    resources = None
    if "--resources" in sys.argv:
        i = sys.argv.index("--resources")
        if i + 1 < len(sys.argv):
            resources = Path(sys.argv[i + 1]).resolve()
    if target.is_file() and target.suffix.lower() == ".exe":
        return _verify_onefile(target, resources)
    if target.is_dir():
        return _verify_onedir(target)
    print(f"[verify] 无效目标: {target}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
