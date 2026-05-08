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
import re
import shutil
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from contextlib import contextmanager

from pypdf import PdfReader, PdfWriter

from non_litigation_output_plan import build_expected_output_tree
from non_litigation_product import load_non_litigation_cases
from text_postprocessor import TextPostProcessor

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


def fuzzy_match_notice(detected: str, target_map: Dict[str, str], threshold: float = 0.85) -> Tuple[Optional[str], float]:
    best_match = None
    best_ratio = 0

    for target in target_map.keys():
        ratio = SequenceMatcher(None, detected, target).ratio()
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
            f'  ⚠️ {doc_type}页数不匹配: 实际 {total_pages} 页，期望 {expected_pages} 页 '
            f'({expected_count} 个 × {pages_per_item} 页)。'
            f'请检查扫描件是否有缺页或多页。'
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
        print(f"  ⚠️ OCR 检测到 {len(boundary_pages)} 个边界，期望 {expected_cases} 个，fallback 到固定页数")
    else:
        print(f"  ⚠️ OCR 未检测到申请书边界，fallback 到固定 {PAGES_PER_CASE['申请书']} 页/案件")

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
        [f.name for f in input_dir.glob('*.pdf')
         if f.name not in SOURCE_MAPPING.values()],
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
    for source_name in notice_files:
        stem = source_name.replace('.pdf', '')
        json_path = output_cache_dir / f'{stem}_ultra_result.json'
        data = safe_load_ocr_cache(json_path)

        if not data:
            continue

        numbers = []
        for page in data['pages']:
            text = page.get('text', '').replace('\n', ' ')
            matches = NOTICE_PATTERN.findall(text)
            numbers.extend(matches)

        if numbers:
            normalized = normalize_notice_number(numbers[0])
            mapping[source_name] = normalized
            print(f"  ✅ {source_name}: 识别到责令号 '{normalized}'")
            if len(numbers) > 1:
                print(f"    ℹ️ 注意: 识别到 {len(numbers)} 个责令号，使用第一个")
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
                        is_notice: bool = False, stop_pattern: Optional[re.Pattern] = None) -> Dict:
    if use_mock or not HAS_OCR:
        if cache_path.exists():
            return safe_load_ocr_cache(cache_path) or {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'mock'}
        return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'mock'}

    existing = safe_load_ocr_cache(cache_path)
    if existing:
        print(f"  [CACHE] 使用已有 OCR 缓存: {cache_path.name}")
        return existing

    print(f"  [OCR] 开始识别: {pdf_path.name}")

    config = OCRConfig(
        dpi=250,
        max_image_size=1024,
        parallel_workers=4,
    )

    try:
        ocr = UltraFastOCR(config)

        if is_notice and stop_pattern:
            print(f"  [OCR] 使用逐页识别模式（找到即停）")

            def stop_condition(page_num: int, text: str) -> bool:
                corrected = apply_ocr_corrections(text)
                if stop_pattern.search(corrected):
                    print(f"    ✅ 第 {page_num} 页找到责令号")
                    return True
                return False

            result = ocr.process_pdf_pages_sequential(
                str(pdf_path),
                stop_condition=stop_condition,
            )
        else:
            result = ocr.process_pdf(str(pdf_path), force_ocr=False)

        if result is None:
            print(f"  [ERROR] OCR 识别失败: {pdf_path.name}")
            return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'error'}

        post_processor = TextPostProcessor()
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
            })

        output = {
            'pages': processed_pages,
            'total_pages': result['total_pages'],
            'filename': result['filename'],
            'method': result['method'],
            'total_duration': result['total_duration'],
        }

        cache_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [OCR] 完成: {pdf_path.name} ({result['total_duration']:.2f}s)")
        return output

    except Exception as e:
        print(f"  [ERROR] OCR 处理异常: {pdf_path.name} - {e}")
        return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'error', 'error': str(e)}


def build_real_ocr_cache(input_dir: Path, cache_dir: Path, use_mock: bool = False) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)

    notice_files = discover_notice_files(input_dir)

    print(f"\n📄 处理责催文件（逐页识别，找到即停）... 共 {len(notice_files)} 个")
    for source_name in notice_files:
        pdf_path = input_dir / source_name
        stem = source_name.replace('.pdf', '')
        cache_path = cache_dir / f'{stem}_ultra_result.json'

        if pdf_path.exists():
            if cache_path.exists():
                print(f"  [CACHE] 跳过已有缓存: {source_name}")
                continue
            run_real_ocr_on_pdf(
                pdf_path,
                cache_path,
                use_mock=use_mock,
                is_notice=True,
                stop_pattern=NOTICE_PATTERN,
            )
        else:
            print(f"  [WARN] 文件不存在: {pdf_path}")

    other_files = [
        (pdf_name, pdf_name.replace('.pdf', ''))
        for pdf_name in _cfg.source_mapping.values()
    ]

    print("\n📄 处理其他文件...")
    for filename, stem in other_files:
        pdf_path = input_dir / filename
        cache_path = cache_dir / f'{stem}_ultra_result.json'

        if pdf_path.exists():
            if cache_path.exists():
                print(f"  [CACHE] 跳过已有缓存: {filename}")
                continue
            run_real_ocr_on_pdf(pdf_path, cache_path, use_mock=use_mock)
        else:
            print(f"  [WARN] 文件不存在: {pdf_path}")

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

    target_map = {}
    for case in cases:
        normalized = normalize_notice_number(case['notice_number'])
        target_map[normalized] = f"{case['sequence']}-责催-{case['notice_number']}.pdf"

    notice_files = discover_notice_files(input_dir)
    source_map = detect_notice_source_mapping_from_ocr(output_cache_dir, notice_files)

    created = 0
    unmatched = []

    for source_name, detected_notice in source_map.items():
        target_name = target_map.get(detected_notice)

        if target_name:
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
            src = input_dir / source_name
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

    print(f"  📄 申请书: {total_pages} 页，期望 {expected_cases} 个案件")

    ranges = detect_application_page_ranges_by_ocr(output_cache_dir, total_pages, expected_cases)

    if len(ranges) != expected_cases:
        print(f"  ⚠️ 切割结果不匹配: 生成 {len(ranges)} 个范围，期望 {expected_cases} 个")

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

    for folder_name, target_names in tree.items():
        folder_path = output_root / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        print(f"\n📁 {folder_name} ({len(target_names)} 个文件)")

        if folder_name == _cfg.directory_mapping['责催']:
            created_count += export_notice_files(sample_root, input_dir, folder_path, cache_dir)

        elif folder_name == _cfg.directory_mapping['申请书']:
            created_count += export_application_files(input_dir, folder_path, target_names, cache_dir)

        elif folder_name == _cfg.directory_mapping['授权书']:
            created_count += export_company_named_files(input_dir, folder_path, target_names, cache_dir, _cfg.doc_type_map['授权书'].source_pdf, _cfg.doc_type_map['授权书'].content_marker)

        elif folder_name == _cfg.directory_mapping['所函']:
            created_count += export_company_named_files(input_dir, folder_path, target_names, cache_dir, _cfg.doc_type_map['所函'].source_pdf, _cfg.doc_type_map['所函'].content_marker)

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
