"""
Multi-monitor detection and geometry calculations for Linux.
Provides physical display bounds, primary monitor detection,
and coordinate mapping across displays of varying resolutions and offsets.
"""

from dataclasses import dataclass, asdict
import ctypes
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

from .logger import log, log_debug

try:
    x11 = ctypes.cdll.LoadLibrary("libX11.so.6")
except Exception:
    try:
        x11 = ctypes.cdll.LoadLibrary("libX11.so")
    except Exception:
        x11 = None

try:
    xinerama = ctypes.cdll.LoadLibrary("libXinerama.so.1")
except Exception:
    try:
        xinerama = ctypes.cdll.LoadLibrary("libXinerama.so")
    except Exception:
        xinerama = None

class XineramaScreenInfo(ctypes.Structure):
    _fields_ = [
        ("screen_number", ctypes.c_int),
        ("x_org", ctypes.c_short),
        ("y_org", ctypes.c_short),
        ("width", ctypes.c_short),
        ("height", ctypes.c_short),
    ]

if x11:
    if hasattr(x11, "XInitThreads"):
        try:
            x11.XInitThreads.restype = ctypes.c_int
            x11.XInitThreads()
        except Exception:
            pass
    try:
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XCloseDisplay.restype = ctypes.c_int
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XFree.restype = ctypes.c_int
        x11.XFree.argtypes = [ctypes.c_void_p]
    except Exception:
        pass

if xinerama:
    try:
        xinerama.XineramaIsActive.restype = ctypes.c_int
        xinerama.XineramaIsActive.argtypes = [ctypes.c_void_p]
        xinerama.XineramaQueryScreens.restype = ctypes.POINTER(XineramaScreenInfo)
        xinerama.XineramaQueryScreens.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    except Exception:
        pass


@dataclass
class MonitorInfo:
    id: str
    name: str = ""
    left: int = 0
    top: int = 0
    right: int = 1920
    bottom: int = 1080
    width: int = 0
    height: int = 0
    primary: bool = False
    index: int = 0

    def __post_init__(self):
        self.id = str(self.id)
        if not self.width:
            self.width = self.right - self.left
        if not self.height:
            self.height = self.bottom - self.top
        if not self.name:
            primary_tag = " (Primary)" if self.primary else ""
            self.name = f"Monitor {self.id}{primary_tag} - {self.width}x{self.height} at ({self.left}, {self.top})"
        try:
            self.index = int(self.id)
        except Exception:
            pass

    def contains(self, x: int, y: int, tol: int = 2) -> bool:
        return (
            (self.left - tol) <= x <= (self.right + tol) and
            (self.top - tol) <= y <= (self.bottom + tol)
        )

    def calculate_ratio(self, x: int, y: int, edge: str) -> float:
        e = edge.lower()
        if e in ("left", "right"):
            if self.height <= 0:
                return 0.5
            return max(0.0, min(1.0, (y - self.top) / float(self.height)))
        else:
            if self.width <= 0:
                return 0.5
            return max(0.0, min(1.0, (x - self.left) / float(self.width)))

    def to_dict(self) -> dict:
        return asdict(self)


def get_monitors() -> List[MonitorInfo]:
    monitors: List[MonitorInfo] = []

    # Method 1: libXinerama
    if x11 and xinerama:
        try:
            dpy = x11.XOpenDisplay(None)
            if dpy:
                try:
                    if xinerama.XineramaIsActive(dpy):
                        num_screens = ctypes.c_int()
                        screens_ptr = xinerama.XineramaQueryScreens(dpy, ctypes.byref(num_screens))
                        if screens_ptr:
                            for i in range(num_screens.value):
                                s = screens_ptr[i]
                                is_primary = (i == 0)
                                monitors.append(MonitorInfo(
                                    id=str(i),
                                    name=f"Monitor {i + 1}{' (Primary)' if is_primary else ''} - {s.width}x{s.height} at ({s.x_org}, {s.y_org})",
                                    left=int(s.x_org),
                                    top=int(s.y_org),
                                    right=int(s.x_org + s.width),
                                    bottom=int(s.y_org + s.height),
                                    width=int(s.width),
                                    height=int(s.height),
                                    primary=is_primary
                                ))
                            x11.XFree(screens_ptr)
                finally:
                    x11.XCloseDisplay(dpy)
        except Exception as e:
            log_debug("Monitors", f"Xinerama query failed: {e}")

    if monitors:
        return monitors

    # Method 2: xrandr CLI parser
    try:
        res = subprocess.run(["xrandr", "--query"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            pattern = re.compile(r"^(\S+)\s+(connected\s+(?:primary\s+)?(\d+)x(\d+)\+([+-]?\d+)\+([+-]?\d+))", re.MULTILINE)
            idx = 0
            for match in pattern.finditer(res.stdout):
                dev = match.group(1)
                full = match.group(2)
                w = int(match.group(3))
                h = int(match.group(4))
                x = int(match.group(5))
                y = int(match.group(6))
                is_primary = "primary" in full
                monitors.append(MonitorInfo(
                    id=str(idx),
                    name=f"Monitor {idx + 1} ({dev}{' Primary' if is_primary else ''}) - {w}x{h} at ({x}, {y})",
                    left=x,
                    top=y,
                    right=x + w,
                    bottom=y + h,
                    width=w,
                    height=h,
                    primary=is_primary
                ))
                idx += 1
    except Exception as e:
        log_debug("Monitors", f"xrandr query failed: {e}")

    if monitors:
        monitors.sort(key=lambda m: (not m.primary, m.left, m.top))
        for i, m in enumerate(monitors):
            m.id = str(i)
        return monitors

    # Method 3: Fallback single monitor
    w, h = 1920, 1080
    if x11:
        try:
            dpy = x11.XOpenDisplay(None)
            if dpy:
                try:
                    scr = x11.XDefaultScreen(dpy)
                    w = x11.XDisplayWidth(dpy, scr)
                    h = x11.XDisplayHeight(dpy, scr)
                finally:
                    x11.XCloseDisplay(dpy)
        except Exception:
            pass

    return [MonitorInfo(
        id="0",
        name=f"Monitor 1 (Primary) - {w}x{h} at (0, 0)",
        left=0,
        top=0,
        right=w,
        bottom=h,
        width=w,
        height=h,
        primary=True
    )]


def get_monitor_for_point(monitors: List[MonitorInfo], x: int, y: int, tol: int = 2) -> Optional[MonitorInfo]:
    if not monitors:
        return None

    for m in monitors:
        if m.left <= x <= m.right and m.top <= y <= m.bottom:
            return m

    for m in monitors:
        if m.contains(x, y, tol=tol):
            return m

    best_m = monitors[0]
    min_dist = float("inf")
    for m in monitors:
        dx = max(m.left - x, 0, x - m.right)
        dy = max(m.top - y, 0, y - m.bottom)
        dist = dx * dx + dy * dy
        if dist < min_dist:
            min_dist = dist
            best_m = m
    return best_m


def get_virtual_desktop_bounds(monitors: List[MonitorInfo]) -> Dict[str, int]:
    if not monitors:
        return {"left": 0, "top": 0, "right": 1920, "bottom": 1080}

    return {
        "left": min(m.left for m in monitors),
        "top": min(m.top for m in monitors),
        "right": max(m.right for m in monitors),
        "bottom": max(m.bottom for m in monitors)
    }
