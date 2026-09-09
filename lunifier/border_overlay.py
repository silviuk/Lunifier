"""
Visual Screen Border Overlay for Lunifier.
Draws 4-6px vibrant orange lines along screen edges to highlight the active switch zones
when adjusting the active border percentage slider or scrolling.
Automatically dismisses 1 second after user interaction.
"""

import sys
import tkinter as tk
from typing import Dict, List, Optional

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32


class BorderOverlayManager:
    """
    Manages non-intrusive, topmost, click-through overlay windows that visually highlight
    the active border switching areas along physical screen edges.
    """
    LINE_THICKNESS: int = 5       # 4-6px thickness
    LINE_COLOR: str = "#FF5722"    # Vibrant, high-visibility orange

    def __init__(self, parent: tk.Misc):
        self.parent = parent
        self._windows: Dict[str, tk.Toplevel] = {}
        self._hide_timer_id: Optional[str] = None
        self._is_visible: bool = False

    def _get_screen_bounds(self) -> Dict[str, int]:
        bounds = {"left": 0, "top": 0, "right": 1920, "bottom": 1080}
        if sys.platform == "win32":
            try:
                SM_XVIRTUALSCREEN = 76
                SM_YVIRTUALSCREEN = 77
                SM_CXVIRTUALSCREEN = 78
                SM_CYVIRTUALSCREEN = 79

                vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
                vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
                vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
                vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

                if vw > 0 and vh > 0:
                    return {
                        "left": vx,
                        "top": vy,
                        "right": vx + vw,
                        "bottom": vy + vh
                    }
            except Exception:
                pass

        try:
            return {
                "left": 0,
                "top": 0,
                "right": self.parent.winfo_screenwidth(),
                "bottom": self.parent.winfo_screenheight()
            }
        except Exception:
            return bounds

    def _create_overlay_window(self, edge: str) -> tk.Toplevel:
        win = tk.Toplevel(self.parent)
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass

        # Fill with vibrant orange color
        win.configure(bg=self.LINE_COLOR)

        # Internal frame ensuring client area is solidly filled
        frame = tk.Frame(win, bg=self.LINE_COLOR)
        frame.pack(fill="both", expand=True)

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

    def show(self, active_zone_pct: int, edges: Optional[List[str]] = None) -> None:
        """
        Displays 5px orange lines along the active border zones for the specified percentage.
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
        target_edges = [e.lower() for e in edges] if edges else ["left", "right", "top", "bottom"]
        if not target_edges:
            target_edges = ["left", "right", "top", "bottom"]

        bounds = self._get_screen_bounds()
        w = max(1, bounds["right"] - bounds["left"])
        h = max(1, bounds["bottom"] - bounds["top"])
        margin = (1.0 - (pct / 100.0)) / 2.0
        thick = self.LINE_THICKNESS

        # Hide any windows for edges not in target_edges
        for e, win in list(self._windows.items()):
            if e not in target_edges:
                try:
                    win.withdraw()
                except Exception:
                    pass

        # Position and show overlays for each target edge
        for edge in target_edges:
            if edge not in self._windows or not self._windows[edge].winfo_exists():
                self._windows[edge] = self._create_overlay_window(edge)
            win = self._windows[edge]

            if edge in ("left", "right"):
                seg_h = max(1, int((1.0 - 2.0 * margin) * h))
                y_pos = int(bounds["top"] + margin * h)
                x_pos = bounds["left"] if edge == "left" else (bounds["right"] - thick)
                geom = f"{thick}x{seg_h}+{x_pos}+{y_pos}"
            else:  # "top" or "bottom"
                seg_w = max(1, int((1.0 - 2.0 * margin) * w))
                x_pos = int(bounds["left"] + margin * w)
                y_pos = bounds["top"] if edge == "top" else (bounds["bottom"] - thick)
                geom = f"{seg_w}x{thick}+{x_pos}+{y_pos}"

            try:
                win.geometry(geom)
                win.deiconify()
                win.lift()
                try:
                    win.attributes("-topmost", True)
                except Exception:
                    pass
            except Exception:
                pass

        self._is_visible = True
        # Schedule automatic hide after 1.0 second of inactivity
        self._hide_timer_id = self.parent.after(1000, self.hide)

    def hide(self) -> None:
        """
        Hides all active border overlay windows.
        """
        self._hide_timer_id = None
        self._is_visible = False
        for win in self._windows.values():
            try:
                win.withdraw()
            except Exception:
                pass

    def destroy(self) -> None:
        """
        Destroys all overlay windows.
        """
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
