"""
Precision Screen Edge Detector for Windows and Linux.
Monitors cursor position and triggers a switch event when the cursor dwells at the configured screen edge.
"""

import sys
import time
import threading
from collections import deque
from typing import Callable, Optional, Tuple, List, Dict

from lunifier.logger import log

# Win32 ctypes definitions
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
                 on_trigger_callback: Optional[Callable[[str, int, int, float], None]] = None):
        """
        :param trigger_edge: 'right', 'left', 'top', or 'bottom'
        :param active_edges: List of edges to monitor, e.g. ['left', 'right']
        :param hold_delay_ms: ms cursor must dwell on border before triggering
        :param cooldown_ms: ms after trigger before next detection is accepted
        :param active_zone_pct: Central percentage of edge active (e.g. 50 = middle 50% [0.25..0.75])
        :param knock_enabled: If True, requires two hits to the border within knock_timeout_ms
        :param knock_timeout_ms: Max time window (ms) between first touch and second touch to switch
        :param on_trigger_callback: func(edge, x, y, ratio) called when triggered
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
        self.on_trigger_callback = on_trigger_callback

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_edge: Optional[str] = None
        self._hold_start_time: Optional[float] = None
        self._last_trigger_time: float = 0.0
        self._screen_bounds = self._get_screen_bounds()

        # Knock state tracking: (edge, timestamp of 1st knock)
        self._last_knock_edge: Optional[str] = None
        self._last_knock_time: float = 0.0

        # Motion tracking: stores recent (timestamp, x, y) tuples to verify cursor approached the edge
        self._cursor_history: deque = deque(maxlen=60)  # ~1 second of samples at ~65Hz
        self._min_approach_displacement: int = 15       # Minimum pixels cursor must have moved toward edge

        # Linux X11 display caching for ultra-low latency & zero subprocess CPU overhead
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

    def _get_screen_bounds(self) -> Dict[str, int]:
        """
        Calculates the bounding rectangle across all displays.
        """
        bounds = {"left": 0, "top": 0, "right": 1920, "bottom": 1080}
        if sys.platform == "win32":
            try:
                # Use virtual screen metrics which cover multi-monitors
                SM_XVIRTUALSCREEN = 76
                SM_YVIRTUALSCREEN = 77
                SM_CXVIRTUALSCREEN = 78
                SM_CYVIRTUALSCREEN = 79

                vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
                vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
                vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
                vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

                if vw > 0 and vh > 0:
                    bounds = {
                        "left": vx,
                        "top": vy,
                        "right": vx + vw,
                        "bottom": vy + vh
                    }
            except Exception as e:
                log("EdgeDetector", f"Error fetching Windows screen metrics: {e}")
        else:
            # Linux: try X11 direct display width/height first
            if getattr(self, "_x11_display", None) and x11:
                try:
                    screen = x11.XDefaultScreen(self._x11_display)
                    w = x11.XDisplayWidth(self._x11_display, screen)
                    h = x11.XDisplayHeight(self._x11_display, screen)
                    if w > 0 and h > 0:
                        return {"left": 0, "top": 0, "right": w, "bottom": h}
                except Exception:
                    pass

            # Fallback 1: xdotool
            try:
                import subprocess
                res = subprocess.run(["xdotool", "getdisplaygeometry"], capture_output=True, text=True, timeout=1)
                if res.returncode == 0:
                    parts = res.stdout.strip().split()
                    bounds = {
                        "left": 0,
                        "top": 0,
                        "right": int(parts[0]),
                        "bottom": int(parts[1])
                    }
            except Exception:
                # Fallback 2: tkinter
                try:
                    import tkinter
                    root = tkinter.Tk()
                    root.withdraw()
                    bounds = {
                        "left": 0,
                        "top": 0,
                        "right": root.winfo_screenwidth(),
                        "bottom": root.winfo_screenheight()
                    }
                    root.destroy()
                except Exception:
                    pass

        return bounds

    def get_cursor_pos(self) -> Tuple[int, int]:
        """
        Returns (x, y) cursor coordinate using zero-copy OS APIs (<0.01ms latency, 0% CPU).
        """
        if sys.platform == "win32":
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            return pt.x, pt.y
        else:
            # Linux: direct X11 XQueryPointer (zero subprocess spawn)
            if self._x11_display and self._x11_root and x11:
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

    def refresh_screen_bounds(self) -> None:
        self._screen_bounds = self._get_screen_bounds()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.refresh_screen_bounds()
        self._thread = threading.Thread(target=self._loop, name="EdgeDetectorThread", daemon=True)
        self._thread.start()
        edges_str = ", ".join(self.active_edges)
        log("EdgeDetector", f"Started monitoring edges [{edges_str}] on bounds {self._screen_bounds}")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        log("EdgeDetector", "Stopped.")

    def _is_at_edge(self, x: int, y: int, edge: Optional[str] = None) -> bool:
        target = edge.lower() if edge else self.trigger_edge
        b = self._screen_bounds
        tol = 2  # pixel tolerance margin
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
        """
        Checks if the cursor position along the border falls within the central active zone.
        e.g. For active_zone_pct = 50%, ratio must be between 0.25 and 0.75.
        """
        if self.active_zone_pct >= 100:
            return True
        ratio = self._calculate_ratio(x, y, edge)
        margin = (1.0 - (self.active_zone_pct / 100.0)) / 2.0
        return margin <= ratio <= (1.0 - margin)

    def _get_triggered_edge(self, x: int, y: int) -> Optional[str]:
        for edge in self.active_edges:
            if self._is_at_edge(x, y, edge):
                if self._is_in_active_zone(x, y, edge):
                    return edge
        return None

    def _calculate_ratio(self, x: int, y: int, edge: Optional[str] = None) -> float:
        target = edge.lower() if edge else self.trigger_edge
        b = self._screen_bounds
        if target in ("left", "right"):
            h = max(1, b["bottom"] - b["top"])
            return max(0.0, min(1.0, (y - b["top"]) / h))
        else:
            w = max(1, b["right"] - b["left"])
            return max(0.0, min(1.0, (x - b["left"]) / w))

    def _is_approaching_edge(self, edge: str, current_x: int, current_y: int, hold_start: Optional[float]) -> bool:
        """
        Validates that the cursor was actually moved toward the border from the interior,
        rather than already resting or appearing on the border upon switching.
        """
        if not self._cursor_history:
            return True

        # Check movement history over the last 0.1s to 1.0s before dwell completed
        target_time = (hold_start or time.time()) - 0.1
        candidates = [pos for (t, pos) in self._cursor_history if t <= target_time]
        if not candidates:
            # If dwell just started, check the oldest available sample in history
            candidates = [self._cursor_history[0][1]]

        prev_x, prev_y = candidates[0]

        # Calculate movement vector towards the target edge
        if edge == "right":
            # Must have moved rightwards from the left/interior (current_x > prev_x)
            return (current_x - prev_x) >= self._min_approach_displacement
        elif edge == "left":
            # Must have moved leftwards from the right/interior (current_x < prev_x)
            return (prev_x - current_x) >= self._min_approach_displacement
        elif edge == "bottom":
            # Must have moved downwards from the top/interior (current_y > prev_y)
            return (current_y - prev_y) >= self._min_approach_displacement
        elif edge == "top":
            # Must have moved upwards from the bottom/interior (current_y < prev_y)
            return (prev_y - current_y) >= self._min_approach_displacement
        return True

    def _loop(self) -> None:
        while self._running:
            now = time.time()
            x, y = self.get_cursor_pos()
            self._cursor_history.append((now, (x, y)))

            # If in cooldown after a recent switch, wait
            if (now - self._last_trigger_time) * 1000 < self.cooldown_ms:
                self._hold_start_time = None
                self._current_edge = None
                time.sleep(0.05)
                continue

            # Expire stale 1st knock if outside time window
            if self.knock_enabled and self._last_knock_edge:
                if (now - self._last_knock_time) * 1000 > self.knock_timeout_ms:
                    self._last_knock_edge = None
                    self._last_knock_time = 0.0

            edge = self._get_triggered_edge(x, y)

            if edge:
                if self._current_edge != edge:
                    self._current_edge = edge
                    self._hold_start_time = now
                else:
                    elapsed_ms = (now - self._hold_start_time) * 1000
                    # If knock is enabled, the knock dwell can be quick (e.g. 50ms or hold_delay_ms/2)
                    required_hold = (min(100, self.hold_delay_ms) if self.knock_enabled else self.hold_delay_ms)
                    if elapsed_ms >= required_hold:
                        # Verify that the cursor genuinely moved toward this border
                        if self._is_approaching_edge(edge, x, y, self._hold_start_time):
                            ratio = self._calculate_ratio(x, y, edge)

                            if self.knock_enabled:
                                if self._last_knock_edge == edge and ((now - self._last_knock_time) * 1000 <= self.knock_timeout_ms):
                                    # 2nd knock received within window! Trigger switch!
                                    log("EdgeDetector", f"Border knock (2/2) confirmed on '{edge}' at ({x}, {y}) ratio={ratio:.2f} -> SWITCHING")
                                    self._last_knock_edge = None
                                    self._last_knock_time = 0.0
                                    self._last_trigger_time = now
                                    self._hold_start_time = None
                                    self._current_edge = None
                                    self._cursor_history.clear()

                                    if self.on_trigger_callback:
                                        try:
                                            self.on_trigger_callback(edge, x, y, ratio)
                                        except Exception as e:
                                            log("EdgeDetector", f"Callback error: {e}")
                                else:
                                    # 1st knock registered! Activate time window.
                                    log("EdgeDetector", f"Border knock (1/2) registered on '{edge}' at ({x}, {y}) - waiting for 2nd knock within {self.knock_timeout_ms}ms...")
                                    self._last_knock_edge = edge
                                    self._last_knock_time = now
                                    # Reset hold so 2nd knock requires cursor to leave/re-enter or re-approach
                                    self._hold_start_time = None
                                    self._current_edge = None
                                    # Sleep briefly so current touch doesn't immediately count as 2nd knock
                                    time.sleep(0.15)
                            else:
                                # Normal continuous hold dwell switch
                                log("EdgeDetector", f"Edge '{edge}' triggered with approach at ({x}, {y}) ratio={ratio:.2f}")
                                self._last_trigger_time = now
                                self._hold_start_time = None
                                self._current_edge = None
                                self._cursor_history.clear()

                                if self.on_trigger_callback:
                                    try:
                                        self.on_trigger_callback(edge, x, y, ratio)
                                    except Exception as e:
                                        log("EdgeDetector", f"Callback error: {e}")
                        else:
                            # Resting on border without directional approach movement (e.g. initial placement on border)
                            self._hold_start_time = now
            else:
                self._current_edge = None
                self._hold_start_time = None

            time.sleep(0.015)  # ~65 Hz polling
