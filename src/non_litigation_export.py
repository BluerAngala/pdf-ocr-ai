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
import re
import shutil
import sys
import time
from difflib import SequenceMatcher
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Iterable

from region_extractor import RegionExtractor, REGIONS
from contextlib import contextmanager

from pypdf import PdfReader, PdfWriter

from non_litigation_output_plan import build_expected_output_tree
from non_litigation_product import load_non_litigation_cases
from text_postprocessor import TextPostProcessor
from system_resource import detect_system_resources

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))

from config_loader import load_config
_cfg = load_config()

try:
    from pdf_ocr_ultra import UltraFastOCR, OCRConfig
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("[WARN] pdf_ocr_ultra 导入失败，将使用 Mock OCR")


SOURCE_MAPPING = _cfg.source_mapping
APPLICATION_BOUNDARY_KEYWORDS = _cfg.boundary_keywords.get('申请书', [])
NON_LITIGATION_RESULT_DIRNAME = _cfg.result_dirname
NON_LITIGATION_TEMP_DIRNAME = _cfg.temp_dirname
NON_LITIGATION_INPUT_DIRNAME = _cfg.input_dirname
NOTICE_PATTERN = _cfg.notice_pattern
NON_LITIGATION_CORRECTIONS = _cfg.ocr_corrections
PAGES_PER_CASE = _cfg.pages_per_case

_audit_log: List[Dict] = []


def _get_doc_regions(doc_type: str):
    return [REGIONS[name] for name in _cfg.ocr_doc_regions.get(doc_type, []) if name in REGIONS]


_worker_ocr = None
_worker_region_extractor = None
_worker_post_processor = None


def _worker_init():
    global _worker_ocr, _worker_region_extractor, _worker_post_processor
    os.environ['OMP_NUM_THREADS'] = '2'
    os.environ['ONNXRUNTIME_CPU_NUM_THREADS'] = '2'
    
    from pdf_ocr_ultra import UltraFastOCR, OCRConfig
    ocr_config = OCRConfig(
        dpi=_cfg.ocr_dpi,
        max_image_size=_cfg.ocr_max_image_size,
        parallel_workers=1,
        small_pdf_page_threshold=_cfg.ocr_small_pdf_page_threshold,
    )
    _worker_ocr = UltraFastOCR(ocr_config, skip_warmup=True)
    _worker_region_extractor = RegionExtractor(dpi=_cfg.ocr_region_dpi, poppler_path=ocr_config.poppler_path)
    _worker_post_processor = TextPostProcessor()
    print("  [INFO] 工作进程初始化完成")


def _ocr_notice_file_worker(args: Tuple) -> Dict:
    global _worker_ocr, _worker_region_extractor, _worker_post_processor
    pdf_path_str, cache_path_str, doc_type_str = args
    pdf_path = Path(pdf_path_str)
    cache_path = Path(cache_path_str)

    if cache_path.exists():
        return {'source': pdf_path.name, 'status': 'cached', 'performance': None}

    try:
        result = run_real_ocr_on_pdf(
            pdf_path,
            cache_path,
            use_mock=False,
            is_notice=True,
            stop_pattern=NOTICE_PATTERN,
            doc_type=doc_type_str,
            ocr=_worker_ocr,
            region_extractor=_worker_region_extractor,
            post_processor=_worker_post_processor,
        )
        return {
            'source': pdf_path.name,
            'status': 'done',
            'performance': result.get('performance_summary', {
                'doc_type': doc_type_str,
                'file_name': pdf_path.name,
                'page_count': result.get('total_pages', 0),
                'total_duration': result.get('total_duration', 0),
                'fallback_pages': result.get('fallback_pages', 0),
            }),
        }
    except Exception as e:
        return {'source': pdf_path.name, 'status': 'error', 'performance': None, 'error': str(e)}


def _build_ocr_config() -> "OCRConfig":
    return OCRConfig(
        dpi=_cfg.ocr_dpi,
        max_image_size=_cfg.ocr_max_image_size,
        parallel_workers=_cfg.ocr_parallel_workers,
        small_pdf_page_threshold=_cfg.ocr_small_pdf_page_threshold,
    )


