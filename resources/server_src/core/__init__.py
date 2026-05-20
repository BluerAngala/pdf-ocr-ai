from core.paths import ROOT, SERVER_SRC, RESOURCES_DIR, USER_DATA_DIR
from core.config_loader import load_config, reload_config, NonLitigationConfig, DocTypeConfig, DocTypeOcrConfig, RegionDefinition
from core.region_extractor import Region, REGIONS, RegionExtractor
from core.text_postprocessor import TextPostProcessor
from core.pdf_ocr_ultra import UltraFastOCR, OCRConfig, ImagePreprocessor, get_ocr_engine, get_ocr_lock, HAS_RAPIDOCR
from core.system_resource import detect_system_resources
from core.task_state import TaskStateManager, Task
from core.task_cancel import is_cancelled, clear, request_cancel
