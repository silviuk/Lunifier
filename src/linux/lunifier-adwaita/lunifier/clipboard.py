"""
Linux Clipboard Manager and Cursor Manager for Lunifier.
"""

import subprocess
import ctypes
from typing import Optional, Dict

try:
    x11 = ctypes.cdll.LoadLibrary("libX11.so.6")
except Exception:
    try:
        x11 = ctypes.cdll.LoadLibrary("libX11.so")
    except Exception:
        x11 = None


class ClipboardManager:
    @staticmethod
    def get_text() -> str:
        for cmd in [["wl-paste"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]]:
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=1)
                if res.returncode == 0:
                    return res.stdout
            except Exception:
                continue
        return ""

    @staticmethod
    def set_text(text: str) -> bool:
        if not text:
            return False

        for cmd in [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
            try:
                res = subprocess.run(cmd, input=text, text=True, timeout=1)
                if res.returncode == 0:
                    return True
            except Exception:
                continue
        return False


class CursorManager:
    def __init__(self):
        self._x11_display = None
        self._x11_root = None
        if x11:
            try:
                self._x11_display = x11.XOpenDisplay(None)
                if self._x11_display:
                    self._x11_root = x11.XDefaultRootWindow(self._x11_display)
            except Exception:
                pass

    def __del__(self):
        if getattr(self, "_x11_display", None) and x11:
            try:
                x11.XCloseDisplay(self._x11_display)
            except Exception:
                pass

    def set_cursor_pos(self, x: int, y: int) -> bool:
        if getattr(self, "_x11_display", None) and getattr(self, "_x11_root", None) and x11:
            try:
                x11.XWarpPointer(self._x11_display, None, self._x11_root, 0, 0, 0, 0, int(x), int(y))
                x11.XFlush(self._x11_display)
                return True
            except Exception:
                pass

        try:
            subprocess.run(["xdotool", "mousemove", str(int(x)), str(int(y))], timeout=1)
            return True
        except Exception:
            pass
        return False

    def position_cursor_at_entry(self, entry_edge: str, ratio: float, bounds: Dict[str, int]) -> None:
        ratio = max(0.0, min(1.0, ratio))
        margin = 60
        w = max(1, bounds["right"] - bounds["left"])
        h = max(1, bounds["bottom"] - bounds["top"])

        if entry_edge == "left":
            target_x = bounds["left"] + margin
            target_y = bounds["top"] + int(ratio * h)
        elif entry_edge == "right":
            target_x = bounds["right"] - margin
            target_y = bounds["top"] + int(ratio * h)
        elif entry_edge == "top":
            target_x = bounds["left"] + int(ratio * w)
            target_y = bounds["top"] + margin
        elif entry_edge == "bottom":
            target_x = bounds["left"] + int(ratio * w)
            target_y = bounds["bottom"] - margin
        else:
            target_x = bounds["left"] + int(w / 2)
            target_y = bounds["top"] + int(h / 2)

        self.set_cursor_pos(target_x, target_y)
