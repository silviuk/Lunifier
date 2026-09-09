"""
Configuration management for Lunifier.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional

from .logger import log

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

    # Multi-edge channel routing: maps each screen edge to a target channel (1, 2, 3, or None)
    edge_channels: Dict[str, Optional[int]] = field(default_factory=lambda: {
        "left": None,
        "right": 2,
        "top": None,
        "bottom": None
    })

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

    log_level: str = "INFO"

    def get_target_channel_for_edge(self, edge: str) -> Optional[int]:
        edge = edge.lower()
        if self.edge_channels and edge in self.edge_channels:
            val = self.edge_channels.get(edge)
            if val is not None:
                return val
        if edge == self.trigger_edge.lower():
            return self.target_channel
        return None

    def get_active_edges(self) -> List[str]:
        edges: List[str] = []
        if self.edge_channels:
            for e, ch in self.edge_channels.items():
                if ch is not None:
                    edges.append(e.lower())
        if not edges and self.trigger_edge:
            edges.append(self.trigger_edge.lower())
        return edges

    @classmethod
    def load(cls, path: Optional[str] = None) -> "AppConfig":
        cfg_path = path or DEFAULT_CONFIG_PATH
        # Try primary config path
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
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
                    return cfg
            except Exception as e:
                log("Config", f"Error migrating legacy config: {e}")
        return cls()

    def save(self, path: Optional[str] = None) -> None:
        cfg_path = path or DEFAULT_CONFIG_PATH
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=4)
        log("Config", f"Configuration saved to {cfg_path}")
