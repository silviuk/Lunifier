"""
Configuration management for Lunifier.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Any

from .logger import log, set_log_level

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/lunifier/config.json")
LEGACY_CONFIG_PATH = os.path.expanduser("~/.config/logiflowbt/config.json")
if os.name == "nt":
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    DEFAULT_CONFIG_PATH = os.path.join(appdata, "Lunifier", "config.json")
    LEGACY_CONFIG_PATH = os.path.join(appdata, "LogiFlowBT", "config.json")


@dataclass
class AppConfig:
    host_name: str = "Host"
    my_channel: int = 1         # 1, 2, or 3 (Easy-Switch slot on this PC)
    target_channel: int = 2     # 1, 2, or 3 (Easy-Switch slot on target PC)
    trigger_edge: str = "right" # Legacy single trigger edge: "right", "left", "top", "bottom"
    entry_edge: str = "left"    # edge where mouse enters on switch back
    hold_delay_ms: int = 250    # ms cursor must dwell on border
    cooldown_ms: int = 2500     # ms after switch before new trigger allowed

    # Configurable central active zone on borders (e.g. 50% = middle half [25%..75%])
    border_active_zone_pct: int = 50   # 10 to 100 percent of border length

    # Border knock (double-touch) activation
    knock_enabled: bool = False        # Require two touches within time window to trigger
    knock_timeout_ms: int = 1000       # Time window in ms for the 2nd knock

    # Global / Primary monitor edge routing (for backward compatibility)
    edge_channels: Dict[str, Optional[int]] = field(default_factory=lambda: {
        "left": None,
        "right": 2,
        "top": None,
        "bottom": None
    })

    # Multi-monitor border configuration:
    # Maps monitor ID ("0", "1", ...) to a dict:
    # {
    #     "enabled": true,
    #     "edges": { "left": null, "right": 2, "top": null, "bottom": null }
    # }
    monitor_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    devices: List[str] = field(default_factory=lambda: [
        "MX Keys",
        "Keys",
        "M370",
        "POP",
        "Triathlon",
        "M720",
        "MX Master",
        "MX Anywhere",
        "Mouse"
    ])
    device_feature_indices: Dict[str, int] = field(default_factory=dict)
    use_solaar_on_linux: bool = True

    # Switching backend selection on Linux:
    # "auto": direct /dev/hidraw for Bluetooth with fallback to Solaar; Solaar for receivers
    # "solaar": Solaar CLI prioritized for ALL devices (both Bluetooth and receivers)
    # "direct": direct /dev/hidraw / hidapi kernel writes prioritized for all devices
    switch_backend: str = "auto"
    
    # Connection support filter:
    # "both": Support both Unifying/receivers and Bluetooth connections
    # "unifying": Support Unifying/receivers ONLY
    # "bluetooth": Support Bluetooth connections ONLY
    connection_support: str = "both"
    
    # Bluetooth Inter-Host P2P options
    bt_p2p_enabled: bool = False
    bt_peer_address: str = ""   # e.g. "00:11:22:33:44:55"
    bt_rfcomm_port: int = 4     # RFCOMM channel 1-30
    sync_cursor_position: bool = True
    sync_clipboard: bool = False

    # Configurable logging level: "normal", "debug", or "none"
    log_level: str = "normal"

    # Autostart with system login
    autostart_enabled: bool = False

    # Tray icon double-click action:
    # "open_gui", "switch_1", "switch_2", "switch_3", "mini_window"
    tray_double_click_action: str = "open_gui"

    # Global keyboard shortcuts for channel switching
    hotkeys_enabled: bool = True
    hotkey_ch1: str = "<ctrl>+<alt>+1"
    hotkey_ch2: str = "<ctrl>+<alt>+2"
    hotkey_ch3: str = "<ctrl>+<alt>+3"

    def get_monitor_config(self, monitor_id: str) -> Dict[str, Any]:
        """
        Returns configuration dictionary for the given monitor ID.
        Provides smooth backward compatibility with existing edge_channels.
        """
        mid = str(monitor_id)
        if self.monitor_configs and mid in self.monitor_configs:
            cfg = self.monitor_configs[mid]
            # Ensure proper shape
            edges = cfg.get("edges", {})
            return {
                "enabled": bool(cfg.get("enabled", True)),
                "edges": {
                    "left": edges.get("left"),
                    "right": edges.get("right"),
                    "top": edges.get("top"),
                    "bottom": edges.get("bottom")
                }
            }

        # Fallback for monitor 0 (Primary) to global edge_channels
        if mid == "0":
            return {
                "enabled": True,
                "edges": dict(self.edge_channels or {"left": None, "right": 2, "top": None, "bottom": None})
            }

        # Default for additional monitors
        return {
            "enabled": True,
            "edges": {"left": None, "right": None, "top": None, "bottom": None}
        }

    def set_monitor_config(self, monitor_id: str, enabled: bool, edges: Dict[str, Optional[int]]) -> None:
        """Saves configuration for a specific monitor."""
        mid = str(monitor_id)
        self.monitor_configs[mid] = {
            "enabled": bool(enabled),
            "edges": {
                "left": edges.get("left"),
                "right": edges.get("right"),
                "top": edges.get("top"),
                "bottom": edges.get("bottom")
            }
        }
        # If updating monitor 0, keep legacy edge_channels in sync
        if mid == "0":
            self.edge_channels = dict(self.monitor_configs[mid]["edges"])

    def is_monitor_enabled(self, monitor_id: str) -> bool:
        return self.get_monitor_config(monitor_id).get("enabled", True)

    def get_target_channel_for_monitor_edge(self, monitor_id: str, edge: str) -> Optional[int]:
        """
        Returns the target channel configured for a specific edge on a specific monitor.
        Returns None if monitor is disabled or edge is unconfigured.
        """
        cfg = self.get_monitor_config(monitor_id)
        if not cfg.get("enabled", True):
            return None
        edges = cfg.get("edges", {})
        return edges.get(edge.lower())

    def get_target_channel_for_edge(self, edge: str, monitor_id: str = "0") -> Optional[int]:
        """Legacy helper: checks monitor 0 then fallback."""
        ch = self.get_target_channel_for_monitor_edge(monitor_id, edge)
        if ch is not None:
            return ch
        edge = edge.lower()
        if self.edge_channels and edge in self.edge_channels:
            val = self.edge_channels.get(edge)
            if val is not None:
                return val
        if edge == self.trigger_edge.lower():
            return self.target_channel
        return None

    def get_active_edges(self, monitor_id: str = "0") -> List[str]:
        """Legacy helper: returns active edges for monitor 0."""
        cfg = self.get_monitor_config(monitor_id)
        if not cfg.get("enabled", True):
            return []
        edges: List[str] = []
        for e, ch in cfg.get("edges", {}).items():
            if ch is not None:
                edges.append(e.lower())
        if not edges and monitor_id == "0":
            if self.edge_channels:
                for e, ch in self.edge_channels.items():
                    if ch is not None:
                        edges.append(e.lower())
            if not edges and self.trigger_edge:
                edges.append(self.trigger_edge.lower())
        return edges

    def get_all_active_monitor_borders(self) -> List[Tuple[str, str, int]]:
        """
        Returns a list of (monitor_id, edge, target_channel) for all enabled monitors and active borders.
        """
        active = []
        # If monitor_configs has entries, iterate over them
        mids = list(self.monitor_configs.keys()) if self.monitor_configs else ["0"]
        if "0" not in mids:
            mids.insert(0, "0")

        for mid in mids:
            cfg = self.get_monitor_config(mid)
            if not cfg.get("enabled", True):
                continue
            for edge, ch in cfg.get("edges", {}).items():
                if ch is not None:
                    active.append((mid, edge.lower(), int(ch)))
        return active

    @classmethod
    def load(cls, path: Optional[str] = None) -> "AppConfig":
        cfg_path = path or DEFAULT_CONFIG_PATH
        config_obj = None
        # Try primary config path
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    config_obj = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception as e:
                log("Config", f"Error loading {cfg_path}: {e}, using defaults.")
        # Fallback to legacy LogiFlowBT config if available
        elif not path and os.path.isfile(LEGACY_CONFIG_PATH):
            try:
                with open(LEGACY_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
                    log("Config", f"Migrated configuration from {LEGACY_CONFIG_PATH} to {DEFAULT_CONFIG_PATH}")
                    cfg.save(DEFAULT_CONFIG_PATH)
                    config_obj = cfg
            except Exception as e:
                log("Config", f"Error migrating legacy config: {e}")

        if config_obj is None:
            config_obj = cls()

        # Apply configured log level immediately
        set_log_level(config_obj.log_level)
        return config_obj

    def save(self, path: Optional[str] = None) -> None:
        cfg_path = path or DEFAULT_CONFIG_PATH
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=4)
        log("Config", f"Configuration saved to {cfg_path}")
        set_log_level(self.log_level)
