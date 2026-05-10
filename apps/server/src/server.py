#!/usr/bin/env python3
"""
公积金 OCR 工具 - JSON-RPC 服务端
通过 stdin/stdout/stderr 与 Tauri 前端通信
"""

import json
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

# 添加项目根目录到路径
ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

class JsonRpcServer:
    def __init__(self):
        self.methods = {}
        self.request_id = 0
        self._register_methods()
    
    def _register_methods(self):
        """注册所有 RPC 方法"""
        # OCR 模块
        self.methods['ocr.recognize'] = self._ocr_recognize
        self.methods['ocr.recognize_batch'] = self._ocr_recognize_batch
        self.methods['ocr.get_cache_status'] = self._ocr_get_cache_status
        
        # 非诉审查模块
        self.methods['non_litigation.process'] = self._non_litigation_process
        self.methods['non_litigation.get_cases'] = self._non_litigation_get_cases
        self.methods['non_litigation.preview_split'] = self._non_litigation_preview_split
        
        # 强制执行模块
        self.methods['enforcement.extract'] = self._enforcement_extract
        self.methods['enforcement.fill_excel'] = self._enforcement_fill_excel
        
        # 配置模块
        self.methods['config.get'] = self._config_get
        self.methods['config.set_corrections'] = self._config_set_corrections
        self.methods['config.reload'] = self._config_reload
        
        # 系统模块
        self.methods['system.get_status'] = self._system_get_status
        self.methods['system.check_dependencies'] = self._system_check_dependencies
    
    def _send_response(self, result: Any, id: Any):
        """发送响应到 stdout"""
        response = {
            "jsonrpc": "2.0",
            "result": result,
            "id": id
        }
        print(json.dumps(response, ensure_ascii=False), flush=True)
    
    def _send_error(self, code: int, message: str, id: Any, data: Optional[Dict] = None):
        """发送错误响应"""
        error = {
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message,
                "data": data
            },
            "id": id
        }
        print(json.dumps(error, ensure_ascii=False), flush=True)
    
    def _send_notification(self, method: str, params: Dict):
        """发送通知到 stderr（进度推送）"""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        print(json.dumps(notification, ensure_ascii=False), file=sys.stderr, flush=True)
    
    def _send_progress(self, task_id: str, phase: str, current: int, total: int, message: str, detail: Optional[Dict] = None):
        """发送进度通知"""
        params = {
            "task_id": task_id,
            "phase": phase,
            "status": "running",
            "current": current,
            "total": total,
            "message": message
        }
        if detail:
            params["detail"] = detail
        self._send_notification("notify.progress", params)
    
    def _send_log(self, level: str, message: str):
        """发送日志通知"""
        import datetime
        self._send_notification("notify.log", {
            "level": level,
            "message": message,
            "timestamp": datetime.datetime.now().isoformat()
        })
    
    # ============ OCR 模块 ============
    
    def _ocr_recognize(self, params: Dict, id: Any) -> Dict:
        """单文件 OCR 识别"""
        file_path = params.get('file_path')
        force_ocr = params.get('force_ocr', False)
        doc_type = params.get('doc_type')
        
        try:
            from pdf_ocr_ultra import UltraFastOCR, OCRConfig
            
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
        parallel = params.get('parallel', True)
        
        results = []
        for i, file_path in enumerate(file_paths):
            self._send_progress(f"ocr-batch-{id}", "ocr_batch", i + 1, len(file_paths), f"识别: {Path(file_path).name}")
            try:
                result = self._ocr_recognize({'file_path': file_path}, id)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e), "file_path": file_path})
        
        return {"results": results}
    
    def _ocr_get_cache_status(self, params: Dict, id: Any) -> Dict:
        """获取 OCR 缓存状态"""
        cache_dir = ROOT / 'temp' / 'non-litigation' / 'ocr-cache'
        cached_files = []
        if cache_dir.exists():
            cached_files = [f.name for f in cache_dir.glob('*_ultra_result.json')]
        
        return {
            "cached_files": cached_files,
            "total_cached": len(cached_files),
            "cache_dir": str(cache_dir)
        }
    
    # ============ 非诉审查模块 ============
    
    def _non_litigation_process(self, params: Dict, id: Any) -> Dict:
        """非诉审查完整处理流程"""
        sample_root = params.get('sample_root')
        mode = params.get('mode', 'mock')
        force = params.get('force', False)
        batch_name = params.get('batch_name', 'batch1')
        
        task_id = f"nl-{id}"
        
        try:
            from non_litigation_export import (
                build_mock_ocr_cache,
                build_real_ocr_cache,
                ensure_non_litigation_input_structure,
                export_non_litigation_standard_outputs,
                get_non_litigation_ocr_cache_dir,
                get_non_litigation_result_root,
            )
            from non_litigation_product import load_non_litigation_cases
            from non_litigation_validator import validate_ocr_results
            from report_generator import generate_html_report
            from project_evaluation import evaluate_non_litigation_quality
            import time
            
            sample_root_path = Path(sample_root)
            input_root = ensure_non_litigation_input_structure(ROOT)
            if (sample_root_path / '原始文件').exists():
                input_root = sample_root_path / '原始文件'
            
            result_root = get_non_litigation_result_root(ROOT)
            ocr_cache_dir = get_non_litigation_ocr_cache_dir(ROOT)
            
            result_root.mkdir(parents=True, exist_ok=True)
            ocr_cache_dir.mkdir(parents=True, exist_ok=True)
            
            # OCR 阶段
            self._send_progress(task_id, "ocr_cache", 0, 5, "开始 OCR 识别...")
            
            if mode == 'real_ocr':
                if force and ocr_cache_dir.exists():
                    import shutil
                    shutil.rmtree(ocr_cache_dir)
                    ocr_cache_dir.mkdir(parents=True, exist_ok=True)
                build_real_ocr_cache(input_root, ocr_cache_dir, use_mock=False)
            else:
                build_mock_ocr_cache(sample_root_path, ocr_cache_dir, input_dir=input_root)
            
            self._send_progress(task_id, "ocr_cache", 1, 5, "OCR 识别完成")
            
            # 导出阶段
            self._send_progress(task_id, "export", 2, 5, "开始导出文件...")
            export_result = export_non_litigation_standard_outputs(
                sample_root=sample_root_path,
                input_dir=input_root,
                output_root=result_root,
                ocr_cache_dir=ocr_cache_dir,
            )
            self._send_progress(task_id, "export", 3, 5, f"导出完成: {export_result['created_count']} 个文件")
            
            # 验证阶段
            self._send_progress(task_id, "validation", 4, 5, "开始验证...")
            cases = load_non_litigation_cases(sample_root_path)
            validation_result = validate_ocr_results(cases, ocr_cache_dir, input_dir=input_root)
            
            # 质量评估
            quality = evaluate_non_litigation_quality(ROOT, result_root, sample_root=sample_root_path)
            
            self._send_progress(task_id, "report", 5, 5, "生成报告...")
            
            # 生成报告
            html_report_path = ROOT / 'output' / 'ocr-validation-report.html'
            html_report_path.parent.mkdir(parents=True, exist_ok=True)
            generate_html_report(
                validation_result,
                html_report_path,
                mode=mode,
                runtime_seconds=0
            )
            
            return {
                "success": True,
                "summary": {
                    "sample_root": str(sample_root_path),
                    "result_root": str(result_root),
                    "runtime_seconds": 0,
                    "mode": mode,
                    "created_count": export_result['created_count'],
                    "quality": {
                        "total_files": quality['total_files'],
                        "page_count_matched": quality['page_count_matched'],
                        "page_count_match_rate": quality['page_count_match_rate']
                    },
                    "validation": validation_result['summary']
                },
                "html_report_path": str(html_report_path)
            }
            
        except Exception as e:
            traceback.print_exc()
            raise Exception(f"非诉审查处理失败: {str(e)}")
    
    def _non_litigation_get_cases(self, params: Dict, id: Any) -> Dict:
        """获取案件列表"""
        sample_root = params.get('sample_root')
        
        try:
            from non_litigation_product import load_non_litigation_cases
            
            cases = load_non_litigation_cases(Path(sample_root))
            return {"cases": cases}
        except Exception as e:
            raise Exception(f"获取案件列表失败: {str(e)}")
    
    def _non_litigation_preview_split(self, params: Dict, id: Any) -> Dict:
        """预览 PDF 分割结果"""
        doc_type = params.get('doc_type')
        pdf_path = params.get('pdf_path')
        expected_count = params.get('expected_count', 0)
        
        try:
            from non_litigation_export import inspect_pdf_page_count, detect_page_ranges
            
            pdf_path_obj = Path(pdf_path)
            total_pages = inspect_pdf_page_count(pdf_path_obj)
            
            ranges = detect_page_ranges(total_pages, expected_count, doc_type)
            
            detected_ranges = []
            for start, end in ranges:
                detected_ranges.append({
                    "start": start + 1,
                    "end": end,
                    "preview_text": f"第 {start + 1} 页到第 {end} 页"
                })
            
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
        input_dir = params.get('input_dir')
        excel_path = params.get('excel_path')
        
        try:
            from enforcement_extractor import process_enforcement_cases
            
            result = process_enforcement_cases(
                input_dir=Path(input_dir),
                excel_path=Path(excel_path)
            )
            
            return {
                "processed": result.get('processed', 0),
                "extracted": result.get('extracted', []),
                "updated_excel_path": result.get('updated_excel_path', '')
            }
        except Exception as e:
            raise Exception(f"强制执行提取失败: {str(e)}")
    
    def _enforcement_fill_excel(self, params: Dict, id: Any) -> Dict:
        """回填到 Excel"""
        # 简化实现
        return {"success": True}
    
    # ============ 配置模块 ============
    
    def _config_get(self, params: Dict, id: Any) -> Dict:
        """获取配置"""
        try:
            from config_loader import load_config
            
            cfg = load_config()
            
            return {
                "doc_types": [
                    {
                        "key": dt.key,
                        "pages_per_case": dt.pages_per_case,
                        "filename_pattern": dt.filename_pattern
                    }
                    for dt in cfg.doc_types
                ],
                "regex_patterns": cfg.regex_patterns,
                "ocr_corrections": cfg.ocr_corrections,
                "validation": {
                    "fuzzy_match_threshold": cfg.validation.fuzzy_match_threshold
                }
            }
        except Exception as e:
            raise Exception(f"获取配置失败: {str(e)}")
    
    def _config_set_corrections(self, params: Dict, id: Any) -> Dict:
        """设置 OCR 纠错词表"""
        corrections = params.get('corrections', [])
        # 简化实现，实际应该写入配置文件
        return {"success": True, "count": len(corrections)}
    
    def _config_reload(self, params: Dict, id: Any) -> Dict:
        """重新加载配置"""
        try:
            from config_loader import load_config
            load_config._config = None  # 清除缓存
            cfg = load_config()
            return {"success": True, "config_path": str(cfg._config_path)}
        except Exception as e:
            raise Exception(f"重新加载配置失败: {str(e)}")
    
    # ============ 系统模块 ============
    
    def _system_get_status(self, params: Dict, id: Any) -> Dict:
        """获取系统状态"""
        import platform
        
        # 检查依赖
        ocr_ready = False
        poppler_installed = False
        
        try:
            from pdf_ocr_ultra import HAS_RAPIDOCR
            ocr_ready = HAS_RAPIDOCR
        except:
            pass
        
        try:
            from pdf_ocr_ultra import check_poppler_installed, OCRConfig
            cfg = OCRConfig()
            poppler_installed = check_poppler_installed(cfg.poppler_path)
        except:
            pass
        
        # 获取内存信息
        memory_gb = 0
        try:
            import psutil
            memory_gb = round(psutil.virtual_memory().available / (1024**3), 1)
        except:
            pass
        
        return {
            "python_version": platform.python_version(),
            "ocr_engine_ready": ocr_ready,
            "poppler_installed": poppler_installed,
            "config_loaded": True,
            "available_memory_gb": memory_gb
        }
    
    def _system_check_dependencies(self, params: Dict, id: Any) -> Dict:
        """检查依赖"""
        dependencies = []
        all_ready = True
        
        # Check RapidOCR
        try:
            from pdf_ocr_ultra import HAS_RAPIDOCR
            if HAS_RAPIDOCR:
                import rapidocr_onnxruntime
                version = getattr(rapidocr_onnxruntime, '__version__', 'unknown')
                dependencies.append({"name": "RapidOCR", "installed": True, "version": version})
            else:
                dependencies.append({"name": "RapidOCR", "installed": False, "message": "请安装: pip install rapidocr-onnxruntime"})
                all_ready = False
        except Exception as e:
            dependencies.append({"name": "RapidOCR", "installed": False, "message": str(e)})
            all_ready = False
        
        # Check pdfplumber
        try:
            import pdfplumber
            version = getattr(pdfplumber, '__version__', 'unknown')
            dependencies.append({"name": "pdfplumber", "installed": True, "version": version})
        except:
            dependencies.append({"name": "pdfplumber", "installed": False, "message": "请安装: pip install pdfplumber"})
            all_ready = False
        
        # Check Poppler
        try:
            from pdf_ocr_ultra import check_poppler_installed, OCRConfig
            cfg = OCRConfig()
            if check_poppler_installed(cfg.poppler_path):
                dependencies.append({"name": "Poppler", "installed": True})
            else:
                dependencies.append({"name": "Poppler", "installed": False, "message": "请运行: python scripts/setup_poppler.py"})
                all_ready = False
        except Exception as e:
            dependencies.append({"name": "Poppler", "installed": False, "message": str(e)})
            all_ready = False
        
        return {
            "all_ready": all_ready,
            "dependencies": dependencies
        }
    
    # ============ 主循环 ============
    
    def handle_request(self, request: Dict):
        """处理单个请求"""
        method = request.get('method')
        params = request.get('params', {})
        id = request.get('id')
        
        if method not in self.methods:
            self._send_error(-32601, f"Method not found: {method}", id)
            return
        
        try:
            result = self.methods[method](params, id)
            self._send_response(result, id)
        except Exception as e:
            self._send_error(-32000, str(e), id, {"traceback": traceback.format_exc()})
    
    def run(self):
        """运行服务器主循环"""
        self._send_log("info", "Python JSON-RPC 服务已启动")
        
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    self._send_error(-32700, f"Parse error: {str(e)}", None)
                    continue
                
                # 在后台线程处理请求，避免阻塞
                threading.Thread(target=self.handle_request, args=(request,)).start()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self._send_log("error", f"Server error: {str(e)}")
        
        self._send_log("info", "Python JSON-RPC 服务已停止")


if __name__ == '__main__':
    server = JsonRpcServer()
    server.run()
