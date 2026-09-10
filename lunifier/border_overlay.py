"""
Visual Screen Border Overlay for Lunifier with Multi-Monitor Support.
Draws 4-6px vibrant orange lines along screen edges to highlight active switch zones
on designated monitors when adjusting the active border percentage slider or scrolling.
Automatically dismisses 1 second after user interaction.
"""

import sys
import tkinter as tk
from typing import Dict, List, Optional, Union, Tuple

from .monitors import MonitorInfo, get_monitors

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32


class BorderOverlayManager:
    """
    Manages non-intrusive, topmost, click-through overlay windows that visually highlight
    the active border switching areas along physical monitor edges.
    """
    LINE_THICKNESS: int = 12      # Modern 12px thickness (10-15px)
    LINE_COLOR: str = "#FF5722"    # Vibrant, high-visibility orange
    BORDER_COLOR: str = "#D84315"  # Deep contrast accent border
    GLOW_COLOR: str = "#FFE082"    # Luminous inner neon core

    def __init__(self, parent: tk.Misc):
        self.parent = parent
        self._windows: Dict[str, tk.Toplevel] = {}
        self._hide_timer_id: Optional[str] = None
        self._is_visible: bool = False

    def _create_overlay_window(self, win_key: str) -> tk.Toplevel:
        win = tk.Toplevel(self.parent)
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass

        win.configure(bg=self.BORDER_COLOR)

        canvas = tk.Canvas(win, bg=self.BORDER_COLOR, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        win._canvas = canvas

        # Make window non-activating and click-through on Windows
        if sys.platform == "win32":
            try:
                win.update_idletasks()
                frame_hwnd = int(win.wm_frame(), 16)
                GWL_EXSTYLE = -20
                WS_EX_LAYERED = 0x00080000
                WS_EX_TRANSPARENT = 0x00000020
                WS_EX_TOOLWINDOW = 0x00000080
                WS_EX_NOACTIVATE = 0x08000000
                old_style = user32.GetWindowLongW(frame_hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(
                    frame_hwnd,
                    GWL_EXSTYLE,
                    old_style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT | WS_EX_LAYERED
                )
                # Ensure full opacity (alpha=255) so the vibrant orange color is cleanly displayed
                user32.SetLayeredWindowAttributes(frame_hwnd, 0, 255, 2)  # LWA_ALPHA = 2
            except Exception:
                pass

        return win

    def show(self,
             active_zone_pct: int,
             edges: Optional[Union[List[str], Dict[str, List[str]]]] = None,
             monitor_id: Optional[str] = None) -> None:
        """
        Displays 5px orange lines along the active border zones for the specified percentage.
        Supports:
          - Dict of {monitor_id: [edges]}: displays borders on respective monitors.
          - List of edges + optional monitor_id: displays on specified or primary monitor.
          - Defaults to all 4 borders across monitors if not specified.
        Resets the 1.0 second auto-dismiss timer.
        """
        # Cancel any pending hide
        if self._hide_timer_id is not None:
            try:
                self.parent.after_cancel(self._hide_timer_id)
            except Exception:
                pass
            self._hide_timer_id = None

        pct = max(10, min(100, int(active_zone_pct)))
        monitors = get_monitors()
        mon_map: Dict[str, MonitorInfo] = {str(m.id): m for m in monitors}

        # Normalize target borders into list of (monitor_id, edge) tuples
        target_items: List[Tuple[str, str]] = []

        if isinstance(edges, dict):
            for mid, m_edges in edges.items():
                if str(mid) in mon_map:
                    for e in m_edges:
                        target_items.append((str(mid), e.lower()))
        elif isinstance(edges, (list, tuple)):
            target_mid = str(monitor_id) if monitor_id is not None and str(monitor_id) in mon_map else "0"
            for e in edges:
                target_items.append((target_mid, e.lower()))
        else:
            # None provided -> default to all 4 borders on specified or primary monitor
            target_mid = str(monitor_id) if monitor_id is not None and str(monitor_id) in mon_map else "0"
            for e in ["left", "right", "top", "bottom"]:
                target_items.append((target_mid, e))

        if not target_items:
            for e in ["left", "right", "top", "bottom"]:
                target_items.append(("0", e))

        margin = (1.0 - (pct / 100.0)) / 2.0
        thick = self.LINE_THICKNESS
        active_keys = set()

        # Position and display each overlay window
        for mid, edge in target_items:
            m = mon_map.get(mid)
            if not m:
                continue

            win_key = f"{mid}_{edge}"
            active_keys.add(win_key)

            if win_key not in self._windows or not self._windows[win_key].winfo_exists():
                self._windows[win_key] = self._create_overlay_window(win_key)
            win = self._windows[win_key]

            # Geometry relative to specific monitor bounds
            if edge in ("left", "right"):
                seg_w = thick
                seg_h = max(1, int((1.0 - 2.0 * margin) * m.height))
                y_pos = int(m.top + margin * m.height)
                x_pos = m.left if edge == "left" else (m.right - thick)
                geom = f"{thick}x{seg_h}+{x_pos}+{y_pos}"
            else:  # "top" or "bottom"
                seg_w = max(1, int((1.0 - 2.0 * margin) * m.width))
                seg_h = thick
                x_pos = int(m.left + margin * m.width)
                y_pos = m.top if edge == "top" else (m.bottom - thick)
                geom = f"{seg_w}x{thick}+{x_pos}+{y_pos}"

            try:
                win.geometry(geom)
                self._draw_overlay_graphics(win, seg_w, seg_h, is_vertical=(edge in ("left", "right")))
                win.deiconify()
                win.lift()
                try:
                    win.attributes("-topmost", True)
                except Exception:
                    pass
            except Exception:
                pass

        # Hide any inactive cached overlay windows
        for key, win in list(self._windows.items()):
            if key not in active_keys:
                try:
                    win.withdraw()
                except Exception:
                    pass

        self._is_visible = True
        # Schedule automatic hide after 1.0 second of inactivity
        self._hide_timer_id = self.parent.after(1000, self.hide)

    def _draw_overlay_graphics(self, win: tk.Toplevel, w: int, h: int, is_vertical: bool) -> None:
        """Draws a modern glowing neon guideline with high-contrast accent core."""
        canvas: Optional[tk.Canvas] = getattr(win, "_canvas", None)
        if not canvas:
            return
        canvas.delete("all")
        # Outer dark accent boundary
        canvas.create_rectangle(0, 0, w, h, fill=self.BORDER_COLOR, outline="")
        # Vibrant neon orange core
        if is_vertical:
            canvas.create_rectangle(1, 0, max(1, w - 1), h, fill=self.LINE_COLOR, outline="")
            # Center bright glowing highlight
            cx = w // 2
            canvas.create_line(cx, 4, cx, max(4, h - 4), fill=self.GLOW_COLOR, width=2)
        else:
            canvas.create_rectangle(0, 1, w, max(1, h - 1), fill=self.LINE_COLOR, outline="")
            # Center bright glowing highlight
            cy = h // 2
            canvas.create_line(4, cy, max(4, w - 4), cy, fill=self.GLOW_COLOR, width=2)

    def hide(self) -> None:
        """Hides all active border overlay windows."""
        self._hide_timer_id = None
        self._is_visible = False
        for win in self._windows.values():
            try:
                win.withdraw()
            except Exception:
                pass

    def destroy(self) -> None:
        """Destroys all overlay windows."""
        if self._hide_timer_id is not None:
            try:
                self.parent.after_cancel(self._hide_timer_id)
            except Exception:
                pass
            self._hide_timer_id = None

        for win in self._windows.values():
            try:
                win.destroy()
            except Exception:
                pass
        self._windows.clear()
        self._is_visible = False
