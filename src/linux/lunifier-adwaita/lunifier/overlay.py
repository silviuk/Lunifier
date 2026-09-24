"""
Visual Screen Border Overlay for Linux with Multi-Monitor Support.
Highlights active border zones along screen edges with an orange indicator (#FF5722)
when adjusting settings or changing monitor edges.
"""

import ctypes
import subprocess
from typing import Dict, List, Optional
try:
    from gi.repository import GLib
except ImportError:
    GLib = None

from .logger import log, log_debug
from .monitors import MonitorInfo, get_monitors

try:
    x11 = ctypes.cdll.LoadLibrary("libX11.so.6")
except Exception:
    try:
        x11 = ctypes.cdll.LoadLibrary("libX11.so")
    except Exception:
        x11 = None

if x11:
    try:
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XCloseDisplay.restype = ctypes.c_int
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XCreateSimpleWindow.restype = ctypes.c_ulong
        x11.XCreateSimpleWindow.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong,
            ctypes.c_int, ctypes.c_int,
            ctypes.c_uint, ctypes.c_uint,
            ctypes.c_uint, ctypes.c_ulong, ctypes.c_ulong
        ]
        x11.XDestroyWindow.restype = ctypes.c_int
        x11.XDestroyWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XMapRaised.restype = ctypes.c_int
        x11.XMapRaised.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XFlush.restype = ctypes.c_int
        x11.XFlush.argtypes = [ctypes.c_void_p]

        class XSetWindowAttributes(ctypes.Structure):
            _fields_ = [
                ("background_pixmap", ctypes.c_ulong),
                ("background_pixel", ctypes.c_ulong),
                ("border_pixmap", ctypes.c_ulong),
                ("border_pixel", ctypes.c_ulong),
                ("bit_gravity", ctypes.c_int),
                ("win_gravity", ctypes.c_int),
                ("backing_store", ctypes.c_int),
                ("backing_planes", ctypes.c_ulong),
                ("backing_pixel", ctypes.c_ulong),
                ("save_under", ctypes.c_int),
                ("event_mask", ctypes.c_long),
                ("do_not_propagate_mask", ctypes.c_long),
                ("override_redirect", ctypes.c_int),
                ("colormap", ctypes.c_ulong),
                ("cursor", ctypes.c_ulong),
            ]

        CWOverrideRedirect = (1 << 9)
        x11.XChangeWindowAttributes.restype = ctypes.c_int
        x11.XChangeWindowAttributes.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
            ctypes.POINTER(XSetWindowAttributes)
        ]
    except Exception as ex:
        log("Overlay", f"Error setting up X11 function signatures: {ex}")
        x11 = None


