#!/usr/bin/env python3

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from core.paths import get_config_path

_CONFIG_CACHE: Optional[dict] = None
_CONFIG_PATH: Optional[Path] = None
_CONFIG_MTIME: Optional[float] = None  # 上次加载时的 mtime（秒）

# P0-#reload: 这些模块在 import 时执行了 `_cfg = load_config()` 和
# `NOTICE_PATTERN = _cfg.notice_pattern` 等模块级赋值。reload_config() 时需要
# 重新加载它们，让模块级常量也刷新。
_REFRESH_TARGETS = (
    "non_litigation.export",
    "non_litigation.product",
    "non_litigation.output_plan",
    "non_litigation.smart_extractor",
    "non_litigation.streaming",
    "non_litigation.validator",
    "enforcement.extractor",
    "enforcement.export",
    "enforcement.product",
)


def _config_path() -> Path:
    global _CONFIG_PATH
    if _CONFIG_PATH is None:
        _CONFIG_PATH = get_config_path()
    return _CONFIG_PATH


def _is_cache_stale() -> bool:
    """检查 yaml 文件是否被外部修改（mtime 变化）"""
    global _CONFIG_MTIME
    if _CONFIG_CACHE is None or _CONFIG_MTIME is None:
        return True
    try:
        current_mtime = _config_path().stat().st_mtime
        return current_mtime > _CONFIG_MTIME
    except OSError:
        return False


def _load_config() -> dict:
    """加载并缓存 config.yaml。mtime 变化时自动重新读取。"""
    global _CONFIG_CACHE, _CONFIG_MTIME
    if _CONFIG_CACHE is None or _is_cache_stale():
        path = _config_path()
        if not path.is_file():
            raise FileNotFoundError(
                f"配置文件不存在: {path}（应位于安装目录 resources/config.yaml）"
            )
        with open(path, 'r', encoding='utf-8') as f:
            _CONFIG_CACHE = yaml.safe_load(f)
        try:
            _CONFIG_MTIME = path.stat().st_mtime
        except OSError:
            _CONFIG_MTIME = 0
    return _CONFIG_CACHE


# 每个模块的「模块级 cfg 属性」和「需要随 cfg 刷新的常量」映射
# key=模块名, value=((cfg_attr_name, *const_attr_names), ...)
# 刷新时: 先 setattr 模块 _cfg = 新的 NonLitigationConfig, 再 setattr 每个 const_attr
_MODULE_REFRESH_PLAN = {
    'non_litigation.export': (
        ('_cfg', 'NOTICE_PATTERN', 'NON_LITIGATION_CORRECTIONS', 'PAGES_PER_CASE',
         'NON_LITIGATION_INPUT_DIRNAME'),
        ('source_mapping',),  # dict 属性（doc_type -> source_pdf）
    ),
    'non_litigation.product': (('_cfg',), ()),
    'non_litigation.output_plan': (('_cfg',), ()),
    'non_litigation.smart_extractor': (('_cfg', 'NOTICE_PATTERN'), ()),
    'non_litigation.streaming': (('_cfg', 'NOTICE_PATTERN'), ()),
    'non_litigation.validator': (('_cfg',), ()),
    'enforcement.extractor': (
        ('_cfg', '_enforcement_cfg', '_extraction_cfg'),
        (),
    ),
    'enforcement.export': (('_cfg', '_enforcement_cfg', '_paths_cfg'), ()),
    'enforcement.product': (('_cfg', '_enforcement_cfg', '_excel_cfg'), ()),
}


def reload_config(path: Optional[Path] = None, refresh_modules: bool = True) -> dict:
    """
    强制重新加载 config.yaml。

    Args:
        path: 切换配置文件路径（None 保持当前路径）
        refresh_modules: 是否刷新依赖 cfg 的模块（默认 True）。
            会重新构造 NonLitigationConfig 并 setattr 到模块级 _cfg,
            同时更新 NOTICE_PATTERN 等模块级常量。不使用 importlib.reload
            （避免 ValidationStatus 等 dataclass 被重新定义导致 == 比较失败）。

    Returns:
        重新加载后的 raw config dict
    """
    global _CONFIG_CACHE, _CONFIG_PATH, _CONFIG_MTIME
    if path:
        _CONFIG_PATH = path
    _CONFIG_CACHE = None
    _CONFIG_MTIME = None
    raw = _load_config()
    if refresh_modules:
        new_cfg = load_config()
        _refresh_dependent_modules(new_cfg)
    return raw


