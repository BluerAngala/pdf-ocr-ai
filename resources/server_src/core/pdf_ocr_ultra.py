#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF OCR 工具 - 超极速版（Ultra Fast）
核心优化策略：
1. 智能识别策略 - 可编辑PDF直接提取，扫描件自动OCR
2. 图像预处理优化 - 提前压缩、增强
3. 多进程并行 - 绕过GIL限制
4. 模型预热 - 预加载保持常驻
5. 支持图片输入 - PNG/JPG/JPEG
"""

import os
import sys
import json
import time
import argparse
import threading
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, asdict
from multiprocessing import Pool, cpu_count
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
import numpy as np

os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
_omp_threads = str(min(cpu_count(), 4))
os.environ['OMP_NUM_THREADS'] = _omp_threads
os.environ['ONNXRUNTIME_CPU_NUM_THREADS'] = _omp_threads
os.environ['KMP_AFFINITY'] = 'granularity=fine,compact,1,0'

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False

try:
    from rapidocr_onnxruntime import RapidOCR
    HAS_RAPIDOCR = True
except ImportError:
    try:
        from rapidocr import RapidOCR
        HAS_RAPIDOCR = True
    except ImportError:
        HAS_RAPIDOCR = False

try:
    from PIL import Image, ImageEnhance, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


_ocr_engine = None
_ocr_lock = threading.Lock()
_gpu_provider = None
_gpu_info = ""


def _generate_test_image():
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (600, 120), 'white')
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("msyh.ttc", 24)
    except Exception:
        try:
            font = ImageFont.truetype("simsun.ttc", 24)
        except Exception:
            font = ImageFont.load_default()
    draw.text((15, 10), "住房公积金管理中心强制执行申请书", fill='black', font=font)
    draw.text((15, 50), "广州住房公积金管理中心越秀管理部", fill='black', font=font)
    draw.text((15, 85), "责令限期缴存决定书穗公积金中心", fill='black', font=font)
    return np.array(img)


def _validate_gpu_det_accuracy(**engine_kwargs):
    try:
        test_engine = RapidOCR(**engine_kwargs)
        test_img = _generate_test_image()
        result = test_engine(test_img)
        if result[0] is None or len(result[0]) == 0:
            return False
        text = ''.join(line[1] for line in result[0])
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in text)
        if not has_chinese:
            return False
        garbage_chars = set('μβäÞðþŋœŧ')
        garbage_count = sum(1 for c in text if c in garbage_chars)
        if garbage_count > 2:
            return False
        return True
    except Exception:
        return False


def _detect_gpu_hardware():
    """检测系统中的 GPU 硬件信息，返回 (vendor, name) 或 (None, None)。"""
    vendor = None
    name = None
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r'SYSTEM\CurrentControlSet\Control\Video',
            access=winreg.KEY_READ,
        )
        i = 0
        gpus = []
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i)
                i += 1
                try:
                    subkey = winreg.OpenKey(key, f'{subkey_name}\\0000', access=winreg.KEY_READ)
                    try:
                        desc, _ = winreg.QueryValueEx(subkey, 'Device Description')
                        gpus.append(desc)
                    except FileNotFoundError:
                        try:
                            desc, _ = winreg.QueryValueEx(subkey, 'DriverDesc')
                            gpus.append(desc)
                        except FileNotFoundError:
                            pass
                    subkey.Close()
                except FileNotFoundError:
                    pass
            except OSError:
                break
        key.Close()
        for desc in gpus:
            dl = desc.lower()
            if 'nvidia' in dl or 'geforce' in dl or 'rtx' in dl or 'gtx' in dl:
                vendor = 'nvidia'
                name = desc
                break
            elif 'amd' in dl or 'radeon' in dl or 'rx ' in dl:
                vendor = 'amd'
                name = desc
                break
            elif 'intel' in dl or 'arc' in dl or 'iris' in dl or 'uhd' in dl:
                vendor = 'intel'
                name = desc
                break
    except Exception:
        pass
    return vendor, name


def detect_gpu_provider():
    global _gpu_provider, _gpu_info
    if _gpu_provider is not None:
        return _gpu_provider, _gpu_info
    if not HAS_RAPIDOCR:
        _gpu_provider = 'cpu'
        _gpu_info = 'CPU only (RapidOCR 未安装)'
        return _gpu_provider, _gpu_info

    hw_vendor, hw_name = _detect_gpu_hardware()

    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()

        if 'CUDAExecutionProvider' in providers:
            cuda_kwargs = dict(use_cls=False, det_use_cuda=True, rec_use_cuda=True)
            if _validate_gpu_det_accuracy(**cuda_kwargs):
                _gpu_provider = 'cuda'
                _gpu_info = f'NVIDIA CUDA GPU (det+rec){f" [{hw_name}]" if hw_name else ""}'
                return _gpu_provider, _gpu_info

        if 'DmlExecutionProvider' in providers:
            try:
                import platform
                win_ver = int(platform.release().split('.')[0])
                if win_ver < 10:
                    _gpu_provider = 'cpu'
                    _gpu_info = f'CPU (Windows {win_ver} < 10, DirectML 不可用)'
                    return _gpu_provider, _gpu_info
            except Exception:
                pass

            dml_det_kwargs = dict(use_cls=False, det_use_dml=True)
            if _validate_gpu_det_accuracy(**dml_det_kwargs):
                _gpu_provider = 'dml_det'
                vendor_label = hw_vendor or 'GPU'
                name_label = f" [{hw_name}]" if hw_name else ""
                _gpu_info = f'DirectML {vendor_label} (det=GPU, rec=CPU){name_label}'
                return _gpu_provider, _gpu_info

            dml_full_kwargs = dict(use_cls=False, det_use_dml=True, rec_use_dml=True)
            if _validate_gpu_det_accuracy(**dml_full_kwargs):
                _gpu_provider = 'dml_det'
                _gpu_info = f'DirectML GPU (det+rec){f" [{hw_name}]" if hw_name else ""}'
                return _gpu_provider, _gpu_info

    except Exception:
        pass

    _gpu_provider = 'cpu'
    if hw_name:
        _gpu_info = f'CPU ({hw_name} 检测到但 GPU 加速不可用)'
    else:
        _gpu_info = 'CPU (无 GPU 或驱动未安装)'
    return _gpu_provider, _gpu_info


def _build_onnx_session_options():
    try:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = min(cpu_count(), 4)
        opts.inter_op_num_threads = 2
        opts.execution_mode = ort.ExecutionMode.ORT_PARALLEL
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.enable_mem_pattern = True
        opts.enable_mem_reuse = True
        return opts
    except Exception:
        return None


def _create_ocr_engine():
    if not HAS_RAPIDOCR:
        raise RuntimeError("RapidOCR 未安装，请运行: pip install rapidocr-onnxruntime")
    provider, info = detect_gpu_provider()
    kwargs = dict(use_cls=False)
    if provider == 'cuda':
        kwargs['det_use_cuda'] = True
        kwargs['rec_use_cuda'] = True
        print(f"[OCR] 使用 NVIDIA CUDA GPU 加速 (det+rec)")
    elif provider == 'dml_det':
        kwargs['det_use_dml'] = True
        sess_opts = _build_onnx_session_options()
        if sess_opts is not None:
            kwargs['rec_session_options'] = sess_opts
        print(f"[OCR] 使用 DirectML GPU 加速 (det=GPU, rec=CPU)")
    else:
        sess_opts = _build_onnx_session_options()
        if sess_opts is not None:
            kwargs['det_session_options'] = sess_opts
            kwargs['rec_session_options'] = sess_opts
        print(f"[OCR] 使用 CPU 模式 (GPU 不可用或准确度验证未通过)")
    return RapidOCR(**kwargs)


def init_worker():
    """子进程初始化 - 预加载OCR模型"""
    global _ocr_engine
    if HAS_RAPIDOCR:
        _ocr_engine = _create_ocr_engine()

def get_ocr_engine():
    """获取OCR引擎 - 线程安全版"""
    global _ocr_engine
    with _ocr_lock:
        if _ocr_engine is None:
            _ocr_engine = _create_ocr_engine()
        return _ocr_engine

def get_ocr_lock() -> threading.Lock:
    """获取OCR引擎全局锁（供外部线程池使用）"""
    return _ocr_lock


def check_poppler_installed(poppler_path: str) -> bool:
    if sys.platform == "win32":
        pdftoppm = Path(poppler_path).resolve() / "pdftoppm.exe"
        return pdftoppm.exists()
    else:
        import shutil
        return shutil.which("pdftoppm") is not None


def show_poppler_setup_guide():
    """显示 poppler 安装指南"""
    print("\n" + "=" * 70)
    print("❌ 缺少 Poppler 工具")
    print("=" * 70)
    print("\nPoppler 是 PDF 转图片的必要工具，请按以下步骤安装：\n")

    if sys.platform == "win32":
        print("【Windows 用户】")
        print("\n方式一：自动配置（推荐）")
        print("  运行以下命令自动下载配置：")
        print("  python scripts/setup_poppler.py")
        print("\n方式二：手动配置")
        print("  1. 下载: https://github.com/oschwartz10612/poppler-windows/releases")
        print("  2. 解压到: tools/poppler/ 目录")
        print("  3. 确保目录结构: tools/poppler/poppler-24.08.0/Library/bin/")
    else:
        print("【Linux/macOS 用户】")
        print("  Ubuntu/Debian: sudo apt-get install poppler-utils")
        print("  macOS: brew install poppler")

    print("\n" + "=" * 70)
    print("详细说明请查看: INSTALL.md")
    print("=" * 70 + "\n")


def _auto_install_poppler() -> bool:
    """自动安装 Poppler（仅 Windows 开发环境），成功返回 True"""
    if sys.platform != "win32":
        return False
    if getattr(sys, "frozen", False):
        return False
    try:
        from core.paths import SERVER_SRC
        setup_script = SERVER_SRC.parent / "scripts" / "setup_poppler.py"
        if not setup_script.exists():
            return False
        import subprocess
        result = subprocess.run(
            [sys.executable, str(setup_script)],
            capture_output=True, text=True, timeout=300,
            cwd=str(SERVER_SRC.parents[1]),
        )
        return result.returncode == 0
    except Exception:
        return False


class ImagePreprocessor:
    """图像预处理器 - 减少OCR计算量"""

    @staticmethod
    def is_blank_page(image: Image.Image, threshold: float = 0.02) -> bool:
        """
        检测是否为空白页
        
        Args:
            image: PIL 图像对象
            threshold: 空白页阈值（非白色像素占比小于此值视为空白页）
        
        Returns:
            True 如果是空白页
        """
        import numpy as np
        
        img_array = np.array(image.convert('L'))
        
        white_pixels = np.sum(img_array > 240)
        total_pixels = img_array.size
        non_white_ratio = 1 - (white_pixels / total_pixels)
        
        return non_white_ratio < threshold

    @staticmethod
    def optimize_for_ocr(
        image: Image.Image,
        target_size: Tuple[int, int] = (800, 800),
        *,
        apply_enhancement: bool = True,
        apply_sharpen: bool = False,
    ) -> Image.Image:
        """
        优化图像以加速OCR - 优化版
        
        策略：
        1. 智能缩放 - 降低到800px，保持文字清晰度
        2. 对比度增强 - 让文字更清晰
        3. 轻度锐化 - 增强文字边缘
        """
        original_size = image.size
        max_dim = max(original_size)
        
        # 降低目标尺寸从1024到800，减少50%的像素处理量
        if max_dim > target_size[0]:
            scale = target_size[0] / max_dim
            new_size = (int(original_size[0] * scale), int(original_size[1] * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        if apply_enhancement:
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.15)  # 从1.2降低到1.15，减少处理时间

        if apply_sharpen:
            image = image.filter(ImageFilter.SHARPEN)

        return image


@dataclass
class OCRConfig:
    """OCR配置 - 优化版"""
    _base_dir: Path = None  # type: ignore
    _server_dir: Path = None  # type: ignore

    def __post_init__(self):
        import sys
        from core.paths import ROOT, RESOURCES_DIR
        if self._base_dir is None:
            self._base_dir = ROOT
        if self._server_dir is None:
            if getattr(sys, "frozen", False):
                self._server_dir = RESOURCES_DIR
            else:
                self._server_dir = Path(__file__).resolve().parents[1]

    @property
    def poppler_path(self) -> str:
        from core.paths import SERVER_SRC
        server_root = SERVER_SRC.parent
        if getattr(sys, "frozen", False):
            return str(server_root / "poppler" / "poppler-24.08.0" / "Library" / "bin")
        return str(server_root / "tools" / "poppler" / "poppler-24.08.0" / "Library" / "bin")

    @property
    def output_dir(self) -> str:
        return str(self._base_dir / "output")

    dpi: int = 200
    max_image_size: int = 800  # 降低到800px，与预处理器保持一致
    parallel_workers: int = min(cpu_count(), 4)
    max_retries: int = 2
    small_pdf_page_threshold: int = 6

    # 新增：快速模式配置
    fast_mode: bool = True  # 启用快速模式
    skip_cls: bool = True  # 跳过方向分类（对于正向文档可提升30%速度）


@dataclass
class PageResult:
    """单页识别结果"""
    page: int
    text: str
    method: str
    duration: float = 0
    error: str = ""


class UltraFastOCR:
    """超极速OCR处理器"""

    SUPPORTED_IMAGE_FORMATS = {'.png', '.jpg', '.jpeg'}
    SUPPORTED_PDF_FORMATS = {'.pdf'}

    def __init__(self, config: Optional[OCRConfig] = None, skip_warmup: bool = False, log_fn: Optional[Callable[[str], None]] = None):
        self.config = config or OCRConfig()
        self.preprocessor = ImagePreprocessor()
        Path(self.config.output_dir).mkdir(exist_ok=True)
        self._log_fn = log_fn or print

        self._check_dependencies()
        if not skip_warmup:
            self._warmup()
    
    def _check_dependencies(self):
        """检查依赖"""
        missing = []
        
        if not HAS_RAPIDOCR:
            missing.append("rapidocr-onnxruntime")
        if not HAS_PIL:
            missing.append("pillow")
        
        if missing:
            print(f"❌ 缺少依赖: {', '.join(missing)}")
            print(f"请运行: pip install {' '.join(missing)}")
            raise RuntimeError("依赖未安装")
        
        if not check_poppler_installed(self.config.poppler_path):
            if getattr(sys, "frozen", False):
                raise RuntimeError(f"打包环境中 Poppler 缺失（路径: {self.config.poppler_path}），请重新安装应用程序")
            self._log_fn("[INFO] Poppler 未安装，正在自动安装...")
            if _auto_install_poppler():
                self._log_fn("[OK] Poppler 自动安装成功")
            else:
                show_poppler_setup_guide()
                raise RuntimeError("Poppler 自动安装失败，请手动运行: python scripts/setup_poppler.py")

    def _warmup(self):
        """模型预热 - 提前加载模型（线程安全版本）"""
        self._log_fn("  [INFO] 模型预热中...")
        start = time.time()
        engine = get_ocr_engine()
        dummy_img = Image.new('RGB', (100, 100), color='white')
        self._run_ocr(engine, dummy_img)
        self._log_fn(f"  [OK] 预热完成 ({time.time()-start:.2f}秒)")
    
    def _extract_texts_from_result(self, result: Any) -> List[str]:
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

    def _run_ocr(self, engine: Any, image: Image.Image, fallback_path: Optional[Path] = None, use_lock: bool = True) -> List[str]:
        """
        执行OCR识别
        
        Args:
            use_lock: 是否使用全局锁（多线程环境下必须设为True）
        """
        image_array = np.array(image)
        
        def _do_ocr():
            try:
                return self._extract_texts_from_result(engine(image_array))
            except Exception:
                if fallback_path is None:
                    raise
                fallback_path.parent.mkdir(exist_ok=True)
                image.save(fallback_path, 'PNG', optimize=False)
                try:
                    return self._extract_texts_from_result(engine(str(fallback_path)))
                finally:
                    fallback_path.unlink(missing_ok=True)
        
        provider, _ = detect_gpu_provider()
        if provider == 'dml_det' and use_lock:
            with _ocr_lock:
                return _do_ocr()
        return _do_ocr()

    def _process_single_image(
        self,
        image: Image.Image,
        page_num: int = 1,
        *,
        max_image_size: Optional[int] = None,
        apply_enhancement: bool = True,
        apply_sharpen: bool = False,
        method: str = "rapidocr",
        optimize_output: bool = True,
    ) -> PageResult:
        """处理单张图片"""
        start = time.time()
        target_max_size = max_image_size or self.config.max_image_size

        for attempt in range(self.config.max_retries + 1):
            temp_img = None
            try:
                w, h = image.size
                max_dim = max(w, h)
                needs_resize = max_dim > target_max_size
                needs_preprocess = needs_resize or apply_enhancement or apply_sharpen

                if needs_preprocess:
                    optimized_img = self.preprocessor.optimize_for_ocr(
                        image,
                        target_size=(target_max_size, target_max_size),
                        apply_enhancement=apply_enhancement,
                        apply_sharpen=apply_sharpen,
                    )
                else:
                    optimized_img = image

                temp_dir = Path(self.config.output_dir) / "_temp"
                temp_img = temp_dir / f"_page_{page_num}_{threading.get_ident()}_opt.png"

                engine = get_ocr_engine()
                texts = self._run_ocr(engine, optimized_img, fallback_path=temp_img, use_lock=True)

                duration = time.time() - start
                return PageResult(
                    page=page_num,
                    text="\n".join(texts),
                    method=method,
                    duration=duration
                )

            except Exception as e:
                if attempt < self.config.max_retries:
                    print(f"  ⚠️ 第 {page_num} 页处理失败，重试 {attempt + 1}/{self.config.max_retries}...")
                    time.sleep(0.5)
                else:
                    error_detail = f"{type(e).__name__}: {str(e)}"
                    print(f"  ✗ 第 {page_num} 页错误: {error_detail}")
                    return PageResult(
                        page=page_num,
                        text="",
                        method="error",
                        duration=time.time() - start,
                        error=error_detail
                    )
            finally:
                if temp_img:
                    temp_img.unlink(missing_ok=True)
                    try:
                        temp_img.parent.rmdir()
                    except:
                        pass

        return PageResult(page=page_num, text="", method="error", duration=time.time() - start)
    
    def process_page_parallel(self, args: Tuple[int, Any]) -> PageResult:
        """并行处理单页（用于多进程）"""
        page_num, image_path = args
        try:
            image = Image.open(image_path) if isinstance(image_path, (str, Path)) else image_path
            return self._process_single_image(image, page_num)
        except Exception as e:
            return PageResult(
                page=page_num,
                text="",
                method="error",
                error=str(e)
            )

    def recognize_image_region(
        self,
        image: Image.Image,
        page_num: int = 1,
        *,
        max_image_size: Optional[int] = None,
        apply_enhancement: bool = False,
        apply_sharpen: bool = False,
        method: str = "rapidocr_region",
        optimize_output: bool = False,
    ) -> PageResult:
        return self._process_single_image(
            image,
            page_num,
            max_image_size=max_image_size,
            apply_enhancement=apply_enhancement,
            apply_sharpen=apply_sharpen,
            method=method,
            optimize_output=optimize_output,
        )

    def recognize_full_page_image(
        self,
        image: Image.Image,
        page_num: int = 1,
        *,
        method: str = "full_page_fallback",
        optimize_output: bool = True,
    ) -> PageResult:
        return self.recognize_image_region(
            image,
            page_num=page_num,
            apply_enhancement=True,
            apply_sharpen=False,
            method=method,
            optimize_output=optimize_output,
        )

    def batch_ocr_images(
        self,
        images: List[Tuple[Image.Image, int]],
        *,
        max_image_size: Optional[int] = None,
        apply_enhancement: bool = False,
        apply_sharpen: bool = False,
        method_prefix: str = "batch_region",
    ) -> List[PageResult]:
        """
        批量 OCR：先对所有图片做 det，收集所有文字行，
        再一次性送入 rec 模型做批量识别，减少模型调用开销。

        Args:
            images: [(PIL.Image, page_num), ...] 列表
            max_image_size: 最大图片尺寸
            apply_enhancement: 是否增强
            apply_sharpen: 是否锐化
            method_prefix: 结果 method 前缀

        Returns:
            PageResult 列表，与输入顺序一一对应
        """
        if not images:
            return []

        target_max_size = max_image_size or self.config.max_image_size
        engine = get_ocr_engine()

        all_crops = []
        page_ranges = []
        preprocessed_images = []

        for img, page_num in images:
            w, h = img.size
            max_dim = max(w, h)
            if max_dim > target_max_size or apply_enhancement or apply_sharpen:
                processed = self.preprocessor.optimize_for_ocr(
                    img,
                    target_size=(target_max_size, target_max_size),
                    apply_enhancement=apply_enhancement,
                    apply_sharpen=apply_sharpen,
                )
            else:
                processed = img
            preprocessed_images.append(np.array(processed))

        provider, _ = detect_gpu_provider()
        need_lock = provider == 'dml_det'

        def _do_det_all():
            crops = []
            ranges = []
            for img_array in preprocessed_images:
                start_idx = len(crops)
                dt_boxes, _ = engine.text_det(img_array)
                if dt_boxes is not None and len(dt_boxes) > 0:
                    dt_boxes = engine.sorted_boxes(dt_boxes)
                    page_crops = engine.get_crop_img_list(img_array, dt_boxes)
                    crops.extend(page_crops)
                ranges.append((start_idx, len(crops)))
            return crops, ranges

        if need_lock:
            with _ocr_lock:
                all_crops, page_ranges = _do_det_all()
        else:
            all_crops, page_ranges = _do_det_all()

        if all_crops:
            rec_results, _ = engine.text_rec(all_crops)
        else:
            rec_results = []

        results = []
        text_score = engine.text_score
        for i, (img, page_num) in enumerate(images):
            start, end = page_ranges[i]
            page_texts = []
            for j in range(start, end):
                if j < len(rec_results):
                    text_val, score = rec_results[j][0], rec_results[j][1]
                    if float(score) >= text_score:
                        page_texts.append(text_val)
            text = "\n".join(page_texts)
            results.append(PageResult(
                page=page_num,
                text=text,
                method=f"{method_prefix}:{i+1}",
                duration=0,
            ))

        return results

    def process_image(self, image_path: str) -> Optional[Dict]:
        """处理图片文件"""
        image_path = Path(image_path)
        if not image_path.exists():
            print(f"❌ 文件不存在: {image_path}")
            return None
        
        print(f"\n{'='*60}")
        print(f"🖼️ 处理图片: {image_path.name}")
        print(f"{'='*60}")
        
        total_start = time.time()
        
        try:
            image = Image.open(image_path)
            result = self._process_single_image(image, 1)
            
            total_duration = time.time() - total_start
            print(f"  ✅ 处理完成 ({total_duration:.2f}秒)")
            
            return {
                'filename': image_path.name,
                'filepath': str(image_path),
                'total_pages': 1,
                'method': 'rapidocr',
                'total_duration': total_duration,
                'pages': [asdict(result)],
                'full_text': result.text
            }
        except Exception as e:
            print(f"❌ 图片处理失败: {e}")
            return None

    def process_pdf(self, pdf_path: str, force_ocr: bool = False) -> Optional[Dict]:
        """处理PDF（超极速模式）"""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            print(f"❌ 文件不存在: {pdf_path}")
            return None
        
        print(f"\n{'='*60}")
        print(f"🚀 超极速处理: {pdf_path.name}")
        print(f"⚡ 配置: DPI={self.config.dpi}, 最大尺寸={self.config.max_image_size}")
        print(f"{'='*60}")
        
        total_start = time.time()
        
        if not force_ocr and HAS_PDFPLUMBER:
            print("  📄 尝试 pdfplumber 提取...")
            result = self._try_pdfplumber(str(pdf_path))
            if result:
                result['total_duration'] = time.time() - total_start
                print(f"  ✅ pdfplumber 成功 ({result['total_duration']:.2f}秒)")
                return result
        
        print("  🔍 使用超极速OCR...")
        
        print(f"  📄 转换PDF (DPI={self.config.dpi})...")
        conv_start = time.time()
        
        try:
            images = convert_from_path(
                str(pdf_path),
                dpi=self.config.dpi,
                poppler_path=self.config.poppler_path
            )
        except Exception as e:
            print(f"❌ PDF转换失败: {e}")
            return None
        
        conv_duration = time.time() - conv_start
        print(f"  ✅ 共 {len(images)} 页 (转换: {conv_duration:.2f}秒)")
        
        print(f"  🔄 多进程处理 ({self.config.parallel_workers} workers)...")
        
        pages = []
        if len(images) == 1:
            result = self._process_single_image(images[0], 1)
            pages.append(result)
        elif len(images) <= self.config.small_pdf_page_threshold:
            print(f"  🔄 顺序处理小页数文档 ({len(images)} 页)...")
            for i, image in enumerate(images, 1):
                pages.append(self._process_single_image(image, i))
        else:
            args_list = [(i, img) for i, img in enumerate(images, 1)]

            with Pool(
                processes=self.config.parallel_workers,
                initializer=init_worker
            ) as pool:
                pages = pool.map(self._process_page_mp_wrapper, args_list)
        
        pages.sort(key=lambda p: p.page)
        total_duration = time.time() - total_start
        
        success_count = sum(1 for p in pages if p.method != "error")
        print(f"\n  📊 处理统计:")
        print(f"     总耗时: {total_duration:.2f}秒")
        print(f"     平均每页: {total_duration/len(pages):.2f}秒")
        print(f"     成功: {success_count}/{len(pages)} 页")
        
        return {
            'filename': pdf_path.name,
            'filepath': str(pdf_path),
            'total_pages': len(pages),
            'method': 'ultra_fast',
            'total_duration': total_duration,
            'pages': [asdict(p) for p in pages],
            'full_text': "\n\n".join([f"=== 第{p.page}页 ===\n{p.text}" for p in pages if p.text])
        }
    
    def _process_page_mp_wrapper(self, args: Tuple[int, Any]) -> PageResult:
        """多进程包装器"""
        global _ocr_engine
        page_num, image = args
        start = time.time()
        
        for attempt in range(self.config.max_retries + 1):
            try:
                if isinstance(image, (str, Path)):
                    image = Image.open(image)
                
                original_size = image.size
                max_dim = max(original_size)
                
                if max_dim > self.config.max_image_size:
                    scale = self.config.max_image_size / max_dim
                    new_size = (int(original_size[0] * scale), int(original_size[1] * scale))
                    image = image.resize(new_size, Image.Resampling.LANCZOS)
                
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.2)
                image = image.filter(ImageFilter.SHARPEN)
                
                temp_dir = Path(self.config.output_dir) / "_temp"
                temp_img = temp_dir / f"_mp_{page_num}_{os.getpid()}.png"

                if _ocr_engine is None:
                    _ocr_engine = RapidOCR()

                texts = self._run_ocr(_ocr_engine, image, fallback_path=temp_img)
                
                duration = time.time() - start
                return PageResult(
                    page=page_num,
                    text="\n".join(texts),
                    method="rapidocr",
                    duration=duration
                )
                
            except Exception as e:
                if attempt < self.config.max_retries:
                    time.sleep(0.3)
                else:
                    return PageResult(
                        page=page_num,
                        text="",
                        method="error",
                        duration=time.time() - start,
                        error=f"{type(e).__name__}: {str(e)}"
                    )
        
        return PageResult(page=page_num, text="", method="error", duration=time.time() - start)

    def _try_pdfplumber(self, pdf_path: str) -> Optional[Dict]:
        """尝试使用pdfplumber"""
        try:
            pages = []
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        pages.append({
                            'page': i,
                            'text': text.strip(),
                            'method': 'pdfplumber',
                            'duration': 0,
                            'error': ''
                        })
            
            if pages and any(p['text'] for p in pages):
                return {
                    'filename': Path(pdf_path).name,
                    'filepath': pdf_path,
                    'total_pages': len(pages),
                    'method': 'pdfplumber',
                    'pages': pages,
                    'full_text': "\n\n".join([f"=== 第{p['page']}页 ===\n{p['text']}" for p in pages])
                }
            return None
        except Exception as e:
            print(f"  ⚠️ pdfplumber 提取失败: {e}")
            return None
    
    def process_file(self, file_path: str, force_ocr: bool = False) -> Optional[Dict]:
        """智能处理文件（自动识别PDF或图片）"""
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        
        if suffix in self.SUPPORTED_PDF_FORMATS:
            return self.process_pdf(str(file_path), force_ocr)
        elif suffix in self.SUPPORTED_IMAGE_FORMATS:
            return self.process_image(str(file_path))
        else:
            print(f"❌ 不支持的文件格式: {suffix}")
            print(f"   支持的格式: PDF, PNG, JPG, JPEG")
            return None

    def process_pdf_pages_sequential(self, pdf_path: str, stop_condition: Optional[Callable[[int, str], bool]] = None, max_pages: Optional[int] = None) -> Optional[Dict]:
        """
        逐页顺序处理PDF，支持提前停止条件
        
        Args:
            pdf_path: PDF文件路径
            stop_condition: 停止条件函数，接收(page_num, text)返回True则停止
            max_pages: 最大处理页数
            
        Returns:
            OCR结果字典，包含已处理的页面
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            print(f"❌ 文件不存在: {pdf_path}")
            return None
        
        print(f"\n{'='*60}")
        print(f"🚀 顺序逐页处理: {pdf_path.name}")
        print(f"{'='*60}")
        
        total_start = time.time()
        
        pdfplumber_limit = min(max_pages, 5) if max_pages else 5
        if HAS_PDFPLUMBER:
            print(f"  📄 尝试 pdfplumber 提取前 {pdfplumber_limit} 页...")
            try:
                pages = []
                scanned_detected = False
                with pdfplumber.open(str(pdf_path)) as pdf:
                    for i, page in enumerate(pdf.pages[:pdfplumber_limit], 1):
                        text = page.extract_text() or ""
                        text = text.strip()
                        if i == 1 and not text and stop_condition:
                            scanned_detected = True
                            break
                        pages.append({
                            'page': i,
                            'text': text,
                            'method': 'pdfplumber',
                            'duration': 0,
                            'error': ''
                        })
                        
                        if stop_condition and stop_condition(i, text):
                            print(f"  ✅ 第 {i} 页满足停止条件，提前结束")
                            total_duration = time.time() - total_start
                            return {
                                'filename': pdf_path.name,
                                'filepath': str(pdf_path),
                                'total_pages': len(pages),
                                'method': 'pdfplumber_sequential',
                                'total_duration': total_duration,
                                'pages': pages,
                                'full_text': "\n\n".join([f"=== 第{p['page']}页 ===\n{p['text']}" for p in pages]),
                                'stopped_at': i
                            }
                
                if not scanned_detected and pages and any(p['text'] for p in pages):
                    total_duration = time.time() - total_start
                    print(f"  ✅ pdfplumber 完成 ({total_duration:.2f}秒)")
                    return {
                        'filename': pdf_path.name,
                        'filepath': str(pdf_path),
                        'total_pages': len(pages),
                        'method': 'pdfplumber_sequential',
                        'total_duration': total_duration,
                        'pages': pages,
                        'full_text': "\n\n".join([f"=== 第{p['page']}页 ===\n{p['text']}" for p in pages])
                    }
            except Exception as e:
                print(f"  ⚠️ pdfplumber 提取失败: {e}")
        
        # 使用OCR逐页处理 - 真正的逐页转换、逐页识别、找到即停
        print(f"  🔍 使用OCR逐页处理（逐页转换，找到即停）...")
        
        try:
            from pdf2image import convert_from_path
            
            max_pages_to_process = max_pages if max_pages is not None else 999
            pages = []
            
            for page_num in range(1, max_pages_to_process + 1):
                print(f"  📄 转换第 {page_num} 页...", end=" ")
                convert_start = time.time()
                
                try:
                    # 只转换当前这一页
                    images = convert_from_path(
                        str(pdf_path),
                        dpi=self.config.dpi,
                        poppler_path=self.config.poppler_path,
                        first_page=page_num,
                        last_page=page_num
                    )
                    
                    if not images:
                        print(f"(无更多页面)")
                        break
                    
                    convert_duration = time.time() - convert_start
                    print(f"({convert_duration:.2f}s)", end=" ")
                    
                    # 识别这一页
                    print(f"📝 识别...", end=" ")
                    ocr_start = time.time()
                    
                    result = self._process_single_image(images[0], page_num)
                    pages.append(asdict(result))
                    
                    ocr_duration = time.time() - ocr_start
                    print(f"({ocr_duration:.2f}s)")
                    
                    # 检查停止条件
                    if stop_condition and stop_condition(page_num, result.text):
                        print(f"  ✅ 第 {page_num} 页满足停止条件，提前结束")
                        break
                    
                except Exception as e:
                    print(f"❌ 第 {page_num} 页处理失败: {e}")
                    break
            
            total_duration = time.time() - total_start
            print(f"\n  📊 处理统计: 共 {len(pages)} 页, 总耗时 {total_duration:.2f}秒")
            
            return {
                'filename': pdf_path.name,
                'filepath': str(pdf_path),
                'total_pages': len(pages),
                'method': 'sequential_ocr_optimized',
                'total_duration': total_duration,
                'pages': pages,
                'full_text': "\n\n".join([f"=== 第{p['page']}页 ===\n{p['text']}" for p in pages]),
                'stopped_early': stop_condition is not None and len(pages) < max_pages_to_process
            }
            
        except Exception as e:
            print(f"❌ OCR处理失败: {e}")
            return None

    def save_result(self, result: Dict, apply_postprocess: bool = True) -> Dict[str, Path]:
        """保存结果"""
        output_dir = Path(self.config.output_dir)
        base_name = Path(result['filename']).stem
        
        # 应用文本后处理
        if apply_postprocess:
            try:
                from core.text_postprocessor import TextPostProcessor
                processor = TextPostProcessor()
                process_result = processor.process(result['full_text'])
                result['full_text'] = process_result['processed']
                result['case_numbers'] = process_result['case_numbers']
                result['postprocess_changes'] = process_result['changes']
                
                # 同时处理每页的文本
                for page in result.get('pages', []):
                    if isinstance(page, dict) and 'text' in page:
                        page_result = processor.process(page['text'])
                        page['text'] = page_result['processed']
                        page['case_numbers'] = page_result['case_numbers']
                
                print(f"\n📝 文本后处理完成:")
                for change in process_result['changes']:
                    print(f"   ✓ {change}")
                if process_result['case_numbers']:
                    print(f"   📋 识别案号: {len(process_result['case_numbers'])} 个")
            except Exception as e:
                print(f"\n⚠️ 文本后处理失败: {e}")
        
        txt_path = output_dir / f"{base_name}_ultra_result.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(result['full_text'])
        
        json_path = output_dir / f"{base_name}_ultra_result.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 已保存:")
        print(f"   TXT:  {txt_path}")
        print(f"   JSON: {json_path}")
        
        return {'txt': txt_path, 'json': json_path}


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='PDF/图片 OCR 工具 - 超极速版',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
支持的文件格式:
  - PDF: .pdf
  - 图片: .png, .jpg, .jpeg

