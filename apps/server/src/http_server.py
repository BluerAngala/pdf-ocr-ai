#!/usr/bin/env python3
"""
公积金 OCR 工具 - HTTP 服务端
提供 RESTful API 供 Tauri 前端调用，替代原有的 stdin/stdout JSON-RPC 模式
"""

import json
import os
import sys
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# 设置 UTF-8 编码
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# 路径设置（必须在导入其他模块前）
if getattr(sys, "frozen", False):
    _exe_dir = Path(sys.executable).resolve().parent
    _resources = Path(os.environ.get("GJJ_OCR_RESOURCES", str(_exe_dir.parent)))
    _external = _resources / "server_src"
    if (_external / "core" / "preset_paths.py").is_file():
        _server_src = _external
        if str(_server_src) not in sys.path:
            sys.path.insert(0, str(_server_src))
else:
    _server_src = Path(__file__).resolve().parent
    if str(_server_src) not in sys.path:
        sys.path.insert(0, str(_server_src))

from core.paths import (
    ROOT,
    SERVER_SRC,
    USER_DATA_DIR,
    RESOURCES_DIR,
    get_app_root,
    get_resources_dir,
    get_user_data_dir,
    resolve_input_path,
    describe_runtime_paths,
    path_for_display,
)
from core.task_cancel import CancelledError, request_cancel, is_cancelled, clear as clear_task

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局状态
_server_start_time = datetime.now()
_active_tasks: Dict[str, Dict[str, Any]] = {}
_task_results: Dict[str, Dict[str, Any]] = {}
_progress_callbacks: Dict[str, callable] = {}


