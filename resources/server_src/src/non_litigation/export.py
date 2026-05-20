#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
非诉组 PDF 导出模块

处理逻辑：
1. 责催证据文件：每个 PDF 就是一个独立案件，不切割，直接重命名
2. 申请书：OCR 检测"强制执行申请书"标题定位页边界，fallback 到固定页数
3. 授权书：固定 1 页/公司，按顺序切割
4. 所函：固定 1 页/公司，按顺序切割
"""

import json
import os
import queue
import re
import shutil
import sys
import threading
import time
from difflib import SequenceMatcher
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Iterable

try:
    from openpyxl import Workbook
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

from core.region_extractor import RegionExtractor, REGIONS
from contextlib import contextmanager

from pypdf import PdfReader, PdfWriter

from non_litigation.output_plan import build_expected_output_tree
from non_litigation.product import load_non_litigation_cases
from core.text_postprocessor import TextPostProcessor
from core.system_resource import detect_system_resources

from core.paths import ROOT, USER_DATA_DIR

from core.config_loader import load_config
_cfg = load_config()

try:
    from core.pdf_ocr_ultra import UltraFastOCR, OCRConfig, ImagePreprocessor
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    ImagePreprocessor = None
    _log("[WARN] pdf_ocr_ultra 导入失败，将使用 Mock OCR")

try:
    from core.task_state import TaskStateManager, Task
    from non_litigation.streaming import StreamingBatchProcessor
    HAS_STREAMING = True
except ImportError:
    HAS_STREAMING = False
    TaskStateManager = None
    Task = None
    StreamingBatchProcessor = None


SOURCE_MAPPING = _cfg.source_mapping
APPLICATION_BOUNDARY_KEYWORDS = _cfg.boundary_keywords.get('申请书', [])
NON_LITIGATION_RESULT_DIRNAME = _cfg.result_dirname
NON_LITIGATION_TEMP_DIRNAME = _cfg.temp_dirname
NON_LITIGATION_INPUT_DIRNAME = _cfg.input_dirname
NOTICE_PATTERN = _cfg.notice_pattern
NON_LITIGATION_CORRECTIONS = _cfg.ocr_corrections
PAGES_PER_CASE = _cfg.pages_per_case

_audit_log: List[Dict] = []

_suppress_print = False
_PDF_TIMEOUT_SECONDS = 300


def _log(msg: str, quiet: bool = False):
    if not quiet and not _suppress_print:
        print(msg)


def _get_doc_regions(doc_type: str):
    return [REGIONS[name] for name in _cfg.ocr_doc_regions.get(doc_type, []) if name in REGIONS]


def _build_ocr_config() -> "OCRConfig":
    return OCRConfig(
        dpi=_cfg.ocr_dpi,
        max_image_size=_cfg.ocr_max_image_size,
        parallel_workers=_cfg.ocr_parallel_workers,
        small_pdf_page_threshold=_cfg.ocr_small_pdf_page_threshold,
    )


def _build_ocr_processors() -> Tuple["UltraFastOCR", RegionExtractor]:
    config = _build_ocr_config()
    from core.pdf_ocr_ultra import _ocr_engine as _global_engine
    skip = _global_engine is not None
    return UltraFastOCR(config, skip_warmup=skip, log_fn=_log), RegionExtractor(dpi=_cfg.ocr_region_dpi, poppler_path=config.poppler_path)


def _collect_region_texts(
    ocr: "UltraFastOCR",
    extractor: RegionExtractor,
    pdf_path: Path,
    page_num: int,
    doc_type: str,
    *,
    full_image=None,
    region_names: Optional[List[str]] = None,
) -> Tuple[str, List[Dict]]:
    requested_names = region_names or _cfg.ocr_doc_regions.get(doc_type, [])
    selected_names = [name for name in requested_names if name in REGIONS]
    regions = [REGIONS[name] for name in selected_names]
    if not regions:
        return "", []

    if full_image is None:
        images = extractor.extract_multiple_regions(pdf_path, page_num, regions)
    else:
        images = extractor.crop_regions_from_image(full_image, regions)
    pieces = []
    logs = []
    doc_ocr = _cfg.get_doc_ocr(doc_type)
    max_img_size = doc_ocr.max_image_size if doc_ocr else _cfg.ocr_region_max_image_size
    for region_name, region, image in zip(selected_names, regions, images):
        result = ocr.recognize_image_region(
            image,
            page_num=page_num,
            max_image_size=max_img_size,
            apply_enhancement=False,
            apply_sharpen=False,
            method=f"region:{region.name}",
            optimize_output=False,
        )
        text = result.text.strip()
        if text:
            pieces.append(text)
        logs.append({
            'region': region.name,
            'region_key': region_name,
            'method': result.method,
            'duration': result.duration,
            'text_length': len(text),
            'text': text,
        })

    return "\n".join(pieces), logs


def get_audit_log() -> List[Dict]:
    return _audit_log.copy()


def _log_audit(event: str, detail: Dict):
    _audit_log.append({'event': event, **detail})


_PREFETCH_SENTINEL = object()


def _prefetch_pages(region_extractor, pdf_path: Path, page_nums: List[int],
                    out_queue: queue.Queue, cancel_check=None):
    """后台线程：按序预提取页面图片放入队列，让 OCR 消费时不用等图片转换。"""
    for pn in page_nums:
        if cancel_check and cancel_check():
            break
        try:
            img = region_extractor.extract_full_page(pdf_path, pn)
            out_queue.put((pn, img), timeout=60)
        except Exception as e:
            out_queue.put((pn, e), timeout=60)
    out_queue.put(_PREFETCH_SENTINEL)


def _get_prefetched(out_queue: queue.Queue, timeout: int = 120):
    """从预取队列取一页；返回 (page_num, image) 或 (page_num, error) 或 None 表示结束。"""
    try:
        item = out_queue.get(timeout=timeout)
    except queue.Empty:
        return None
    if item is _PREFETCH_SENTINEL:
        return None
    return item


@contextmanager
def open_pdf_reader(pdf_path: Path):
    reader = PdfReader(str(pdf_path))
    try:
        yield reader
    finally:
        if hasattr(reader, 'stream') and reader.stream:
            reader.stream.close()


def apply_ocr_corrections(text: str, doc_type: str = None) -> str:
    corrections = _cfg.get_doc_corrections(doc_type) if doc_type else NON_LITIGATION_CORRECTIONS
    for wrong, correct in corrections:
        if wrong in text:
            text = text.replace(wrong, correct)
    return text


def normalize_notice_number(text: str) -> str:
    text = text.replace(' ', '')
    text = text.replace('(', '〔').replace(')', '〕')
    text = text.replace('（', '〔').replace('）', '〕')
    text = text.replace('[', '〔').replace(']', '〕')
    return text


def _get_notice_root_number(notice_number: str) -> str:
    normalized = normalize_notice_number(notice_number)
    return re.sub(r'(\d+)-\d+号$', r'\1号', normalized)


def _score_notice_candidate(page_num: int, text: str, post_processor: TextPostProcessor) -> Dict:
    corrected_text = apply_ocr_corrections(text, doc_type='责催')
    structured = post_processor.extract_notice_fields(corrected_text)
    decision_numbers = [normalize_notice_number(item) for item in structured.get('decision_numbers', [])]
    
    return {
        'page': page_num,
        'decision_numbers': decision_numbers,
        'has_notice': bool(decision_numbers),
        'company_name': structured.get('company_name'),
    }


def _select_notice_candidate(candidate_pages: List[Dict]) -> Dict:
    if not candidate_pages:
        return {}

    all_candidates = []
    for page_entry in candidate_pages:
        for number in page_entry.get('decision_numbers', []):
            normalized = normalize_notice_number(number)
            root_number = _get_notice_root_number(normalized)
            all_candidates.append({
                'page': page_entry.get('page'),
                'number': normalized,
                'root_number': root_number,
                'is_base_number': normalized == root_number,
                'company_name': page_entry.get('company_name'),
            })

    if not all_candidates:
        return {}

    base_candidates = [c for c in all_candidates if c['is_base_number']]
    best = base_candidates[0] if base_candidates else all_candidates[0]

    return {
        'selected_notice': best['number'],
        'selected_page': best['page'],
        'selected_root_notice': best['root_number'],
        'candidate_notices': all_candidates,
    }


def _compact_text(text: str) -> str:
    return text.replace('\n', '').replace(' ', '')


def _build_region_stats(page_logs: List[Dict]) -> Dict:
    text_lengths = [item.get('text_length', 0) for item in page_logs]
    return {
        'attempt_count': len(page_logs),
        'total_duration': round(sum(item.get('duration', 0) for item in page_logs), 4),
        'max_text_length': max(text_lengths, default=0),
        'total_text_length': sum(text_lengths),
        'regions': [item.get('region') for item in page_logs],
    }


def _should_fallback_notice(region_text: str, page_candidate: Optional[Dict], min_text_length: int = None) -> Tuple[bool, Optional[str]]:
    compact = _compact_text(region_text)
    
    if page_candidate and page_candidate.get('decision_numbers'):
        return False, None
    
    fallback_min = min_text_length or _cfg.notice_region_fallback_min_text_length
    if len(compact) < fallback_min:
        if '责字' in compact or '责令' in compact or '公积金' in compact or '穗' in compact or '越秀' in compact:
            return False, 'weak_notice_signal_only'
        return True, 'region_text_too_short'
    
    if '责字' in compact or '责令' in compact or '公积金' in compact:
        return False, 'weak_notice_signal_only'
    
    if '穗' in compact or '越秀' in compact or '中心' in compact:
        return False, 'weak_location_signal'
    
    return True, 'no_notice_signal'


def _should_fallback_application(
    page_num: int,
    text: str,
    detected_boundaries: List[int],
    expected_boundaries: int,
    expected_start_pages: set,
    min_text_length: int = None,
) -> Tuple[bool, Optional[str]]:
    compact = _compact_text(text)
    is_candidate_boundary_page = page_num in expected_start_pages
    previous_page_detected = (page_num - 1) in detected_boundaries
    next_page_detected = (page_num + 1) in detected_boundaries
    boundary_gap_exists = len(detected_boundaries) < expected_boundaries
    nearby_boundary_signal = previous_page_detected or next_page_detected
    fallback_min = min_text_length or _cfg.application_region_fallback_min_text_length
    weak_region_text = len(compact) < fallback_min

    if not is_candidate_boundary_page:
        return False, None
    if any(keyword in text for keyword in APPLICATION_BOUNDARY_KEYWORDS):
        return False, None
    if weak_region_text:
        return True, 'boundary_candidate_text_short'
    if boundary_gap_exists and not nearby_boundary_signal:
        return True, 'boundary_gap_without_neighbor_signal'
    return False, None


def _should_fallback_company_doc(combined_text: str, region_usable: bool, marker_detected: bool) -> Tuple[bool, Optional[str]]:
    if marker_detected or region_usable:
        return False, None
    if len(_compact_text(combined_text)) < _cfg.company_doc_region_fallback_min_text_length:
        return True, 'region_text_too_short'
    return False, 'marker_missing_and_region_unusable'


def _build_ocr_output_summary(pdf_path: Path, pages: List[Dict], total_duration: float, *, doc_type: Optional[str] = None) -> Dict:
    if not pages:
        return {
            'doc_type': doc_type,
            'file_name': pdf_path.name,
            'page_count': 0,
            'total_duration': round(total_duration, 4),
            'fallback_pages': 0,
            'fallback_rate': 0.0,
            'region_attempts_total': 0,
            'region_ocr_duration_total': 0.0,
            'slowest_page': None,
        }

    fallback_pages = sum(1 for page in pages if page.get('fallback_used'))
    slowest_page = max(pages, key=lambda page: page.get('duration', 0))
    return {
        'doc_type': doc_type,
        'file_name': pdf_path.name,
        'page_count': len(pages),
        'total_duration': round(total_duration, 4),
        'fallback_pages': fallback_pages,
        'fallback_rate': round(fallback_pages / len(pages), 4),
        'region_attempts_total': sum(page.get('region_stats', {}).get('attempt_count', 0) for page in pages),
        'region_ocr_duration_total': round(sum(page.get('region_stats', {}).get('total_duration', 0) for page in pages), 4),
        'slowest_page': {
            'page': slowest_page.get('page'),
            'duration': round(slowest_page.get('duration', 0), 4),
            'method': slowest_page.get('method'),
            'fallback_used': slowest_page.get('fallback_used', False),
            'fallback_trigger_reason': slowest_page.get('fallback_trigger_reason'),
        },
    }


def fuzzy_match_notice(detected: str, target_map: Dict[str, str], threshold: float = 0.85) -> Tuple[Optional[str], float]:
    best_match = None
    best_ratio = 0
    detected_root = _get_notice_root_number(detected)

    for target in target_map.keys():
        if _get_notice_root_number(target) != detected_root:
            continue
        ratio = SequenceMatcher(None, detected, target).ratio()
        target_is_base = normalize_notice_number(target) == _get_notice_root_number(target)
        if not target_is_base and normalize_notice_number(detected) == detected_root:
            ratio -= 0.03
        if ratio > best_ratio and ratio >= threshold:
            best_ratio = ratio
            best_match = target_map[target]

    return (best_match, best_ratio) if best_match else (None, 0)


def _get_ocr_result(ocr_results: Dict[str, Dict], stem: str) -> Optional[Dict]:
    key = f'{stem}.pdf'
    if key in ocr_results:
        return ocr_results[key]
    bare = stem.replace('_ultra_result', '')
    if bare in ocr_results:
        return ocr_results[bare]
    if f'{bare}.pdf' in ocr_results:
        return ocr_results[f'{bare}.pdf']
    return None


def inspect_pdf_page_count(pdf_path: Path) -> int:
    with open_pdf_reader(pdf_path) as reader:
        return len(reader.pages)


def get_non_litigation_input_root(project_root: Path) -> Path:
    return project_root / 'input' / NON_LITIGATION_INPUT_DIRNAME


def get_non_litigation_result_root(project_root: Path) -> Path:
    return USER_DATA_DIR / 'output' / NON_LITIGATION_RESULT_DIRNAME


def get_non_litigation_temp_root(project_root: Path) -> Path:
    return USER_DATA_DIR / 'temp' / NON_LITIGATION_TEMP_DIRNAME


def ensure_non_litigation_input_structure(project_root: Path) -> Path:
    input_root = get_non_litigation_input_root(project_root)
    input_root.mkdir(parents=True, exist_ok=True)
    for item in input_root.parent.iterdir():
        if item.is_file() and item.suffix.lower() == '.pdf' and not (input_root / item.name).exists():
            shutil.move(str(item), str(input_root / item.name))
    return input_root


def get_notice_input_dirs(input_dir: Path) -> List[Path]:
    candidate_dirs = [input_dir]
    for subdir_name in ['责催（证据材料）', 'notice-evidence']:
        nested_dir = input_dir / subdir_name
        if nested_dir.exists() and nested_dir.is_dir():
            candidate_dirs.append(nested_dir)
    return candidate_dirs


def iter_notice_pdf_paths(input_dir: Path) -> Iterable[Path]:
    seen: set[str] = set()
    for notice_dir in get_notice_input_dirs(input_dir):
        for pdf_path in sorted(notice_dir.glob('*.pdf')):
            if pdf_path.name in SOURCE_MAPPING.values() or pdf_path.name in seen:
                continue
            seen.add(pdf_path.name)
            yield pdf_path


def normalize_company_name_for_matching(value: str) -> str:
    text = str(value).strip()
    text = text.replace('\n', '').replace('\r', '').replace(' ', '')
    text = text.replace('（', '(').replace('）', ')')
    return text


def detect_page_ranges(total_pages: int, expected_count: int, doc_type: str) -> List[Tuple[int, int]]:
    pages_per_item = PAGES_PER_CASE.get(doc_type, 1)
    expected_pages = expected_count * pages_per_item

    if total_pages != expected_pages:
        _log(
            f'  [INFO] {doc_type}: 实际 {total_pages} 页，台账期望 {expected_pages} 页 '
            f'({expected_count} 个 × {pages_per_item} 页)，按实际页数处理'
        )

    actual_count = min(expected_count, total_pages // pages_per_item) if total_pages > 0 else 0
    ranges = []
    for i in range(actual_count):
        start = i * pages_per_item
        end = start + pages_per_item
        ranges.append((start, end))
    return ranges


def detect_application_page_ranges_by_ocr(ocr_results: Dict[str, Dict], total_pages: int, expected_cases: int) -> List[Tuple[int, int]]:
    """
    通过 OCR 识别"强制执行申请书"标题来定位页边界。
    如果 OCR 结果不可用或检测到的边界数不匹配，fallback 到固定页数。
    """
    data = _get_ocr_result(ocr_results, '申请书')
    if not data or not data.get('pages'):
        _log(f"  [WARN] 无申请书 OCR 缓存，使用固定 {PAGES_PER_CASE['申请书']} 页/案件")
        return detect_page_ranges(total_pages, expected_cases, '申请书')

    boundary_pages = []
    for page_data in data['pages']:
        text = page_data.get('text', '')
        page_num = page_data.get('page', 0)
        for keyword in APPLICATION_BOUNDARY_KEYWORDS:
            if keyword in text:
                boundary_pages.append(page_num - 1)
                break

    if len(boundary_pages) == expected_cases:
        ranges = []
        for i, start in enumerate(boundary_pages):
            end = boundary_pages[i + 1] if i + 1 < len(boundary_pages) else total_pages
            ranges.append((start, end))
        _log(f"  [OK] OCR 检测到 {len(boundary_pages)} 个申请书边界")
        return ranges

    if boundary_pages:
        _log(f"  [INFO] OCR 检测到 {len(boundary_pages)} 个边界，台账期望 {expected_cases} 个，按实际处理")
    else:
        _log(f"  [INFO] OCR 未检测到申请书边界，使用固定 {PAGES_PER_CASE['申请书']} 页/案件")

    return detect_page_ranges(total_pages, expected_cases, '申请书')


def discover_notice_files(input_dir: Path) -> List[str]:
    """
    动态发现输入目录中的责催 PDF 文件。
    按文件名自然排序（1.pdf, 2.pdf, ..., 10.pdf, ...）
    """
    def natural_sort_key(name: str) -> List:
        parts = []
        for part in re.split(r'(\d+)', name):
            if part.isdigit():
                parts.append(int(part))
            else:
                parts.append(part)
        return parts

    pdf_files = sorted(
        [pdf_path.name for pdf_path in iter_notice_pdf_paths(input_dir)],
        key=natural_sort_key,
    )
    return pdf_files


def detect_notice_source_mapping_from_ocr(ocr_results: Dict[str, Dict], notice_files: List[str]) -> Dict[str, str]:
    """
    从 OCR 结果中识别责催文件的责令号

    Returns:
        {source_filename: detected_notice_number}
    """
    mapping: Dict[str, str] = {}
    post_processor = TextPostProcessor()
    for source_name in notice_files:
        stem = source_name.replace('.pdf', '')
        data = _get_ocr_result(ocr_results, stem)

        if not data:
            continue

        candidate_pages = []
        for page in data['pages']:
            text = page.get('text', '').replace('\n', ' ')
            candidate = _score_notice_candidate(page.get('page', 0), text, post_processor)
            if candidate.get('decision_numbers'):
                candidate_pages.append(candidate)

        selection = _select_notice_candidate(candidate_pages)
        selected_notice = selection.get('selected_notice') or data.get('selected_notice')
        selected_page = selection.get('selected_page') or data.get('selected_page')

        if selected_notice:
            mapping[source_name] = selected_notice
            _log(f"  [OK] {source_name}: 识别到责令号 '{selected_notice}'")
            if selected_page:
                _log(f"    [INFO] 采用第 {selected_page} 页候选")
        else:
            _log(f"  [WARN] {source_name}: 未识别到责令号")

    return mapping


def build_mock_ocr_results(sample_root: Path, input_dir: Path | None = None) -> Dict[str, Dict]:
    """构建 Mock OCR 结果（用于测试）"""
    standard_root = sample_root / _cfg.standard_output_dirname
    ocr_results: Dict[str, Dict] = {}

    ocr_noise_samples = _cfg.mock_noise_samples

    def get_subdir(doc_type: str) -> str:
        return _cfg.standard_output_subdirs.get(doc_type, _cfg.directory_mapping.get(doc_type, doc_type))

    application_pages = []
    for index, pdf_path in enumerate(sorted((standard_root / get_subdir('申请书')).glob('*.pdf'))):
        page_count = inspect_pdf_page_count(pdf_path)
        for page_offset in range(page_count):
            page_number = len(application_pages) + 1
            if page_offset == 0:
                noise_idx = index % len(ocr_noise_samples)
                text = f'强制执行申请书\n名称：案子{index + 1}\n穗公积金中心{ocr_noise_samples[noise_idx]}越秀责字'
            else:
                text = f'被执行人：公司{index + 1}\n金额：10000元'
            application_pages.append({'page': page_number, 'text': text})
    ocr_results['申请书.pdf'] = {'pages': application_pages, 'total_pages': len(application_pages), 'filename': '申请书.pdf'}

    for doc_type_key in ['授权书', '所函']:
        marker = _cfg.doc_type_map[doc_type_key].content_marker
        folder = get_subdir(doc_type_key)
        pages = []
        for index, pdf_path in enumerate(sorted((standard_root / folder).glob('*.pdf'))):
            company_name = pdf_path.stem
            noise_idx = index % len(ocr_noise_samples)
            text = f'{marker}\n{ocr_noise_samples[noise_idx]}\n{company_name}'
            pages.append({'page': index + 1, 'text': text})
        ocr_results[f'{doc_type_key}.pdf'] = {'pages': pages, 'total_pages': len(pages), 'filename': f'{doc_type_key}.pdf'}

    notice_files = sorted((standard_root / get_subdir('责催')).glob('*.pdf'))

    if input_dir and input_dir.exists():
        std_page_map: Dict[Path, int] = {}
        std_used: Dict[int, Path] = {}
        for pdf_path in notice_files:
            pc = inspect_pdf_page_count(pdf_path)
            std_page_map[pdf_path] = pc

        src_files = discover_notice_files(input_dir)
        for src_name in src_files:
            src_path = input_dir / src_name
            if not src_path.exists():
                continue
            src_pages = inspect_pdf_page_count(src_path)
            matched_std = None
            for std_path, std_pages in std_page_map.items():
                if std_pages == src_pages and std_pages not in std_used:
                    matched_std = std_path
                    std_used[std_pages] = std_path
                    break

            if matched_std:
                stem_name = matched_std.stem
                if '-责催-' in stem_name:
                    notice_number = stem_name.split('-责催-')[1]
                    normalized_number = normalize_notice_number(notice_number)
                    ocr_results[src_name] = {
                        'pages': [{'page': 1, 'text': normalized_number}],
                        'total_pages': 1,
                        'filename': src_name,
                    }
            else:
                _log(f"  [WARN] Mock: 无法按页数匹配 {src_name}，使用顺序匹配")
                fallback_idx = src_files.index(src_name)
                if fallback_idx < len(notice_files):
                    notice_number = notice_files[fallback_idx].stem.split('-责催-')[1]
                    normalized_number = normalize_notice_number(notice_number)
                    ocr_results[src_name] = {
                        'pages': [{'page': 1, 'text': normalized_number}],
                        'total_pages': 1,
                        'filename': src_name,
                    }
    else:
        notice_numbers = [pdf_path.stem.split('-责催-')[1] for pdf_path in notice_files]
        for idx, notice_number in enumerate(notice_numbers):
            normalized_number = normalize_notice_number(notice_number)
            src_name = f'{idx + 1}.pdf'
            ocr_results[src_name] = {
                'pages': [{'page': 1, 'text': normalized_number}],
                'total_pages': 1,
                'filename': src_name,
            }

    return ocr_results


def run_real_ocr_on_pdf(pdf_path: Path, use_mock: bool = False,
                        is_notice: bool = False, stop_pattern: Optional[re.Pattern] = None,
                        doc_type: Optional[str] = None, ocr: Optional["UltraFastOCR"] = None,
                        region_extractor: Optional[RegionExtractor] = None,
                        post_processor: Optional[TextPostProcessor] = None,
                        quiet: bool = False,
                        page_progress: Optional[callable] = None,
                        cancel_check: Optional[callable] = None) -> Dict:
    if use_mock or not HAS_OCR:
        return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'mock'}

    _log(f"  [OCR] 开始识别: {pdf_path.name}")

    try:
        if ocr is None or region_extractor is None:
            shared_ocr, shared_region_extractor = _build_ocr_processors()
            ocr = ocr or shared_ocr
            region_extractor = region_extractor or shared_region_extractor

        if is_notice and stop_pattern:
            _log(f"  [OCR] 使用逐页识别模式（短窗口扫描后停止）")
            notice_post_processor = post_processor or TextPostProcessor()

            doc_ocr = _cfg.get_doc_ocr(doc_type or '责催')
            if doc_ocr.enable_region_first:
                pages = []
                total_start = time.perf_counter()
                page_num = 1
                stopped_early = False
                candidate_pages = []
                first_hit_page = None
                stop_after_page = None
                max_scan_pages = max(1, doc_ocr.scan_max_pages)
                scan_window_pages = max(0, doc_ocr.scan_window_pages)

                while page_num <= max_scan_pages:
                    if cancel_check and cancel_check():
                        break
                    try:
                        full_image = region_extractor.extract_full_page(pdf_path, page_num)
                    except Exception:
                        break

                    if doc_ocr.skip_blank_pages:
                        if ImagePreprocessor.is_blank_page(full_image, threshold=doc_ocr.blank_page_threshold):
                            pages.append({
                                'page': page_num,
                                'text': '',
                                'method': 'blank_page_skipped',
                                'duration': 0,
                                'region_attempts': [],
                                'region_stats': {'attempt_count': 0, 'total_duration': 0, 'max_text_length': 0, 'total_text_length': 0, 'regions': []},
                                'region_text_length': 0,
                                'fallback_used': False,
                                'fallback_trigger_reason': None,
                                'notice_matched': False,
                                'notice_candidates': [],
                                'notice_candidate_score': None,
                                'notice_page_profile': {},
                            })
                            page_num += 1
                            continue

                    page_logs = []
                    region_text = ''
                    if doc_type:
                        region_text, page_logs = _collect_region_texts(
                            ocr,
                            region_extractor,
                            pdf_path,
                            page_num,
                            doc_type,
                            full_image=full_image,
                        )
                    region_text = apply_ocr_corrections(region_text, doc_type=doc_type)

                    duration = sum(item['duration'] for item in page_logs)
                    text = region_text
                    method = 'region_first'
                    page_candidate = _score_notice_candidate(page_num, text, notice_post_processor) if text else None
                    matched = bool(page_candidate and page_candidate.get('decision_numbers'))
                    needs_fallback, fallback_trigger_reason = _should_fallback_notice(region_text, page_candidate, min_text_length=doc_ocr.region_fallback_min_text_length)

                    if needs_fallback and doc_ocr.allow_full_page_fallback:
                        full_result = ocr.recognize_full_page_image(
                            full_image,
                            page_num=page_num,
                            method='full_page_fallback',
                            optimize_output=True,
                        )
                        full_text = apply_ocr_corrections(full_result.text, doc_type=doc_type)
                        duration += full_result.duration
                        if full_text:
                            text = full_text
                            method = full_result.method
                            page_candidate = _score_notice_candidate(page_num, text, notice_post_processor)
                            matched = bool(page_candidate.get('decision_numbers'))

                    if matched and page_candidate:
                        candidate_pages.append(page_candidate)
                        pages.append({
                            'page': page_num,
                            'text': text,
                            'method': method,
                            'duration': duration,
                            'region_attempts': page_logs,
                            'region_stats': _build_region_stats(page_logs),
                            'region_text_length': len(_compact_text(region_text)),
                            'fallback_used': method == 'full_page_fallback',
                            'fallback_trigger_reason': fallback_trigger_reason if method == 'full_page_fallback' else None,
                            'notice_matched': matched,
                            'notice_candidates': page_candidate.get('decision_numbers', []) if page_candidate else [],
                        })
                        _log(f"    [OK] 第 {page_num} 页找到责令号，立即停止")
                        stopped_early = True
                        break

                    pages.append({
                        'page': page_num,
                        'text': text,
                        'method': method,
                        'duration': duration,
                        'region_attempts': page_logs,
                        'region_stats': _build_region_stats(page_logs),
                        'region_text_length': len(_compact_text(region_text)),
                        'fallback_used': method == 'full_page_fallback',
                        'fallback_trigger_reason': fallback_trigger_reason if method == 'full_page_fallback' else None,
                        'notice_matched': matched,
                        'notice_candidates': page_candidate.get('decision_numbers', []) if page_candidate else [],
                    })

                    page_num += 1

                total_duration = time.perf_counter() - total_start
                selection = _select_notice_candidate(candidate_pages)
                result = {
                    'filename': pdf_path.name,
                    'filepath': str(pdf_path),
                    'total_pages': len(pages),
                    'method': 'region_first_sequential',
                    'total_duration': total_duration,
                    'pages': pages,
                    'full_text': "\n\n".join([f"=== 第{p['page']}页 ===\n{p['text']}" for p in pages if p['text']]),
                    'stopped_early': stopped_early,
                    'selected_notice': selection.get('selected_notice'),
                    'selected_page': selection.get('selected_page'),
                    'selected_root_notice': selection.get('selected_root_notice'),
                    'candidate_notices': selection.get('candidate_notices', []),
                    'performance_summary': _build_ocr_output_summary(pdf_path, pages, total_duration, doc_type=doc_type),
                }
            else:
                result = ocr.process_pdf_pages_sequential(
                    str(pdf_path),
                    stop_condition=lambda page_num, text: bool(stop_pattern.search(apply_ocr_corrections(text, doc_type='责催'))),
                    max_pages=max(1, _cfg.notice_scan_max_pages),
                )
        elif doc_type in {'申请书', '授权书', '所函'} and _cfg.ocr_enable_region_first:
            total_pages = inspect_pdf_page_count(pdf_path)
            pages = []
            total_start = time.perf_counter()
            fallback_used = False
            application_region_results = []

            def _is_application_boundary(text: str) -> bool:
                return any(keyword in text for keyword in APPLICATION_BOUNDARY_KEYWORDS)

            def _has_title_fragments(compact: str, fragments: List[str], *, min_hits: int) -> bool:
                return sum(1 for fragment in fragments if fragment in compact) >= min_hits

            def _check_region_usable(doc_type_key: str, logs: List[Dict], combined_text: str) -> bool:
                dt = _cfg.doc_type_map.get(doc_type_key)
                if not dt or not dt.ocr.usability_check:
                    return len(combined_text.replace('\n', '').replace(' ', '')) >= 6
                uc = dt.ocr.usability_check
                compact = combined_text.replace('\n', '').replace(' ', '')
                for kw in uc.keywords:
                    if kw in compact:
                        return True
                if uc.fragment_keywords and _has_title_fragments(compact, uc.fragment_keywords, min_hits=uc.min_fragment_hits):
                    return True
                if logs and logs[0].get('text_length', 0) >= uc.min_text_length:
                    return True
                return len(compact) >= uc.min_text_length

            if doc_type == '申请书':
                pages_per = PAGES_PER_CASE['申请书']
                expected_cases = max(1, total_pages // pages_per)
                _log(f"  [申请书] {total_pages} pages, {pages_per} pages/case, {expected_cases} cases expected")

                all_page_nums_app = list(range(1, min(total_pages, expected_cases * pages_per) + 1))
                pf_queue_app: queue.Queue = queue.Queue(maxsize=4)
                pf_thread_app = threading.Thread(
                    target=_prefetch_pages,
                    args=(region_extractor, pdf_path, all_page_nums_app, pf_queue_app, cancel_check),
                    daemon=True,
                )
                pf_thread_app.start()
                prefetched_app: Dict[int, Any] = {}

                for case_idx in range(expected_cases):
                    if cancel_check and cancel_check():
                        _log(f"  [申请书] 已取消，已完成 {case_idx}/{expected_cases}")
                        break
                    start_page = 1 + case_idx * pages_per
                    if page_progress and case_idx % 10 == 0:
                        page_progress(start_page, total_pages)
                    for offset in range(pages_per):
                        page_num = start_page + offset
                        if page_num > total_pages:
                            break
                        if any(p['page'] == page_num for p in pages):
                            continue
                        if page_num not in prefetched_app:
                            item = _get_prefetched(pf_queue_app)
                            if item is not None:
                                pn, img_or_err = item
                                if not isinstance(img_or_err, Exception):
                                    prefetched_app[pn] = img_or_err
                        full_image = prefetched_app.pop(page_num, None)
                        if full_image is None:
                            full_image = region_extractor.extract_full_page(pdf_path, page_num)
                        is_group_start = (offset == 0)
                        if is_group_start:
                            region_text, page_logs = _collect_region_texts(
                                ocr,
                                region_extractor,
                                pdf_path,
                                page_num,
                                doc_type,
                                full_image=full_image,
                            )
                        else:
                            qs_cfg = _cfg.get_doc_ocr(doc_type).quick_scan if _cfg.get_doc_ocr(doc_type) else None
                            qs_size = tuple(qs_cfg.target_size) if qs_cfg and qs_cfg.enabled else (400, 400)
                            img = ImagePreprocessor.optimize_for_ocr(full_image, target_size=qs_size)
                            result = ocr.recognize_image_region(img, page_num, method='quick_scan', optimize_output=False)
                            region_text = result.text
                            page_logs = [{'region': 'quick_scan', 'text_length': len(region_text), 'duration': result.duration}]
                        corrected_text = apply_ocr_corrections(region_text, doc_type=doc_type)
                        duration = sum(item['duration'] for item in page_logs)
                        boundary = _is_application_boundary(corrected_text) if is_group_start else False
                        application_region_results.append({
                            'page_num': page_num,
                            'full_image': full_image,
                            'page_logs': page_logs,
                            'text': corrected_text,
                            'duration': duration,
                            'boundary': boundary,
                        })

                pf_thread_app.join(timeout=30)

                detected_boundaries = [item['page_num'] for item in application_region_results if item['boundary']]
                expected_boundaries = max(1, total_pages // PAGES_PER_CASE['申请书'])

                boundary_page_set = set(detected_boundaries)
                expected_start_pages = {
                    1 + index * PAGES_PER_CASE['申请书'] for index in range(expected_boundaries)
                }

                for item in application_region_results:
                    page_num = item['page_num']
                    text = item['text']
                    page_logs = item['page_logs']
                    duration = item['duration']
                    method = 'region_first'
                    doc_ocr_app = _cfg.get_doc_ocr(doc_type)
                    needs_fallback, fallback_trigger_reason = _should_fallback_application(
                        page_num,
                        text,
                        detected_boundaries,
                        expected_boundaries,
                        expected_start_pages,
                        min_text_length=doc_ocr_app.region_fallback_min_text_length if doc_ocr_app else None,
                    )

                    if needs_fallback and doc_ocr_app and doc_ocr_app.allow_full_page_fallback:
                        fallback_used = True
                        full_result = ocr.recognize_full_page_image(
                            item['full_image'],
                            page_num=page_num,
                            method='full_page_fallback',
                            optimize_output=True,
                        )
                        fallback_text = apply_ocr_corrections(full_result.text, doc_type=doc_type)
                        duration += full_result.duration
                        if fallback_text:
                            text = fallback_text
                            method = full_result.method

                    pages.append({
                        'page': page_num,
                        'text': text,
                        'method': method,
                        'duration': duration,
                        'region_attempts': page_logs,
                        'region_stats': _build_region_stats(page_logs),
                        'region_text_length': len(_compact_text(item['text'])),
                        'fallback_used': method == 'full_page_fallback',
                        'fallback_trigger_reason': fallback_trigger_reason if method == 'full_page_fallback' else None,
                        'boundary_detected': item['boundary'] or _is_application_boundary(text),
                    })
            else:
                doc_cfg = _cfg.doc_type_map[doc_type]
                default_regions = _cfg.ocr_doc_regions.get(doc_type, [])

                all_page_nums = list(range(1, total_pages + 1))
                pf_queue: queue.Queue = queue.Queue(maxsize=2)
                pf_thread = threading.Thread(
                    target=_prefetch_pages,
                    args=(region_extractor, pdf_path, all_page_nums, pf_queue, cancel_check),
                    daemon=True,
                )
                pf_thread.start()

                while True:
                    prefetched = _get_prefetched(pf_queue)
                    if prefetched is None:
                        break
                    page_num, full_image = prefetched
                    if isinstance(full_image, Exception):
                        _log(f"    [{doc_type}] 第{page_num}页提取失败: {full_image}", level="ERROR")
                        continue
                    if cancel_check and cancel_check():
                        _log(f"    [{doc_type}] 已取消")
                        break
                    if page_num % 50 == 1 or page_num == total_pages:
                        _log(f"    [{doc_type}] {page_num}/{total_pages}...")
                    if page_progress and (page_num % 20 == 0 or page_num == total_pages):
                        page_progress(page_num, total_pages)
                    primary_text, primary_logs = _collect_region_texts(
                        ocr,
                        region_extractor,
                        pdf_path,
                        page_num,
                        doc_type,
                        full_image=full_image,
                        region_names=default_regions,
                    )
                    page_logs = list(primary_logs)
                    combined_text = apply_ocr_corrections(primary_text, doc_type=doc_type)

                    if doc_type:
                        region_usable = _check_region_usable(doc_type, page_logs, combined_text)
                    else:
                        region_usable = len(combined_text.replace('\n', '').replace(' ', '')) >= 6

                    text = combined_text
                    method = 'region_first'
                    duration = sum(item['duration'] for item in page_logs)
                    marker_detected = bool(doc_cfg.content_marker and doc_cfg.content_marker in combined_text)

                    pages.append({
                        'page': page_num,
                        'text': text,
                        'method': method,
                        'duration': duration,
                        'region_attempts': page_logs,
                        'region_stats': _build_region_stats(page_logs),
                        'region_text_length': len(_compact_text(combined_text)),
                        'fallback_used': False,
                        'fallback_trigger_reason': None,
                        'marker_detected': marker_detected,
                        'region_usable': region_usable,
                    })

                pf_thread.join(timeout=30)

            total_duration = time.perf_counter() - total_start
            result = {
                'filename': pdf_path.name,
                'filepath': str(pdf_path),
                'total_pages': len(pages),
                'method': 'region_first' if not fallback_used else 'region_first_with_fallback',
                'total_duration': total_duration,
                'pages': pages,
                'full_text': "\n\n".join([f"=== 第{p['page']}页 ===\n{p['text']}" for p in pages if p['text']]),
                'performance_summary': _build_ocr_output_summary(pdf_path, pages, total_duration, doc_type=doc_type),
            }
        else:
            result = ocr.process_pdf(str(pdf_path), force_ocr=False)

        if result is None:
            _log(f"  [ERROR] OCR 识别失败: {pdf_path.name}")
            return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'error'}

        post_processor = post_processor or TextPostProcessor()
        processed_pages = []

        for page_data in result['pages']:
            text = page_data.get('text', '')
            text = apply_ocr_corrections(text, doc_type=doc_type)
            processed = post_processor.process(text)

            processed_pages.append({
                'page': page_data['page'],
                'text': processed['processed'],
                'original_text': text,
                'method': page_data.get('method', 'unknown'),
                'duration': page_data.get('duration', 0),
                'region_attempts': page_data.get('region_attempts', []),
                'region_stats': page_data.get('region_stats', _build_region_stats(page_data.get('region_attempts', []))),
                'region_text_length': page_data.get('region_text_length', 0),
                'fallback_used': page_data.get('fallback_used', False),
                'fallback_trigger_reason': page_data.get('fallback_trigger_reason'),
                'notice_matched': page_data.get('notice_matched', False),
                'boundary_detected': page_data.get('boundary_detected', False),
                'marker_detected': page_data.get('marker_detected', False),
                'region_usable': page_data.get('region_usable', False),
            })

        output = {
            'pages': processed_pages,
            'total_pages': result['total_pages'],
            'filename': result['filename'],
            'method': result['method'],
            'total_duration': result['total_duration'],
            'fallback_pages': sum(1 for page in processed_pages if page.get('fallback_used')),
            'region_pages': sum(1 for page in processed_pages if page.get('method') == 'region_first'),
            'optimization_strategy': result.get('method', 'unknown'),
            'stopped_early': result.get('stopped_early', False),
            'selected_notice': result.get('selected_notice'),
            'selected_page': result.get('selected_page'),
            'selected_root_notice': result.get('selected_root_notice'),
            'candidate_notices': result.get('candidate_notices', []),
            'performance_summary': result.get('performance_summary') or _build_ocr_output_summary(pdf_path, processed_pages, result.get('total_duration', 0), doc_type=doc_type),
        }

        perf = output.get('performance_summary', {})
        slowest_page = perf.get('slowest_page') or {}
        _log(
            f"  [OCR] 完成: {pdf_path.name} ({result['total_duration']:.2f}s, "
            f"fallback {output['fallback_pages']}/{output['total_pages']}, "
            f"最慢页 P{slowest_page.get('page', '-')} {slowest_page.get('duration', 0):.2f}s)"
        )
        return output

    except Exception as e:
        _log(f"  [ERROR] OCR 处理异常: {pdf_path.name} - {e}")
        return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'error', 'error': str(e)}


def _run_ocr_with_timeout(pdf_path: Path, **kwargs) -> Dict:
    timeout = kwargs.pop('timeout', None)
    page_progress = kwargs.pop('page_progress', None)
    cancel_check = kwargs.get('cancel_check')
    kwargs['page_progress'] = page_progress
    if timeout is None:
        total_pages = inspect_pdf_page_count(pdf_path) if pdf_path.exists() else 1
        timeout = max(_PDF_TIMEOUT_SECONDS, total_pages * 5)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_real_ocr_on_pdf, pdf_path, **kwargs)
        try:
            elapsed = 0
            step = 2
            while elapsed < timeout:
                try:
                    return future.result(timeout=step)
                except FuturesTimeoutError:
                    elapsed += step
                    if cancel_check and cancel_check():
                        _log(f"  [CANCEL] {pdf_path.name} 已取消，等待 OCR 退出...")
                        try:
                            return future.result(timeout=30)
                        except FuturesTimeoutError:
                            _log(f"  [CANCEL] {pdf_path.name} OCR 未在 30s 内退出，强制跳过")
                            return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'cancelled'}
            _log(f"  [TIMEOUT] {pdf_path.name} 处理超时 ({timeout}s)，跳过")
            return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'timeout'}
        except Exception as e:
            _log(f"  [ERROR] {pdf_path.name}: {e}")
            return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'error'}


# ---------------------------------------------------------------------------
# 流式批次处理器集成
# ---------------------------------------------------------------------------

_STREAMING_THRESHOLD = 50


def _should_use_streaming(total_tasks: int, actual_task_count: int = 0) -> bool:
    """流式路径缺少图片预处理、全页回退、责令号候选选择、空白页跳过等关键逻辑，
    识别准确率远低于串行路径。暂时禁用，后续补齐功能后再启用。"""
    return False


def _build_tasks_from_cases(input_dir: Path, cases: List[Dict]) -> List["Task"]:
    """从台账 cases 生成 Task 列表，供 StreamingBatchProcessor 消费。"""
    tasks: List["Task"] = []

    # 源 PDF 路径映射
    app_pdf = input_dir / _cfg.source_mapping.get('输出文件（申请书）', '申请书.pdf')
    auth_pdf = input_dir / _cfg.source_mapping.get('输出文件（授权书）', '授权书.pdf')
    letter_pdf = input_dir / _cfg.source_mapping.get('输出文件（所函）', '所函.pdf')

    # 授权书：作为一个整体 task（每页对应一个 case，OCR 后按页拆）
    if auth_pdf.exists():
        tasks.append(Task(
            task_id="auth_all",
            task_type='auth_all',
            source_file=str(auth_pdf),
            page_start=1,
            page_end=0,
            company_name=None,
            notice_number=None,
            sequence=None,
        ))

    # 所函：作为一个整体 task
    if letter_pdf.exists():
        tasks.append(Task(
            task_id="letter_all",
            task_type='letter_all',
            source_file=str(letter_pdf),
            page_start=1,
            page_end=0,
            company_name=None,
            notice_number=None,
            sequence=None,
        ))

    # 申请书：作为一个整体 task
    if app_pdf.exists():
        tasks.append(Task(
            task_id="application",
            task_type='application',
            source_file=str(app_pdf),
            page_start=1,
            page_end=0,
            company_name=None,
            notice_number=None,
            sequence=None,
        ))

    # 责催：每个存在的 notice PDF 对应一个 task
    notice_path_map = {path.name: path for path in iter_notice_pdf_paths(input_dir)}
    for name, path in notice_path_map.items():
        tasks.append(Task(
            task_id=f"notice_{name}",
            task_type='notice',
            source_file=str(path),
            page_start=1,
            page_end=1,
            company_name=None,
            notice_number=None,
            sequence=None,
        ))

    return tasks


def _streaming_db_fingerprint(input_dir: Path) -> str:
    """确定性指纹：基于输入目录路径 + 已有 PDF 文件名列表。"""
    import hashlib
    pdf_files = sorted(p.name for p in input_dir.glob('*.pdf') if p.is_file())
    raw = str(input_dir) + '\n' + '\n'.join(pdf_files)
    return hashlib.md5(raw.encode('utf-8')).hexdigest()[:12]


def _run_streaming_ocr(input_dir: Path, cases: List[Dict],
                       progress_callback: Optional[callable],
                       cancel_check: Optional[callable],
                       force: bool = False,
                       log_callback: Optional[callable] = None) -> Dict[str, Dict]:
    """流式 OCR 入口：构建任务 → 流式批次处理 → 聚合结果。"""
    if not HAS_STREAMING or TaskStateManager is None or StreamingBatchProcessor is None:
        _log("[WARN] 流式处理器未导入，回退到串行逻辑")
        return {}

    tasks = _build_tasks_from_cases(input_dir, cases)
    if not tasks:
        _log("[WARN] 无可用任务，流式处理器返回空结果")
        return {}

    fingerprint = _streaming_db_fingerprint(input_dir)
    db_path = USER_DATA_DIR / 'temp' / f'streaming_{fingerprint}.db'
    state_mgr = TaskStateManager(db_path)

    saved_fp = state_mgr.get_meta('input_fingerprint')
    if saved_fp and saved_fp != fingerprint:
        _log("输入文件已变化，清除旧缓存")
        state_mgr.clear_all()

    existing = state_mgr.get_summary()

    if existing['progress'] >= 1.0 and saved_fp == fingerprint and not force:
        _log(f"OCR 已完成（{existing['done']}/{existing['total']}），直接返回缓存结果")
        results = state_mgr.get_all_results()
        state_mgr.close()
        return results

    if force or existing['total'] == 0:
        state_mgr.clear_all()
        state_mgr.insert_tasks(tasks)
    else:
        _log(f"断点续跑: 已完成 {existing['done']}/{existing['total']}, 继续处理...")
        state_mgr.insert_tasks(tasks)

    state_mgr.set_meta('input_fingerprint', fingerprint)

    from non_litigation.streaming import set_log_fn as _set_streaming_log
    def _streaming_log(msg: str):
        if log_callback:
            try:
                log_callback("info", msg)
            except Exception:
                pass
        _log(msg)
    _set_streaming_log(_streaming_log)

    processor = StreamingBatchProcessor(state_mgr, batch_size=50, max_workers=1)
    processor.initialize()

    # 包装进度回调（summary dict -> 原有签名）
    def _streaming_progress(summary: Dict):
        if progress_callback:
            done = summary.get('done', 0)
            total = summary.get('total', 0)
            try:
                progress_callback(done, total, 'streaming_batch')
            except Exception:
                pass

    processor.run(progress_callback=_streaming_progress, cancel_check=cancel_check)

    # 聚合为 {filename: ocr_result} 格式，兼容现有调用方
    ocr_results = state_mgr.get_all_results()

    # 清理
    state_mgr.close()

    return ocr_results


def run_real_ocr(input_dir: Path, use_mock: bool = False,
                 progress_callback: Optional[callable] = None,
                 cancel_check: Optional[callable] = None,
                 log_callback: Optional[callable] = None,
                 cached_results: Optional[Dict[str, Dict]] = None,
                 force: bool = False,
                 result_callback: Optional[callable] = None) -> Dict[str, Dict]:
    ocr_start = time.perf_counter()
    ocr_results: Dict[str, Dict] = dict(cached_results) if cached_results else {}
    skipped_count = 0

    def _on_result(filename: str, result: Dict):
        if result_callback:
            try:
                result_callback(filename, result, ocr_results)
            except Exception:
                pass

    def _report(msg: str):
        _log(msg)
        if log_callback:
            log_callback("info", msg)

    _report(f"OCR 引擎状态: HAS_OCR={HAS_OCR}, use_mock={use_mock}")

    # ---------- 自动流式切换判断 ----------
    total_tasks = 0
    cases: List[Dict] = []
    try:
        # 尝试从 input_dir 的父目录加载台账（常规目录结构）
        sample_root = input_dir.parent
        cases = load_non_litigation_cases(sample_root)
        # 每个 case 约产生 2 个细粒度任务(auth/letter) + 1 个 application + notice
        total_tasks = len(cases) * 2 + 1 + len(discover_notice_files(input_dir))
    except Exception:
        # 加载失败时回退到文件数统计
        notice_files = discover_notice_files(input_dir)
        other_files_expected = [
            (pdf_name, pdf_name.replace('.pdf', ''))
            for pdf_name in _cfg.source_mapping.values()
        ]
        other_existing = [(name, stem) for name, stem in other_files_expected if (input_dir / name).exists()]
        total_tasks = len(notice_files) + len(other_existing)
        cases = []

    if cases and _should_use_streaming(total_tasks, len(_build_tasks_from_cases(input_dir, cases))) and not use_mock and HAS_OCR and HAS_STREAMING:
        _report(f"总任务数 {total_tasks} >= {_STREAMING_THRESHOLD}，启用流式批次处理器")
        streaming_results = _run_streaming_ocr(input_dir, cases, progress_callback, cancel_check, force, log_callback)
        if cached_results:
            merged = dict(cached_results)
            merged.update(streaming_results)
            ocr_results = merged
        else:
            ocr_results = streaming_results
        total_duration = round(time.perf_counter() - ocr_start, 4)
        _report(f"OCR 阶段完成(流式): {total_duration:.2f}s, 共处理 {len(ocr_results)} 个文件")
        return ocr_results
    # -------------------------------------

    notice_files = discover_notice_files(input_dir)
    notice_path_map = {path.name: path for path in iter_notice_pdf_paths(input_dir)}

    other_files_expected = [
        (pdf_name, pdf_name.replace('.pdf', ''))
        for pdf_name in _cfg.source_mapping.values()
    ]
    other_existing = [(name, stem) for name, stem in other_files_expected if (input_dir / name).exists()]

    total_found = len(notice_files) + len(other_existing)
    _report(f"文件发现: 责催 {len(notice_files)} 个, 其他 {len(other_existing)} 个, 合计 {total_found} 个")

    _global_done = [0]
    _global_total = total_found

    def _progress_update(filename: str):
        _global_done[0] += 1
        if progress_callback:
            progress_callback(_global_done[0], _global_total, filename)

    shared_ocr = None
    shared_region_extractor = None
    shared_post_processor = None

    notice_items = []
    for source_name in notice_files:
        pdf_path = notice_path_map.get(source_name, input_dir / source_name)
        if pdf_path.exists():
            notice_items.append((source_name, pdf_path))
        else:
            _report(f"  [WARN] 文件不存在: {pdf_path}")

    if notice_items and not use_mock and HAS_OCR:
        notice_count = len(notice_items)
        _report(f"处理责催文件（逐页识别，找到即停）... 共 {notice_count} 个")

        shared_ocr, shared_region_extractor = _build_ocr_processors()
        shared_post_processor = TextPostProcessor()
        notice_start = time.perf_counter()
        for idx, (source_name, pdf_path) in enumerate(notice_items, 1):
            if cancel_check and cancel_check():
                _report(f"责催已取消，已完成 {idx-1}/{notice_count}")
                break
            if source_name in ocr_results:
                skipped_count += 1
                _progress_update(source_name)
                continue
            t0 = time.perf_counter()
            result = _run_ocr_with_timeout(
                pdf_path,
                use_mock=use_mock,
                is_notice=True,
                stop_pattern=NOTICE_PATTERN,
                doc_type='责催',
                ocr=shared_ocr,
                region_extractor=shared_region_extractor,
                post_processor=shared_post_processor,
                cancel_check=cancel_check,
            )
            file_dur = time.perf_counter() - t0
            ocr_results[source_name] = result
            _on_result(source_name, result)
            _report(f"[{idx}/{notice_count}] {source_name} ({file_dur:.1f}s)")
            _progress_update(source_name)
        notice_dur = time.perf_counter() - notice_start
        _report(f"责催完成: {notice_count} 个文件, 耗时 {notice_dur:.1f}s")

    if cancel_check and cancel_check():
        _report(f"任务已取消，跳过其他文件处理，已缓存 {len(ocr_results)} 个结果")
        total_duration = round(time.perf_counter() - ocr_start, 4)
        _report(f"OCR 阶段中断: {total_duration:.2f}s, 已处理 {len(ocr_results)} 个文件")
        return ocr_results

    other_files = [
        (pdf_name, pdf_name.replace('.pdf', ''))
        for pdf_name in _cfg.source_mapping.values()
    ]

    _report("处理其他文件...")
    if not use_mock and HAS_OCR and shared_ocr is None:
        shared_ocr, shared_region_extractor = _build_ocr_processors()
        shared_post_processor = TextPostProcessor()

    parallel_candidates = []
    serial_candidates = []
    for filename, stem in other_files:
        pdf_path = input_dir / filename
        if not pdf_path.exists():
            continue
        if filename in ocr_results:
            skipped_count += 1
            _progress_update(filename)
            _report(f"[SKIP] {filename} (已有缓存)")
            continue
        doc_type = stem if stem in {'申请书', '授权书', '所函'} else None
        if doc_type:
            parallel_candidates.append((filename, doc_type, pdf_path))
        else:
            serial_candidates.append((filename, stem, pdf_path))

    if parallel_candidates:
        from core.pdf_ocr_ultra import detect_gpu_provider
        gpu_provider, _ = detect_gpu_provider()
        use_parallel = gpu_provider not in ('dml_det',) and len(parallel_candidates) > 1

        t_parallel = time.perf_counter()

        if use_parallel:
            _report(f"  [并行] 启动 {len(parallel_candidates)} 个文档的多线程 OCR (GPU={gpu_provider})...")

            def _ocr_one_file(task):
                filename, doc_type, pdf_path = task
                return filename, _run_ocr_with_timeout(
                    pdf_path,
                    use_mock=use_mock,
                    doc_type=doc_type,
                    ocr=shared_ocr,
                    region_extractor=shared_region_extractor,
                    post_processor=shared_post_processor,
                    cancel_check=cancel_check,
                )

            from concurrent.futures import as_completed
            with ThreadPoolExecutor(max_workers=min(len(parallel_candidates), 3)) as pool:
                future_map = {
                    pool.submit(_ocr_one_file, task): task[0]
                    for task in parallel_candidates
                }
                for future in as_completed(future_map):
                    filename = future_map[future]
                    try:
                        _, result = future.result()
                        ocr_results[filename] = result
                        _on_result(filename, result)
                        _progress_update(filename)
                        _report(f"  [并行完成] {filename}")
                    except Exception as e:
                        _report(f"  [并行失败] {filename}: {e}")
        else:
            _report(f"  [串行] DirectML 模式下禁止多线程并行，改为逐文件处理...")
            for idx, (filename, doc_type, pdf_path) in enumerate(parallel_candidates, 1):
                if cancel_check and cancel_check():
                    _report(f"  [取消] 已取消，已完成 {idx-1}/{len(parallel_candidates)}")
                    break
                total_pages = inspect_pdf_page_count(pdf_path) if pdf_path.exists() else 0
                _report(f"  [{idx}/{len(parallel_candidates)}] {filename} ({total_pages} pages)...")
                t_file = time.perf_counter()
                result = _run_ocr_with_timeout(
                    pdf_path,
                    use_mock=use_mock,
                    doc_type=doc_type,
                    ocr=shared_ocr,
                    region_extractor=shared_region_extractor,
                    post_processor=shared_post_processor,
                    cancel_check=cancel_check,
                )
                ocr_results[filename] = result
                _on_result(filename, result)
                _progress_update(filename)
                _report(f"  [{idx}/{len(parallel_candidates)}] {filename} done ({time.perf_counter() - t_file:.1f}s)")

        parallel_dur = time.perf_counter() - t_parallel
        mode_label = '并行' if use_parallel else '串行'
        _report(f"  [{mode_label}] 完成: {len(parallel_candidates)} 个文件, 耗时 {parallel_dur:.1f}s")

    other_idx = len(parallel_candidates)
    other_total = len(parallel_candidates) + len(serial_candidates)
    type_durations = {}
    for filename, stem, pdf_path in serial_candidates:
        if cancel_check and cancel_check():
            _report(f"其他文件已取消，已完成 {other_idx}/{other_total}")
            break
        other_idx += 1
        total_pages = inspect_pdf_page_count(pdf_path)
        _report(f"[{other_idx}/{other_total}] {filename} ({total_pages} pages)...")
        t_file = time.perf_counter()

        def _make_page_progress(fname: str, tot: int):
            def _cb(done: int, total: int):
                _report(f"  {fname}: {done}/{total} pages")
            return _cb

        result = _run_ocr_with_timeout(
            pdf_path,
            use_mock=use_mock,
            doc_type=None,
            ocr=shared_ocr,
            region_extractor=shared_region_extractor,
            post_processor=shared_post_processor,
            page_progress=_make_page_progress(filename, total_pages),
            cancel_check=cancel_check,
        )
        file_dur = time.perf_counter() - t_file
        ocr_results[filename] = result
        _on_result(filename, result)
        _report(f"[{other_idx}/{other_total}] {filename} 完成 ({file_dur:.1f}s)")
        _progress_update(filename)

    for dt, dur in type_durations.items():
        _report(f"{dt}完成: {dur:.1f}s")

    total_duration = round(time.perf_counter() - ocr_start, 4)
    if skipped_count:
        _report(f"跳过缓存: {skipped_count} 个文件")
    _report(f"OCR 阶段完成: {total_duration:.2f}s, 共处理 {len(ocr_results)} 个文件")

    return ocr_results


def export_pdf_ranges(source_pdf: Path, ranges: List[Tuple[int, int]], output_dir: Path, target_names: List[str]) -> int:
    created = 0
    with open_pdf_reader(source_pdf) as reader:
        for i, ((start, end), target_name) in enumerate(zip(ranges, target_names)):
            target_path = output_dir / target_name
            if target_path.exists():
                created += 1
                _log(f"  [SKIP] 跳过已存在: {target_name}")
                continue

            if start >= len(reader.pages):
                _log(f"  [ERROR] 页码超出范围: {target_name} (起始页 {start} >= 总页数 {len(reader.pages)})")
                continue

            writer = PdfWriter()
            actual_end = min(end, len(reader.pages))
            for page_index in range(start, actual_end):
                writer.add_page(reader.pages[page_index])

            with target_path.open('wb') as file_obj:
                writer.write(file_obj)

            created += 1
            _log(f"  [OK] 导出: {target_name} (第 {start+1}-{actual_end} 页)")

    return created


def export_notice_files(sample_root: Path, input_dir: Path, output_dir: Path, ocr_results: Dict[str, Dict], excel_path: Optional[Path] = None) -> int:
    cases = load_non_litigation_cases(sample_root, excel_path=excel_path)

    target_map = {}
    target_notice_map = {}
    for case in cases:
        normalized = normalize_notice_number(case['notice_number'])
        target_name = f"{case['sequence']}-责催-{case['notice_number']}.pdf"
        target_map[normalized] = target_name
        target_notice_map[target_name] = normalized

    notice_files = discover_notice_files(input_dir)
    source_map = detect_notice_source_mapping_from_ocr(ocr_results, notice_files)

    created = 0
    unmatched = []

    for source_name, detected_notice in source_map.items():
        target_name = target_map.get(detected_notice)
        detected_root = _get_notice_root_number(detected_notice)
        ratio = None

        if not target_name and detected_root in target_map:
            target_name = target_map[detected_root]
            match_type = 'same_root_base'
            _log_audit('root_base_match', {
                'source': source_name,
                'detected': detected_notice,
                'matched_target': target_name,
                'root_notice': detected_root,
            })
            _log(f"    🔁 同根主号匹配: '{detected_notice}' -> '{target_name}'")
        elif target_name:
            match_type = 'exact'
        else:
            target_name, ratio = fuzzy_match_notice(detected_notice, target_map)
            if target_name:
                match_type = 'fuzzy'
                _log_audit('fuzzy_match', {
                    'source': source_name,
                    'detected': detected_notice,
                    'matched_target': target_name,
                    'similarity': ratio,
                })
                _log(f"    [INFO] 模糊匹配: '{detected_notice}' -> '{target_name}' (相似度: {ratio:.1%})")
                _log(f"    [WARN] 模糊匹配需人工确认！已记录到审计日志")

        if target_name:
            target_notice = target_notice_map.get(target_name)
            same_root_remap = bool(
                target_notice
                and target_notice != detected_notice
                and _get_notice_root_number(target_notice) == detected_root
            )
            export_metadata = {
                'matched_target': target_name,
                'matched_target_notice': target_notice,
                'export_match_type': match_type,
                'same_root_remap': same_root_remap,
            }
            if ratio is not None:
                export_metadata['export_match_similarity'] = ratio
            if same_root_remap:
                export_metadata['same_root_selected_notice'] = detected_notice
                _log_audit('same_root_remap', {
                    'source': source_name,
                    'selected_notice': detected_notice,
                    'target_notice': target_notice,
                    'matched_target': target_name,
                    'match_type': match_type,
                })
                _log(f"    [WARN] 主号识别后按同根目标导出: '{detected_notice}' -> '{target_notice}'")

            src = next((path for path in iter_notice_pdf_paths(input_dir) if path.name == source_name), input_dir / source_name)
            dst = output_dir / target_name
            if dst.exists():
                created += 1
                _log(f"  [SKIP] 跳过已存在: {target_name}")
                continue
            if src.exists():
                shutil.copy2(src, dst)
                created += 1
                _log(f"  [OK] {source_name} -> {target_name}")
                _log_audit('notice_renamed', {
                    'source': source_name,
                    'target': target_name,
                    'match_type': match_type,
                    'detected_notice': detected_notice,
                    'target_notice': target_notice,
                    'same_root_remap': same_root_remap,
                })
            else:
                _log(f"  [ERROR] 源文件不存在: {src}")
                unmatched.append((source_name, detected_notice, "源文件不存在"))
        else:
            _log(f"  [ERROR] 无法匹配: {source_name} (识别到 '{detected_notice}')")
            unmatched.append((source_name, detected_notice, "无匹配台账"))
            _log_audit('match_failed', {
                'source': source_name,
                'detected': detected_notice,
            })

    if unmatched:
        _log(f"\n  [WARN] 未匹配文件汇总 ({len(unmatched)} 个):")
        for source_name, notice, reason in unmatched:
            _log(f"    - {source_name}: {reason} (识别: '{notice}')")

    return created


def export_application_files(input_dir: Path, output_dir: Path, target_names: List[str], ocr_results: Dict[str, Dict]) -> int:
    source_pdf = input_dir / SOURCE_MAPPING['输出文件（申请书）'] 

    if not source_pdf.exists():
        _log(f"  [ERROR] 申请书文件不存在: {source_pdf}")
        return 0

    total_pages = inspect_pdf_page_count(source_pdf)
    expected_cases = len(target_names)

    _log(f"  [INFO] 申请书: {total_pages} 页，台账期望 {expected_cases} 个案件")

    ranges = detect_application_page_ranges_by_ocr(ocr_results, total_pages, expected_cases)

    if len(ranges) != expected_cases:
        _log(f"  [INFO] 按实际识别到 {len(ranges)} 个案件处理（台账 {expected_cases} 个）")

    return export_pdf_ranges(source_pdf, ranges, output_dir, target_names)


def _extract_company_name_from_target(target_name: str) -> str:
    stem = Path(target_name).stem
    return normalize_company_name_for_matching(stem)


_COMPANY_SUFFIXES = '有限公司|股份有限公司|有限责任公司|集团公司|合伙企业|分公司|幼儿园|事务所|研究院|服务中心|合作社|医院|大学|学院|幼儿园'
_EXECUTION_PATTERN = re.compile(r'与(.+?)(?:关于|强制执行)')
_AGENCY_PATTERN = re.compile(r'与(.+?)关于.*?(?:执行|审查|一案)')

_COMPANY_STRIP_PREFIXES = re.compile(r'^(委托人|申请人|被执行人|申请执行人)[:：]?')
_COMPANY_STRIP_SUFFIXES = re.compile(r'(?:关于|强制执行|行政非诉审查|补缴).*$')

# 公司类型后缀，用于区分总公司/分公司/有限公司/股份有限公司等
_COMPANY_TYPE_SUFFIXES = [
    '股份有限公司', '有限责任公司', '有限公司', '集团公司', '股份公司',
    '合伙企业', '分公司', '事务所', '研究院', '服务中心', '合作社',
    '医院', '大学', '学院', '幼儿园', '管理中心', '协会', '中心',
]


def _extract_company_core_name(name: str) -> str:
    """提取公司核心名称（去掉通用后缀）"""
    name = name.strip()
    for suffix in _COMPANY_TYPE_SUFFIXES:
        if name.endswith(suffix):
            return name[:-len(suffix)].strip()
    return name


def _get_company_suffixes(name: str) -> List[str]:
    """提取公司名称中的所有类型后缀"""
    result = []
    name = name.strip()
    for suffix in _COMPANY_TYPE_SUFFIXES:
        if suffix in name:
            result.append(suffix)
    return result


def _extract_target_company(text: str, fallback_fn=None) -> Optional[str]:
    collapsed = re.sub(r'\n', '', text)
    m = _EXECUTION_PATTERN.search(collapsed)
    if not m:
        m = _AGENCY_PATTERN.search(collapsed)
    if m:
        name = m.group(1)
        name = _COMPANY_STRIP_PREFIXES.sub('', name).strip()
        if len(name) >= 4:
            return name
    if fallback_fn:
        return fallback_fn(text)
    return None


def _is_suffix_compatible(detected: str, target: str) -> bool:
    """
    检查两个公司名的后缀是否兼容，避免总公司匹配到分公司。
    核心规则：如果一方明确包含'分公司'，另一方不能是不含'分公司'的总公司。
    """
    detected_suffixes = set(_get_company_suffixes(detected))
    target_suffixes = set(_get_company_suffixes(target))

    # 如果一方有"分公司"另一方没有，不兼容
    has_branch_d = '分公司' in detected_suffixes
    has_branch_t = '分公司' in target_suffixes
    if has_branch_d != has_branch_t:
        return False

    return True


def _fuzzy_match_company_name(detected: str, target_names: List[str], used_indices: set,
                               threshold: float = 0.85) -> Optional[Tuple[int, str]]:
    """
    公司名称模糊匹配，策略：
    1. 精确匹配（规范化后完全一致）
    2. 核心名称匹配（去掉通用后缀后一致，且后缀兼容）
    3. SequenceMatcher 模糊匹配（≥阈值，且后缀兼容）
    """
    best_idx = None
    best_target = None
    best_score = -1

    detected_norm = normalize_company_name_for_matching(detected)
    detected_core = _extract_company_core_name(detected_norm)

    candidates = []
    for i, target in enumerate(target_names):
        if i in used_indices:
            continue
        target_company = _extract_company_name_from_target(target)
        target_norm = normalize_company_name_for_matching(target_company)

        # 1. 精确匹配
        if detected_norm == target_norm:
            candidates.append((i, target, 100.0, 'exact'))
            continue

        # 2. 核心名称匹配（去掉有限公司/分公司等后缀）
        target_core = _extract_company_core_name(target_norm)
        if detected_core and target_core and detected_core == target_core:
            if _is_suffix_compatible(detected_norm, target_norm):
                candidates.append((i, target, 95.0, 'core'))
                continue

        # 3. 模糊匹配
        ratio = SequenceMatcher(None, detected_norm, target_norm).ratio()
        if ratio >= threshold and _is_suffix_compatible(detected_norm, target_norm):
            candidates.append((i, target, ratio, 'fuzzy'))

    if not candidates:
        return None

    # 排序：精确 > 核心 > 模糊；同类型选更长的（更具体）
    def sort_key(item):
        score, match_type, name = item[2], item[3], item[1]
        type_order = {'exact': 3, 'core': 2, 'fuzzy': 1}
        return (type_order.get(match_type, 0), score, len(name))

    candidates.sort(key=sort_key, reverse=True)
    best = candidates[0]
    return (best[0], best[1])


def detect_company_page_mapping_from_ocr(ocr_results: Dict[str, Dict], doc_type: str,
                                          target_names: List[str]) -> Optional[List[str]]:
    data = _get_ocr_result(ocr_results, doc_type)
    if not data or not data.get('pages'):
        return None

    post_processor = TextPostProcessor()
    pages = data['pages']
    if len(pages) < len(target_names):
        return None

    matched_targets: List[Optional[str]] = [None] * len(pages)
    used_indices: set = set()

    for page_idx, page_data in enumerate(pages):
        text = page_data.get('text', '')
        detected_company = _extract_target_company(text, fallback_fn=post_processor.extract_company_name_from_text)
        if detected_company:
            normalized = normalize_company_name_for_matching(detected_company)
            result = _fuzzy_match_company_name(normalized, target_names, used_indices)
            if result:
                idx, target = result
                matched_targets[page_idx] = target
                used_indices.add(idx)

                ratio = SequenceMatcher(None, normalized, _extract_company_name_from_target(target)).ratio()
                _log_audit('company_name_match', {
                    'doc_type': doc_type,
                    'page': page_idx + 1,
                    'detected': detected_company,
                    'matched_target': target,
                    'similarity': round(ratio, 3),
                })

    unmatched_pages = [i for i, t in enumerate(matched_targets) if t is None]
    if unmatched_pages:
        remaining_targets = [(i, t) for i, t in enumerate(target_names) if i not in used_indices]
        for page_idx in unmatched_pages:
            if remaining_targets:
                fallback_idx, fallback_target = remaining_targets.pop(0)
                matched_targets[page_idx] = fallback_target
                used_indices.add(fallback_idx)
                _log(f"  [WARN] {doc_type} 第{page_idx + 1}页未识别到公司名，按顺序分配: {fallback_target}")
            else:
                page_data = pages[page_idx]
                matched_targets[page_idx] = f"未匹配_第{page_idx + 1}页.pdf"
                _log(f"  [WARN] {doc_type} 第{page_idx + 1}页无法匹配公司名")

    matched_count = sum(1 for t in matched_targets if t is not None and not t.startswith('未匹配'))
    if matched_count == 0:
        return None

    _log(f"  [OK] {doc_type} OCR 匹配: {matched_count}/{len(pages)} 页成功匹配公司名")
    return matched_targets


def export_company_named_files(input_dir: Path, output_dir: Path, target_names: List[str],
                               ocr_results: Dict[str, Dict], source_name: Optional[str], marker: str) -> int:
    if not source_name:
        _log(f"  [ERROR] {marker} 未配置 source_pdf")
        return 0

    source_pdf = input_dir / source_name

    if not source_pdf.exists():
        _log(f"  [ERROR] {source_name} 文件不存在")
        return 0

    total_pages = inspect_pdf_page_count(source_pdf)
    doc_type = '授权书' if '授权' in marker else '所函'

    _log(f"  [INFO] {source_name}: {total_pages} 页")

    data = _get_ocr_result(ocr_results, doc_type)
    if data and data.get('pages'):
        pages = data['pages']
        post_processor = TextPostProcessor()

        matched_names: List[str] = []
        used_indices: set = set()

        for page_idx, page_data in enumerate(pages):
            text = page_data.get('text', '')
            detected = _extract_target_company(text, fallback_fn=post_processor.extract_company_name_from_text)
            if detected:
                normalized = normalize_company_name_for_matching(detected)
                match = _fuzzy_match_company_name(normalized, target_names, used_indices)
                if match:
                    idx, target_name = match
                    matched_names.append(target_name)
                    used_indices.add(idx)
                    _log(f"    [MATCH] 第{page_idx + 1}页 '{detected}' -> 台账 '{target_name}'")
                    _log_audit('company_name_match', {
                        'doc_type': doc_type,
                        'page': page_idx + 1,
                        'detected': detected,
                        'matched_target': target_name,
                    })
                else:
                    matched_names.append(f"{detected}.pdf")
                    _log(f"    [WARN] 第{page_idx + 1}页 '{detected}' 未匹配台账，使用识别结果")
                    _log_audit('company_name_unmatched', {
                        'doc_type': doc_type,
                        'page': page_idx + 1,
                        'detected': detected,
                    })
            else:
                matched_names.append(f"未匹配_第{page_idx + 1}页.pdf")
                _log(f"    [WARN] 第{page_idx + 1}页未识别到公司名")

        ranges = detect_page_ranges(total_pages, len(matched_names), doc_type)
        actual_names = matched_names[:len(ranges)]
        shortage = len(ranges) - len(actual_names)
        if shortage > 0:
            remaining = [(i, t) for i, t in enumerate(target_names) if i not in used_indices]
            for i in range(len(actual_names), len(ranges)):
                if remaining:
                    idx, target = remaining.pop(0)
                    actual_names.append(target)
                    used_indices.add(idx)
                    _log(f"    [FALLBACK] 第{i + 1}页按顺序分配: {target}")
                else:
                    actual_names.append(f"未匹配_第{i + 1}页.pdf")
        _log(f"  [OK] {doc_type} OCR匹配: {sum(1 for n in actual_names if not n.startswith('未匹配'))}/{len(pages)} 页成功匹配台账")
        return export_pdf_ranges(source_pdf, ranges, output_dir, actual_names)

    _log(f"  [INFO] {doc_type} 无 OCR 结果，按Excel顺序分配")
    expected_count = len(target_names)
    ranges = detect_page_ranges(total_pages, expected_count, doc_type)
    return export_pdf_ranges(source_pdf, ranges, output_dir, target_names)


def export_non_litigation_standard_outputs(sample_root: Path, input_dir: Path, output_root: Path, ocr_results: Dict[str, Dict], excel_path: Optional[Path] = None) -> Dict:
    output_root.mkdir(parents=True, exist_ok=True)
    tree = build_expected_output_tree(sample_root, excel_path=excel_path)
    created_count = 0
    _audit_log.clear()

    _log("\n[INFO] 开始导出文件...")
    _log("=" * 60)

    total_targets = sum(len(target_names) for target_names in tree.values())
    if total_targets == 0:
        _log("\n[WARN] 导出计划为空！台账中未加载到任何案件数据")
        _log(f"  请检查 Excel 文件是否存在于: {sample_root}")
        _log(f"  输入目录: {input_dir}")

    export_tasks = []
    for folder_name, target_names in tree.items():
        folder_path = output_root / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        _log(f"\n[INFO] {folder_name} ({len(target_names)} 个文件)")

        if folder_name == _cfg.directory_mapping['责催']:
            count = export_notice_files(sample_root, input_dir, folder_path, ocr_results, excel_path=excel_path)
            export_tasks.append(('责催', count))

        elif folder_name == _cfg.directory_mapping['申请书']:
            count = export_application_files(input_dir, folder_path, target_names, ocr_results)
            export_tasks.append(('申请书', count))

        elif folder_name == _cfg.directory_mapping['授权书']:
            count = export_company_named_files(input_dir, folder_path, target_names, ocr_results, _cfg.doc_type_map['授权书'].source_pdf, _cfg.doc_type_map['授权书'].content_marker)
            export_tasks.append(('授权书', count))

        elif folder_name == _cfg.directory_mapping['所函']:
            count = export_company_named_files(input_dir, folder_path, target_names, ocr_results, _cfg.doc_type_map['所函'].source_pdf, _cfg.doc_type_map['所函'].content_marker)
            export_tasks.append(('所函', count))

    created_count = sum(count for _, count in export_tasks)

    if created_count == 0:
        _log("\n[WARN] 导出 0 个文件！可能原因：")
        _log(f"  1. 输入目录 ({input_dir}) 中没有 PDF 文件")
        _log(f"  2. OCR 识别未成功")
        _log(f"  3. 台账 Excel 中没有匹配的案件数据")
        _log(f"  请检查以上路径和文件是否正确")

    # 写入审计日志（仅当有问题时输出，格式为易读文本）
    if _audit_log:
        audit_path = output_root / 'audit-log.txt'
        audit_lines = [f"OCR 识别审计报告（共 {len(_audit_log)} 条）", "=" * 60, ""]
        for i, entry in enumerate(_audit_log, 1):
            event = entry.get('event', 'unknown')
            detail = {k: v for k, v in entry.items() if k != 'event'}
            audit_lines.append(f"【{i}】事件: {event}")
            for k, v in detail.items():
                audit_lines.append(f"    {k}: {v}")
            audit_lines.append("")
        audit_path.write_text("\n".join(audit_lines), encoding='utf-8')
        _log(f"\n[INFO] 审计日志已保存: {audit_path} ({len(_audit_log)} 条)")
    # 清理旧版 json 审计日志（如存在）
    old_audit_json = output_root / 'audit-log.json'
    if old_audit_json.exists():
        old_audit_json.unlink()

    # 生成页码映射表（按 OCR 实际识别顺序）
    try:
        cases = load_non_litigation_cases(sample_root, excel_path=excel_path)
        mappings = build_company_page_mapping(cases, ocr_results)
        mapping_path = output_root / '页码映射表.xlsx'
        write_mapping_excel(cases, mappings, mapping_path)
    except Exception as e:
        _log(f"  [WARN] 生成页码映射表失败: {e}")

    _log("\n" + "=" * 60)
    _log(f"[OK] 导出完成: {created_count} 个文件")

    return {
        'created_count': created_count,
        'output_root': str(output_root),
        'tree': tree,
    }


def get_actual_page_companies(ocr_results: Dict[str, Dict], doc_type: str) -> List[Optional[str]]:
    """从 OCR 结果中提取每页实际识别到的公司名（不强制匹配台账）"""
    data = _get_ocr_result(ocr_results, doc_type)
    if not data or not data.get('pages'):
        return []

    post_processor = TextPostProcessor()
    companies = []
    for page_data in data['pages']:
        text = page_data.get('text', '')
        detected = _extract_target_company(text, fallback_fn=post_processor.extract_company_name_from_text)
        companies.append(detected)
    return companies


def build_company_page_mapping(cases: List[Dict], ocr_results: Dict[str, Dict]) -> Dict[str, Dict]:
    """构建公司名到授权书/所函页码的映射（按 PDF 实际页顺序）"""
    auth_companies = get_actual_page_companies(ocr_results, '授权书')
    letter_companies = get_actual_page_companies(ocr_results, '所函')

    result = {}
    for case in cases:
        company = case['company_name']
        norm_company = normalize_company_name_for_matching(company)
        result[company] = {
            'sequence': case.get('sequence', ''),
            'notice_number': case.get('notice_number', ''),
            'auth_page': None,
            'letter_page': None,
            'auth_detected': None,
            'letter_detected': None,
        }

        # 找授权书页码
        for i, detected in enumerate(auth_companies):
            if detected and normalize_company_name_for_matching(detected) == norm_company:
                result[company]['auth_page'] = i + 1
                result[company]['auth_detected'] = detected
                break

        # 找所函页码
        for i, detected in enumerate(letter_companies):
            if detected and normalize_company_name_for_matching(detected) == norm_company:
                result[company]['letter_page'] = i + 1
                result[company]['letter_detected'] = detected
                break

    return result


def write_mapping_excel(cases: List[Dict], mappings: Dict[str, Dict], output_path: Path):
    """生成台账-页码映射 Excel，方便人工核对"""
    if not HAS_OPENPYXL:
        _log(f"  [WARN] openpyxl 未安装，跳过生成映射表")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "页码映射"

    headers = ['台账序号', '责令号', '公司名', '授权书页码', '所函页码', '授权书文件名', '所函文件名', '备注']
    ws.append(headers)

    for case in cases:
        company = case['company_name']
        mapping = mappings.get(company, {})
        auth_page = mapping.get('auth_page')
        letter_page = mapping.get('letter_page')

        auth_file = f"{company}.pdf" if auth_page else '未匹配'
        letter_file = f"{company}.pdf" if letter_page else '未匹配'

        notes = []
        if not auth_page:
            notes.append('授权书未匹配')
        if not letter_page:
            notes.append('所函未匹配')

        ws.append([
            mapping.get('sequence', case.get('sequence', '')),
            mapping.get('notice_number', case.get('notice_number', '')),
            company,
            auth_page if auth_page else '未匹配',
            letter_page if letter_page else '未匹配',
            auth_file,
            letter_file,
            '；'.join(notes) if notes else '',
        ])

    wb.save(output_path)
    _log(f"  [OK] 页码映射表已保存: {output_path}")
