"""
Visual Screen Border Overlay for Linux with Multi-Monitor Support.
Highlights active border zones along screen edges when adjusting settings.
"""

from typing import Dict, List, Optional
from .monitors import MonitorInfo, get_monitors

class BorderOverlayManager:
    def __init__(self, parent=None):
        self.parent = parent
        self._windows = {}
        self._hide_timer_id = None

    def show(self, active_zone_pct: int, edges: Optional[Dict[str, List[str]]] = None, monitor_id: Optional[str] = None):
        # In GTK4 / headless / Wayland environments, overlay is optional and non-blocking
        pass

    def hide(self):
        pass
