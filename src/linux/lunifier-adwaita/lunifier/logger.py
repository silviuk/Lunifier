"""
Unified timestamped logger for Lunifier Linux.
Outputs thread-safe logs with millisecond precision to stdout and registered listeners.
Supports configurable log levels: "none", "normal", and "debug".
"""
from datetime import datetime
import sys
import threading
from typing import Callable, List

LOG_LEVEL_NONE = "none"
LOG_LEVEL_NORMAL = "normal"
LOG_LEVEL_DEBUG = "debug"

_listeners: List[Callable[[str], None]] = []
_listeners_lock = threading.Lock()
_print_lock = threading.Lock()
_level_lock = threading.Lock()
_current_log_level: str = LOG_LEVEL_NORMAL


def set_log_level(level: str) -> None:
    global _current_log_level
    lvl = str(level).strip().lower()
    if lvl in ("none", "off", "disabled", "silent"):
        norm = LOG_LEVEL_NONE
    elif lvl in ("debug", "verbose", "trace"):
        norm = LOG_LEVEL_DEBUG
    else:
        norm = LOG_LEVEL_NORMAL

    with _level_lock:
        _current_log_level = norm


def get_log_level() -> str:
    with _level_lock:
        return _current_log_level


def is_debug_enabled() -> bool:
    with _level_lock:
        return _current_log_level == LOG_LEVEL_DEBUG


def add_log_listener(listener: Callable[[str], None]) -> None:
    with _listeners_lock:
        if listener not in _listeners:
            _listeners.append(listener)


def remove_log_listener(listener: Callable[[str], None]) -> None:
    with _listeners_lock:
        if listener in _listeners:
            _listeners.remove(listener)


def log(tag: str, message: str, level: str = LOG_LEVEL_NORMAL) -> None:
    with _level_lock:
        cur_level = _current_log_level

    if cur_level == LOG_LEVEL_NONE:
        return

    lvl = str(level).lower()
    if cur_level == LOG_LEVEL_NORMAL and lvl == LOG_LEVEL_DEBUG:
        return

    now = datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M:%S") + f".{now.microsecond // 1000:03d}"

    prefix = f"[{ts}] [{tag}]"
    if lvl == LOG_LEVEL_DEBUG:
        prefix = f"[{ts}] [DEBUG] [{tag}]"

    lines = str(message).splitlines()
    if not lines:
        lines = [""]

    formatted_lines = [f"{prefix} {lines[0]}"]
    indent = " " * len(prefix)
    for l in lines[1:]:
        formatted_lines.append(f"{indent}   {l}")

    formatted = "\n".join(formatted_lines)

    with _print_lock:
        try:
            print(formatted, flush=True)
        except Exception:
            pass

    with _listeners_lock:
        listeners_copy = list(_listeners)

    for cb in listeners_copy:
        try:
            cb(formatted)
        except Exception:
            pass


def log_debug(tag: str, message: str) -> None:
    log(tag, message, level=LOG_LEVEL_DEBUG)
