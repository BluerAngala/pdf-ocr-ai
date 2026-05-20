#!/usr/bin/env python3
"""跨模块任务取消注册表 — 基于 threading.Event"""

import threading
from typing import Dict

_lock = threading.Lock()
_events: Dict[str, threading.Event] = {}


def request_cancel(task_id: str):
    with _lock:
        ev = _events.get(task_id)
        if ev is None:
            ev = threading.Event()
            _events[task_id] = ev
        ev.set()


def is_cancelled(task_id: str) -> bool:
    with _lock:
        ev = _events.get(task_id)
    return ev is not None and ev.is_set()


def get_event(task_id: str) -> threading.Event:
    with _lock:
        if task_id not in _events:
            _events[task_id] = threading.Event()
        return _events[task_id]


def clear(task_id: str):
    with _lock:
        _events.pop(task_id, None)


def clear_all():
    with _lock:
        _events.clear()


class CancelledError(Exception):
    pass
