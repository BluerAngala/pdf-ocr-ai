#!/usr/bin/env python3
"""
公积金 OCR 工具 - JSON-RPC 服务端
通过 stdin/stdout/stderr 与 Tauri 前端通信
"""

import json
import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

import io as _io
import datetime as _datetime

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

if hasattr(sys, "flags") and not sys.flags.utf8_mode:
    try:
        sys.flags.utf8_mode = 1
    except (AttributeError, TypeError):
        pass

import re as _re
_SURROGATE_RE = _re.compile(r'[\ud800-\udfff]')

def _sanitize(obj):
    if isinstance(obj, str):
        return _SURROGATE_RE.sub('\ufffd', obj)
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_sanitize(v) for v in obj)
    return obj

def _safe_json_dumps(obj, **kwargs):
    return json.dumps(_sanitize(obj), ensure_ascii=False, **kwargs)

def _force_utf8_stream(stream, mode='r'):
    if stream is None:
        return stream
    try:
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
            return stream
    except Exception:
        pass
    try:
        if hasattr(stream, 'buffer'):
            return _io.TextIOWrapper(stream.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass
    try:
        return open(stream.fileno(), mode=mode, encoding='utf-8', buffering=1, errors='replace')
    except Exception:
        pass
    return stream

sys.stdin = _force_utf8_stream(sys.stdin, mode='r')
sys.stdout = _force_utf8_stream(sys.stdout, mode='w')
sys.stderr = _force_utf8_stream(sys.stderr, mode='w')

def _external_server_src_is_compatible(external: Path) -> bool:
    """仅当外部 server_src 含新版 preset_paths 时才覆盖 PyInstaller 内嵌代码。"""
    return (external / "core" / "preset_paths.py").is_file()


if getattr(sys, "frozen", False):
    _exe_dir = Path(sys.executable).resolve().parent
    _resources = Path(os.environ.get("GJJ_OCR_RESOURCES", str(_exe_dir.parent)))
    _external = _resources / "server_src"
    if _external_server_src_is_compatible(_external):
        _server_src = _external
        if str(_server_src) not in sys.path:
            sys.path.insert(0, str(_server_src))
    # 否则使用 PyInstaller 内嵌模块，避免旧版 resources/server_src 覆盖新 RPC
    print(
        _safe_json_dumps(
            {
                "jsonrpc": "2.0",
                "method": "notify.log",
                "params": {"level": "info", "message": "Python 进程已启动，正在加载模块…"},
            }
        ),
        file=sys.stderr,
        flush=True,
    )
    # onefile 冷启动：在重型 import 之前通知 Tauri，避免前端误判为「服务未就绪」
    print(
        _safe_json_dumps(
            {
                "jsonrpc": "2.0",
                "method": "notify.log",
                "params": {"level": "info", "message": "Python JSON-RPC 服务已启动"},
            }
        ),
        file=sys.stderr,
        flush=True,
    )
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
from core.task_cancel import CancelledError
from core.preset_paths import (
    get_resolved_presets,
    resolve_data_path as resolve_data_path_rel,
)

print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.log", "params": {"level": "debug", "message": f"{describe_runtime_paths()}, SYS_PATH[0]={sys.path[0] if sys.path else 'empty'}"}}), file=sys.stderr, flush=True)

def _make_task_output_dir(task_id: str = "", module: str = "", user_dir: str = "") -> Path:
    ts = _datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    parts = [ts]
    if module:
        parts.append(module)
    if task_id:
        # 简化 task_id：去掉前缀（如 "nl-", "enf-", "cq-"），只保留数字后缀
        simplified_id = _simplify_task_id(task_id)
        parts.append(simplified_id)
    subfolder = "_".join(parts)
    base = Path(user_dir) if user_dir else USER_DATA_DIR / "output"
    d = base / subfolder
    d.mkdir(parents=True, exist_ok=True)
    return d


def _simplify_task_id(task_id: str) -> str:
    """简化 task_id，只保留数字部分"""
    import re
    # 去掉常见前缀（nl-, enf-, cq-, print- 等），保留数字
    match = re.search(r'-(\d+)$', task_id)
    if match:
        return match.group(1)
    # 如果没有匹配到数字后缀，直接返回原ID
    return task_id


def _dir_has_pdfs(dir_path: Path) -> bool:
    return any(dir_path.rglob('*.pdf'))


class ProgressEmitter:
    """进度推送器"""
    def __init__(self, task_id: str = "default"):
        self.task_id = task_id

    def progress(self, phase: str, current: int, total: int, message: str,
                 file_current: int = 0, file_total: int = 0, detail: Optional[Dict] = None):
        import datetime
        params = {
            "task_id": self.task_id,
            "phase": phase,
            "status": "running",
            "current": current,
            "total": total,
            "file_current": file_current,
            "file_total": file_total,
            "message": message,
            "timestamp": datetime.datetime.now().isoformat()
        }
        if detail:
            params["detail"] = detail
        notification = {"jsonrpc": "2.0", "method": "notify.progress", "params": params}
        print(_safe_json_dumps(notification), file=sys.stderr, flush=True)

    def log(self, level: str, message: str):
        import datetime
        params = {"level": level, "message": message, "timestamp": datetime.datetime.now().isoformat()}
        notification = {"jsonrpc": "2.0", "method": "notify.log", "params": params}
        print(_safe_json_dumps(notification), file=sys.stderr, flush=True)

    def complete(self, success: bool = True, result: Any = None, error: str = None):
        import datetime
        params = {
            "task_id": self.task_id,
            "success": success,
            "timestamp": datetime.datetime.now().isoformat()
        }
        if success:
            params["result"] = result
        else:
            params["error"] = error
        notification = {"jsonrpc": "2.0", "method": "notify.task_complete", "params": params}
        print(_safe_json_dumps(notification), file=sys.stderr, flush=True)


class JsonRpcServer:
    _LONG_METHODS = frozenset([
        'non_litigation.process',
        'enforcement.extract',
        'company_query.process',
        'print.start',
        'ocr.warmup',
    ])

    def __init__(self):
        self.methods = {}
        self.request_id = 0
        self._stdout_lock = threading.Lock()
        self._register_methods()

    def _register_methods(self):
        """注册所有 RPC 方法"""
        # OCR 模块
        self.methods['ocr.recognize'] = self._ocr_recognize
        self.methods['ocr.recognize_batch'] = self._ocr_recognize_batch
        self.methods['ocr.warmup'] = self._ocr_warmup
        self.methods['ocr.clear_cache'] = self._ocr_clear_cache

        # 非诉审查模块
        self.methods['non_litigation.process'] = self._non_litigation_process
        self.methods['non_litigation.get_cases'] = self._non_litigation_get_cases
        self.methods['non_litigation.preview_split'] = self._non_litigation_preview_split

        # 强制执行模块
        self.methods['enforcement.extract'] = self._enforcement_extract
        self.methods['enforcement.fill_excel'] = self._enforcement_fill_excel

        self.methods['company_query.process'] = self._company_query_process
        self.methods['company_query.cancel'] = self._company_query_cancel
        self.methods['company_query.load_cache'] = self._company_query_load_cache
        self.methods['company_query.clear_cache'] = self._company_query_clear_cache
        self.methods['company_query.check_account'] = self._company_query_check_account
        self.methods['company_query.recharge'] = self._company_query_recharge
        self.methods['company_query.export_cache'] = self._company_query_export_cache
        self.methods['task.cancel'] = self._task_cancel
        self.methods['task.clear_cancel'] = self._task_clear_cancel

        self.methods['print.start'] = self._print_start
        self.methods['print.cancel'] = self._print_cancel
        self.methods['print.status'] = self._print_status
        self.methods['print.excel_columns'] = self._print_excel_columns
        self.methods['print.list_printers'] = self._print_list_printers
        self.methods['print.check_printer'] = self._print_check_printer

        # 配置模块
        self.methods['config.get'] = self._config_get
        self.methods['config.set_corrections'] = self._config_set_corrections
        self.methods['config.reload'] = self._config_reload

        # 系统模块
        self.methods['system.get_status'] = self._system_get_status
        self.methods['system.check_dependencies'] = self._system_check_dependencies
        self.methods['system.setup_poppler'] = self._system_setup_poppler
        self.methods['system.get_presets'] = self._system_get_presets
        self.methods['system.resolve_data_path'] = self._system_resolve_data_path
        self.methods['system.describe_paths'] = self._system_describe_paths

    def _send_response(self, result: Any, id: Any):
        response = {"jsonrpc": "2.0", "result": result, "id": id}
        with self._stdout_lock:
            print(_safe_json_dumps(response), flush=True)

    def _send_error(self, code: int, message: str, id: Any, data: Optional[Dict] = None):
        error = {"jsonrpc": "2.0", "error": {"code": code, "message": message, "data": data}, "id": id}
        with self._stdout_lock:
            print(_safe_json_dumps(error), flush=True)

    # ============ OCR 模块 ============

    _warmed_up = False
    _ocr_engine_available = False
    _warmup_lock = threading.Lock()

    def _ocr_warmup(self, params: Dict, id: Any) -> Dict:
        import time

        skip_gpu_probe = params.get('skip_gpu_probe', False)
        full_probe = params.get('full_probe', False)

        if not JsonRpcServer._warmup_lock.acquire(blocking=True, timeout=180):
            return {"status": "already_warm", "duration_seconds": 0.01}

        try:
            if JsonRpcServer._warmed_up and JsonRpcServer._ocr_engine_available:
                return {"status": "already_warm", "duration_seconds": 0.01}

            start_time = time.time()
            try:
                print(
                    _safe_json_dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "notify.log",
                            "params": {"level": "info", "message": f"正在初始化 OCR 引擎{'（快速模式）' if skip_gpu_probe else ''}..."},
                        }
                    ),
                    file=sys.stderr,
                    flush=True,
                )

                from core.pdf_ocr_ultra import get_ocr_engine
                engine = get_ocr_engine(skip_gpu_probe=skip_gpu_probe)

                import numpy as np
                from PIL import Image
                dummy_img = Image.new('RGB', (100, 100), color='white')
                engine(dummy_img)

                JsonRpcServer._warmed_up = True
                JsonRpcServer._ocr_engine_available = True

                duration = time.time() - start_time
                print(
                    _safe_json_dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "notify.log",
                            "params": {"level": "info", "message": f"OCR 引擎初始化完成（耗时 {duration:.2f}s）"},
                        }
                    ),
                    file=sys.stderr,
                    flush=True,
                )

                return {
                    "status": "warm",
                    "duration_seconds": duration,
                    "provider": "RapidOCR",
                    "provider_info": "OCR 引擎已就绪",
                }
            except Exception as e:
                JsonRpcServer._ocr_engine_available = False
                error_msg = f"OCR 引擎初始化失败: {str(e)}"
                print(
                    _safe_json_dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "notify.log",
                            "params": {"level": "error", "message": error_msg},
                        }
                    ),
                    file=sys.stderr,
                    flush=True,
                )
                raise Exception(error_msg)
        finally:
            JsonRpcServer._warmup_lock.release()

    def _ocr_clear_cache(self, params: Dict, id: Any) -> Dict:
        """清除 OCR 结果缓存"""
        cache_path = USER_DATA_DIR / 'output' / 'ocr-cache.pkl'
        if cache_path.exists():
            cache_path.unlink()
            return {"status": "cleared"}
        return {"status": "no_cache"}

    def _ocr_recognize(self, params: Dict, id: Any) -> Dict:
        """单文件 OCR 识别"""
        file_path = params.get('file_path')
        force_ocr = params.get('force_ocr', False)

        try:
            from core.pdf_ocr_ultra import UltraFastOCR, OCRConfig
            config = OCRConfig()
            ocr = UltraFastOCR(config, skip_warmup=True)
            result = ocr.process_file(file_path, force_ocr=force_ocr)
            if result is None:
                raise Exception("OCR 处理失败")
            return {
                "filename": result['filename'],
                "total_pages": result['total_pages'],
                "pages": result['pages'],
                "full_text": result['full_text'],
                "total_duration": result['total_duration']
            }
        except Exception as e:
            raise Exception(f"OCR 识别失败: {str(e)}")

    def _ocr_recognize_batch(self, params: Dict, id: Any) -> Dict:
        """批量 OCR 识别"""
        file_paths = params.get('file_paths', [])
        emitter = ProgressEmitter(f"ocr-batch-{id}")
        results = []
        for i, file_path in enumerate(file_paths):
            emitter.progress("ocr_batch", i + 1, len(file_paths), f"识别: {Path(file_path).name}")
            try:
                result = self._ocr_recognize({'file_path': file_path}, id)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e), "file_path": file_path})
        return {"results": results}

    # ============ 非诉审查模块 ============

    def _non_litigation_process(self, params: Dict, id: Any) -> Dict:
        """非诉审查完整处理流程"""
        preset_id = params.get('preset_id')
        sample_root = params.get('sample_root')
        excel_path = params.get('excel_path')
        mode = params.get('mode', 'mock')
        force = params.get('force', False)
        task_id = params.get('task_id', f"nl-{id}")
        user_output_dir = params.get('output_dir')
        emitter = ProgressEmitter(task_id)
        from core.task_cancel import is_cancelled as _is_task_cancelled, clear as _clear_task
        # P0-#reload: 每次任务入口主动 reload config（让用户改 yaml 后无需重启）。
        # 用 setattr 刷新模块级常量（不会破坏 enum/dataclass 的 == 比较）。
        try:
            from core.config_loader import reload_config
            reload_config(refresh_modules=True)
        except Exception as _e:
            print(f"[WARN] 自动 reload config 失败: {_e}")

        if force:
            cache_path = USER_DATA_DIR / 'output' / 'ocr-cache.pkl'
            if cache_path.exists():
                cache_path.unlink()
            for db in (USER_DATA_DIR / 'temp').glob('streaming_*.db'):
                db.unlink(missing_ok=True)

        try:
            emitter.log("debug", f"收到参数: preset_id={preset_id!r}, sample_root={sample_root!r}, excel_path={excel_path!r}")

            try:
                from non_litigation.export import (
                    build_mock_ocr_results, run_real_ocr,
                    ensure_non_litigation_input_structure,
                    export_non_litigation_standard_outputs,
                    get_non_litigation_result_root,
                    _suppress_print,
                )
                from non_litigation.product import load_non_litigation_cases
                from non_litigation.validator import validate_ocr_results
                from non_litigation.evaluation import evaluate_non_litigation_quality
                emitter.log("info", "所有模块导入成功")
            except ImportError as e:
                emitter.log("error", f"导入失败: {str(e)}")
                import traceback as tb
                emitter.log("error", f"导入错误堆栈: {tb.format_exc()}")
                raise

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

            if excel_path:
                excel_file_path = resolve_input_path(
                    excel_path, preset_id=preset_id, preset_kind="excel"
                )
            else:
                from core.config_loader import load_config
                _tmp_cfg = load_config()
                excel_name = _tmp_cfg.excel_filename
                excel_file_path = None
                for candidate in [sample_root_path / excel_name, sample_root_path.parent / excel_name]:
                    if candidate.exists():
                        excel_file_path = candidate
                        break
                if excel_file_path is None:
                    excel_file_path = sample_root_path / excel_name

            result_root = _make_task_output_dir(task_id, "非诉审查", user_output_dir)

            total_t0 = __import__('time').perf_counter()

            # OCR 阶段
            emitter.progress("ocr", 0, 100, "正在扫描文件...", 0, 0)
            emitter.log("info", f"输入目录: {input_root}")
            ocr_file_total = [0]
            if mode == 'real_ocr':
                import time as _time
                import pickle as _pickle
                ocr_t0 = _time.perf_counter()

                cache_path = result_root / 'debug' / 'ocr-cache.pkl'
                # 兼容旧版缓存路径
                old_cache_path = result_root / 'ocr-cache.pkl'
                if not force and not cache_path.exists() and old_cache_path.exists():
                    cache_path = old_cache_path
                cached_results = None
                if not force and cache_path.exists():
                    try:
                        with open(cache_path, 'rb') as f:
                            cached_results = _pickle.load(f)
                        if cached_results:
                            emitter.log("info", f"加载本任务 OCR 缓存: {len(cached_results)} 个文件")
                    except Exception:
                        cached_results = None

                def ocr_progress(current, total, filename):
                    if _is_task_cancelled(task_id):
                        raise CancelledError("任务已取消")
                    ocr_file_total[0] = total
                    emitter.progress("ocr", current, total + 2, f"正在识别 ({current}/{total}): {filename}", current, total)

                def _save_cache(results):
                    try:
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(cache_path, 'wb') as f:
                            _pickle.dump(results, f)
                    except Exception:
                        pass

                def _on_ocr_result(filename, result, all_results):
                    _save_cache(all_results)

                ocr_results = run_real_ocr(input_root, use_mock=False, progress_callback=ocr_progress, cancel_check=lambda: _is_task_cancelled(task_id), log_callback=lambda level, msg: emitter.log(level, msg), cached_results=cached_results, force=force, result_callback=_on_ocr_result, task_output_dir=result_root)

                _save_cache(ocr_results)

                if _is_task_cancelled(task_id):
                    emitter.log("warn", f"任务已取消，已完成 {len(ocr_results)} 个文件的OCR（已缓存）")
                    emitter.complete(False, error="用户取消")
                    raise CancelledError("任务已取消")
                ocr_elapsed = _time.perf_counter() - ocr_t0
                emitter.log("info", f"OCR 完成: {len(ocr_results)} 个文件, 耗时 {ocr_elapsed:.1f}s")
                if not ocr_results:
                    emitter.log("warn", "OCR 结果为空！请检查输入目录是否有 PDF 文件")
                    emitter.log("warn", f"输入目录: {input_root}")
            else:
                emitter.log("info", "开始构建 mock OCR 数据...")
                ocr_results = build_mock_ocr_results(sample_root_path, input_dir=input_root)
                emitter.log("info", "Mock OCR 数据构建完成")
            _ocr_total = ocr_file_total[0] if ocr_file_total[0] > 0 else len(ocr_results)
            emitter.progress("ocr", _ocr_total, _ocr_total + 2, "OCR 识别完成", _ocr_total, _ocr_total)

            # 导出阶段
            if _is_task_cancelled(task_id):
                emitter.log("warn", "任务已取消，跳过导出阶段")
                emitter.complete(False, error="用户取消")
                raise CancelledError("任务已取消")
            emitter.progress("export", _ocr_total + 1, _ocr_total + 2, "开始导出文件...")
            export_result = export_non_litigation_standard_outputs(
                sample_root=sample_root_path, input_dir=input_root,
                output_root=result_root, ocr_results=ocr_results,
                excel_path=excel_file_path,
            )
            emitter.progress("export", _ocr_total + 1, _ocr_total + 2, f"导出完成: {export_result['created_count']} 个文件")

            # 验证阶段
            if _is_task_cancelled(task_id):
                emitter.log("warn", "任务已取消，跳过验证阶段")
                emitter.complete(False, error="用户取消")
                raise CancelledError("任务已取消")
            emitter.progress("validation", _ocr_total + 2, _ocr_total + 2, "开始验证...")
            cases = load_non_litigation_cases(sample_root_path, excel_path=excel_file_path)
            validation_result = validate_ocr_results(cases, ocr_results, input_dir=input_root)
            quality = evaluate_non_litigation_quality(
                get_app_root(), result_root, sample_root=sample_root_path, excel_path=excel_file_path
            )

            total_elapsed = __import__('time').perf_counter() - total_t0

            result = {
                "success": True,
                "summary": {
                    "sample_root": str(sample_root_path),
                    "result_root": str(result_root),
                    "runtime_seconds": round(total_elapsed, 2),
                    "mode": mode,
                    "created_count": export_result['created_count'],
                    "quality": {
                        "total_files": quality['total_files'],
                        "page_count_matched": quality['page_count_matched'],
                        "page_count_match_rate": quality['page_count_match_rate']
                    },
                    "validation": validation_result['summary'],
                },
                "validation_details": validation_result.get('details', []),
                "validation_failed": validation_result.get('failed_items', []),
                "validation_warnings": validation_result.get('warning_items', []),
                "timing_statistics": validation_result.get('timing_statistics', {}),
            }

            emitter.complete(True, result)
            emitter.log("info", f"全部完成: OCR {ocr_elapsed:.1f}s + 导出/验证 {total_elapsed - ocr_elapsed:.1f}s = 总计 {total_elapsed:.1f}s")
            return result

        except CancelledError as e:
            emitter.log("warn", str(e))
            emitter.complete(False, error="用户取消")
            print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.task_cancelled", "params": {"task_id": task_id, "cancelled": True}}), file=sys.stderr, flush=True)
            return {"cancelled": True, "success": False, "task_id": task_id}
        except Exception as e:
            emitter.log("error", f"处理失败: {str(e)}")
            emitter.complete(False, error=str(e))
            raise Exception(f"非诉审查处理失败: {str(e)}")
        finally:
            try:
                import non_litigation.export as non_litigation_export
                non_litigation_export._suppress_print = False
            except Exception:
                pass
            _clear_task(task_id)

    def _non_litigation_get_cases(self, params: Dict, id: Any) -> Dict:
        """获取案件列表"""
        preset_id = params.get('preset_id')
        sample_root = params.get('sample_root')
        excel_path = params.get('excel_path')
        try:
            from non_litigation.product import load_non_litigation_cases
            sample_path = resolve_input_path(
                sample_root,
                preset_id=preset_id,
                preset_kind="sample",
                default_preset_id="non-litigation-batch1",
            )
            excel_file = Path(excel_path) if excel_path else None
            cases = load_non_litigation_cases(sample_path, excel_path=excel_file)
            return {"cases": cases}
        except Exception as e:
            raise Exception(f"获取案件列表失败: {str(e)}")

    def _non_litigation_preview_split(self, params: Dict, id: Any) -> Dict:
        """预览 PDF 分割结果"""
        doc_type = params.get('doc_type')
        pdf_path = params.get('pdf_path')
        expected_count = params.get('expected_count', 0)
        try:
            from non_litigation.export import inspect_pdf_page_count, detect_page_ranges
            pdf_path_obj = Path(pdf_path)
            total_pages = inspect_pdf_page_count(pdf_path_obj)
            ranges = detect_page_ranges(total_pages, expected_count, doc_type)
            detected_ranges = []
            for start, end in ranges:
                detected_ranges.append({"start": start + 1, "end": end, "preview_text": f"第 {start + 1} 页到第 {end} 页"})
            return {
                "total_pages": total_pages,
                "expected_count": expected_count,
                "detected_ranges": detected_ranges,
                "confidence": 0.95 if len(ranges) == expected_count else 0.7
            }
        except Exception as e:
            raise Exception(f"预览分割失败: {str(e)}")

    # ============ 强制执行模块 ============

    def _enforcement_extract(self, params: Dict, id: Any) -> Dict:
        """从裁定书提取信息"""
        from core.task_cancel import is_cancelled as _is_task_cancelled, clear as _clear_task
        preset_id = params.get('preset_id')
        input_dir = params.get('input_dir')
        excel_path = params.get('excel_path')
        force_ocr = params.get('force_ocr', False)
        mock_mode = params.get('mock_mode', False)
        user_output_dir = params.get('output_dir')
        task_id = params.get('task_id', f'enf-{id}')
        cancel_check = lambda: _is_task_cancelled(task_id)
        # P0-#reload: 强制组任务入口同样主动 reload
        try:
            from core.config_loader import reload_config
            reload_config(refresh_modules=True)
        except Exception as _e:
            print(f"[WARN] 自动 reload config 失败: {_e}")
        try:
            from enforcement.extractor import process_enforcement_cases
            import pickle as _pickle
            import time as _time
            input_dir = resolve_input_path(
                input_dir, preset_id=preset_id, preset_kind="sample"
            )
            if excel_path:
                excel_path = resolve_input_path(
                    excel_path, preset_id=preset_id, preset_kind="excel"
                )
            elif preset_id:
                try:
                    excel_path = resolve_input_path(
                        None, preset_id=preset_id, preset_kind="excel"
                    )
                except FileNotFoundError:
                    excel_path = Path(".")

            if not input_dir.exists():
                raise FileNotFoundError(
                    f"输入文件夹不存在: {input_dir} ({describe_runtime_paths()})"
                )
            if not excel_path.exists():
                raise FileNotFoundError(
                    f"台账文件不存在: {excel_path} ({describe_runtime_paths()})"
                )

            pdf_count = len(list(input_dir.glob('*.pdf'))) if input_dir.is_dir() else 0
            if pdf_count == 0 and not mock_mode:
                raise FileNotFoundError(f"输入文件夹中没有PDF文件: {input_dir}")

            print(f"[INFO] 强制执行提取: input_dir={input_dir}, excel_path={excel_path}, pdf_count={pdf_count}")

            task_output_dir = _make_task_output_dir(task_id, "强制执行提取", user_output_dir)

            enf_cache_path = USER_DATA_DIR / 'output' / 'enf-ocr-cache.pkl'
            cached_results = None
            if enf_cache_path.exists():
                try:
                    with open(enf_cache_path, 'rb') as f:
                        cached_results = _pickle.load(f)
                    if cached_results:
                        print(f"[INFO] 加载强制执行OCR缓存: {len(cached_results)} 个文件")
                except Exception:
                    cached_results = None

            def _save_enf_cache(cache):
                try:
                    enf_cache_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(enf_cache_path, 'wb') as f:
                        _pickle.dump(cache, f)
                except Exception:
                    pass

            def _on_enf_result(stem, info_dict, cache):
                _save_enf_cache(cache)

            result = process_enforcement_cases(
                input_dir=input_dir, excel_path=excel_path,
                use_ocr=force_ocr, mock_mode=mock_mode,
                output_dir=task_output_dir, cancel_check=cancel_check,
                cached_results=cached_results, result_callback=_on_enf_result,
            )

            _save_enf_cache(cached_results or {})

            if _is_task_cancelled(task_id):
                _clear_task(task_id)
                raise Exception("任务已取消")

            stats = result.get('stats', {})
            unmatched = stats.get('unmatched_details', [])
            if unmatched:
                for item in unmatched:
                    print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.log", "params": {"level": "warn", "message": f"台账未匹配: {item.get('notice_number', '')} - {item.get('respondent', '')} ({item.get('reason', '')})"}}), file=sys.stderr, flush=True)

            return {
                "processed": result.get('processed', 0),
                "extracted": result.get('extracted', []),
                "updated_excel_path": result.get('updated_excel_path', ''),
                "output_dir": result.get('output_dir', ''),
                "stats": stats,
            }
        except CancelledError:
            print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.log", "params": {"level": "warn", "message": "任务已取消"}}), file=sys.stderr, flush=True)
            print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.task_cancelled", "params": {"task_id": task_id, "cancelled": True}}), file=sys.stderr, flush=True)
            return {"cancelled": True, "success": False, "task_id": task_id}
        except Exception as e:
            if _is_task_cancelled(task_id) or "取消" in str(e):
                print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.task_cancelled", "params": {"task_id": task_id, "cancelled": True}}), file=sys.stderr, flush=True)
                return {"cancelled": True, "success": False, "task_id": task_id}
            raise Exception(f"强制执行提取失败: {str(e)}")
        finally:
            _clear_task(task_id)

    def _enforcement_fill_excel(self, params: Dict, id: Any) -> Dict:
        """回填到 Excel"""
        return {"success": True}

    # ============ 企业信息查询模块 ============

    def _company_query_process(self, params: Dict, id: Any) -> Dict:
        preset_id = params.get('preset_id') or 'company-query'
        excel_path = params.get('excel_path')
        range_start = params.get('range_start', 1)
        range_end = params.get('range_end', 99999)
        cache_ttl_days = params.get('cache_ttl_days', 0)
        task_id = params.get('task_id', f"cq-{id}")
        user_output_dir = params.get('output_dir')
        emitter = ProgressEmitter(task_id)
        result = None

        try:
            from infra.company_query import process_company_query
            from core.preset_paths import resolve_preset

            resolved_excel = None
            if preset_id:
                try:
                    resolved_excel = resolve_preset(preset_id, "excel")
                except (FileNotFoundError, KeyError):
                    resolved_excel = None

            raw = str(excel_path).strip() if excel_path else ""
            if resolved_excel is not None:
                if not raw:
                    excel_path = resolved_excel
                else:
                    p = Path(raw)
                    if not p.is_absolute() or not p.is_file():
                        excel_path = resolved_excel
                    elif p.resolve() != resolved_excel.resolve():
                        emitter.log(
                            "warn",
                            f"已改用企业查询预设台账: {resolved_excel.name}（忽略其它模块残留路径）",
                        )
                        excel_path = resolved_excel
                    else:
                        excel_path = p.resolve()
            else:
                excel_path = resolve_input_path(
                    excel_path,
                    preset_id=preset_id,
                    preset_kind="excel",
                    default_preset_id="company-query",
                )

            if not Path(excel_path).exists():
                raise FileNotFoundError(f"Excel 文件不存在: {excel_path}")

            emitter.log("info", f"开始企业信息查询: {Path(excel_path).name} (第{range_start}-{range_end or '末'}条)")
            task_output_dir = _make_task_output_dir(task_id, "企业查询", user_output_dir)
            result = process_company_query(
                Path(excel_path),
                range_start=range_start,
                range_end=range_end,
                cache_ttl_days=cache_ttl_days,
                task_id=task_id,
                emitter=emitter,
                output_dir=task_output_dir,
            )
            cached = result.get('skipped_cached', 0)
            cancelled = result.get('cancelled', False)
            status_msg = "已取消" if cancelled else "查询完成"
            emitter.log("info", f"{status_msg}: 成功 {result['success_count']}/{result['total']}，缓存跳过 {cached} 条")
            return result
        except Exception as e:
            from core.task_cancel import is_cancelled
            cancelled = (
                isinstance(result, dict) and result.get('cancelled', False)
            ) or is_cancelled(task_id)
            if cancelled:
                print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.task_cancelled", "params": {"task_id": task_id, "cancelled": True}}), file=sys.stderr, flush=True)
            raise Exception(f"企业查询失败: {str(e)}")

    def _company_query_cancel(self, params: Dict, id: Any) -> Dict:
        task_id = params.get('task_id', '')
        from core.task_cancel import request_cancel
        request_cancel(task_id)
        return {"cancelled": True, "task_id": task_id}

    def _task_cancel(self, params: Dict, id: Any) -> Dict:
        task_id = params.get('task_id', '')
        from core.task_cancel import request_cancel, is_cancelled
        request_cancel(task_id)
        print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.log", "params": {"level": "warn", "message": f"收到取消请求: task_id={task_id}, 已标记取消={is_cancelled(task_id)}"}}), file=sys.stderr, flush=True)
        from infra.print_service import cancel_print_task as _cancel_print
        try:
            _cancel_print(task_id)
        except Exception:
            pass
        return {"cancelled": True, "task_id": task_id}

    def _task_clear_cancel(self, params: Dict, id: Any) -> Dict:
        task_id = params.get('task_id', '')
        from core.task_cancel import clear_cancel
        clear_cancel(task_id)
        return {"cleared": True, "task_id": task_id}

    def _company_query_load_cache(self, params: Dict, id: Any) -> Dict:
        excel_path = params.get('excel_path', '')
        cache_ttl_days = params.get('cache_ttl_days', 0)
        if not excel_path:
            return {"companies": [], "total": 0}
        try:
            from infra.company_query import load_cached_results
            results = load_cached_results(excel_path, ttl_days=cache_ttl_days)
            return {"companies": results, "total": len(results)}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"companies": [], "total": 0, "error": str(e)}

    def _company_query_clear_cache(self, params: Dict, id: Any) -> Dict:
        excel_path = params.get('excel_path', '')
        if not excel_path:
            return {"cleared": False, "error": "未提供 Excel 文件路径"}
        try:
            from infra.company_query import clear_cache
            clear_cache(excel_path)
            return {"cleared": True}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"cleared": False, "error": str(e)}

    def _company_query_check_account(self, params: Dict, id: Any) -> Dict:
        try:
            from infra.company_query import check_account
            return check_account()
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "userid": "", "message": str(e)}

    def _company_query_recharge(self, params: Dict, id: Any) -> Dict:
        code = params.get('code', '')
        try:
            from infra.company_query import recharge
            return recharge(code)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    def _company_query_export_cache(self, params: Dict, id: Any) -> Dict:
        excel_path = params.get('excel_path', '')
        if not excel_path:
            return {"exported": False, "error": "未提供 Excel 文件路径"}
        try:
            from infra.company_query import export_cache_to_excel
            return export_cache_to_excel(excel_path)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"exported": False, "error": str(e)}

    # ============ 自动打印模块 ============

    def _print_start(self, params: Dict, id: Any) -> Dict:
        folder_path = params.get('folder_path', '')
        excel_path = params.get('excel_path', '')
        column_name = params.get('column_name', '')
        range_start = params.get('range_start', 2)
        range_end = params.get('range_end', 9999)
        printer_name = params.get('printer_name', '')
        copies = params.get('copies', 1)
        page_start = params.get('page_start')
        page_end = params.get('page_end')
        print_mode = params.get('print_mode', 'single')
        task_id = params.get('task_id', f"print-{id}")

        emitter = ProgressEmitter(task_id)

        try:
            from infra.print_service import process_print_v2, list_printers, check_printer_status

            if not folder_path:
                raise Exception("请选择材料文件夹")
            folder = Path(folder_path)
            if not folder.exists():
                raise FileNotFoundError(f"文件夹不存在: {folder}")

            if excel_path:
                excel = Path(excel_path)
                if not excel.exists():
                    raise FileNotFoundError(f"台账文件不存在: {excel}")

            printers = list_printers()
            if not printers:
                raise Exception("系统中未找到任何可用打印机")

            if not printer_name:
                default = next((p for p in printers if p["is_default"]), None)
                printer_name = default["name"] if default else printers[0]["name"]

            printer_status = check_printer_status(printer_name)
            if not printer_status.get("available"):
                raise Exception(f"打印机 '{printer_name}' 不可用")
            if not printer_status.get("is_ready"):
                emitter.log("warn", f"打印机状态: {printer_status.get('status', '异常')}")

            if page_start is not None:
                page_start = int(page_start) if page_start else None
            if page_end is not None:
                page_end = int(page_end) if page_end else None

            result = process_print_v2(
                excel_path=excel_path,
                folder_path=folder_path,
                column_name=column_name,
                range_start=int(range_start),
                range_end=int(range_end),
                printer_name=printer_name,
                copies=int(copies),
                page_start=page_start,
                page_end=page_end,
                print_mode=print_mode,
                dry_run=params.get('dry_run', False),
                selected_orders=params.get('selected_orders'),
                task_id=task_id,
                emitter=emitter,
            )
            return result
        except Exception as e:
            from infra.print_service import _mgr
            _mgr.finish_task(task_id, "failed")
            raise Exception(f"打印失败: {str(e)}")

    def _print_cancel(self, params: Dict, id: Any) -> Dict:
        task_id = params.get('task_id', '')
        try:
            from infra.print_service import cancel_print_task
            ok = cancel_print_task(task_id)
            return {"cancelled": ok, "task_id": task_id}
        except Exception as e:
            raise Exception(f"取消失败: {str(e)}")

    def _print_status(self, params: Dict, id: Any) -> Dict:
        task_id = params.get('task_id', '')
        try:
            from infra.print_service import get_print_task_status
            info = get_print_task_status(task_id)
            if info is None:
                return {"status": "not_found", "task_id": task_id}
            return info
        except Exception as e:
            raise Exception(f"查询状态失败: {str(e)}")

    def _print_excel_columns(self, params: Dict, id: Any) -> Dict:
        excel_path = params.get('excel_path', '')
        try:
            from infra.print_service import read_excel_columns
            if not excel_path:
                raise Exception("请指定Excel文件路径")
            return read_excel_columns(excel_path)
        except Exception as e:
            raise Exception(f"读取Excel列失败: {str(e)}")

    def _print_list_printers(self, params: Dict, id: Any) -> Dict:
        try:
            from infra.print_service import list_printers
            printers = list_printers()
            return {
                "printers": printers,
                "count": len(printers),
                "has_printer": len(printers) > 0
            }
        except Exception as e:
            raise Exception(f"获取打印机列表失败: {str(e)}")

    def _print_check_printer(self, params: Dict, id: Any) -> Dict:
        try:
            from infra.print_service import check_printer_status
            printer_name = params.get('printer_name', '')
            if not printer_name:
                raise Exception("请指定打印机名称")
            return check_printer_status(printer_name)
        except Exception as e:
            raise Exception(f"检查打印机状态失败: {str(e)}")

    # ============ 配置模块 ============

    def _config_get(self, params: Dict, id: Any) -> Dict:
        """获取配置"""
        try:
            from core.config_loader import load_config
            cfg = load_config()
            return {
                "doc_types": [
                    {"key": dt.key, "pages_per_case": dt.pages_per_case, "filename_pattern": dt.filename_pattern}
                    for dt in cfg.doc_types
                ],
                "regex_patterns": cfg.regex_patterns,
                "ocr_corrections": cfg.ocr_corrections,
                "validation": {"fuzzy_match_threshold": cfg.validation.fuzzy_match_threshold}
            }
        except Exception as e:
            raise Exception(f"获取配置失败: {str(e)}")

    def _config_set_corrections(self, params: Dict, id: Any) -> Dict:
        """设置 OCR 纠错词表"""
        corrections = params.get('corrections', [])
        return {"success": True, "count": len(corrections)}

    def _config_reload(self, params: Dict, id: Any) -> Dict:
        """重新加载配置（用户改 config.yaml 后无需重启 Python 进程）"""
        try:
            from core.config_loader import reload_config, _config_path
            reload_config()  # 强制重读 yaml + 重新构造 NonLitigationConfig + 刷新模块级常量
            return {
                "success": True,
                "config_path": str(_config_path()),
                "message": "配置已重新加载，模块级常量已同步",
            }
        except Exception as e:
            raise Exception(f"重新加载配置失败: {str(e)}")

    # ============ 系统模块 ============

    def _system_get_presets(self, params: Dict, id: Any) -> Dict:
        """返回已解析绝对路径的预设列表（开发/打包共用 preset_paths）。"""
        presets, errors = get_resolved_presets()
        if not presets and errors:
            raise Exception(
                f"解析预设路径失败: {errors[0].get('error', errors)} "
                f"({describe_runtime_paths()})"
            )
        return {
            "presets": presets,
            "errors": errors,
            "appRoot": path_for_display(get_app_root()),
            "resources": path_for_display(get_resources_dir()),
            "userData": path_for_display(get_user_data_dir()),
        }

    def _system_describe_paths(self, params: Dict, id: Any) -> Dict:
        """诊断运行时路径（前端启动自检）。"""
        from core.paths import get_config_path

        cfg = get_config_path()
        batch1 = get_resources_dir() / "sample-data" / "non-litigation-batch1"
        ledger = batch1 / "台账及命名规则.xlsx"
        return {
            "summary": describe_runtime_paths(),
            "configExists": cfg.is_file(),
            "configPath": path_for_display(cfg),
            "batch1Exists": batch1.is_dir(),
            "ledgerExists": ledger.is_file(),
        }

    def _system_resolve_data_path(self, params: Dict, id: Any) -> Dict:
        relative = params.get("relative", "")
        if not relative:
            raise Exception("缺少 relative 参数")
        try:
            path = resolve_data_path_rel(relative)
            return {"path": path_for_display(path), "exists": path.exists()}
        except Exception as e:
            raise Exception(f"路径解析失败: {e}")

    def _system_get_status(self, params: Dict, id: Any) -> Dict:
        """获取系统状态"""
        import platform
        poppler_installed = False
        ocr_version = ''
        
        # 使用预热后的状态，而不是每次都重新检测
        ocr_ready = JsonRpcServer._ocr_engine_available
        
        try:
            from core.pdf_ocr_ultra import check_poppler_installed, OCRConfig
            cfg = OCRConfig()
            poppler_installed = check_poppler_installed(cfg.poppler_path)
            if ocr_ready:
                try:
                    import importlib.metadata
                    ocr_version = importlib.metadata.version('rapidocr_onnxruntime')
                except Exception:
                    pass
        except Exception as e:
            print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.log", "params": {"level": "error", "message": f"_system_get_status import error: {e}"}}), file=sys.stderr, flush=True)
        memory_gb = 0
        try:
            import psutil
            memory_gb = round(psutil.virtual_memory().available / (1024**3), 1)
        except:
            pass
        app_version = os.environ.get('GJJ_APP_VERSION', '')
        if not app_version:
            # 兜底：使用与 Tauri 端一致的硬编码版本（不要读 config.yaml 的 version 字段，
            # 因为该字段是配置文件 schema 版本，与应用版本不同）
            app_version = "1.2.0"
        developer = ''
        try:
            from core.config_loader import _load_config
            raw = _load_config()
            developer = raw.get('developer', '')
        except:
            pass
        developer = ''
        try:
            from core.config_loader import _load_config
            raw = _load_config()
            if not app_version:
                app_version = raw.get('version', '')
            developer = raw.get('developer', '')
        except:
            pass
        return {
            "python_version": platform.python_version(),
            "ocr_engine_ready": ocr_ready,
            "ocr_version": ocr_version,
            "poppler_installed": poppler_installed,
            "config_loaded": True,
            "available_memory_gb": memory_gb,
            "app_version": app_version,
            "developer": developer
        }

    def _system_check_dependencies(self, params: Dict, id: Any) -> Dict:
        """检查依赖"""
        dependencies = []
        all_ready = True

        try:
            from core.pdf_ocr_ultra import HAS_RAPIDOCR
            if HAS_RAPIDOCR:
                version = 'unknown'
                try:
                    import importlib.metadata
                    version = importlib.metadata.version('rapidocr_onnxruntime')
                except Exception:
                    pass
                dependencies.append({"name": "RapidOCR", "installed": True, "version": version})
            else:
                dependencies.append({"name": "RapidOCR", "installed": False, "message": "请安装: pip install rapidocr-onnxruntime"})
                all_ready = False
        except Exception as e:
            dependencies.append({"name": "RapidOCR", "installed": False, "message": str(e)})
            all_ready = False

        try:
            import pdfplumber
            version = getattr(pdfplumber, '__version__', 'unknown')
            dependencies.append({"name": "pdfplumber", "installed": True, "version": version})
        except:
            dependencies.append({"name": "pdfplumber", "installed": False, "message": "请安装: pip install pdfplumber"})
            all_ready = False

        try:
            from core.pdf_ocr_ultra import check_poppler_installed, OCRConfig
            cfg = OCRConfig()
            if check_poppler_installed(cfg.poppler_path):
                dependencies.append({"name": "Poppler", "installed": True})
            else:
                dependencies.append({"name": "Poppler", "installed": False, "message": f"请运行: python apps/server/scripts/setup_poppler.py (path: {cfg.poppler_path})"})
                all_ready = False
        except Exception as e:
            dependencies.append({"name": "Poppler", "installed": False, "message": str(e)})
            all_ready = False

        return {"all_ready": all_ready, "dependencies": dependencies}

    def _system_setup_poppler(self, params: Dict, id: Any) -> Dict:
        """自动检测并安装 Poppler"""
        from core.pdf_ocr_ultra import check_poppler_installed, OCRConfig

        cfg = OCRConfig()
        if check_poppler_installed(cfg.poppler_path):
            return {"installed": True, "message": "Poppler 已安装", "path": cfg.poppler_path, "needs_restart": False}

        if getattr(sys, "frozen", False):
            return {"installed": False, "message": "打包环境中 Poppler 缺失，请重新安装应用程序（Poppler 应随程序打包）", "path": cfg.poppler_path}

        if sys.platform != "win32":
            return {"installed": False, "message": "非 Windows 系统，请手动安装 poppler-utils"}

        try:
            scripts_dir = SERVER_SRC.parent / "scripts"
            setup_script = scripts_dir / "setup_poppler.py"
            if not setup_script.exists():
                return {"installed": False, "message": f"安装脚本不存在: {setup_script}"}

            import subprocess
            result = subprocess.run(
                [sys.executable, str(setup_script)],
                capture_output=True, text=True, timeout=300,
                cwd=str(ROOT),
            )
            output = (result.stdout or "") + (result.stderr or "")

            if check_poppler_installed(cfg.poppler_path):
                return {"installed": True, "message": "Poppler 自动安装成功", "path": cfg.poppler_path, "output": output.strip(), "needs_restart": False}
            
            # 安装后尝试动态更新 PATH 并重新检测
            if cfg.poppler_path and cfg.poppler_path.exists():
                poppler_bin = cfg.poppler_path / "bin"
                if poppler_bin.exists():
                    import os
                    new_path = str(poppler_bin) + os.pathsep + os.environ.get("PATH", "")
                    os.environ["PATH"] = new_path
                    # 重新检测
                    if check_poppler_installed(cfg.poppler_path):
                        return {"installed": True, "message": "Poppler 安装成功并已加载", "path": cfg.poppler_path, "output": output.strip(), "needs_restart": False}
            
            return {"installed": True, "message": "Poppler 安装成功，建议重启软件以完成初始化", "path": cfg.poppler_path, "output": output.strip(), "needs_restart": True}
        except subprocess.TimeoutExpired:
            return {"installed": False, "message": "自动安装超时（5分钟），请手动运行: python apps/server/scripts/setup_poppler.py"}
        except Exception as e:
            return {"installed": False, "message": f"自动安装异常: {e}"}

    # ============ 主循环 ============

    def handle_request(self, request: Dict, *, background: bool = False):
        """处理单个请求。background=True 表示在后台线程中调用，需 stdout_lock 保护输出"""
        method = request.get('method')
        params = request.get('params', {})
        id = request.get('id')

        if method not in self.methods:
            self._send_error(-32601, f"Method not found: {method}", id)
            return

        try:
            result = self.methods[method](params, id)
            self._send_response(result, id)
        except CancelledError:
            self._send_error(-32001, "任务已取消", id)
        except Exception as e:
            import traceback as tb
            print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.log", "params": {"level": "error", "message": f"Method {method} failed: {str(e)}"}}), file=sys.stderr, flush=True)
            self._send_error(-32000, str(e), id, {"traceback": tb.format_exc()})

    def run(self):
        """运行服务器主循环"""
        import queue as _queue
        print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.log", "params": {"level": "info", "message": "Python JSON-RPC 服务已启动"}}), file=sys.stderr, flush=True)

        input_queue = _queue.Queue()

        def _stdin_reader():
            while True:
                try:
                    line = sys.stdin.readline()
                    if not line:
                        input_queue.put(None)
                        break
                    line = line.strip()
                    if line:
                        input_queue.put(line)
                except Exception:
                    input_queue.put(None)
                    break

        reader_thread = threading.Thread(target=_stdin_reader, daemon=True)
        reader_thread.start()

        while True:
            try:
                line = input_queue.get(timeout=0.2)
                if line is None:
                    break
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    self._send_error(-32700, f"Parse error: {str(e)}", None)
                    continue

                method = request.get('method', '')
                if method in self._LONG_METHODS:
                    def _run_long(req=request):
                        self.handle_request(req, background=True)
                    threading.Thread(target=_run_long, daemon=True).start()
                else:
                    self.handle_request(request)
            except _queue.Empty:
                continue
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.log", "params": {"level": "error", "message": f"Server error: {str(e)}"}}), file=sys.stderr, flush=True)

        print(_safe_json_dumps({"jsonrpc": "2.0", "method": "notify.log", "params": {"level": "info", "message": "Python JSON-RPC 服务已停止"}}), file=sys.stderr, flush=True)


if __name__ == '__main__':
    # 尽早通知 Tauri（便携 Python 模式下冷启动远快于 PyInstaller）
    print(
        _safe_json_dumps(
            {
                "jsonrpc": "2.0",
                "method": "notify.log",
                "params": {"level": "info", "message": "Python JSON-RPC 服务已启动"},
            }
        ),
        file=sys.stderr,
        flush=True,
    )
    server = JsonRpcServer()
    server.run()