使用示例:
  # 处理PDF
  python pdf_ocr_ultra.py input/document.pdf

  # 处理图片
  python pdf_ocr_ultra.py input/scanned.png

  # 批量处理
  python pdf_ocr_ultra.py input/*.pdf input/*.png

  # 强制OCR（跳过pdfplumber）
  python pdf_ocr_ultra.py document.pdf --force-ocr

  # 调整参数
  python pdf_ocr_ultra.py document.pdf --dpi 200 --workers 6
        '''
    )
    
    parser.add_argument('files', nargs='+', help='PDF或图片文件路径')
    parser.add_argument('-o', '--output', default='./output', help='输出目录')
    parser.add_argument('--force-ocr', action='store_true', help='强制使用OCR')
    parser.add_argument('--dpi', type=int, default=200, help='DPI (默认: 200)')
    parser.add_argument('--max-size', type=int, default=900, help='最大图像尺寸 (默认: 900)')
    parser.add_argument('--workers', type=int, default=min(cpu_count(), 4), help=f'进程数 (默认: {min(cpu_count(), 4)})')
    
    args = parser.parse_args()
    
    config = OCRConfig(
        output_dir=args.output,
        dpi=args.dpi,
        max_image_size=args.max_size,
        parallel_workers=args.workers
    )
    
    try:
        processor = UltraFastOCR(config)
    except RuntimeError:
        return 1
    
    success_count = 0
    for file_path in args.files:
        result = processor.process_file(file_path, force_ocr=args.force_ocr)
        if result:
            processor.save_result(result)
            
            print(f"\n{'='*60}")
            print(f"📋 预览 (前500字符):")
            print(f"{'='*60}")
            preview = result['full_text'][:500]
            print(preview + "..." if len(result['full_text']) > 500 else preview)
            success_count += 1
        else:
            print(f"❌ 处理失败: {file_path}")
    
    print(f"\n✅ 完成! 成功处理 {success_count}/{len(args.files)} 个文件")
    return 0 if success_count == len(args.files) else 1


if __name__ == '__main__':
    sys.exit(main())
