#!/usr/bin/env python3
"""跨模块任务取消注册表"""

import threading
from typing import Dict

_lock = threading.Lock()
_flags: Dict[str, bool] = {}


def request_cancel(task_id: str):
    with _lock:
        _flags[task_id] = True


def is_cancelled(task_id: str) -> bool:
    with _lock:
        return _flags.get(task_id, False)


def clear(task_id: str):
    with _lock:
        _flags.pop(task_id, None)