def _refresh_dependent_modules(new_cfg):
    """
    把新的 NonLitigationConfig 实例和派生常量 setattr 到每个模块。
    不 importlib.reload，避免 enum/dataclass 重新定义。
    """
    for mod_name, (cfg_attrs, dict_attrs) in _MODULE_REFRESH_PLAN.items():
        if mod_name not in sys.modules:
            continue
        mod = sys.modules[mod_name]
        try:
            for attr in cfg_attrs:
                if attr == '_cfg':
                    mod._cfg = new_cfg
                elif attr == '_enforcement_cfg':
                    mod._enforcement_cfg = new_cfg.raw_config.get('enforcement', {})
                elif attr == '_extraction_cfg':
                    mod._extraction_cfg = mod._enforcement_cfg.get('extraction', {})
                elif attr == '_paths_cfg':
                    mod._paths_cfg = mod._enforcement_cfg.get('paths', {})
                elif attr == '_excel_cfg':
                    mod._excel_cfg = mod._enforcement_cfg.get('excel_parsing', {})
                elif attr == 'NOTICE_PATTERN':
                    mod.NOTICE_PATTERN = new_cfg.notice_pattern
                elif attr == 'NON_LITIGATION_CORRECTIONS':
                    mod.NON_LITIGATION_CORRECTIONS = new_cfg.ocr_corrections
                elif attr == 'PAGES_PER_CASE':
                    mod.PAGES_PER_CASE = new_cfg.pages_per_case
                elif attr == 'NON_LITIGATION_INPUT_DIRNAME':
                    mod.NON_LITIGATION_INPUT_DIRNAME = new_cfg.input_dirname
            for attr in dict_attrs:
                # source_mapping 是从 cfg 派生的 dict（doc_type -> source_pdf），
                # 在 doc_types 重新解析时已通过 _build_doc_type_map 更新 new_cfg
                if hasattr(new_cfg, attr):
                    setattr(mod, attr, getattr(new_cfg, attr))
        except Exception as e:
            print(f"[WARN] 刷新 {mod_name} 模块级常量失败: {e}")


@dataclass
class UsabilityCheckConfig:
    keywords: List[str] = field(default_factory=list)
    fragment_keywords: List[str] = field(default_factory=list)
    min_fragment_hits: int = 2
    min_text_length: int = 6


@dataclass
class QuickScanConfig:
    enabled: bool = False
    target_size: Tuple[int, int] = (400, 400)


@dataclass
class ImagePreprocessingConfig:
    enhance_contrast: bool = False
    sharpen: bool = False


@dataclass
class DocTypeOcrConfig:
    dpi: int = 150
    max_image_size: int = 600
    regions: List[str] = field(default_factory=list)
    enable_region_first: bool = True
    allow_full_page_fallback: bool = True
    region_fallback_min_text_length: int = 8
    scan_max_pages: int = 10
    scan_window_pages: int = 4
    skip_blank_pages: bool = True
    blank_page_threshold: float = 0.02
    stop_on_match: bool = False
    image_preprocessing: ImagePreprocessingConfig = field(default_factory=ImagePreprocessingConfig)
    quick_scan: QuickScanConfig = field(default_factory=QuickScanConfig)
    usability_check: Optional[UsabilityCheckConfig] = None
    corrections: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class RegionDefinition:
    name: str
    top: float
    bottom: float
    left: float
    right: float


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
    ocr: DocTypeOcrConfig = field(default_factory=DocTypeOcrConfig)
    secondary_boundary_evidence: List[str] = field(default_factory=list)


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

    company_name_corrections: List[Tuple[str, str]] = field(default_factory=list)

    region_definitions: Dict[str, RegionDefinition] = field(default_factory=dict)

    ocr_dpi: int = 150
    ocr_max_image_size: int = 600
    ocr_parallel_workers: int = 4
    ocr_small_pdf_page_threshold: int = 6
    ocr_auto_detect_resources: bool = True
    ocr_max_parallel_workers: int = 4
    ocr_memory_reserve_gb: float = 1.5

    excel_min_columns: int = 5
    excel_column_original_notice: int = 1
    excel_column_renamed_notice: int = 2
    excel_column_company_name: int = 4
    excel_filter_original_notice: str = '责字'
    excel_filter_renamed_notice: str = '责催-'

    fuzzy_match_threshold: float = 0.85
    text_quality: Dict[str, Dict[str, int]] = field(default_factory=dict)

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

    raw_config: Dict = field(default_factory=dict)

    # 兼容旧代码的字段
    ocr_corrections: List[Tuple[str, str]] = field(default_factory=list)
    ocr_enable_region_first: bool = True
    ocr_allow_full_page_fallback: bool = True
    ocr_region_dpi: int = 150
    ocr_region_max_image_size: int = 600
    ocr_doc_regions: Dict[str, List[str]] = field(default_factory=dict)
    notice_scan_window_pages: int = 4
    notice_scan_max_pages: int = 10
    notice_region_fallback_min_text_length: int = 8
    application_region_fallback_min_text_length: int = 5
    company_doc_region_fallback_min_text_length: int = 6
    application_secondary_boundary_evidence: List[str] = field(default_factory=list)
    ocr_skip_blank_pages: bool = True
    ocr_blank_page_threshold: float = 0.02

    def get_doc_ocr(self, doc_type_key: str) -> DocTypeOcrConfig:
        dt = self.doc_type_map.get(doc_type_key)
        if dt:
            return dt.ocr
        return DocTypeOcrConfig()

    def get_doc_corrections(self, doc_type_key: str) -> List[Tuple[str, str]]:
        """获取文档类型的纠错规则，合并文档特定规则和根级别通用规则"""
        dt = self.doc_type_map.get(doc_type_key)
        doc_corrections = dt.ocr.corrections if dt else []

        # 合并文档特定规则和根级别规则，去重
        seen = set()
        merged = []
        for wrong, correct in doc_corrections + self.ocr_corrections:
            if wrong not in seen:
                seen.add(wrong)
                merged.append((wrong, correct))
        return merged


