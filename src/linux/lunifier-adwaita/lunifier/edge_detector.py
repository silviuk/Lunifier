"""
Precision Screen Edge Detector for Linux with Multi-Monitor Support.
Monitors cursor position and triggers a switch event when the cursor dwells at configured
screen edges on designated monitors.
"""

from collections import deque
import sys
import time
import threading
import ctypes
import subprocess
from typing import Callable, Optional, Tuple, List, Dict, Any

from .logger import log, log_debug
from .monitors import MonitorInfo, get_monitors, get_monitor_for_point, get_virtual_desktop_bounds

try:
    x11 = ctypes.cdll.LoadLibrary("libX11.so.6")
except Exception:
    try:
        x11 = ctypes.cdll.LoadLibrary("libX11.so")
    except Exception:
        x11 = None

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
        x11.XQueryPointer.restype = ctypes.c_int
        x11.XQueryPointer.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint)
        ]
        XErrorHandler = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        def _ignore_x_error(d, e): return 0
        _c_err_handler = XErrorHandler(_ignore_x_error)
        x11.XSetErrorHandler(_c_err_handler)
        x11.XSetIOErrorHandler(_c_err_handler)
    except Exception:
        pass


class ScreenEdgeDetector:
    def __init__(self,
                 trigger_edge: str = "right",
                 active_edges: Optional[List[str]] = None,
                 hold_delay_ms: int = 250,
                 cooldown_ms: int = 2500,
                 active_zone_pct: int = 50,
                 knock_enabled: bool = False,
                 knock_timeout_ms: int = 1000,
                 monitor_configs: Optional[Dict[str, Dict[str, Any]]] = None,
                 on_trigger_callback: Optional[Callable] = None):
        self.trigger_edge = trigger_edge.lower() if trigger_edge else "right"
        self.active_edges = [e.lower() for e in active_edges] if active_edges else [self.trigger_edge]
        self.hold_delay_ms = hold_delay_ms
        self.cooldown_ms = cooldown_ms
        self.active_zone_pct = max(10, min(100, active_zone_pct))
        self.knock_enabled = knock_enabled
        self.knock_timeout_ms = knock_timeout_ms
        self.monitor_configs = monitor_configs or {}
        self.on_trigger_callback = on_trigger_callback

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_edge: Optional[str] = None
        self._current_monitor_id: Optional[str] = None
        self._hold_start_time: Optional[float] = None
        self._last_trigger_time: float = 0.0

        self.monitors: List[MonitorInfo] = []
        self._screen_bounds: Dict[str, int] = {}
        self.refresh_screen_bounds()

        self._last_knock_edge: Optional[str] = None
        self._last_knock_time: float = 0.0

        self._is_switched_out: bool = False
        self._switched_out_edge: Optional[str] = None
        self._last_known_cursor_pos: Optional[Tuple[int, int]] = None
        self._return_guard_until: float = 0.0

        self._cursor_history: deque = deque(maxlen=60)
        self._min_approach_displacement: int = 15

    def _get_monitor_config(self, monitor_id: str) -> Dict[str, Any]:
        mid = str(monitor_id)
        if self.monitor_configs and mid in self.monitor_configs:
            return self.monitor_configs[mid]
        if mid == "0":
            edges = {}
            for e in self.active_edges:
                edges[e] = 2
            return {"enabled": True, "edges": edges}
        return {"enabled": True, "edges": {}}

    def refresh_screen_bounds(self) -> None:
        self.monitors = get_monitors()
        self._screen_bounds = get_virtual_desktop_bounds(self.monitors)

    def get_cursor_pos(self, dpy: Any = None, root: Any = None) -> Tuple[int, int]:
        if x11:
            display = dpy
            root_win = root
            close_after = False

            if not display:
                try:
                    display = x11.XOpenDisplay(None)
                    if display:
                        root_win = x11.XDefaultRootWindow(display)
                        close_after = True
                except Exception:
                    display = None

            if display and root_win:
                try:
                    root_return = ctypes.c_ulong()
                    child_return = ctypes.c_ulong()
                    root_x = ctypes.c_int()
                    root_y = ctypes.c_int()
                    win_x = ctypes.c_int()
                    win_y = ctypes.c_int()
                    mask_return = ctypes.c_uint()

                    ret = x11.XQueryPointer(
                        display, root_win,
                        ctypes.byref(root_return), ctypes.byref(child_return),
                        ctypes.byref(root_x), ctypes.byref(root_y),
                        ctypes.byref(win_x), ctypes.byref(win_y),
                        ctypes.byref(mask_return)
                    )
                    if ret:
                        return root_x.value, root_y.value
                except Exception:
                    pass
                finally:
                    if close_after and display:
                        try:
                            x11.XCloseDisplay(display)
                        except Exception:
                            pass

        try:
            res = subprocess.run(["xdotool", "getmouselocation", "--shell"], capture_output=True, text=True, timeout=1)
            if res.returncode == 0:
                x, y = 0, 0
                for line in res.stdout.splitlines():
                    if line.startswith("X="):
                        x = int(line[2:])
                    elif line.startswith("Y="):
                        y = int(line[2:])
                return x, y
        except Exception:
            pass
        return 0, 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.refresh_screen_bounds()
        self._thread = threading.Thread(target=self._loop, name="LinuxEdgeDetectorThread", daemon=True)
        self._thread.start()
        log("EdgeDetector", f"Started monitoring across {len(self.monitors)} monitor(s).")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        log("EdgeDetector", "Stopped.")

    def notify_switched_out(self, edge: str, cursor_x: int, cursor_y: int) -> None:
        self._is_switched_out = True
        self._switched_out_edge = edge
        self._last_known_cursor_pos = (cursor_x, cursor_y)
        self._last_trigger_time = time.time()
        self._return_guard_until = 0.0
        self._last_knock_edge = None
        self._last_knock_time = 0.0
        self._hold_start_time = None
        self._current_edge = None
        self._current_monitor_id = None
        self._cursor_history.clear()
        log("EdgeDetector", f"Switched out via '{edge}'. Return guard armed.")

    def notify_switched_in(self, entry_edge: Optional[str] = None) -> None:
        now = time.time()
        self._is_switched_out = False
        self._last_trigger_time = now
        self._return_guard_until = now + (self.cooldown_ms / 1000.0)
        self._last_knock_edge = None
        self._last_knock_time = 0.0
        self._hold_start_time = None
        self._current_edge = None
        self._current_monitor_id = None
        self._cursor_history.clear()
        log("EdgeDetector", f"Mouse return detected (entry: {entry_edge or 'unknown'}). Return guard: {self.cooldown_ms}ms.")

    def _get_triggered_edge_info(self, x: int, y: int) -> Optional[Tuple[str, float, str, int]]:
        m = get_monitor_for_point(self.monitors, x, y)
        if not m:
            return None

        mid = str(m.id)
        m_cfg = self._get_monitor_config(mid)
        if not m_cfg.get("enabled", True):
            return None

        edges_cfg = m_cfg.get("edges", {})
        tol = 2

        for edge_name, ch in edges_cfg.items():
            if ch is None:
                continue
            edge = edge_name.lower()
            at_border = False
            if edge == "left":
                at_border = (x <= m.left + tol) and (m.top - tol <= y <= m.bottom + tol)
            elif edge == "right":
                at_border = (x >= m.right - tol) and (m.top - tol <= y <= m.bottom + tol)
            elif edge == "top":
                at_border = (y <= m.top + tol) and (m.left - tol <= x <= m.right + tol)
            elif edge == "bottom":
                at_border = (y >= m.bottom - tol) and (m.left - tol <= x <= m.right + tol)

            if at_border:
                if edge in ("left", "right"):
                    h = max(1, m.height)
                    ratio = max(0.0, min(1.0, (y - m.top) / float(h)))
                else:
                    w = max(1, m.width)
                    ratio = max(0.0, min(1.0, (x - m.left) / float(w)))

                if self.active_zone_pct < 100:
                    margin = (1.0 - (self.active_zone_pct / 100.0)) / 2.0
                    if not (margin <= ratio <= (1.0 - margin)):
                        continue

                return (edge, ratio, mid, int(ch))

        return None

    def _is_approaching_edge(self, edge: str, current_x: int, current_y: int, hold_start: Optional[float]) -> bool:
        if not self._cursor_history:
            return True

        target_time = (hold_start or time.time()) - 0.1
        candidates = [pos for (t, pos) in self._cursor_history if t <= target_time]
        if not candidates:
            candidates = [self._cursor_history[0][1]]

        prev_x, prev_y = candidates[0]

        if edge == "right":
            return (current_x - prev_x) >= self._min_approach_displacement
        elif edge == "left":
            return (prev_x - current_x) >= self._min_approach_displacement
        elif edge == "bottom":
            return (current_y - prev_y) >= self._min_approach_displacement
        elif edge == "top":
            return (prev_y - current_y) >= self._min_approach_displacement
        return True

    def _loop(self) -> None:
        local_dpy = None
        local_root = None
        if x11:
            try:
                local_dpy = x11.XOpenDisplay(None)
                if local_dpy:
                    local_root = x11.XDefaultRootWindow(local_dpy)
            except Exception:
                pass

        try:
            while self._running:
                now = time.time()
                x, y = self.get_cursor_pos(local_dpy, local_root)

                if self._is_switched_out:
                    if self._last_known_cursor_pos is not None:
                        lx, ly = self._last_known_cursor_pos
                        dx = x - lx
                        dy = y - ly
                        if (dx * dx + dy * dy) > 225:
                            log("EdgeDetector", f"Physical mouse movement detected on host ({lx}, {ly}) -> ({x}, {y})")
                            self.notify_switched_in(self._switched_out_edge)
                            self._last_known_cursor_pos = (x, y)
                            time.sleep(0.05)
                            continue
                    else:
                        self._last_known_cursor_pos = (x, y)
                    time.sleep(0.05)
                    continue

                self._cursor_history.append((now, (x, y)))

                if (now - self._last_trigger_time) * 1000 < self.cooldown_ms or now < self._return_guard_until:
                    self._hold_start_time = None
                    self._current_edge = None
                    self._current_monitor_id = None
                    time.sleep(0.05)
                    continue

                if self.knock_enabled and self._last_knock_edge:
                    if (now - self._last_knock_time) * 1000 > self.knock_timeout_ms:
                        self._last_knock_edge = None
                        self._last_knock_time = 0.0

                trigger_info = self._get_triggered_edge_info(x, y)

                if trigger_info:
                    edge, ratio, mid, ch = trigger_info
                    key = f"{mid}_{edge}"
                    if self._current_edge != key:
                        self._current_edge = key
                        self._current_monitor_id = mid
                        self._hold_start_time = now
                    else:
                        elapsed_ms = (now - self._hold_start_time) * 1000
                        required_hold = (min(100, self.hold_delay_ms) if self.knock_enabled else self.hold_delay_ms)
                        if elapsed_ms >= required_hold:
                            if self._is_approaching_edge(edge, x, y, self._hold_start_time):
                                if self.knock_enabled:
                                    if self._last_knock_edge == key and ((now - self._last_knock_time) * 1000 <= self.knock_timeout_ms):
                                        log("EdgeDetector", f"Border knock (2/2) on Monitor {mid} '{edge}' -> Switch to Channel {ch}")
                                        self._last_knock_edge = None
                                        self._last_knock_time = 0.0
                                        self._last_trigger_time = now
                                        self._hold_start_time = None
                                        self._current_edge = None
                                        self._current_monitor_id = None
                                        self._cursor_history.clear()
                                        if self.on_trigger_callback:
                                            try:
                                                self.on_trigger_callback(edge, x, y, ratio, mid, ch)
                                            except Exception as cb_err:
                                                log("EdgeDetector", f"Error in trigger callback: {cb_err}")
                                    else:
                                        log("EdgeDetector", f"Border knock (1/2) on Monitor {mid} '{edge}' at ({x}, {y})")
                                        self._last_knock_edge = key
                                        self._last_knock_time = now
                                        self._hold_start_time = None
                                        self._current_edge = None
                                        time.sleep(0.15)
                                else:
                                    log("EdgeDetector", f"Edge '{edge}' on Monitor {mid} triggered -> Channel {ch}")
                                    self._last_trigger_time = now
                                    self._hold_start_time = None
                                    self._current_edge = None
                                    self._current_monitor_id = None
                                    self._cursor_history.clear()
                                    if self.on_trigger_callback:
                                        try:
                                            self.on_trigger_callback(edge, x, y, ratio, mid, ch)
                                        except Exception as cb_err:
                                            log("EdgeDetector", f"Error in trigger callback: {cb_err}")
                            else:
                                self._hold_start_time = now
                else:
                    self._current_edge = None
                    self._current_monitor_id = None
                    self._hold_start_time = None

                time.sleep(0.015)
        finally:
            if local_dpy and x11:
                try:
                    x11.XCloseDisplay(local_dpy)
                except Exception:
                    pass
