"""
Unified, high-precision timestamped logger for Lunifier.
Outputs thread-safe logs with millisecond precision to stdout and registered listeners.
"""
from datetime import datetime
import sys
import threading
from typing import Callable, List, Optional

_listeners: List[Callable[[str], None]] = []
_listeners_lock = threading.Lock()
_print_lock = threading.Lock()


def add_log_listener(listener: Callable[[str], None]) -> None:
    with _listeners_lock:
        if listener not in _listeners:
            _listeners.append(listener)


def remove_log_listener(listener: Callable[[str], None]) -> None:
    with _listeners_lock:
        if listener in _listeners:
            _listeners.remove(listener)


def log(tag: str, message: str) -> None:
    """
    Format: [YYYY-MM-DD HH:MM:SS.mmm] [TAG] message
    Splits multi-line messages and tags each line.
    Flushes to stdout immediately and dispatches to any UI listeners.
    """
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M:%S") + f".{now.microsecond // 1000:03d}"
    
    lines = str(message).splitlines()
    if not lines:
        lines = [""]
        
    formatted_lines = [f"[{ts}] [{tag}] {lines[0]}"]
    for l in lines[1:]:
        formatted_lines.append(f"[{ts}] [{tag}]   {l}")
        
    formatted = "\n".join(formatted_lines)
    
    with _print_lock:
        try:
            print(formatted, flush=True)
        except Exception:
            pass

    with _listeners_lock:
        listeners_copy = list(_listeners)
        
    for listener in listeners_copy:
        try:
            listener(formatted)
        except Exception:
            pass
