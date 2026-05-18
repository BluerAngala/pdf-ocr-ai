#!/usr/bin/env python3

import os
import platform
from dataclasses import dataclass
from multiprocessing import cpu_count
from typing import Optional


@dataclass
class ResourceProfile:
    cpu_count: int
    total_memory_gb: float
    available_memory_gb: float
    recommended_workers: int
    memory_per_worker_gb: float
    safety_level: str

    def __str__(self) -> str:
        return (
            f"CPU: {self.cpu_count} 核, "
            f"内存: {self.available_memory_gb:.1f}/{self.total_memory_gb:.1f} GB 可用, "
            f"推荐并发: {self.recommended_workers}, "
            f"安全等级: {self.safety_level}"
        )


OCR_MODEL_MEMORY_GB = 1.5


def _get_total_memory_gb() -> float:
    if platform.system() == 'Windows':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            status = ctypes.c_ulonglong()
            kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            MEMORYSTATUSEX = ctypes.c_ulonglong * 8
            buf = MEMORYSTATUSEX()
            buf[0] = ctypes.sizeof(buf)
            kernel32.GlobalMemoryStatusEx(buf)
            return float(buf[1]) / (1024 ** 3)
        except Exception:
            pass
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        pass
    return 8.0


def _get_available_memory_gb() -> float:
    if platform.system() == 'Windows':
        try:
            import ctypes
            MEMORYSTATUSEX = ctypes.c_ulonglong * 8
            buf = MEMORYSTATUSEX()
            buf[0] = ctypes.sizeof(buf)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(buf)
            return float(buf[3]) / (1024 ** 3)
        except Exception:
            pass
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 ** 3)
    except ImportError:
        pass
    return 4.0


def _calc_safety_level(available_gb: float, workers: int) -> str:
    needed = workers * OCR_MODEL_MEMORY_GB
    if needed >= available_gb * 0.85:
        return 'critical'
    if needed >= available_gb * 0.65:
        return 'low'
    if needed >= available_gb * 0.45:
        return 'moderate'
    return 'high'


def detect_system_resources(*, reserve_gb: float = 1.5, max_workers: Optional[int] = None) -> ResourceProfile:
    cpus = cpu_count()
    total_gb = _get_total_memory_gb()
    available_gb = _get_available_memory_gb()
    
    # 保留 40% 的可用内存，只使用 60%
    usable_gb = available_gb * 0.6

    max_by_memory = max(1, int(usable_gb / OCR_MODEL_MEMORY_GB))
    max_by_cpu = max(1, cpus - 1) if cpus > 2 else 1
    workers = min(max_by_memory, max_by_cpu, 4)
    if max_workers is not None:
        workers = min(workers, max_workers)
    workers = max(1, workers)

    safety = _calc_safety_level(available_gb, workers)

    return ResourceProfile(
        cpu_count=cpus,
        total_memory_gb=round(total_gb, 2),
        available_memory_gb=round(available_gb, 2),
        recommended_workers=workers,
        memory_per_worker_gb=OCR_MODEL_MEMORY_GB,
        safety_level=safety,
    )
