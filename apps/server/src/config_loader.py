#!/usr/bin/env python3

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from paths import ROOT

_CONFIG_CACHE: Optional[dict] = None
_CONFIG_PATH = ROOT / 'config.yaml'


def _load_config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            _CONFIG_CACHE = yaml.safe_load(f)
    return _CONFIG_CACHE


def reload_config(path: Optional[Path] = None):
    global _CONFIG_CACHE, _CONFIG_PATH
    if path:
        _CONFIG_PATH = path
    _CONFIG_CACHE = None
    _load_config()


@dataclass
class DocTypeConfig:
    key: str
    source_pdf: Optional[str]
    output_dir: str
    pages_per_case: Optional[int]
    boundary_keywords: List[str]
    validation_keywords: List[str]
    filename_pattern: str
    is_notice: bool
    content_marker: Optional[str] = None


@dataclass
class NonLitigationConfig:
    doc_types: List[DocTypeConfig] = field(default_factory=list)
    doc_type_map: Dict[str, DocTypeConfig] = field(default_factory=dict)

    source_mapping: Dict[str, str] = field(default_factory=dict)
    directory_mapping: Dict[str, str] = field(default_factory=dict)
    pages_per_case: Dict[str, int] = field(default_factory=dict)
    boundary_keywords: Dict[str, List[str]] = field(default_factory=dict)

    notice_pattern: re.Pattern = field(default=None)
    notice_doc_type: Optional[DocTypeConfig] = None

    ocr_corrections: List[Tuple[str, str]] = field(default_factory=list)
    company_name_corrections: List[Tuple[str, str]] = field(default_factory=list)

    excel_min_columns: int = 5
    excel_column_original_notice: int = 1
    excel_column_renamed_notice: int = 2
    excel_column_company_name: int = 4
    excel_filter_original_notice: str = '责字'
    excel_filter_renamed_notice: str = '责催-'

    fuzzy_match_threshold: float = 0.85
    text_quality: Dict[str, Dict[str, int]] = field(default_factory=dict)

    ocr_dpi: int = 250
    ocr_max_image_size: int = 1024
    ocr_parallel_workers: int = 4
    ocr_small_pdf_page_threshold: int = 6
    ocr_enable_region_first: bool = True
    ocr_allow_full_page_fallback: bool = True
    ocr_region_dpi: int = 200
    ocr_region_max_image_size: int = 900
    ocr_doc_regions: Dict[str, List[str]] = field(default_factory=dict)
    notice_scan_window_pages: int = 2
    notice_scan_max_pages: int = 6
    notice_region_fallback_min_text_length: int = 8
    application_region_fallback_min_text_length: int = 5
    company_doc_region_fallback_min_text_length: int = 6
    ocr_skip_blank_pages: bool = True
    ocr_blank_page_threshold: float = 0.02
    ocr_auto_detect_resources: bool = True
    ocr_max_parallel_workers: int = 4
    ocr_memory_reserve_gb: float = 1.5

    result_dirname: str = 'non-litigation-results'
    temp_dirname: str = 'non-litigation'
    input_dirname: str = 'non-litigation'
    excel_filename: str = '台账及命名规则.xlsx'
    standard_output_dirname: str = '对应输出文件（标准版）'
    standard_output_subdirs: Dict[str, str] = field(default_factory=dict)
    audit_log_filename: str = 'audit-log.json'

    company_keywords: List[str] = field(default_factory=list)
    document_types: List[str] = field(default_factory=list)
    noise_prefixes: List[str] = field(default_factory=list)
    decision_number_range_max_spread: int = 20
    decision_id_types: str = '责字|行审|民初|刑初|执字'

    mock_noise_samples: List[str] = field(default_factory=list)

    notice_number_range_pattern: Optional[re.Pattern] = None
    single_decision_number_pattern: Optional[re.Pattern] = None
    
    # 原始配置字典（用于访问其他模块的配置）
    raw_config: Dict = field(default_factory=dict)


