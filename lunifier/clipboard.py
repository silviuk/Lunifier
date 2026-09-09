"""
Cross-Platform Clipboard Manager for Windows and Linux.
Enables clipboard text synchronization over Bluetooth without network requirements.
"""

import sys
import subprocess
from typing import Optional

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL


class ClipboardManager:
    @staticmethod
    def get_text() -> str:
        """
        Reads current UTF-8/Unicode text from system clipboard.
        """
        if sys.platform == "win32":
            text = ""
            if not user32.OpenClipboard(None):
                return text
            try:
                h_data = user32.GetClipboardData(CF_UNICODETEXT)
                if h_data:
                    p_data = kernel32.GlobalLock(h_data)
                    if p_data:
                        text = ctypes.c_wchar_p(p_data).value or ""
                        kernel32.GlobalUnlock(h_data)
            finally:
                user32.CloseClipboard()
            return text
        else:
            # Linux: try xclip, xsel, or wl-paste
            for cmd in [["xclip", "-selection", "clipboard", "-o"],
                        ["xsel", "--clipboard", "--output"],
                        ["wl-paste"]]:
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=1)
                    if res.returncode == 0:
                        return res.stdout
                except Exception:
                    continue
            return ""

    @staticmethod
    def set_text(text: str) -> bool:
        """
        Sets UTF-8/Unicode text into the system clipboard.
        """
        if not text:
            return False

        if sys.platform == "win32":
            if not user32.OpenClipboard(None):
                return False
            try:
                user32.EmptyClipboard()
                # Windows wchar is 2 bytes + null terminator
                text_bytes = (text + "\0").encode("utf-16le")
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
                if not h_mem:
                    return False
                p_mem = kernel32.GlobalLock(h_mem)
                if not p_mem:
                    return False
                ctypes.memmove(p_mem, text_bytes, len(text_bytes))
                kernel32.GlobalUnlock(h_mem)
                user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                return True
            finally:
                user32.CloseClipboard()
        else:
            # Linux: try xclip, xsel, wl-copy
            for cmd in [["xclip", "-selection", "clipboard"],
                        ["xsel", "--clipboard", "--input"],
                        ["wl-copy"]]:
                try:
                    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                    proc.communicate(input=text.encode("utf-8"), timeout=1)
                    if proc.returncode == 0:
                        return True
                except Exception:
                    continue
            return False