class BorderOverlayManager:
    """Manages visual orange indicators along active monitor border switching zones."""

    LINE_THICKNESS = 6
    ORANGE_PIXEL = 0x00FF5722  # Vibrant Logitech orange (#FF5722)

    def __init__(self, parent=None):
        self.parent = parent
        self._x11_windows: List[int] = []
        self._hide_timer_id: Optional[int] = None
        self._dpy: Optional[ctypes.c_void_p] = None
        self._root: Optional[int] = None

    def _ensure_display(self) -> bool:
        if not x11:
            return False
        if not self._dpy:
            try:
                self._dpy = x11.XOpenDisplay(None)
                if self._dpy:
                    self._root = x11.XDefaultRootWindow(self._dpy)
            except Exception as ex:
                log("Overlay", f"Failed to open X11 display: {ex}")
                self._dpy = None
                self._root = None
        return bool(self._dpy and self._root)

    def _get_accent_color(self) -> int:
        gnome_accents = {
            "orange": 0x00FF5722,
            "blue": 0x003584E4,
            "teal": 0x0021A4DF,
            "green": 0x002EC27E,
            "yellow": 0x00E5A50A,
            "red": 0x00E01B24,
            "pink": 0x00E661AC,
            "purple": 0x009141AC,
            "slate": 0x0077767B,
        }
        try:
            res = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "accent-color"], capture_output=True, text=True, timeout=0.2)
            if res.returncode == 0:
                name = res.stdout.strip().strip("'\"").lower()
                if name in gnome_accents:
                    return gnome_accents[name]
        except Exception:
            pass
        return self.ORANGE_PIXEL

    def show(self, active_zone_pct: int, edges: Optional[Dict[str, List[str]]] = None, monitor_id: Optional[str] = None):
        """
        Displays accent/orange bars along the active zones of configured screen edges.
        Automatically hides after 1.5 seconds.
        """
        # Cancel any pending auto-hide timer
        if self._hide_timer_id:
            try:
                GLib.source_remove(self._hide_timer_id)
            except Exception:
                pass
            self._hide_timer_id = None

        # Clean up existing overlay windows first
        self._close_windows()

        if not self._ensure_display():
            log_debug("Overlay", "X11 display not available; visual border overlay skipped.")
            return

        monitors = get_monitors()
        pct = max(10, min(100, active_zone_pct))
        margin_ratio = (1.0 - (pct / 100.0)) / 2.0
        bar_color = self._get_accent_color()

        for m in monitors:
            mid = str(m.id)
            if edges is not None:
                if mid in edges:
                    active_edges = edges[mid]
                elif mid == "0" and "0" in edges:
                    active_edges = edges["0"]
                else:
                    continue  # Do not draw on unconfigured or disabled monitors
            elif monitor_id is not None:
                if mid != str(monitor_id):
                    continue
                active_edges = ["left", "right", "top", "bottom"]
            else:
                active_edges = ["left", "right", "top", "bottom"]

            if not active_edges:
                continue

            for edge in active_edges:
                edge_lower = edge.lower()
                seg_x, seg_y, seg_w, seg_h = 0, 0, 0, 0

                if edge_lower == "left":
                    seg_x = m.left
                    seg_y = int(m.top + margin_ratio * m.height)
                    seg_w = self.LINE_THICKNESS
                    seg_h = max(1, int((1.0 - 2.0 * margin_ratio) * m.height))
                elif edge_lower == "right":
                    seg_x = m.left + m.width - self.LINE_THICKNESS
                    seg_y = int(m.top + margin_ratio * m.height)
                    seg_w = self.LINE_THICKNESS
                    seg_h = max(1, int((1.0 - 2.0 * margin_ratio) * m.height))
                elif edge_lower == "top":
                    seg_x = int(m.left + margin_ratio * m.width)
                    seg_y = m.top
                    seg_w = max(1, int((1.0 - 2.0 * margin_ratio) * m.width))
                    seg_h = self.LINE_THICKNESS
                elif edge_lower == "bottom":
                    seg_x = int(m.left + margin_ratio * m.width)
                    seg_y = m.top + m.height - self.LINE_THICKNESS
                    seg_w = max(1, int((1.0 - 2.0 * margin_ratio) * m.width))
                    seg_h = self.LINE_THICKNESS
                else:
                    continue

                try:
                    win = x11.XCreateSimpleWindow(
                        self._dpy, self._root,
                        seg_x, seg_y, seg_w, seg_h,
                        0, 0, bar_color
                    )
                    attr = XSetWindowAttributes()
                    attr.override_redirect = 1
                    x11.XChangeWindowAttributes(self._dpy, win, CWOverrideRedirect, ctypes.byref(attr))
                    x11.XMapRaised(self._dpy, win)
                    self._x11_windows.append(win)
                except Exception as ex:
                    log("Overlay", f"Error creating overlay segment for {edge_lower} on monitor {mid}: {ex}")

        if self._x11_windows:
            try:
                x11.XFlush(self._dpy)
            except Exception:
                pass
            # Schedule automatic hide after 1.5 seconds
            if GLib:
                self._hide_timer_id = GLib.timeout_add(1500, self._on_timer_hide)

    def _on_timer_hide(self) -> bool:
        self._hide_timer_id = None
        self.hide()
        return False  # Do not repeat

    def _close_windows(self):
        if self._dpy and self._x11_windows:
            for win in self._x11_windows:
                try:
                    x11.XDestroyWindow(self._dpy, win)
                except Exception:
                    pass
            try:
                x11.XFlush(self._dpy)
            except Exception:
                pass
            self._x11_windows.clear()

    def hide(self):
        """Hides any visible border overlays immediately."""
        if self._hide_timer_id:
            try:
                GLib.source_remove(self._hide_timer_id)
            except Exception:
                pass
            self._hide_timer_id = None
        self._close_windows()

    def close(self):
        """Clean up overlay windows and display connection."""
        self.hide()
        if self._dpy and x11:
            try:
                x11.XCloseDisplay(self._dpy)
            except Exception:
                pass
            self._dpy = None
            self._root = None

