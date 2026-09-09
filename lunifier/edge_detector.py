"""
Precision Screen Edge Detector for Windows and Linux with Multi-Monitor Support.
Monitors cursor position and triggers a switch event when the cursor dwells at configured
screen edges on designated monitors, correctly handling different resolutions and side-by-side/stacked layouts.
"""

from collections import deque
import sys
import time
import threading
from typing import Callable, Optional, Tuple, List, Dict, Any

from .logger import log, log_debug
from .monitors import MonitorInfo, get_monitors, get_monitor_for_point, get_virtual_desktop_bounds

# Win32 ctypes definitions
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
else:
    import ctypes
    try:
        x11 = ctypes.cdll.LoadLibrary("libX11.so.6")
    except Exception:
        try:
            x11 = ctypes.cdll.LoadLibrary("libX11.so")
        except Exception:
            x11 = None


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
        """
        :param trigger_edge: Legacy 'right', 'left', 'top', or 'bottom'
        :param active_edges: Legacy list of edges to monitor, e.g. ['left', 'right']
        :param hold_delay_ms: ms cursor must dwell on border before triggering
        :param cooldown_ms: ms after trigger before next detection is accepted
        :param active_zone_pct: Central percentage of edge active (e.g. 50 = middle 50% [0.25..0.75])
        :param knock_enabled: If True, requires two hits to the border within knock_timeout_ms
        :param knock_timeout_ms: Max time window (ms) between first touch and second touch to switch
        :param monitor_configs: Per-monitor configurations: {mid: {"enabled": bool, "edges": {...}}}
        :param on_trigger_callback: func(edge, x, y, ratio, [monitor_id, target_ch]) called when triggered
        """
        self.trigger_edge = trigger_edge.lower() if trigger_edge else "right"
        if active_edges:
            self.active_edges = [e.lower() for e in active_edges]
        else:
            self.active_edges = [self.trigger_edge]

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

        # Multi-monitor bounds and geometry
        self.monitors: List[MonitorInfo] = []
        self._screen_bounds: Dict[str, int] = {}
        self.refresh_screen_bounds()

        # Knock state tracking: (edge, timestamp of 1st knock)
        self._last_knock_edge: Optional[str] = None
        self._last_knock_time: float = 0.0

        # Motion tracking: stores recent (timestamp, x, y) tuples to verify cursor approached the edge
        self._cursor_history: deque = deque(maxlen=60)  # ~1 second of samples at ~65Hz
        self._min_approach_displacement: int = 15       # Minimum pixels cursor must have moved toward edge

        # Linux X11 display caching
        self._x11_display = None
        self._x11_root = None
        if sys.platform.startswith("linux") and x11:
            try:
                self._x11_display = x11.XOpenDisplay(None)
                if self._x11_display:
                    self._x11_root = x11.XDefaultRootWindow(self._x11_display)
            except Exception:
                pass

    def __del__(self):
        if hasattr(self, "_x11_display") and self._x11_display and x11:
            try:
                x11.XCloseDisplay(self._x11_display)
            except Exception:
                pass

    def _get_monitor_config(self, monitor_id: str) -> Dict[str, Any]:
        mid = str(monitor_id)
        if self.monitor_configs and mid in self.monitor_configs:
            return self.monitor_configs[mid]
        # Legacy fallback for monitor 0
        if mid == "0":
            edges = {}
            for e in self.active_edges:
                edges[e] = 2
            return {"enabled": True, "edges": edges}
        return {"enabled": True, "edges": {}}

    def refresh_screen_bounds(self) -> None:
        self.monitors = get_monitors()
        self._screen_bounds = get_virtual_desktop_bounds(self.monitors)

    def _get_screen_bounds(self) -> Dict[str, int]:
        return get_virtual_desktop_bounds(get_monitors())

    def get_cursor_pos(self) -> Tuple[int, int]:
        if sys.platform == "win32":
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            return pt.x, pt.y
        else:
            if getattr(self, "_x11_display", None) and getattr(self, "_x11_root", None) and x11:
                try:
                    root_return = ctypes.c_ulong()
                    child_return = ctypes.c_ulong()
                    root_x = ctypes.c_int()
                    root_y = ctypes.c_int()
                    win_x = ctypes.c_int()
                    win_y = ctypes.c_int()
                    mask_return = ctypes.c_uint()

                    ret = x11.XQueryPointer(
                        self._x11_display,
                        self._x11_root,
                        ctypes.byref(root_return),
                        ctypes.byref(child_return),
                        ctypes.byref(root_x),
                        ctypes.byref(root_y),
                        ctypes.byref(win_x),
                        ctypes.byref(win_y),
                        ctypes.byref(mask_return)
                    )
                    if ret:
                        return root_x.value, root_y.value
                except Exception:
                    pass

            # Fallback for Wayland or non-X11: xdotool
            try:
                import subprocess
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
        self._thread = threading.Thread(target=self._loop, name="EdgeDetectorThread", daemon=True)
        self._thread.start()
        log("EdgeDetector", f"Started monitoring across {len(self.monitors)} monitor(s) on bounds {self._screen_bounds}")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        log("EdgeDetector", "Stopped.")

    def _is_at_edge(self, x: int, y: int, edge: Optional[str] = None) -> bool:
        """Legacy helper matching single-screen bounds."""
        target = edge.lower() if edge else self.trigger_edge
        b = self._screen_bounds
        tol = 2
        if target == "right":
            return x >= (b["right"] - tol)
        elif target == "left":
            return x <= (b["left"] + tol)
        elif target == "bottom":
            return y >= (b["bottom"] - tol)
        elif target == "top":
            return y <= (b["top"] + tol)
        return False

    def _is_in_active_zone(self, x: int, y: int, edge: str) -> bool:
        """Legacy helper matching single-screen bounds."""
        if self.active_zone_pct >= 100:
            return True
        ratio = self._calculate_ratio(x, y, edge)
        margin = (1.0 - (self.active_zone_pct / 100.0)) / 2.0
        return margin <= ratio <= (1.0 - margin)

    def _calculate_ratio(self, x: int, y: int, edge: Optional[str] = None) -> float:
        """Legacy helper matching single-screen bounds."""
        target = edge.lower() if edge else self.trigger_edge
        b = self._screen_bounds
        if target in ("left", "right"):
            h = max(1, b["bottom"] - b["top"])
            return max(0.0, min(1.0, (y - b["top"]) / h))
        else:
            w = max(1, b["right"] - b["left"])
            return max(0.0, min(1.0, (x - b["left"]) / w))

    def _get_triggered_edge_info(self, x: int, y: int) -> Optional[Tuple[str, float, str, int]]:
        """
        Evaluates cursor (x, y) against each monitor's configured borders.
        Correctly handles multi-monitor layouts with different resolutions and offsets.
        Returns: (edge, ratio, monitor_id, target_channel) or None.
        """
        m = get_monitor_for_point(self.monitors, x, y)
        if not m:
            return None

        mid = str(m.id)
        m_cfg = self._get_monitor_config(mid)
        if not m_cfg.get("enabled", True):
            return None

        edges_cfg = m_cfg.get("edges", {})
        tol = 2

        # Check configured edges on this monitor
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
                # Calculate active zone ratio along this specific monitor border
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

        # Legacy fallback if no monitor_configs provided
        if not self.monitor_configs and self.active_edges:
            for edge in self.active_edges:
                if self._is_at_edge(x, y, edge):
                    if self._is_in_active_zone(x, y, edge):
                        return (edge, self._calculate_ratio(x, y, edge), "0", 2)

        return None

    def _get_triggered_edge(self, x: int, y: int) -> Optional[str]:
        """Legacy helper returning just the edge name."""
        info = self._get_triggered_edge_info(x, y)
        return info[0] if info else None

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

    def _invoke_callback(self, edge: str, x: int, y: int, ratio: float, monitor_id: str, target_channel: int) -> None:
        if not self.on_trigger_callback:
            return
        try:
            # Full 6-argument call
            self.on_trigger_callback(edge, x, y, ratio, monitor_id, target_channel)
        except TypeError:
            try:
                # 4-argument call (edge, x, y, ratio)
                self.on_trigger_callback(edge, x, y, ratio)
            except Exception as e:
                log("EdgeDetector", f"Callback error: {e}")
        except Exception as e:
            log("EdgeDetector", f"Callback error: {e}")

    def _loop(self) -> None:
        while self._running:
            now = time.time()
            x, y = self.get_cursor_pos()
            self._cursor_history.append((now, (x, y)))

            # If in cooldown after a recent switch, wait
            if (now - self._last_trigger_time) * 1000 < self.cooldown_ms:
                self._hold_start_time = None
                self._current_edge = None
                self._current_monitor_id = None
                time.sleep(0.05)
                continue

            # Expire stale 1st knock if outside time window
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
                                    self._invoke_callback(edge, x, y, ratio, mid, ch)
                                else:
                                    log("EdgeDetector", f"Border knock (1/2) on Monitor {mid} '{edge}' at ({x}, {y})")
                                    self._last_knock_edge = key
                                    self._last_knock_time = now
                                    self._hold_start_time = None
                                    self._current_edge = None
                                    time.sleep(0.15)
                            else:
                                log("EdgeDetector", f"Edge '{edge}' on Monitor {mid} triggered at ({x}, {y}) ratio={ratio:.2f} -> Switch to Channel {ch}")
                                self._last_trigger_time = now
                                self._hold_start_time = None
                                self._current_edge = None
                                self._current_monitor_id = None
                                self._cursor_history.clear()
                                self._invoke_callback(edge, x, y, ratio, mid, ch)
                        else:
                            self._hold_start_time = now
            else:
                self._current_edge = None
                self._current_monitor_id = None
                self._hold_start_time = None

            time.sleep(0.015)
