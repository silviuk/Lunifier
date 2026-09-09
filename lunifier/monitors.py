"""
Multi-monitor detection and geometry calculations for Windows and Linux.
Provides precise physical display bounds, primary monitor detection,
and coordinate mapping across displays of varying resolutions and offsets.
"""

from dataclasses import dataclass, asdict
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

from .logger import log, log_debug

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG)
        ]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32)
        ]
else:
    import ctypes
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
    id: str               # Unique identifier, e.g. "0", "1" or "DISPLAY1"
    name: str = ""        # Display name: "Monitor 1 (Primary - 2560x1440)"
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

    @property
    def is_primary(self) -> bool:
        return self.primary

    def contains(self, x: int, y: int, tol: int = 2) -> bool:
        """Returns True if the coordinates fall within or on the border of this monitor."""
        return (
            (self.left - tol) <= x <= (self.right + tol) and
            (self.top - tol) <= y <= (self.bottom + tol)
        )

    def contains_point(self, x: int, y: int, tol: int = 2) -> bool:
        return self.contains(x, y, tol=tol)

    def calculate_ratio(self, x: int, y: int, edge: str) -> float:
        """Calculates normalized position along specified edge (0.0 to 1.0)."""
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


def _get_monitors_windows() -> List[MonitorInfo]:
    monitors: List[MonitorInfo] = []

    def enum_callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
            r = info.rcMonitor
            is_primary = bool(info.dwFlags & 1)
            w = r.right - r.left
            h = r.bottom - r.top
            dev_name = str(info.szDevice).replace("\\\\.\\", "")
            idx = len(monitors) + 1
            primary_tag = " (Primary)" if is_primary else ""
            label = f"Monitor {idx}{primary_tag} - {w}x{h} at ({r.left}, {r.top})"
            monitors.append(MonitorInfo(
                id=str(idx - 1),
                name=label,
                left=int(r.left),
                top=int(r.top),
                right=int(r.right),
                bottom=int(r.bottom),
                width=int(w),
                height=int(h),
                primary=is_primary
            ))
        return True

    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(RECT),
        wintypes.LPARAM
    )
    user32.EnumDisplayMonitors(None, None, MonitorEnumProc(enum_callback), 0)

    # Sort so primary is first, then left-to-right
    monitors.sort(key=lambda m: (not m.primary, m.left, m.top))
    # Re-index IDs and clean names after sorting
    for i, m in enumerate(monitors):
        m.id = str(i)
        primary_tag = " (Primary)" if m.primary else ""
        m.name = f"Monitor {i + 1}{primary_tag} - {m.width}x{m.height} at ({m.left}, {m.top})"
    return monitors


def _get_monitors_linux() -> List[MonitorInfo]:
    monitors: List[MonitorInfo] = []

    # Method 1: libXinerama direct C query
    if x11 and xinerama:
        try:
            dpy = x11.XOpenDisplay(None)
            if dpy:
                try:
                    if xinerama.XineramaIsActive(dpy):
                        num_screens = ctypes.c_int()
                        xinerama.XineramaQueryScreens.restype = ctypes.POINTER(XineramaScreenInfo)
                        screens_ptr = xinerama.XineramaQueryScreens(dpy, ctypes.byref(num_screens))
                        if screens_ptr:
                            for i in range(num_screens.value):
                                s = screens_ptr[i]
                                is_primary = (i == 0)  # Default first as primary in Xinerama
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
            # Matches: HDMI-1 connected primary 1920x1080+0+0
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

    # Method 3: Fallback single monitor via X11 default screen or Tkinter
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


def get_monitors() -> List[MonitorInfo]:
    """
    Returns an ordered list of all detected physical displays.
    The primary display is always at index 0.
    """
    try:
        if sys.platform == "win32":
            monitors = _get_monitors_windows()
        else:
            monitors = _get_monitors_linux()
        if monitors:
            return monitors
    except Exception as e:
        log("Monitors", f"Error enumerating monitors: {e}")

    # Universal ultimate fallback
    return [MonitorInfo(
        id="0",
        name="Monitor 1 (Primary) - 1920x1080 at (0, 0)",
        left=0,
        top=0,
        right=1920,
        bottom=1080,
        width=1920,
        height=1080,
        primary=True
    )]


def get_monitor_for_point(monitors: List[MonitorInfo], x: int, y: int, tol: int = 2) -> Optional[MonitorInfo]:
    """
    Determines which monitor contains the specified cursor coordinate (x, y).
    If coordinate falls right on a shared boundary, prioritizes the primary or matching monitor.
    """
    if not monitors:
        return None

    # First exact match
    for m in monitors:
        if m.left <= x <= m.right and m.top <= y <= m.bottom:
            return m

    # Near match with boundary tolerance
    for m in monitors:
        if m.contains(x, y, tol=tol):
            return m

    # If cursor is off-screen (e.g. during fast flick), return closest monitor
    best_m = monitors[0]
    min_dist = float("inf")
    for m in monitors:
        # Distance to monitor rectangle
        dx = max(m.left - x, 0, x - m.right)
        dy = max(m.top - y, 0, y - m.bottom)
        dist = dx * dx + dy * dy
        if dist < min_dist:
            min_dist = dist
            best_m = m
    return best_m


def get_virtual_desktop_bounds(monitors: List[MonitorInfo]) -> Dict[str, int]:
    """
    Calculates the aggregate bounding box covering all monitors.
    """
    if not monitors:
        return {"left": 0, "top": 0, "right": 1920, "bottom": 1080}

    left = min(m.left for m in monitors)
    top = min(m.top for m in monitors)
    right = max(m.right for m in monitors)
    bottom = max(m.bottom for m in monitors)
    return {"left": left, "top": top, "right": right, "bottom": bottom}