def _make_task_output_dir(task_id: str = "", module: str = "", user_dir: str = "") -> Path:
    """创建任务输出目录"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    parts = [ts]
    if module:
        parts.append(module)
    if task_id:
        parts.append(task_id)
    subfolder = "_".join(parts)
    base = Path(user_dir) if user_dir else USER_DATA_DIR / "output"
    d = base / subfolder
    d.mkdir(parents=True, exist_ok=True)
    return d


def _dir_has_pdfs(dir_path: Path) -> bool:
    """检查目录是否包含 PDF 文件"""
    return any(dir_path.rglob('*.pdf'))


class ProgressEmitter:
    """进度推送器 - 通过回调函数推送进度"""
    def __init__(self, task_id: str = "default"):
        self.task_id = task_id

    def progress(self, phase: str, current: int, total: int, message: str,
                 file_current: int = 0, file_total: int = 0, detail: Optional[Dict] = None):
        """发送进度更新"""
        params = {
            "task_id": self.task_id,
            "phase": phase,
            "status": "running",
            "current": current,
            "total": total,
            "file_current": file_current,
            "file_total": file_total,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        if detail:
            params["detail"] = detail
        
        # 存储到任务状态
        if self.task_id in _active_tasks:
            _active_tasks[self.task_id]["last_progress"] = params
        
        # 调用回调（如果有）
        callback = _progress_callbacks.get(self.task_id)
        if callback:
            try:
                callback(params)
            except Exception:
                pass

    def log(self, level: str, message: str):
        """发送日志"""
        params = {
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        if self.task_id in _active_tasks:
            _active_tasks[self.task_id]["last_log"] = params

    def complete(self, success: bool = True, result: Any = None, error: str = None):
        """标记任务完成"""
        params = {
            "task_id": self.task_id,
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
        if success:
            params["result"] = result
        else:
            params["error"] = error
        
        _task_results[self.task_id] = params
        if self.task_id in _active_tasks:
            _active_tasks[self.task_id]["status"] = "completed" if success else "failed"
            _active_tasks[self.task_id]["result"] = params


# ============ 健康检查端点 ============

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "version": "1.1.1",
        "uptime_seconds": (datetime.now() - _server_start_time).total_seconds(),
        "active_tasks": len(_active_tasks),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    })


@app.route('/ready', methods=['GET'])
def ready_check():
    """就绪检查端点 - 用于检查 OCR 引擎是否就绪"""
    try:
        # 检查核心模块是否可以导入
        from core.pdf_ocr_ultra import UltraFastOCR, OCRConfig
        return jsonify({
            "ready": True,
            "ocr_engine": "RapidOCR",
            "mode": "lazy_load"  # 延迟加载模式
        })
    except Exception as e:
        return jsonify({
            "ready": False,
            "error": str(e)
        }), 503


# ============ 任务管理端点 ============

@app.route('/task/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id: str):
    """取消任务"""
    request_cancel(task_id)
    
    # 同时取消打印任务（如果存在）
    try:
        from infra.print_service import cancel_print_task as _cancel_print
        _cancel_print(task_id)
    except Exception:
        pass
    
    return jsonify({
        "cancelled": True,
        "task_id": task_id,
        "was_active": task_id in _active_tasks
    })


@app.route('/task/<task_id>/status', methods=['GET'])
def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id in _active_tasks:
        return jsonify(_active_tasks[task_id])
    if task_id in _task_results:
        return jsonify(_task_results[task_id])
    return jsonify({"error": "Task not found"}), 404


@app.route('/task/<task_id>/progress', methods=['GET'])
def get_task_progress(task_id: str):
    """获取任务最新进度（SSE 长轮询替代方案）"""
    if task_id in _active_tasks:
        task = _active_tasks[task_id]
        return jsonify({
            "task_id": task_id,
            "status": task.get("status", "unknown"),
            "progress": task.get("last_progress"),
            "log": task.get("last_log")
        })
    return jsonify({"error": "Task not found"}), 404


# ============ OCR 端点 ============

@app.route('/ocr/warmup', methods=['POST'])
def ocr_warmup():
    """OCR 预热 - 延迟加载模式，立即返回成功"""
    return jsonify({
        "status": "warm",
        "duration_seconds": 0.01,
        "provider": "auto",
        "provider_info": "延迟加载模式：模型将在首次识别时自动初始化"
    })


@app.route('/ocr/recognize', methods=['POST'])
def ocr_recognize():
    """单文件 OCR 识别"""
    data = request.get_json() or {}
    file_path = data.get('file_path')
    force_ocr = data.get('force_ocr', False)
    task_id = data.get('task_id', f"ocr-{uuid.uuid4().hex[:8]}")
    
    _active_tasks[task_id] = {
        "task_id": task_id,
        "status": "running",
        "type": "ocr_recognize",
        "started_at": datetime.now().isoformat()
    }
    
    try:
        from core.pdf_ocr_ultra import UltraFastOCR, OCRConfig
        config = OCRConfig()
        ocr = UltraFastOCR(config, skip_warmup=True)
        result = ocr.process_file(file_path, force_ocr=force_ocr)
        
        if result is None:
            raise Exception("OCR 处理失败")
        
        _active_tasks[task_id]["status"] = "completed"
        return jsonify({
            "success": True,
            "task_id": task_id,
            "result": {
                "filename": result['filename'],
                "total_pages": result['total_pages'],
                "pages": result['pages'],
                "full_text": result['full_text'],
                "total_duration": result['total_duration']
            }
        })
    except Exception as e:
        _active_tasks[task_id]["status"] = "failed"
        _active_tasks[task_id]["error"] = str(e)
        return jsonify({
            "success": False,
            "task_id": task_id,
            "error": str(e)
        }), 500


@app.route('/ocr/clear-cache', methods=['POST'])
def ocr_clear_cache():
    """清除 OCR 结果缓存"""
    cache_path = USER_DATA_DIR / 'output' / 'ocr-cache.pkl'
    if cache_path.exists():
        cache_path.unlink()
        return jsonify({"status": "cleared"})
    return jsonify({"status": "no_cache"})


# ============ 非诉审查端点 ============

@app.route('/non-litigation/process', methods=['POST'])
def non_litigation_process():
    """非诉审查完整处理流程"""
    data = request.get_json() or {}
    preset_id = data.get('preset_id')
    sample_root = data.get('sample_root')
    excel_path = data.get('excel_path')
    mode = data.get('mode', 'mock')
    force = data.get('force', False)
    task_id = data.get('task_id', f"nl-{uuid.uuid4().hex[:8]}")
    user_output_dir = data.get('output_dir')
    
    _active_tasks[task_id] = {
        "task_id": task_id,
        "status": "running",
        "type": "non_litigation",
        "started_at": datetime.now().isoformat()
    }
    
    emitter = ProgressEmitter(task_id)
    
    if force:
        cache_path = USER_DATA_DIR / 'output' / 'ocr-cache.pkl'
        if cache_path.exists():
            cache_path.unlink()
        for db in (USER_DATA_DIR / 'temp').glob('streaming_*.db'):
            db.unlink(missing_ok=True)
    
    try:
        emitter.log("debug", f"收到参数: preset_id={preset_id!r}, sample_root={sample_root!r}, excel_path={excel_path!r}")
        
        from non_litigation.export import (
            build_mock_ocr_results, run_real_ocr,
            ensure_non_litigation_input_structure,
            export_non_litigation_standard_outputs,
            get_non_litigation_result_root,
        )
        from non_litigation.product import load_non_litigation_cases
        from non_litigation.validator import validate_ocr_results
        from non_litigation.evaluation import evaluate_non_litigation_quality
        
        emitter.log("info", "所有模块导入成功")
        
        import non_litigation.export as non_litigation_export
        non_litigation_export._suppress_print = True
        
        sample_root_path = resolve_input_path(
            sample_root,
            preset_id=preset_id,
            preset_kind="sample",
            default_preset_id="non-litigation-batch1",
        )
        emitter.log("info", f"样本目录: {sample_root_path}")
        
        input_root = ensure_non_litigation_input_structure(get_app_root())
        original_files_dir = sample_root_path / '原始文件'
        sample_input_dir = sample_root_path / 'input'
        if original_files_dir.exists() and list(original_files_dir.glob('*.pdf')):
            input_root = original_files_dir
        elif sample_input_dir.exists() and _dir_has_pdfs(sample_input_dir):
            input_root = sample_input_dir
        elif _dir_has_pdfs(sample_root_path):
            input_root = sample_root_path
        
        # ... 继续处理逻辑（简化版）
        emitter.log("info", f"输入目录: {input_root}")
        
        # 模拟处理完成
        _active_tasks[task_id]["status"] = "completed"
        return jsonify({
            "success": True,
            "task_id": task_id,
            "summary": {
                "sample_root": str(sample_root_path),
                "mode": mode,
                "processed": 0
            }
        })
        
    except CancelledError:
        emitter.log("warn", "任务已取消")
        _active_tasks[task_id]["status"] = "cancelled"
        return jsonify({
            "cancelled": True,
            "success": False,
            "task_id": task_id
        })
    except Exception as e:
        emitter.log("error", f"处理失败: {str(e)}")
        _active_tasks[task_id]["status"] = "failed"
        _active_tasks[task_id]["error"] = str(e)
        return jsonify({
            "success": False,
            "task_id": task_id,
            "error": str(e)
        }), 500


# ============ 强制执行端点 ============

@app.route('/enforcement/extract', methods=['POST'])
def enforcement_extract():
    """强制执行裁定信息提取"""
    data = request.get_json() or {}
    task_id = data.get('task_id', f"ef-{uuid.uuid4().hex[:8]}")
    
    _active_tasks[task_id] = {
        "task_id": task_id,
        "status": "running",
        "type": "enforcement",
        "started_at": datetime.now().isoformat()
    }
    
    # TODO: 实现强制执行逻辑
    _active_tasks[task_id]["status"] = "completed"
    return jsonify({
        "success": True,
        "task_id": task_id,
        "processed": 0
    })


# ============ 企业查询端点 ============

@app.route('/company-query/process', methods=['POST'])
def company_query_process():
    """企业信息查询处理"""
    data = request.get_json() or {}
    task_id = data.get('task_id', f"cq-{uuid.uuid4().hex[:8]}")
    
    _active_tasks[task_id] = {
        "task_id": task_id,
        "status": "running",
        "type": "company_query",
        "started_at": datetime.now().isoformat()
    }
    
    # TODO: 实现企业查询逻辑
    _active_tasks[task_id]["status"] = "completed"
    return jsonify({
        "success": True,
        "task_id": task_id,
        "total": 0
    })


@app.route('/company-query/cancel', methods=['POST'])
def company_query_cancel():
    """取消企业查询"""
    data = request.get_json() or {}
    task_id = data.get('task_id', '')
    request_cancel(task_id)
    return jsonify({"cancelled": True, "task_id": task_id})


# ============ 打印服务端点 ============

@app.route('/print/start', methods=['POST'])
def print_start():
    """开始打印任务"""
    data = request.get_json() or {}
    task_id = data.get('task_id', f"print-{uuid.uuid4().hex[:8]}")
    
    _active_tasks[task_id] = {
        "task_id": task_id,
        "status": "running",
        "type": "print",
        "started_at": datetime.now().isoformat()
    }
    
    # TODO: 实现打印逻辑
    _active_tasks[task_id]["status"] = "completed"
    return jsonify({
        "success": True,
        "task_id": task_id,
        "status": "completed"
    })


@app.route('/print/cancel', methods=['POST'])
def print_cancel():
    """取消打印任务"""
    data = request.get_json() or {}
    task_id = data.get('task_id', '')
    
    try:
        from infra.print_service import cancel_print_task as _cancel_print
        _cancel_print(task_id)
    except Exception:
        pass
    
    request_cancel(task_id)
    return jsonify({"cancelled": True, "task_id": task_id})


# ============ 系统端点 ============

@app.route('/system/status', methods=['GET'])
def system_status():
    """获取系统状态"""
    try:
        from core.pdf_ocr_ultra import UltraFastOCR, OCRConfig
        ocr_available = True
    except Exception:
        ocr_available = False
    
    return jsonify({
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "ocr_engine_ready": ocr_available,
        "ocr_version": "1.4.4" if ocr_available else None,
        "poppler_installed": True,  # TODO: 实际检测
        "config_loaded": True,
        "available_memory_gb": 8.5,  # TODO: 实际检测
        "app_version": "1.1.1",
        "developer": "陈恒律师"
    })


@app.route('/system/presets', methods=['GET'])
def system_get_presets():
    """获取预设路径"""
    from core.preset_paths import get_resolved_presets
    presets = get_resolved_presets()
    return jsonify({
        "presets": presets,
        "appRoot": str(get_app_root()),
        "resources": str(get_resources_dir())
    })


@app.route('/system/paths', methods=['GET'])
def system_describe_paths():
    """描述运行时路径"""
    config_path = get_resources_dir() / "config.yaml"
    batch1_path = get_resources_dir() / "sample-data" / "non-litigation-batch1"
    ledger_path = batch1_path / "台账及命名规则.xlsx"
    
    return jsonify({
        "summary": describe_runtime_paths(),
        "configExists": config_path.is_file(),
        "batch1Exists": batch1_path.is_dir(),
        "ledgerExists": ledger_path.is_file()
    })


@app.route('/system/check-dependencies', methods=['GET'])
def system_check_dependencies():
    """检查依赖状态"""
    dependencies = []
    
    # RapidOCR
    try:
        import rapidocr_onnxruntime
        dependencies.append({
            "name": "RapidOCR",
            "installed": True,
            "version": rapidocr_onnxruntime.__version__
        })
    except Exception:
        dependencies.append({"name": "RapidOCR", "installed": False})
    
    # pdfplumber
    try:
        import pdfplumber
        dependencies.append({
            "name": "pdfplumber",
            "installed": True,
            "version": pdfplumber.__version__
        })
    except Exception:
        dependencies.append({"name": "pdfplumber", "installed": False})
    
    return jsonify({
        "all_ready": all(d.get("installed") for d in dependencies),
        "dependencies": dependencies
    })


# ============ 配置端点 ============

@app.route('/config', methods=['GET'])
def config_get():
    """获取配置"""
    from core.config_loader import get_config
    config = get_config()
    return jsonify(config.to_dict() if hasattr(config, 'to_dict') else {})


@app.route('/config/reload', methods=['POST'])
def config_reload():
    """重新加载配置"""
    from core.config_loader import reload_config
    reload_config()
    return jsonify({"reloaded": True})


def find_free_port(start_port: int = 17852) -> int:
    """查找可用端口"""
    import socket
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
        port += 1
    raise RuntimeError("No free port found")


def start_server(port: Optional[int] = None, host: str = "127.0.0.1") -> int:
    """启动 HTTP 服务器"""
    if port is None:
        port = find_free_port()
    
    print(f"[HTTP Server] Starting on {host}:{port}", file=sys.stderr, flush=True)
    
    # 使用 threading 模式，避免阻塞
    import threading
    server_thread = threading.Thread(
        target=lambda: app.run(
            host=host,
            port=port,
            threaded=True,
            debug=False,
            use_reloader=False
        ),
        daemon=True
    )
    server_thread.start()
    
    return port


if __name__ == "__main__":
    # 开发模式直接运行
    port = int(os.environ.get("GJJ_HTTP_PORT", "17852"))
    print(f"[HTTP Server] Development mode on port {port}")
    app.run(host="127.0.0.1", port=port, debug=True)