def _parse_ocr_config(ocr_raw: dict) -> DocTypeOcrConfig:
    cfg = DocTypeOcrConfig()
    cfg.dpi = ocr_raw.get('dpi', 150)
    cfg.max_image_size = ocr_raw.get('max_image_size', 600)
    cfg.regions = ocr_raw.get('regions', [])
    cfg.enable_region_first = ocr_raw.get('enable_region_first', True)
    cfg.allow_full_page_fallback = ocr_raw.get('allow_full_page_fallback', True)
    cfg.region_fallback_min_text_length = ocr_raw.get('region_fallback_min_text_length', 8)
    cfg.scan_max_pages = ocr_raw.get('scan_max_pages', 10)
    cfg.scan_window_pages = ocr_raw.get('scan_window_pages', 4)
    cfg.skip_blank_pages = ocr_raw.get('skip_blank_pages', True)
    cfg.blank_page_threshold = ocr_raw.get('blank_page_threshold', 0.02)
    cfg.stop_on_match = ocr_raw.get('stop_on_match', False)

    pp_raw = ocr_raw.get('image_preprocessing', {})
    cfg.image_preprocessing = ImagePreprocessingConfig(
        enhance_contrast=pp_raw.get('enhance_contrast', False),
        sharpen=pp_raw.get('sharpen', False),
    )

    qs_raw = ocr_raw.get('quick_scan', {})
    cfg.quick_scan = QuickScanConfig(
        enabled=qs_raw.get('enabled', False),
        target_size=tuple(qs_raw.get('target_size', [400, 400])),
    )

    uc_raw = ocr_raw.get('usability_check')
    if uc_raw:
        cfg.usability_check = UsabilityCheckConfig(
            keywords=uc_raw.get('keywords', []),
            fragment_keywords=uc_raw.get('fragment_keywords', []),
            min_fragment_hits=uc_raw.get('min_fragment_hits', 2),
            min_text_length=uc_raw.get('min_text_length', 6),
        )

    cfg.corrections = [
        (item['wrong'], item['correct'])
        for item in ocr_raw.get('corrections', [])
    ]

    return cfg