def load_config() -> NonLitigationConfig:
    raw = _load_config()
    cfg = NonLitigationConfig()

    for dt_raw in raw.get('doc_types', []):
        dt = DocTypeConfig(
            key=dt_raw['key'],
            source_pdf=dt_raw.get('source_pdf'),
            output_dir=dt_raw.get('output_dir', ''),
            pages_per_case=dt_raw.get('pages_per_case'),
            boundary_keywords=dt_raw.get('boundary_keywords', []),
            validation_keywords=dt_raw.get('validation_keywords', []),
            filename_pattern=dt_raw.get('filename_pattern', ''),
            is_notice=dt_raw.get('is_notice', False),
            content_marker=dt_raw.get('content_marker'),
        )
        cfg.doc_types.append(dt)
        cfg.doc_type_map[dt.key] = dt
        if dt.source_pdf:
            cfg.source_mapping[dt.output_dir] = dt.source_pdf
        cfg.directory_mapping[dt.key] = dt.output_dir
        if dt.pages_per_case is not None:
            cfg.pages_per_case[dt.key] = dt.pages_per_case
        if dt.boundary_keywords:
            cfg.boundary_keywords[dt.key] = dt.boundary_keywords

    for dt in cfg.doc_types:
        if dt.is_notice:
            cfg.notice_doc_type = dt
            break

    patterns = raw.get('regex_patterns', {})
    notice_re = patterns.get('notice_number', '')
    if notice_re:
        cfg.notice_pattern = re.compile(notice_re)

    range_re = patterns.get('decision_number_range', '')
    if range_re:
        cfg.notice_number_range_pattern = re.compile(range_re)

    single_re = patterns.get('single_decision_number', '')
    if single_re:
        cfg.single_decision_number_pattern = re.compile(single_re)

    cfg.decision_id_types = patterns.get('decision_id_types', '责字|行审|民初|刑初|执字')

    ocr_corr = raw.get('ocr_corrections', {})
    cfg.ocr_corrections = [
        (item['wrong'], item['correct'])
        for item in ocr_corr.get('non_litigation', [])
    ]
    cfg.company_name_corrections = [
        (item['pattern'], item['replacement'])
        for item in ocr_corr.get('company_name_corrections', [])
    ]

    excel = raw.get('excel_parsing', {})
    cfg.excel_min_columns = excel.get('min_columns', 5)
    cfg.excel_column_original_notice = excel.get('column_original_notice', 1)
    cfg.excel_column_renamed_notice = excel.get('column_renamed_notice', 2)
    cfg.excel_column_company_name = excel.get('column_company_name', 4)
    filters = excel.get('filter_keywords', {})
    cfg.excel_filter_original_notice = filters.get('original_notice', '责字')
    cfg.excel_filter_renamed_notice = filters.get('renamed_notice', '责催-')

    validation = raw.get('validation', {})
    cfg.fuzzy_match_threshold = validation.get('fuzzy_match_threshold', 0.85)
    cfg.text_quality = validation.get('text_quality', {})

    ocr = raw.get('ocr', {})
    ocr_engine = ocr.get('engine', {})
    cfg.ocr_dpi = ocr_engine.get('dpi', 250)
    cfg.ocr_max_image_size = ocr_engine.get('max_image_size', 1024)
    cfg.ocr_parallel_workers = ocr_engine.get('parallel_workers', 4)
    cfg.ocr_small_pdf_page_threshold = ocr_engine.get('small_pdf_page_threshold', 6)

    optimization = ocr.get('optimization', {})
    cfg.ocr_enable_region_first = optimization.get('enable_region_first', True)
    cfg.ocr_allow_full_page_fallback = optimization.get('allow_full_page_fallback', True)
    cfg.ocr_region_dpi = optimization.get('region_dpi', 200)
    cfg.ocr_region_max_image_size = optimization.get('region_max_image_size', 900)
    cfg.ocr_doc_regions = optimization.get('doc_regions', {})
    cfg.notice_scan_window_pages = optimization.get('notice_scan_window_pages', 2)
    cfg.notice_scan_max_pages = optimization.get('notice_scan_max_pages', 6)
    cfg.notice_region_fallback_min_text_length = optimization.get('notice_region_fallback_min_text_length', 8)
    cfg.application_region_fallback_min_text_length = optimization.get('application_region_fallback_min_text_length', 5)
    cfg.company_doc_region_fallback_min_text_length = optimization.get('company_doc_region_fallback_min_text_length', 6)
    cfg.ocr_skip_blank_pages = optimization.get('skip_blank_pages', True)
    cfg.ocr_blank_page_threshold = optimization.get('blank_page_threshold', 0.02)

    parallelism = ocr.get('parallelism', {})
    cfg.ocr_auto_detect_resources = parallelism.get('auto_detect_resources', True)
    cfg.ocr_max_parallel_workers = parallelism.get('max_parallel_workers', 4)
    cfg.ocr_memory_reserve_gb = parallelism.get('memory_reserve_gb', 1.5)

    paths = raw.get('paths', {})
    dirs = paths.get('directories', {})
    cfg.result_dirname = dirs.get('result_dirname', 'non-litigation-results')
    cfg.temp_dirname = dirs.get('temp_dirname', 'non-litigation')
    cfg.input_dirname = dirs.get('input_dirname', 'non-litigation')
    files = paths.get('files', {})
    cfg.excel_filename = files.get('excel_filename', '台账及命名规则.xlsx')
    cfg.standard_output_dirname = files.get('standard_output_dirname', '对应输出文件（标准版）')
    cfg.audit_log_filename = files.get('audit_log_filename', 'audit-log.json')
    cfg.standard_output_subdirs = paths.get('standard_output_subdirs', {})

    tp = raw.get('text_processing', {})
    cfg.company_keywords = tp.get('company_keywords', [])
    cfg.document_types = tp.get('document_types', [])
    cfg.noise_prefixes = tp.get('noise_prefixes', [])
    cfg.decision_number_range_max_spread = tp.get('decision_number_range_max_spread', 20)

    cfg.mock_noise_samples = raw.get('mock_ocr', {}).get('noise_samples', [])
    
    # 保存原始配置
    cfg.raw_config = raw

    return cfg
