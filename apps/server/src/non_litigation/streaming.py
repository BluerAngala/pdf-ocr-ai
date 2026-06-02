#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
流式批次处理器

1. 按文档粒度逐页 OCR（授权书/所函/申请书整体扫描，责催逐个扫描）
2. OCR 引擎单例 — CPU 推理天然串行，多线程争锁只会增加开销
3. 生产者/消费者流水线：提取第 N+1 页图片同时 OCR 第 N 页
4. 纠错/后处理与串行路径一致（apply_ocr_corrections + TextPostProcessor）
5. 区域配置从 config.yaml 读取，不硬编码
6. 断点续跑（TaskStateManager + SQLite）
7. 责催类型支持 NOTICE_PATTERN 命中即停
"""

import gc
import queue
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any

from core.paths import ROOT, USER_DATA_DIR
from core.task_cancel import CancelledError
from core.task_state import TaskStateManager, Task
from core.region_extractor import RegionExtractor, REGIONS
from core.text_postprocessor import TextPostProcessor
from core.config_loader import load_config
from core.pdf_ocr_ultra import get_ocr_engine, OCRConfig, _ocr_lock as _global_ocr_lock

_cfg = load_config()

WHOLE_PDF_TYPES = ('auth_all', 'letter_all', 'application')

NOTICE_PATTERN = _cfg.notice_pattern

_log_fn = None
_log_info = True


def _log(msg: str, level: str = "INFO"):
    if level == "ERROR" or _log_info:
        if _log_fn:
            _log_fn(msg)
        else:
            import sys
            stream = sys.stderr if level == "ERROR" else sys.stdout
            print(msg, file=stream, flush=True)


def set_log_fn(fn):
    global _log_fn
    _log_fn = fn


def set_log_info(enabled: bool):
    global _log_info
    _log_info = enabled


def _get_doc_regions(task_type: str) -> list:
    cfg_key = {
        'notice': '责催', 'auth': '授权书', 'letter': '所函',
        'auth_all': '授权书', 'letter_all': '所函',
        'application': '申请书',
    }.get(task_type, '')
    names = _cfg.ocr_doc_regions.get(cfg_key, [])
    return [REGIONS[n] for n in names if n in REGIONS]


def apply_ocr_corrections(text: str) -> str:
    for wrong, correct in _cfg.ocr_corrections:
        if wrong in text and correct not in text[:text.index(wrong)]:
            text = text.replace(wrong, correct)
    return text


_SENTINEL = object()


class StreamingBatchProcessor:

    def __init__(self,
                 state_mgr: TaskStateManager,
                 batch_size: int = 50,
                 max_workers: int = 1,
                 timeout_per_task: int = 1800):
        self.state = state_mgr
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.timeout = timeout_per_task

        self._ocr_engine = None
        self.region_extractor = None
        self.post_processor = None

        self._processed_count = 0
        self._error_count = 0

    def initialize(self):
        if self._ocr_engine is not None:
            return

        _log("初始化 OCR 引擎...")
        t0 = time.perf_counter()

        self._ocr_engine = get_ocr_engine()

        config = OCRConfig()
        self.region_extractor = RegionExtractor(
            dpi=_cfg.ocr_region_dpi,
            poppler_path=config.poppler_path,
        )
        self.post_processor = TextPostProcessor()

        dur = time.perf_counter() - t0
        _log(f"OCR 引擎初始化完成 ({dur:.2f}s)")

    def run(self,
            progress_callback: Optional[Callable[[Dict], None]] = None,
            cancel_check: Optional[Callable[[], bool]] = None):
        batch_idx = 0

        while True:
            if cancel_check and cancel_check():
                _log("收到取消信号，优雅退出")
                raise CancelledError("用户取消")

            batch = self.state.get_pending(
                batch_size=self.batch_size,
                include_error=True,
                max_attempts=2
            )

            if not batch:
                _log("所有任务处理完成")
                break

            batch_idx += 1
            _log(f"批次 {batch_idx}: 处理 {len(batch)} 个文档...")

            try:
                self._process_batch(batch, progress_callback, cancel_check)
            finally:
                pass

            gc.collect()

        summary = self.state.get_summary()
        _log(f"完成 {summary['done']}/{summary['total']}, "
             f"失败 {summary['failed_permanently']}, "
             f"进度 {summary['progress']:.0%}")

    def _process_batch(self,
                       tasks: List[Task],
                       progress_callback: Optional[Callable] = None,
                       cancel_check: Optional[Callable] = None):

        for task in tasks:
            if cancel_check and cancel_check():
                _log("收到取消信号，停止处理")
                raise CancelledError("用户取消")
            try:
                result = self._execute_task(task, cancel_check)
                self.state.update_status(
                    task.task_id, 'done',
                    result=result.get('ocr_result'),
                    output_file=result.get('output_file')
                )
                self._processed_count += 1
                ocr_r = result.get('ocr_result', {})
                _log(f"  {ocr_r.get('filename', task.task_id)}: "
                     f"{ocr_r.get('total_pages', 0)}页, "
                     f"{ocr_r.get('duration', 0):.1f}s")
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                _log(f"  {task.task_id} 失败: {error_msg}", level="ERROR")
                self.state.update_status(task.task_id, 'error', error=error_msg)
                self._error_count += 1

            if progress_callback:
                try:
                    summary = self.state.get_summary()
                    progress_callback(summary)
                except Exception:
                    pass

    def _ocr_image(self, image) -> List[str]:
        import numpy as np
        image_array = np.array(image)
        with _global_ocr_lock:
            result = self._ocr_engine(image_array)
        texts = []
        if result:
            if isinstance(result, tuple) and len(result) >= 1 and result[0]:
                for item in result[0]:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        text = str(item[1]).strip()
                        if text:
                            texts.append(text)
            elif hasattr(result, 'txts') and result.txts:
                for text in result.txts:
                    if text and str(text).strip():
                        texts.append(str(text))
        return texts

    def _execute_task(self, task: Task,
                      cancel_check: Optional[Callable] = None) -> Dict[str, Any]:
        pdf_path = Path(task.source_file)
        regions = _get_doc_regions(task.task_type)
        is_notice = task.task_type == 'notice'

        total_pages = self.region_extractor.get_page_count(pdf_path)
        is_whole = task.task_type in WHOLE_PDF_TYPES
        page_end = total_pages if is_whole else total_pages

        page_range = range(task.page_start, page_end + 1)
        page_list = list(page_range)

        # 大文件使用批量渲染优化：逐页调用 pdftoppm 有 ~0.4s 启动开销
        # 377页单页调用 = 377 × ~1.5s = 565s；批量20页 = 19批 × ~20s = 380s
        batch_size = 20 if total_pages > 50 else 5
        img_queue: queue.Queue = queue.Queue(maxsize=max(4, batch_size // 2))

        def _producer():
            # 批量渲染页面，减少 pdftoppm 子进程调用次数
            for i in range(0, len(page_list), batch_size):
                if cancel_check and cancel_check():
                    break
                batch_pages = page_list[i:i + batch_size]
                try:
                    # 使用批量渲染
                    page_images = self.region_extractor.render_pages_batch(pdf_path, batch_pages)
                    for page_num in batch_pages:
                        if cancel_check and cancel_check():
                            break
                        if page_num not in page_images:
                            img_queue.put((page_num, None, RuntimeError(f"页面 {page_num} 渲染失败")), timeout=120)
                            continue
                        full_image = page_images[page_num]
                        if regions:
                            images = self.region_extractor.crop_regions_from_image(full_image, regions)
                        else:
                            images = [full_image]
                        img_queue.put((page_num, full_image, images), timeout=120)
                except Exception as e:
                    # 批量失败时，回退到单页提取
                    _log(f"  {pdf_path.name}: 批量渲染失败，回退到单页模式: {e}")
                    for page_num in batch_pages:
                        if cancel_check and cancel_check():
                            break
                        try:
                            full_image = self.region_extractor.extract_full_page(pdf_path, page_num)
                            if regions:
                                images = self.region_extractor.crop_regions_from_image(full_image, regions)
                            else:
                                images = [full_image]
                            img_queue.put((page_num, full_image, images), timeout=120)
                        except Exception as e2:
                            img_queue.put((page_num, None, e2), timeout=120)
            img_queue.put(_SENTINEL)

        producer = threading.Thread(target=_producer, daemon=True)
        producer.start()

        all_pages = []
        total_duration = 0.0
        _last_log_time = time.perf_counter()
        notice_found = False

        while True:
            item = img_queue.get(timeout=self.timeout)

            if item is _SENTINEL:
                break

            page_num, full_image, images_or_err = item

            if full_image is None:
                if isinstance(images_or_err, Exception):
                    _log(f"  {pdf_path.name}: 第{page_num}页提取失败: {images_or_err}", level="ERROR")
                continue

            page_t0 = time.perf_counter()

            texts = []
            for img in images_or_err:
                ocr_texts = self._ocr_image(img)
                texts.append("\n".join(ocr_texts))

            raw_text = "\n".join(texts)
            page_dur = time.perf_counter() - page_t0
            total_duration += page_dur

            corrected = apply_ocr_corrections(raw_text)
            processed = self.post_processor.process(corrected)

            all_pages.append({
                'page': page_num,
                'text': processed['processed'],
                'original_text': raw_text,
                'method': 'streaming_pipeline',
                'duration': page_dur,
            })

            del full_image
            del images_or_err

            now = time.perf_counter()
            if page_num % 5 == 0 or now - _last_log_time > 8:
                _log(f"  {pdf_path.name}: {page_num}/{total_pages} 页 ({total_duration:.1f}s)")
                _last_log_time = now

            if is_notice and NOTICE_PATTERN:
                if NOTICE_PATTERN.search(processed['processed']):
                    _log(f"  {pdf_path.name}: 第{page_num}页命中责令号，停止扫描")
                    notice_found = True
                    while True:
                        leftover = img_queue.get(timeout=5)
                        if leftover is _SENTINEL:
                            break
                    break

        producer.join(timeout=30)

        full_text = "\n".join(p['text'] for p in all_pages)
        result = {
            'ocr_result': {
                'pages': all_pages,
                'total_pages': len(all_pages),
                'filename': pdf_path.name,
                'duration': total_duration,
                'full_text': full_text,
                'notice_found': notice_found,
            },
            'matched_company': None,
            'output_file': None,
        }

        return result
