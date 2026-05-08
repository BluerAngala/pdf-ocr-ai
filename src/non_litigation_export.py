#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
非诉组 PDF 导出模块

处理逻辑：
1. 责催证据文件：每个 PDF 就是一个独立案件，不切割，直接重命名
2. 申请书：固定 2 页/案件，按顺序切割
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

from pypdf import PdfReader, PdfWriter

from non_litigation_output_plan import build_expected_output_tree
from non_litigation_product import load_non_litigation_cases
from text_postprocessor import TextPostProcessor

# 导入 OCR 工具
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))

try:
    from pdf_ocr_ultra import UltraFastOCR, OCRConfig
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("[WARN] pdf_ocr_ultra 导入失败，将使用 Mock OCR")


SOURCE_MAPPING = {
    '输出文件（责催）': ['1.pdf', '2.pdf', '3.pdf'],
    '输出文件（申请书）': '申请书.pdf',
    '输出文件（授权书）': '授权书.pdf',
    '输出文件（所函）': '所函.pdf',
}

NON_LITIGATION_RESULT_DIRNAME = 'non-litigation-results'
NON_LITIGATION_TEMP_DIRNAME = 'non-litigation'
NON_LITIGATION_INPUT_DIRNAME = 'non-litigation'

# 责令号匹配正则
NOTICE_PATTERN = re.compile(r'穗公积金中心[^\s，。；、《》]*?责字[〔\[(]\d{4}[〕\])]\d+(?:-\d+)?号')

# OCR 纠错词库 - 非诉组专用
NON_LITIGATION_CORRECTIONS = {
    '责行': '责令',
    '责成': '责令',
    '公积全': '公积金',
    '住房公积全': '住房公积金',
    '公基金': '公积金',
    '住方公积金': '住房公积金',
    '岭南律师': '岭南律师事务所',
    '授权委拖书': '授权委托书',
    '授校委托书': '授权委托书',
    '强制申请书': '强制执行申请书',
}

# 固定页数配置
PAGES_PER_CASE = {
    '申请书': 2,  # 申请书固定2页/案件
    '授权书': 1,  # 授权书固定1页/公司
    '所函': 1,    # 所函固定1页/公司
}


def apply_ocr_corrections(text: str) -> str:
    """应用 OCR 纠错词库"""
    for wrong, correct in NON_LITIGATION_CORRECTIONS.items():
        text = text.replace(wrong, correct)
    return text


def normalize_notice_number(text: str) -> str:
    """统一责令号格式"""
    text = text.replace(' ', '')
    text = text.replace('(', '〔').replace(')', '〕')
    text = text.replace('（', '〔').replace('）', '〕')
    text = text.replace('[', '〔').replace(']', '〕')
    return text


def fuzzy_match_notice(detected: str, target_map: Dict[str, str], threshold: float = 0.85) -> Optional[str]:
    """模糊匹配责令号"""
    best_match = None
    best_ratio = 0

    for target in target_map.keys():
        ratio = SequenceMatcher(None, detected, target).ratio()
        if ratio > best_ratio and ratio >= threshold:
            best_ratio = ratio
            best_match = target_map[target]

    return best_match, best_ratio if best_match else (None, 0)


def safe_load_ocr_cache(ocr_json_path: Path) -> Optional[Dict]:
    """安全加载 OCR 缓存"""
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
        except:
            pass
        return None

    except Exception as e:
        print(f"  ❌ 读取缓存失败: {ocr_json_path.name} - {e}")
        return None