def _build_ocr_processors() -> Tuple["UltraFastOCR", RegionExtractor]:
    config = _build_ocr_config()
    return UltraFastOCR(config), RegionExtractor(dpi=_cfg.ocr_region_dpi, poppler_path=config.poppler_path)


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
    for region_name, region, image in zip(selected_names, regions, images):
        result = ocr.recognize_image_region(
            image,
            page_num=page_num,
            max_image_size=_cfg.ocr_region_max_image_size,
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


@contextmanager
def open_pdf_reader(pdf_path: Path):
    reader = PdfReader(str(pdf_path))
    try:
        yield reader
    finally:
        if hasattr(reader, 'stream') and reader.stream:
            reader.stream.close()


def apply_ocr_corrections(text: str) -> str:
    for wrong, correct in NON_LITIGATION_CORRECTIONS:
        if wrong in text and correct not in text[:text.index(wrong)]:
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
    corrected_text = apply_ocr_corrections(text)
    structured = post_processor.extract_notice_fields(corrected_text)
    page_profile = structured.get('page_profile', {})
    decision_numbers = [normalize_notice_number(item) for item in structured.get('decision_numbers', [])]

    score = 0
    if page_profile.get('is_notice_main_page'):
        score += 150
    if structured.get('document_type') == '责令限期办理决定书':
        score += 120
    if structured.get('company_name'):
        score += 50
    if '名称' in corrected_text:
        score += 30
    if '统一社会信用代码' in corrected_text:
        score += 35
    if '责令你单位履行以下义务' in corrected_text:
        score += 60
    if decision_numbers:
        score += 30

    if page_profile.get('is_notice_revoke_page'):
        score -= 160
    if page_profile.get('is_notice_delivery_page'):
        score -= 120
    if page_profile.get('is_notice_logistics_page'):
        score -= 180

    score -= max(page_num - 1, 0) * 2

    return {
        'page': page_num,
        'score': score,
        'decision_numbers': decision_numbers,
        'document_type': structured.get('document_type'),
        'company_name': structured.get('company_name'),
        'page_profile': page_profile,
        'has_uscc_signal': '统一社会信用代码' in corrected_text,
        'has_duty_signal': '责令你单位履行以下义务' in corrected_text,
    }


def _select_notice_candidate(candidate_pages: List[Dict]) -> Dict:
    if not candidate_pages:
        return {}

    all_candidates = []
    root_best_scores: Dict[str, float] = {}
    root_has_main_page: Dict[str, bool] = {}
    root_has_base_number: Dict[str, bool] = {}
    root_has_company_signal: Dict[str, bool] = {}
    root_has_uscc_signal: Dict[str, bool] = {}
    root_has_duty_signal: Dict[str, bool] = {}

    for page in candidate_pages:
        page_profile = page.get('page_profile', {})
        page_has_company_signal = bool(page.get('company_name'))
        page_has_uscc_signal = bool(page.get('has_uscc_signal'))
        page_has_duty_signal = bool(page.get('has_duty_signal'))
        for number in page.get('decision_numbers', []):
            normalized = normalize_notice_number(number)
            root_number = _get_notice_root_number(normalized)
            is_base_number = normalized == root_number
            score = page.get('score', 0)
            if is_base_number:
                score += 80
            if page_profile.get('is_notice_main_page') and is_base_number:
                score += 60
            if page_has_company_signal and is_base_number:
                score += 35
            if page_has_uscc_signal and is_base_number:
                score += 35
            if page_has_duty_signal and is_base_number:
                score += 25
            all_candidates.append({
                'page': page.get('page'),
                'number': normalized,
                'root_number': root_number,
                'score': score,
                'is_base_number': is_base_number,
                'page_profile': page_profile,
                'document_type': page.get('document_type'),
                'company_name': page.get('company_name'),
            })
            root_best_scores[root_number] = max(root_best_scores.get(root_number, float('-inf')), score)
            root_has_main_page[root_number] = root_has_main_page.get(root_number, False) or bool(page_profile.get('is_notice_main_page'))
            root_has_base_number[root_number] = root_has_base_number.get(root_number, False) or is_base_number
            root_has_company_signal[root_number] = root_has_company_signal.get(root_number, False) or page_has_company_signal
            root_has_uscc_signal[root_number] = root_has_uscc_signal.get(root_number, False) or page_has_uscc_signal
            root_has_duty_signal[root_number] = root_has_duty_signal.get(root_number, False) or page_has_duty_signal

    def candidate_sort_key(item: Dict):
        root_number = item['root_number']
        return (
            root_best_scores.get(root_number, float('-inf')),
            1 if root_has_main_page.get(root_number) else 0,
            1 if root_has_base_number.get(root_number) else 0,
            1 if root_has_company_signal.get(root_number) else 0,
            1 if root_has_uscc_signal.get(root_number) else 0,
            1 if root_has_duty_signal.get(root_number) else 0,
            1 if item.get('is_base_number') else 0,
            item.get('score', float('-inf')),
            -item.get('page', 0),
        )

    all_candidates.sort(key=candidate_sort_key, reverse=True)
    selected = all_candidates[0]
    return {
        'selected_notice': selected['number'],
        'selected_page': selected['page'],
        'selected_root_notice': selected['root_number'],
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


def _should_fallback_notice(region_text: str, page_candidate: Optional[Dict]) -> Tuple[bool, Optional[str]]:
    compact = _compact_text(region_text)
    if page_candidate and page_candidate.get('decision_numbers'):
        return False, None
    if len(compact) < _cfg.notice_region_fallback_min_text_length:
        return True, 'region_text_too_short'
    if '责字' in compact or '责令' in compact or '公积金' in compact:
        return False, 'weak_notice_signal_only'
    return True, 'no_notice_signal'


def _should_fallback_application(
    page_num: int,
    text: str,
    detected_boundaries: List[int],
    expected_boundaries: int,
    expected_start_pages: set,
) -> Tuple[bool, Optional[str]]:
    compact = _compact_text(text)
    is_candidate_boundary_page = page_num in expected_start_pages
    previous_page_detected = (page_num - 1) in detected_boundaries
    next_page_detected = (page_num + 1) in detected_boundaries
    boundary_gap_exists = len(detected_boundaries) < expected_boundaries
    nearby_boundary_signal = previous_page_detected or next_page_detected
    weak_region_text = len(compact) < _cfg.application_region_fallback_min_text_length

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


def _is_high_confidence_notice_candidate(page_candidate: Optional[Dict]) -> bool:
    if not page_candidate:
        return False
    decision_numbers = page_candidate.get('decision_numbers', [])
    if not decision_numbers:
        return False
    page_profile = page_candidate.get('page_profile', {})
    has_base_number = any(
        normalize_notice_number(number) == _get_notice_root_number(number)
        for number in decision_numbers
    )
    strong_page_signal = bool(page_profile.get('is_notice_main_page'))
    strong_content_signal = bool(
        page_candidate.get('company_name')
        or page_candidate.get('has_uscc_signal')
        or page_candidate.get('has_duty_signal')
    )
    return has_base_number and strong_page_signal and strong_content_signal and page_candidate.get('score', 0) >= 260


def _has_decisive_notice_candidate(candidate_pages: List[Dict]) -> bool:
    if not candidate_pages:
        return False
    selection = _select_notice_candidate(candidate_pages)
    selected_notice = selection.get('selected_notice')
    if not selected_notice:
        return False
    selected_page = next(
        (page for page in candidate_pages if selected_notice in page.get('decision_numbers', [])),
        None,
    )
    return _is_high_confidence_notice_candidate(selected_page)


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


def safe_load_ocr_cache(ocr_json_path: Path) -> Optional[Dict]:
    try:
        if not ocr_json_path.exists():
            print(f"  ⚠️ 缓存不存在: {ocr_json_path.name}")
            return None

        content = ocr_json_path.read_text(encoding='utf-8')
        data = json.loads(content)

        if 'pages' not in data or 'total_pages' not in data:
            print(f"  ⚠️ 缓存格式错误: {ocr_json_path.name}")
            return None

        return data

    except json.JSONDecodeError as e:
        print(f"  ❌ 缓存文件损坏: {ocr_json_path.name} - {e}")
        backup_path = ocr_json_path.with_suffix('.json.bak')
        try:
            ocr_json_path.rename(backup_path)
            print(f"  📁 已备份到: {backup_path}")
        except Exception:
            pass
        return None

    except Exception as e:
        print(f"  ❌ 读取缓存失败: {ocr_json_path.name} - {e}")
        return None


def inspect_pdf_page_count(pdf_path: Path) -> int:
    with open_pdf_reader(pdf_path) as reader:
        return len(reader.pages)


def get_non_litigation_input_root(project_root: Path) -> Path:
    return project_root / 'input' / NON_LITIGATION_INPUT_DIRNAME


def get_non_litigation_result_root(project_root: Path) -> Path:
    return project_root / 'output' / NON_LITIGATION_RESULT_DIRNAME


def get_non_litigation_temp_root(project_root: Path) -> Path:
    return project_root / 'temp' / NON_LITIGATION_TEMP_DIRNAME


def get_non_litigation_ocr_cache_dir(project_root: Path) -> Path:
    return get_non_litigation_temp_root(project_root) / 'ocr-cache'


def ensure_non_litigation_input_structure(project_root: Path) -> Path:
    input_root = get_non_litigation_input_root(project_root)
    input_root.mkdir(parents=True, exist_ok=True)
    for item in input_root.parent.iterdir():
        if item.is_file() and item.suffix.lower() == '.pdf' and not (input_root / item.name).exists():
            shutil.move(str(item), str(input_root / item.name))
    return input_root


def get_notice_input_dirs(input_dir: Path) -> List[Path]:
    candidate_dirs = [input_dir]
    nested_notice_dir = input_dir / '责催（证据材料）'
    if nested_notice_dir.exists() and nested_notice_dir.is_dir():
        candidate_dirs.append(nested_notice_dir)
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
        print(
            f'  ℹ️ {doc_type}: 实际 {total_pages} 页，台账期望 {expected_pages} 页 '
            f'({expected_count} 个 × {pages_per_item} 页)，按实际页数处理'
        )

    actual_count = min(expected_count, total_pages // pages_per_item) if total_pages > 0 else 0
    ranges = []
    for i in range(actual_count):
        start = i * pages_per_item
        end = start + pages_per_item
        ranges.append((start, end))
    return ranges


def detect_application_page_ranges_by_ocr(ocr_cache_dir: Path, total_pages: int, expected_cases: int) -> List[Tuple[int, int]]:
    """
    通过 OCR 识别"强制执行申请书"标题来定位页边界。
    如果 OCR 缓存不可用或检测到的边界数不匹配，fallback 到固定页数。
    """
    json_path = ocr_cache_dir / '申请书_ultra_result.json'
    data = safe_load_ocr_cache(json_path)
    if not data or not data.get('pages'):
        print(f"  ⚠️ 无申请书 OCR 缓存，使用固定 {PAGES_PER_CASE['申请书']} 页/案件")
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
        print(f"  ✅ OCR 检测到 {len(boundary_pages)} 个申请书边界")
        return ranges

    if boundary_pages:
        print(f"  ℹ️ OCR 检测到 {len(boundary_pages)} 个边界，台账期望 {expected_cases} 个，按实际处理")
    else:
        print(f"  ℹ️ OCR 未检测到申请书边界，使用固定 {PAGES_PER_CASE['申请书']} 页/案件")

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


def detect_notice_source_mapping_from_ocr(output_cache_dir: Path, notice_files: List[str]) -> Dict[str, str]:
    """
    从 OCR 结果中识别责催文件的责令号

    Returns:
        {source_filename: detected_notice_number}
    """
    mapping: Dict[str, str] = {}
    post_processor = TextPostProcessor()
    for source_name in notice_files:
        stem = source_name.replace('.pdf', '')
        json_path = output_cache_dir / f'{stem}_ultra_result.json'
        data = safe_load_ocr_cache(json_path)

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
            print(f"  ✅ {source_name}: 识别到责令号 '{selected_notice}'")
            if selected_page:
                print(f"    ℹ️ 采用第 {selected_page} 页候选")
        else:
            print(f"  ⚠️ {source_name}: 未识别到责令号")

    return mapping


def build_mock_ocr_cache(sample_root: Path, cache_dir: Path, input_dir: Path | None = None) -> Path:
    """构建 Mock OCR 缓存（用于测试）"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    standard_root = sample_root / _cfg.standard_output_dirname

    ocr_noise_samples = _cfg.mock_noise_samples
    import random

    application_pages = []
    for index, pdf_path in enumerate(sorted((standard_root / _cfg.directory_mapping['申请书']).glob('*.pdf'))):
        page_count = inspect_pdf_page_count(pdf_path)
        for page_offset in range(page_count):
            page_number = len(application_pages) + 1
            if page_offset == 0:
                noise_idx = index % len(ocr_noise_samples)
                text = f'强制执行申请书\n名称：案子{index + 1}\n穗公积金中心{ocr_noise_samples[noise_idx]}越秀责字'
            else:
                text = f'被执行人：公司{index + 1}\n金额：10000元'
            application_pages.append({'page': page_number, 'text': text})
    (cache_dir / '申请书_ultra_result.json').write_text(
        json.dumps({'pages': application_pages, 'total_pages': len(application_pages), 'filename': '申请书.pdf'}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    for filename, marker, folder in [
        (f'授权书{_cfg.ocr_cache_suffix}', _cfg.doc_type_map['授权书'].content_marker, _cfg.directory_mapping['授权书']),
        (f'所函{_cfg.ocr_cache_suffix}', _cfg.doc_type_map['所函'].content_marker, _cfg.directory_mapping['所函']),
    ]:
        pages = []
        for index, pdf_path in enumerate(sorted((standard_root / folder).glob('*.pdf'))):
            company_name = pdf_path.stem
            noise_idx = index % len(ocr_noise_samples)
            text = f'{marker}\n{ocr_noise_samples[noise_idx]}\n{company_name}'
            pages.append({'page': index + 1, 'text': text})
        (cache_dir / filename).write_text(
            json.dumps({'pages': pages, 'total_pages': len(pages), 'filename': filename.replace('_ultra_result.json', '.pdf')}, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    notice_files = sorted((standard_root / _cfg.directory_mapping['责催']).glob('*.pdf'))

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
                    payload = {
                        'pages': [{'page': 1, 'text': normalized_number}],
                        'total_pages': 1,
                        'filename': src_name,
                    }
                    stem = src_name.replace('.pdf', '')
                    (cache_dir / f'{stem}_ultra_result.json').write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding='utf-8',
                    )
            else:
                print(f"  ⚠️ Mock: 无法按页数匹配 {src_name}，使用顺序匹配")
                stem = src_name.replace('.pdf', '')
                fallback_idx = src_files.index(src_name)
                if fallback_idx < len(notice_files):
                    notice_number = notice_files[fallback_idx].stem.split('-责催-')[1]
                    normalized_number = normalize_notice_number(notice_number)
                    payload = {
                        'pages': [{'page': 1, 'text': normalized_number}],
                        'total_pages': 1,
                        'filename': src_name,
                    }
                    (cache_dir / f'{stem}_ultra_result.json').write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding='utf-8',
                    )
    else:
        notice_numbers = [pdf_path.stem.split('-责催-')[1] for pdf_path in notice_files]
        for idx, notice_number in enumerate(notice_numbers):
            normalized_number = normalize_notice_number(notice_number)
            payload = {
                'pages': [{'page': 1, 'text': normalized_number}],
                'total_pages': 1,
                'filename': f'{idx + 1}.pdf',
            }
            (cache_dir / f'{idx + 1}_ultra_result.json').write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )

    return cache_dir


def run_real_ocr_on_pdf(pdf_path: Path, cache_path: Path, use_mock: bool = False,
                        is_notice: bool = False, stop_pattern: Optional[re.Pattern] = None,
                        doc_type: Optional[str] = None, ocr: Optional["UltraFastOCR"] = None,
                        region_extractor: Optional[RegionExtractor] = None,
                        post_processor: Optional[TextPostProcessor] = None) -> Dict:
    if use_mock or not HAS_OCR:
        if cache_path.exists():
            return safe_load_ocr_cache(cache_path) or {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'mock'}
        return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'mock'}

    existing = safe_load_ocr_cache(cache_path)
    if existing:
        print(f"  [CACHE] 使用已有 OCR 缓存: {cache_path.name}")
        return existing

    print(f"  [OCR] 开始识别: {pdf_path.name}")

    try:
        if ocr is None or region_extractor is None:
            shared_ocr, shared_region_extractor = _build_ocr_processors()
            ocr = ocr or shared_ocr
            region_extractor = region_extractor or shared_region_extractor

        if is_notice and stop_pattern:
            print(f"  [OCR] 使用逐页识别模式（短窗口扫描后停止）")
            notice_post_processor = post_processor or TextPostProcessor()

            if _cfg.ocr_enable_region_first:
                pages = []
                total_start = time.perf_counter()
                page_num = 1
                stopped_early = False
                candidate_pages = []
                first_hit_page = None
                stop_after_page = None
                max_scan_pages = max(1, _cfg.notice_scan_max_pages)
                scan_window_pages = max(0, _cfg.notice_scan_window_pages)

                while page_num <= max_scan_pages:
                    try:
                        full_image = region_extractor.extract_full_page(pdf_path, page_num)
                    except Exception:
                        break

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
                    region_text = apply_ocr_corrections(region_text)

                    duration = sum(item['duration'] for item in page_logs)
                    text = region_text
                    method = 'region_first'
                    page_candidate = _score_notice_candidate(page_num, text, notice_post_processor) if text else None
                    matched = bool(page_candidate and page_candidate.get('decision_numbers'))
                    needs_fallback, fallback_trigger_reason = _should_fallback_notice(region_text, page_candidate)

                    if needs_fallback and _cfg.ocr_allow_full_page_fallback:
                        full_result = ocr.recognize_full_page_image(
                            full_image,
                            page_num=page_num,
                            method='full_page_fallback',
                            optimize_output=True,
                        )
                        full_text = apply_ocr_corrections(full_result.text)
                        duration += full_result.duration
                        if full_text:
                            text = full_text
                            method = full_result.method
                            page_candidate = _score_notice_candidate(page_num, text, notice_post_processor)
                            matched = bool(page_candidate.get('decision_numbers'))

                    if matched and page_candidate:
                        candidate_pages.append(page_candidate)
                        high_confidence_hit = _is_high_confidence_notice_candidate(page_candidate)
                        if first_hit_page is None:
                            first_hit_page = page_num
                            if high_confidence_hit:
                                stop_after_page = min(max_scan_pages, page_num + 1)
                                print(f"    ✅ 第 {page_num} 页高置信命中责令号，继续扫描至第 {stop_after_page} 页")
                            else:
                                stop_after_page = min(max_scan_pages, page_num + scan_window_pages)
                                print(f"    ✅ 第 {page_num} 页首次找到责令号，继续扫描至第 {stop_after_page} 页")
                        elif high_confidence_hit:
                            stop_after_page = min(stop_after_page or max_scan_pages, page_num)

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
                        'notice_candidate_score': page_candidate.get('score') if page_candidate else None,
                        'notice_page_profile': page_candidate.get('page_profile') if page_candidate else {},
                    })

                    if stop_after_page is not None and page_num >= stop_after_page:
                        stopped_early = True
                        break
                    if page_num >= 3 and _has_decisive_notice_candidate(candidate_pages):
                        stopped_early = True
                        print(f"    ✅ 前 {page_num} 页已形成高置信责令号候选，提前停止")
                        break
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
                    stop_condition=lambda page_num, text: bool(stop_pattern.search(apply_ocr_corrections(text))),
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

            def _is_letter_region_usable(text: str) -> bool:
                compact = text.replace('\n', '').replace(' ', '')
                if '律师事务所函' in compact:
                    return True
                if _has_title_fragments(compact, ['律师', '事务所', '所函', '函'], min_hits=2):
                    return True
                return len(compact) >= 6

            def _is_authorization_region_usable(logs: List[Dict], combined_text: str) -> bool:
                compact = combined_text.replace('\n', '').replace(' ', '')
                if '授权委托书' in compact:
                    return True
                if _has_title_fragments(compact, ['授权', '委托', '托书'], min_hits=2):
                    return True
                if logs and logs[0].get('text_length', 0) >= 5:
                    return True
                return len(compact) >= 6

            if doc_type == '申请书':
                for page_num in range(1, total_pages + 1):
                    full_image = region_extractor.extract_full_page(pdf_path, page_num)
                    region_text, page_logs = _collect_region_texts(
                        ocr,
                        region_extractor,
                        pdf_path,
                        page_num,
                        doc_type,
                        full_image=full_image,
                    )
                    corrected_region_text = apply_ocr_corrections(region_text)
                    application_region_results.append({
                        'page_num': page_num,
                        'full_image': full_image,
                        'page_logs': page_logs,
                        'text': corrected_region_text,
                        'duration': sum(item['duration'] for item in page_logs),
                        'boundary': _is_application_boundary(corrected_region_text),
                    })

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
                    needs_fallback, fallback_trigger_reason = _should_fallback_application(
                        page_num,
                        text,
                        detected_boundaries,
                        expected_boundaries,
                        expected_start_pages,
                    )

                    if needs_fallback and _cfg.ocr_allow_full_page_fallback:
                        fallback_used = True
                        full_result = ocr.recognize_full_page_image(
                            item['full_image'],
                            page_num=page_num,
                            method='full_page_fallback',
                            optimize_output=True,
                        )
                        fallback_text = apply_ocr_corrections(full_result.text)
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
                primary_regions = default_regions[:1]
                secondary_regions = default_regions[1:2]

                for page_num in range(1, total_pages + 1):
                    full_image = region_extractor.extract_full_page(pdf_path, page_num)
                    primary_text, primary_logs = _collect_region_texts(
                        ocr,
                        region_extractor,
                        pdf_path,
                        page_num,
                        doc_type,
                        full_image=full_image,
                        region_names=primary_regions,
                    )
                    page_logs = list(primary_logs)
                    combined_text = apply_ocr_corrections(primary_text)

                    if doc_type == '授权书':
                        region_usable = _is_authorization_region_usable(page_logs, combined_text)
                    else:
                        region_usable = _is_letter_region_usable(combined_text)

                    if not region_usable and secondary_regions:
                        secondary_text, secondary_logs = _collect_region_texts(
                            ocr,
                            region_extractor,
                            pdf_path,
                            page_num,
                            doc_type,
                            full_image=full_image,
                            region_names=secondary_regions,
                        )
                        page_logs.extend(secondary_logs)
                        combined_text = apply_ocr_corrections("\n".join(filter(None, [combined_text, secondary_text])))
                        if doc_type == '授权书':
                            region_usable = _is_authorization_region_usable(page_logs, combined_text)
                        else:
                            region_usable = _is_letter_region_usable(combined_text)

                    text = combined_text
                    method = 'region_first'
                    duration = sum(item['duration'] for item in page_logs)
                    marker_detected = bool(doc_cfg.content_marker and doc_cfg.content_marker in combined_text)
                    needs_fallback, fallback_trigger_reason = _should_fallback_company_doc(combined_text, region_usable, marker_detected)

                    if needs_fallback and _cfg.ocr_allow_full_page_fallback:
                        fallback_used = True
                        full_result = ocr.recognize_full_page_image(
                            full_image,
                            page_num=page_num,
                            method='full_page_fallback',
                            optimize_output=True,
                        )
                        fallback_text = apply_ocr_corrections(full_result.text)
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
                        'region_text_length': len(_compact_text(combined_text)),
                        'fallback_used': method == 'full_page_fallback',
                        'fallback_trigger_reason': fallback_trigger_reason if method == 'full_page_fallback' else None,
                        'marker_detected': bool(doc_cfg.content_marker and doc_cfg.content_marker in text),
                        'region_usable': region_usable,
                    })

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
            print(f"  [ERROR] OCR 识别失败: {pdf_path.name}")
            return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'error'}

        post_processor = post_processor or TextPostProcessor()
        processed_pages = []

        for page_data in result['pages']:
            text = page_data.get('text', '')
            text = apply_ocr_corrections(text)
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

        cache_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
        perf = output.get('performance_summary', {})
        slowest_page = perf.get('slowest_page') or {}
        print(
            f"  [OCR] 完成: {pdf_path.name} ({result['total_duration']:.2f}s, "
            f"fallback {output['fallback_pages']}/{output['total_pages']}, "
            f"最慢页 P{slowest_page.get('page', '-')} {slowest_page.get('duration', 0):.2f}s)"
        )
        return output

    except Exception as e:
        print(f"  [ERROR] OCR 处理异常: {pdf_path.name} - {e}")
        return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'error', 'error': str(e)}


def build_real_ocr_cache(input_dir: Path, cache_dir: Path, use_mock: bool = False) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_start = time.perf_counter()
    performance_records: List[Dict] = []

    shared_ocr = None
    shared_region_extractor = None
    shared_post_processor = None

    notice_files = discover_notice_files(input_dir)
    notice_path_map = {path.name: path for path in iter_notice_pdf_paths(input_dir)}

    profile = None
    parallel_workers = 1

    uncached_notice_files = []
    for source_name in notice_files:
        pdf_path = notice_path_map.get(source_name, input_dir / source_name)
        stem = source_name.replace('.pdf', '')
        cache_path = cache_dir / f'{stem}_ultra_result.json'
        if cache_path.exists():
            print(f"  [CACHE] 跳过已有缓存: {source_name}")
            continue
        if pdf_path.exists():
            uncached_notice_files.append((source_name, pdf_path, cache_path))
        else:
            print(f"  [WARN] 文件不存在: {pdf_path}")

    if uncached_notice_files and not use_mock and HAS_OCR:
        if _cfg.ocr_auto_detect_resources:
            profile = detect_system_resources(
                reserve_gb=_cfg.ocr_memory_reserve_gb,
                max_workers=_cfg.ocr_max_parallel_workers,
            )
        else:
            from system_resource import ResourceProfile
            profile = ResourceProfile(
                cpu_count=1,
                total_memory_gb=0,
                available_memory_gb=0,
                recommended_workers=1,
                memory_per_worker_gb=0.55,
                safety_level='manual',
            )
        notice_count = len(uncached_notice_files)
        parallel_workers = profile.recommended_workers if notice_count > 1 else 1

        print(f"\n📄 处理责催文件（逐页识别，找到即停）... 共 {notice_count} 个")
        print(f"  🖥️ 系统资源: {profile}")
        print(f"  ⚙️ 并发配置: {parallel_workers} 个工作进程")

        if parallel_workers > 1 and notice_count > 1:
            worker_args = [
                (str(pdf_path), str(cache_path), '责催')
                for source_name, pdf_path, cache_path in uncached_notice_files
            ]
            completed = 0
            with Pool(processes=parallel_workers, initializer=_worker_init) as pool:
                for result in pool.imap_unordered(_ocr_notice_file_worker, worker_args):
                    completed += 1
                    source = result['source']
                    status = result['status']
                    perf = result.get('performance')
                    if perf:
                        performance_records.append(perf)
                    if status == 'done':
                        dur = perf.get('total_duration', 0) if perf else 0
                        print(f"  ✅ [{completed}/{notice_count}] {source} ({dur:.2f}s)")
                    elif status == 'cached':
                        print(f"  ⏭️ [{completed}/{notice_count}] {source} (已缓存)")
                    elif status == 'error':
                        print(f"  ❌ [{completed}/{notice_count}] {source}: {result.get('error', '未知错误')}")
        else:
            if not use_mock and HAS_OCR:
                shared_ocr, shared_region_extractor = _build_ocr_processors()
                shared_post_processor = TextPostProcessor()
            for source_name, pdf_path, cache_path in uncached_notice_files:
                result = run_real_ocr_on_pdf(
                    pdf_path,
                    cache_path,
                    use_mock=use_mock,
                    is_notice=True,
                    stop_pattern=NOTICE_PATTERN,
                    doc_type='责催',
                    ocr=shared_ocr,
                    region_extractor=shared_region_extractor,
                    post_processor=shared_post_processor,
                )
                performance_records.append(result.get('performance_summary', {
                    'doc_type': '责催',
                    'file_name': pdf_path.name,
                    'page_count': result.get('total_pages', 0),
                    'total_duration': result.get('total_duration', 0),
                    'fallback_pages': result.get('fallback_pages', 0),
                }))
    elif uncached_notice_files:
        if not use_mock and HAS_OCR:
            shared_ocr, shared_region_extractor = _build_ocr_processors()
            shared_post_processor = TextPostProcessor()
        print(f"\n📄 处理责催文件... 共 {len(uncached_notice_files)} 个")
        for source_name, pdf_path, cache_path in uncached_notice_files:
            result = run_real_ocr_on_pdf(
                pdf_path,
                cache_path,
                use_mock=use_mock,
                is_notice=True,
                stop_pattern=NOTICE_PATTERN,
                doc_type='责催',
                ocr=shared_ocr,
                region_extractor=shared_region_extractor,
                post_processor=shared_post_processor,
            )
            performance_records.append(result.get('performance_summary', {
                'doc_type': '责催',
                'file_name': pdf_path.name,
                'page_count': result.get('total_pages', 0),
                'total_duration': result.get('total_duration', 0),
                'fallback_pages': result.get('fallback_pages', 0),
            }))

    other_files = [
        (pdf_name, pdf_name.replace('.pdf', ''))
        for pdf_name in _cfg.source_mapping.values()
    ]

    print("\n📄 处理其他文件...")
    if not use_mock and HAS_OCR and shared_ocr is None:
        shared_ocr, shared_region_extractor = _build_ocr_processors()
        shared_post_processor = TextPostProcessor()
    for filename, stem in other_files:
        pdf_path = input_dir / filename
        cache_path = cache_dir / f'{stem}_ultra_result.json'

        if pdf_path.exists():
            if cache_path.exists():
                print(f"  [CACHE] 跳过已有缓存: {filename}")
                continue
            doc_type = stem if stem in {'申请书', '授权书', '所函'} else None
            result = run_real_ocr_on_pdf(
                pdf_path,
                cache_path,
                use_mock=use_mock,
                doc_type=doc_type,
                ocr=shared_ocr,
                region_extractor=shared_region_extractor,
                post_processor=shared_post_processor,
            )
            performance_records.append(result.get('performance_summary', {
                'doc_type': doc_type,
                'file_name': pdf_path.name,
                'page_count': result.get('total_pages', 0),
                'total_duration': result.get('total_duration', 0),
                'fallback_pages': result.get('fallback_pages', 0),
            }))
        else:
            print(f"  [WARN] 文件不存在: {pdf_path}")

    slowest_files = sorted(
        performance_records,
        key=lambda item: item.get('total_duration', 0),
        reverse=True,
    )[:5]
    performance_summary = {
        'stage': 'ocr_cache_build',
        'total_files': len(performance_records),
        'total_duration': round(time.perf_counter() - cache_start, 4),
        'fallback_pages_total': sum(item.get('fallback_pages', 0) for item in performance_records),
        'region_attempts_total': sum(item.get('region_attempts_total', 0) for item in performance_records),
        'slowest_files': slowest_files,
        'parallelism': {
            'workers': parallel_workers,
            'safety_level': profile.safety_level if profile else 'serial',
            'available_memory_gb': profile.available_memory_gb if profile else 0,
        },
    }
    (cache_dir / 'ocr-cache-performance-summary.json').write_text(
        json.dumps(performance_summary, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    if slowest_files:
        print(f"\n⏱️ OCR缓存阶段完成: {performance_summary['total_duration']:.2f}s, 最慢文件 {slowest_files[0].get('file_name')} {slowest_files[0].get('total_duration', 0):.2f}s")

    return cache_dir


def export_pdf_ranges(source_pdf: Path, ranges: List[Tuple[int, int]], output_dir: Path, target_names: List[str]) -> int:
    created = 0
    with open_pdf_reader(source_pdf) as reader:
        for i, ((start, end), target_name) in enumerate(zip(ranges, target_names)):
            target_path = output_dir / target_name
            if target_path.exists():
                created += 1
                print(f"  ⏭️ 跳过已存在: {target_name}")
                continue

            if start >= len(reader.pages):
                print(f"  ❌ 页码超出范围: {target_name} (起始页 {start} >= 总页数 {len(reader.pages)})")
                continue

            writer = PdfWriter()
            actual_end = min(end, len(reader.pages))
            for page_index in range(start, actual_end):
                writer.add_page(reader.pages[page_index])

            with target_path.open('wb') as file_obj:
                writer.write(file_obj)

            created += 1
            print(f"  ✅ 导出: {target_name} (第 {start+1}-{actual_end} 页)")

    return created


def export_notice_files(sample_root: Path, input_dir: Path, output_dir: Path, output_cache_dir: Path) -> int:
    cases = load_non_litigation_cases(sample_root)

    def get_notice_cache_path(source_filename: str) -> Path:
        return output_cache_dir / f"{Path(source_filename).stem}_ultra_result.json"

    def update_notice_cache_export_metadata(source_filename: str, metadata: Dict):
        cache_path = get_notice_cache_path(source_filename)
        data = safe_load_ocr_cache(cache_path)
        if not data:
            return
        data.update(metadata)
        cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    target_map = {}
    target_notice_map = {}
    for case in cases:
        normalized = normalize_notice_number(case['notice_number'])
        target_name = f"{case['sequence']}-责催-{case['notice_number']}.pdf"
        target_map[normalized] = target_name
        target_notice_map[target_name] = normalized

    notice_files = discover_notice_files(input_dir)
    source_map = detect_notice_source_mapping_from_ocr(output_cache_dir, notice_files)

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
            print(f"    🔁 同根主号匹配: '{detected_notice}' -> '{target_name}'")
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
                print(f"    🔍 模糊匹配: '{detected_notice}' -> '{target_name}' (相似度: {ratio:.1%})")
                print(f"    ⚠️ 模糊匹配需人工确认！已记录到审计日志")

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
                print(f"    ⚠️ 主号识别后按同根目标导出: '{detected_notice}' -> '{target_notice}'")
            update_notice_cache_export_metadata(source_name, export_metadata)

            src = next((path for path in iter_notice_pdf_paths(input_dir) if path.name == source_name), input_dir / source_name)
            dst = output_dir / target_name
            if dst.exists():
                created += 1
                print(f"  ⏭️ 跳过已存在: {target_name}")
                continue
            if src.exists():
                shutil.copy2(src, dst)
                created += 1
                print(f"  ✅ {source_name} -> {target_name}")
                _log_audit('notice_renamed', {
                    'source': source_name,
                    'target': target_name,
                    'match_type': match_type,
                    'detected_notice': detected_notice,
                    'target_notice': target_notice,
                    'same_root_remap': same_root_remap,
                })
            else:
                print(f"  ❌ 源文件不存在: {src}")
                unmatched.append((source_name, detected_notice, "源文件不存在"))
        else:
            print(f"  ❌ 无法匹配: {source_name} (识别到 '{detected_notice}')")
            unmatched.append((source_name, detected_notice, "无匹配台账"))
            _log_audit('match_failed', {
                'source': source_name,
                'detected': detected_notice,
            })

    if unmatched:
        print(f"\n  ⚠️ 未匹配文件汇总 ({len(unmatched)} 个):")
        for source_name, notice, reason in unmatched:
            print(f"    - {source_name}: {reason} (识别: '{notice}')")

    return created


def export_application_files(input_dir: Path, output_dir: Path, target_names: List[str], output_cache_dir: Path) -> int:
    source_pdf = input_dir / SOURCE_MAPPING['输出文件（申请书）']

    if not source_pdf.exists():
        print(f"  ❌ 申请书文件不存在: {source_pdf}")
        return 0

    total_pages = inspect_pdf_page_count(source_pdf)
    expected_cases = len(target_names)

    print(f"  📄 申请书: {total_pages} 页，台账期望 {expected_cases} 个案件")

    ranges = detect_application_page_ranges_by_ocr(output_cache_dir, total_pages, expected_cases)

    if len(ranges) != expected_cases:
        print(f"  ℹ️ 按实际识别到 {len(ranges)} 个案件处理（台账 {expected_cases} 个）")

    return export_pdf_ranges(source_pdf, ranges, output_dir, target_names)


def export_company_named_files(input_dir: Path, output_dir: Path, target_names: List[str],
                               output_cache_dir: Path, source_name: str, marker: str) -> int:
    source_pdf = input_dir / source_name

    if not source_pdf.exists():
        print(f"  ❌ {source_name} 文件不存在")
        return 0

    total_pages = inspect_pdf_page_count(source_pdf)
    expected_count = len(target_names)
    doc_type = '授权书' if '授权' in marker else '所函'

    print(f"  📄 {source_name}: {total_pages} 页，期望 {expected_count} 个公司")

    ranges = detect_page_ranges(total_pages, expected_count, doc_type)

    return export_pdf_ranges(source_pdf, ranges, output_dir, target_names)


def export_non_litigation_standard_outputs(sample_root: Path, input_dir: Path, output_root: Path, ocr_cache_dir: Path | None = None) -> Dict:
    output_root.mkdir(parents=True, exist_ok=True)
    tree = build_expected_output_tree(sample_root)
    created_count = 0
    cache_dir = ocr_cache_dir or (input_dir.parent / 'output')
    _audit_log.clear()

    print("\n📦 开始导出文件...")
    print("=" * 60)

    export_tasks = []
    for folder_name, target_names in tree.items():
        folder_path = output_root / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        print(f"\n📁 {folder_name} ({len(target_names)} 个文件)")

        if folder_name == _cfg.directory_mapping['责催']:
            count = export_notice_files(sample_root, input_dir, folder_path, cache_dir)
            export_tasks.append(('责催', count))

        elif folder_name == _cfg.directory_mapping['申请书']:
            count = export_application_files(input_dir, folder_path, target_names, cache_dir)
            export_tasks.append(('申请书', count))

        elif folder_name == _cfg.directory_mapping['授权书']:
            count = export_company_named_files(input_dir, folder_path, target_names, cache_dir, _cfg.doc_type_map['授权书'].source_pdf, _cfg.doc_type_map['授权书'].content_marker)
            export_tasks.append(('授权书', count))

        elif folder_name == _cfg.directory_mapping['所函']:
            count = export_company_named_files(input_dir, folder_path, target_names, cache_dir, _cfg.doc_type_map['所函'].source_pdf, _cfg.doc_type_map['所函'].content_marker)
            export_tasks.append(('所函', count))

    created_count = sum(count for _, count in export_tasks)

    audit_path = output_root / 'audit-log.json'
    audit_path.write_text(json.dumps(_audit_log, ensure_ascii=False, indent=2), encoding='utf-8')
    if _audit_log:
        print(f"\n📋 审计日志已保存: {audit_path} ({len(_audit_log)} 条)")

    print("\n" + "=" * 60)
    print(f"✅ 导出完成: {created_count} 个文件")

    return {
        'created_count': created_count,
        'output_root': str(output_root),
        'ocr_cache_dir': str(cache_dir),
        'tree': tree,
    }