def load_config() -> NonLitigationConfig:
    raw = _load_config()
    cfg = NonLitigationConfig()

    # ---------- 区域定义 ----------
    for region_key, region_raw in raw.get('regions', {}).items():
        cfg.region_definitions[region_key] = RegionDefinition(
            name=region_raw.get('name', region_key),
            top=region_raw.get('top', 0.0),
            bottom=region_raw.get('bottom', 1.0),
            left=region_raw.get('left', 0.0),
            right=region_raw.get('right', 1.0),
        )

    # ---------- 文书类型 ----------
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
            ocr=_parse_ocr_config(dt_raw.get('ocr', {})),
            secondary_boundary_evidence=dt_raw.get('secondary_boundary_evidence', []),
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

    # ---------- 正则 ----------
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

    # ---------- 公司名称纠错 ----------
    cfg.company_name_corrections = [
        (item['pattern'], item['replacement'])
        for item in raw.get('company_name_corrections', [])
    ]

    # ---------- 兼容旧字段：从 per-doc-type 聚合 ----------
    all_corrections = []
    seen = set()
    for dt in cfg.doc_types:
        for wrong, correct in dt.ocr.corrections:
            if wrong not in seen:
                seen.add(wrong)
                all_corrections.append((wrong, correct))
    
    # 添加根级别的 ocr_corrections（区名纠错等通用规则）
    for item in raw.get('ocr_corrections', []):
        wrong = item.get('wrong', '')
        correct = item.get('correct', '')
        if wrong and correct and wrong not in seen:
            seen.add(wrong)
            all_corrections.append((wrong, correct))
    
    cfg.ocr_corrections = all_corrections

    cfg.ocr_doc_regions = {dt.key: dt.ocr.regions for dt in cfg.doc_types}

    notice_dt = cfg.doc_type_map.get('责催')
    if notice_dt:
        cfg.notice_scan_max_pages = notice_dt.ocr.scan_max_pages
        cfg.notice_scan_window_pages = notice_dt.ocr.scan_window_pages
        cfg.notice_region_fallback_min_text_length = notice_dt.ocr.region_fallback_min_text_length

    app_dt = cfg.doc_type_map.get('申请书')
    if app_dt:
        cfg.application_region_fallback_min_text_length = app_dt.ocr.region_fallback_min_text_length
        cfg.application_secondary_boundary_evidence = app_dt.secondary_boundary_evidence

    company_dts = [dt for dt in cfg.doc_types if dt.key in ('授权书', '所函')]
    if company_dts:
        cfg.company_doc_region_fallback_min_text_length = max(
            dt.ocr.region_fallback_min_text_length for dt in company_dts
        )

    cfg.ocr_enable_region_first = all(dt.ocr.enable_region_first for dt in cfg.doc_types)
    cfg.ocr_allow_full_page_fallback = any(dt.ocr.allow_full_page_fallback for dt in cfg.doc_types)
    cfg.ocr_skip_blank_pages = any(dt.ocr.skip_blank_pages for dt in cfg.doc_types)
    cfg.ocr_blank_page_threshold = min(
        (dt.ocr.blank_page_threshold for dt in cfg.doc_types if dt.ocr.skip_blank_pages),
        default=0.02,
    )
    cfg.ocr_region_dpi = max(dt.ocr.dpi for dt in cfg.doc_types)
    cfg.ocr_region_max_image_size = max(dt.ocr.max_image_size for dt in cfg.doc_types)

    # ---------- Excel 解析 ----------
    excel = raw.get('excel_parsing', {})
    cfg.excel_min_columns = excel.get('min_columns', 5)
    cfg.excel_column_original_notice = excel.get('column_original_notice', 1)
    cfg.excel_column_renamed_notice = excel.get('column_renamed_notice', 2)
    cfg.excel_column_company_name = excel.get('column_company_name', 4)
    filters = excel.get('filter_keywords', {})
    cfg.excel_filter_original_notice = filters.get('original_notice', '责字')
    cfg.excel_filter_renamed_notice = filters.get('renamed_notice', '责催-')

    # ---------- 验证 ----------
    validation = raw.get('validation', {})
    cfg.fuzzy_match_threshold = validation.get('fuzzy_match_threshold', 0.85)
    cfg.text_quality = validation.get('text_quality', {})

    # ---------- 全局 OCR 引擎 ----------
    ocr = raw.get('ocr', {})
    ocr_engine = ocr.get('engine', {})
    cfg.ocr_dpi = ocr_engine.get('dpi', 150)
    cfg.ocr_max_image_size = ocr_engine.get('max_image_size', 600)
    cfg.ocr_parallel_workers = ocr_engine.get('parallel_workers', 4)
    cfg.ocr_small_pdf_page_threshold = ocr_engine.get('small_pdf_page_threshold', 6)

    parallelism = ocr.get('parallelism', {})
    cfg.ocr_auto_detect_resources = parallelism.get('auto_detect_resources', True)
    cfg.ocr_max_parallel_workers = parallelism.get('max_parallel_workers', 4)
    cfg.ocr_memory_reserve_gb = parallelism.get('memory_reserve_gb', 1.5)

    # ---------- 路径 ----------
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

    # ---------- 文本处理 ----------
    tp = raw.get('text_processing', {})
    cfg.company_keywords = tp.get('company_keywords', [])
    cfg.document_types = tp.get('document_types', [])
    cfg.noise_prefixes = tp.get('noise_prefixes', [])
    cfg.decision_number_range_max_spread = tp.get('decision_number_range_max_spread', 20)

    cfg.mock_noise_samples = raw.get('mock_ocr', {}).get('noise_samples', [])

    cfg.raw_config = raw

    return cfg