def inspect_pdf_page_count(pdf_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
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
    for source_name in ['1.pdf', '2.pdf', '3.pdf', '申请书.pdf', '授权书.pdf', '所函.pdf']:
        legacy_path = project_root / 'input' / source_name
        target_path = input_root / source_name
        if legacy_path.exists() and not target_path.exists():
            shutil.move(str(legacy_path), str(target_path))
    return input_root


def normalize_company_name_for_matching(value: str) -> str:
    text = str(value).strip()
    text = text.replace('\n', '').replace('\r', '').replace(' ', '')
    text = text.replace('（', '(').replace('）', ')')
    return text


def detect_application_page_ranges_fixed(total_pages: int, expected_cases: int) -> List[Tuple[int, int]]:
    """
    申请书固定 2 页/案件切割

    Args:
        total_pages: PDF 总页数
        expected_cases: 期望的案件数量（从台账读取）

    Returns:
        页码范围列表，如 [(0,2), (2,4), (4,6)]
    """
    pages_per_case = PAGES_PER_CASE['申请书']

    # 验证页数是否匹配
    expected_pages = expected_cases * pages_per_case
    if total_pages != expected_pages:
        print(f"  ⚠️ 申请书页数不匹配: 实际 {total_pages} 页，期望 {expected_pages} 页 ({expected_cases} 案件 × {pages_per_case} 页)")

    ranges = []
    for i in range(expected_cases):
        start = i * pages_per_case
        end = min(start + pages_per_case, total_pages)
        ranges.append((start, end))

    return ranges


def detect_fixed_page_ranges(total_pages: int, expected_count: int, doc_type: str) -> List[Tuple[int, int]]:
    """
    固定页数切割（授权书、所函）

    Args:
        total_pages: PDF 总页数
        expected_count: 期望的数量（公司数）
        doc_type: 文档类型 ('授权书' 或 '所函')

    Returns:
        页码范围列表
    """
    pages_per_item = PAGES_PER_CASE.get(doc_type, 1)

    # 验证页数是否匹配
    expected_pages = expected_count * pages_per_item
    if total_pages != expected_pages:
        print(f"  ⚠️ {doc_type}页数不匹配: 实际 {total_pages} 页，期望 {expected_pages} 页 ({expected_count} 个 × {pages_per_item} 页)")

    ranges = []
    for i in range(expected_count):
        start = i * pages_per_item
        end = min(start + pages_per_item, total_pages)
        ranges.append((start, end))

    return ranges


def detect_notice_source_mapping_from_ocr(output_cache_dir: Path) -> Dict[str, str]:
    """
    从 OCR 结果中识别责催文件的责令号

    Returns:
        {source_filename: detected_notice_number}
    """
    mapping: Dict[str, str] = {}
    for source_name in SOURCE_MAPPING['输出文件（责催）']:
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
        else:
            print(f"  ⚠️ {source_name}: 未识别到责令号")

    return mapping


def build_mock_ocr_cache(sample_root: Path, cache_dir: Path) -> Path:
    """构建 Mock OCR 缓存（用于测试）"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    standard_root = sample_root / '对应输出文件（标准版）'

    # 申请书：固定 2 页/案件
    application_pages = []
    for index, pdf_path in enumerate(sorted((standard_root / '输出文件（申请书）').glob('*.pdf'))):
        page_count = inspect_pdf_page_count(pdf_path)
        for page_offset in range(page_count):
            page_number = len(application_pages) + 1
            text = '普通页'
            if page_offset == 0:
                text = f'强制执行申请书\n名称：案子{index + 1}'
            application_pages.append({'page': page_number, 'text': text})
    (cache_dir / '申请书_ultra_result.json').write_text(
        json.dumps({'pages': application_pages, 'total_pages': len(application_pages), 'filename': '申请书.pdf'}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    # 授权书、所函：固定 1 页/公司
    for filename, marker, folder in [
        ('授权书_ultra_result.json', '授权委托书', '输出文件（授权书）'),
        ('所函_ultra_result.json', '广东岭南律师事务所函', '输出文件（所函）'),
    ]:
        pages = []
        for index, pdf_path in enumerate(sorted((standard_root / folder).glob('*.pdf'))):
            company_name = pdf_path.stem
            pages.append({'page': index + 1, 'text': f'{marker}\n{company_name}'})
        (cache_dir / filename).write_text(
            json.dumps({'pages': pages, 'total_pages': len(pages), 'filename': filename.replace('_ultra_result.json', '.pdf')}, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    # 责催文件：每个 PDF 就是一个案件
    notice_files = sorted((standard_root / '输出文件（责催）').glob('*.pdf'))
    notice_numbers = [pdf_path.stem.split('-责催-')[1] for pdf_path in notice_files]
    source_names = ['1', '2', '3']
    # 按顺序对应
    for source_name, notice_number in zip(source_names, notice_numbers):
        normalized_number = normalize_notice_number(notice_number)
        payload = {
            'pages': [{'page': 1, 'text': normalized_number}],
            'total_pages': 1,
            'filename': f'{source_name}.pdf',
        }
        (cache_dir / f'{source_name}_ultra_result.json').write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    return cache_dir


def run_real_ocr_on_pdf(pdf_path: Path, cache_path: Path, use_mock: bool = False, 
                        is_notice: bool = False, stop_pattern: Optional[re.Pattern] = None) -> Dict:
    """
    对 PDF 运行真实 OCR 识别
    
    Args:
        pdf_path: PDF 文件路径
        cache_path: 缓存文件路径
        use_mock: 是否使用 Mock 数据
        is_notice: 是否是责催文件（使用逐页识别优化）
        stop_pattern: 停止条件正则（找到即停）
    """
    if use_mock or not HAS_OCR:
        if cache_path.exists():
            return safe_load_ocr_cache(cache_path) or {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'mock'}
        return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'mock'}

    # 检查缓存是否已存在
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
        
        # 责催文件使用逐页识别优化（找到责令号即停）
        if is_notice and stop_pattern:
            print(f"  [OCR] 使用逐页识别模式（找到即停）")
            
            def stop_condition(page_num: int, text: str) -> bool:
                """停止条件：找到责令号"""
                if stop_pattern.search(text):
                    print(f"    ✅ 第 {page_num} 页找到责令号")
                    return True
                return False
            
            result = ocr.process_pdf_pages_sequential(
                str(pdf_path), 
                stop_condition=stop_condition,
                max_pages=3  # 最多识别前3页
            )
        else:
            # 其他文件使用完整识别
            result = ocr.process_pdf(str(pdf_path), force_ocr=False)

        if result is None:
            print(f"  [ERROR] OCR 识别失败: {pdf_path.name}")
            return {'pages': [], 'total_pages': 0, 'filename': pdf_path.name, 'method': 'error'}

        # 应用后处理
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
    """构建真实 OCR 缓存"""
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 责催文件（使用逐页识别优化）
    notice_files = [
        ('1.pdf', '1'),
        ('2.pdf', '2'),
        ('3.pdf', '3'),
    ]
    
    print("\n📄 处理责催文件（逐页识别，找到即停）...")
    for filename, stem in notice_files:
        pdf_path = input_dir / filename
        cache_path = cache_dir / f'{stem}_ultra_result.json'

        if pdf_path.exists():
            run_real_ocr_on_pdf(
                pdf_path, 
                cache_path, 
                use_mock=use_mock,
                is_notice=True,
                stop_pattern=NOTICE_PATTERN
            )
        else:
            print(f"  [WARN] 文件不存在: {pdf_path}")

    # 其他文件（申请书、授权书、所函）
    other_files = [
        ('申请书.pdf', '申请书'),
        ('授权书.pdf', '授权书'),
        ('所函.pdf', '所函'),
    ]
    
    print("\n📄 处理其他文件...")
    for filename, stem in other_files:
        pdf_path = input_dir / filename
        cache_path = cache_dir / f'{stem}_ultra_result.json'

        if pdf_path.exists():
            run_real_ocr_on_pdf(pdf_path, cache_path, use_mock=use_mock)
        else:
            print(f"  [WARN] 文件不存在: {pdf_path}")

    return cache_dir


def export_pdf_ranges(source_pdf: Path, ranges: List[Tuple[int, int]], output_dir: Path, target_names: List[str]) -> int:
    """按页码范围导出 PDF"""
    reader = PdfReader(str(source_pdf))
    created = 0

    for i, ((start, end), target_name) in enumerate(zip(ranges, target_names)):
        writer = PdfWriter()
        actual_end = min(end, len(reader.pages))

        if start >= len(reader.pages):
            print(f"  ❌ 页码超出范围: {target_name} (起始页 {start} >= 总页数 {len(reader.pages)})")
            continue

        for page_index in range(start, actual_end):
            writer.add_page(reader.pages[page_index])

        target_path = output_dir / target_name
        with target_path.open('wb') as file_obj:
            writer.write(file_obj)

        created += 1
        print(f"  ✅ 导出: {target_name} (第 {start+1}-{actual_end} 页)")

    return created


def export_notice_files(sample_root: Path, input_dir: Path, output_dir: Path, output_cache_dir: Path) -> int:
    """
    导出责催文件
    每个 PDF 就是一个独立案件，不切割，直接重命名
    """
    cases = load_non_litigation_cases(sample_root)

    # 构建 target_map（使用统一格式）
    target_map = {}
    for case in cases:
        normalized = normalize_notice_number(case['notice_number'])
        target_map[normalized] = f"{case['sequence']}-责催-{case['notice_number']}.pdf"

    source_map = detect_notice_source_mapping_from_ocr(output_cache_dir)

    created = 0
    unmatched = []

    for source_name, detected_notice in source_map.items():
        target_name = target_map.get(detected_notice)

        # 如果精确匹配失败，尝试模糊匹配
        if not target_name:
            target_name, ratio = fuzzy_match_notice(detected_notice, target_map)
            if target_name:
                print(f"    🔍 模糊匹配: '{detected_notice}' -> '{target_name}' (相似度: {ratio:.1%})")

        if target_name:
            src = input_dir / source_name
            dst = output_dir / target_name
            if src.exists():
                shutil.copy2(src, dst)
                created += 1
                print(f"  ✅ {source_name} -> {target_name}")
            else:
                print(f"  ❌ 源文件不存在: {src}")
                unmatched.append((source_name, detected_notice, "源文件不存在"))
        else:
            print(f"  ❌ 无法匹配: {source_name} (识别到 '{detected_notice}')")
            unmatched.append((source_name, detected_notice, "无匹配台账"))

    # 报告未匹配的文件
    if unmatched:
        print(f"\n  ⚠️ 未匹配文件汇总 ({len(unmatched)} 个):")
        for source_name, notice, reason in unmatched:
            print(f"    - {source_name}: {reason} (识别: '{notice}')")

    return created


def export_application_files(input_dir: Path, output_dir: Path, target_names: List[str], output_cache_dir: Path) -> int:
    """
    导出申请书
    固定 2 页/案件，按顺序切割
    """
    source_pdf = input_dir / SOURCE_MAPPING['输出文件（申请书）']

    if not source_pdf.exists():
        print(f"  ❌ 申请书文件不存在: {source_pdf}")
        return 0

    # 获取总页数
    total_pages = inspect_pdf_page_count(source_pdf)
    expected_cases = len(target_names)

    print(f"  📄 申请书: {total_pages} 页，期望 {expected_cases} 个案件")

    # 使用固定页数切割
    ranges = detect_application_page_ranges_fixed(total_pages, expected_cases)

    # 验证切割结果
    if len(ranges) != expected_cases:
        print(f"  ⚠️ 切割结果不匹配: 生成 {len(ranges)} 个范围，期望 {expected_cases} 个")

    return export_pdf_ranges(source_pdf, ranges, output_dir, target_names)


def export_company_named_files(input_dir: Path, output_dir: Path, target_names: List[str],
                               output_cache_dir: Path, source_name: str, marker: str) -> int:
    """
    导出授权书/所函
    固定 1 页/公司，按顺序切割
    """
    source_pdf = input_dir / source_name

    if not source_pdf.exists():
        print(f"  ❌ {source_name} 文件不存在")
        return 0

    # 获取总页数
    total_pages = inspect_pdf_page_count(source_pdf)
    expected_count = len(target_names)
    doc_type = '授权书' if '授权' in marker else '所函'

    print(f"  📄 {source_name}: {total_pages} 页，期望 {expected_count} 个公司")

    # 使用固定页数切割
    ranges = detect_fixed_page_ranges(total_pages, expected_count, doc_type)

    return export_pdf_ranges(source_pdf, ranges, output_dir, target_names)


def export_non_litigation_standard_outputs(sample_root: Path, input_dir: Path, output_root: Path, ocr_cache_dir: Path | None = None) -> Dict:
    """导出非诉组标准输出"""
    output_root.mkdir(parents=True, exist_ok=True)
    tree = build_expected_output_tree(sample_root)
    created_count = 0
    cache_dir = ocr_cache_dir or (input_dir.parent / 'output')

    print("\n📦 开始导出文件...")
    print("=" * 60)

    for folder_name, target_names in tree.items():
        folder_path = output_root / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        print(f"\n📁 {folder_name} ({len(target_names)} 个文件)")

        if folder_name == '输出文件（责催）':
            created_count += export_notice_files(sample_root, input_dir, folder_path, cache_dir)

        elif folder_name == '输出文件（申请书）':
            created_count += export_application_files(input_dir, folder_path, target_names, cache_dir)

        elif folder_name == '输出文件（授权书）':
            created_count += export_company_named_files(input_dir, folder_path, target_names, cache_dir, '授权书.pdf', '授权委托书')

        elif folder_name == '输出文件（所函）':
            created_count += export_company_named_files(input_dir, folder_path, target_names, cache_dir, '所函.pdf', '广东岭南律师事务所函')

    print("\n" + "=" * 60)
    print(f"✅ 导出完成: {created_count} 个文件")

    return {
        'created_count': created_count,
        'output_root': str(output_root),
        'ocr_cache_dir': str(cache_dir),
        'tree': tree,
    }
