"""
Modern Graphical User Interface for LogiFlowBT built with CustomTkinter.
Provides a sleek, modern dark/light desktop experience on Windows and Linux.
Optimized for Linux X11/Wayland with pixel-perfect font and geometry rendering.
"""

import sys
import threading
from typing import Optional, List

try:
    import customtkinter as ctk
    from tkinter import messagebox
except ImportError as err:
    raise ImportError(
        "CustomTkinter is required for the Lunifier GUI. "
        "Install it via: pip install customtkinter (or pip3 install --break-system-packages customtkinter)"
    ) from err

from .config import AppConfig
from .hidpp import HIDPPMaster, LogitechDevice
from .logger import (
    log, add_log_listener, remove_log_listener, set_log_level, get_log_level,
    LOG_LEVEL_NONE, LOG_LEVEL_NORMAL, LOG_LEVEL_DEBUG
)
from .border_overlay import BorderOverlayManager
from .monitors import get_monitors, MonitorInfo

IS_LINUX = sys.platform.startswith("linux")
# On Linux X11, canvas corner masks can cause jagged notch artifacts; use crisp flat geometry
BTN_RADIUS = 0 if IS_LINUX else 6
CARD_RADIUS = 0 if IS_LINUX else 8


def get_ui_font(size: int, weight: str = "normal") -> ctk.CTkFont:
    """
    Returns high-quality anti-aliased font suitable for current OS.
    Avoids hardcoding 'Segoe UI' on Linux which causes fallback to pixelated bitmap fonts.
    """
    if IS_LINUX:
        return ctk.CTkFont(size=size, weight=weight)
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


class LunifierGUI:
    def __init__(self, root: ctk.CTk, app_instance=None):
        self.root = root
        self.app = app_instance
        self.config = self.app.config if self.app else AppConfig.load()
        self.hidpp = self.app.hidpp if self.app else HIDPPMaster()
        self.overlay_mgr = BorderOverlayManager(self.root)
        self._is_scanning: bool = False

        # Multi-monitor state tracking
        self.monitors: List[MonitorInfo] = get_monitors()
        self.selected_monitor_id: str = "0"
        self._mon_id_map: dict = {}
        self.monitor_edge_vars: dict = {}
        self.monitor_enabled_vars: dict = {}

        # CustomTkinter styling
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.root.title("Lunifier - Logitech Easy-Switch Flow")
        self.root.geometry("740x940")
        self.root.minsize(640, 750)
        self._set_app_icon()

        self._last_rendered_device_sig: Optional[str] = None
        self._build_ui()
        self._load_config_values()
        self._refresh_devices_async()
        self._schedule_device_poll()

    def _set_app_icon(self) -> None:
        """Sets the application icon for window title bar, Alt+Tab, and taskbar."""
        import os
        base_dir = os.path.dirname(__file__)
        ico_path = os.path.join(base_dir, "resources", "icon.ico")
        png_path = os.path.join(base_dir, "resources", "icon.png")

        if sys.platform == "win32" and os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass
        elif os.path.exists(png_path):
            try:
                import tkinter as tk
                img = tk.PhotoImage(file=png_path)
                self.root.iconphoto(True, img)
            except Exception:
                pass

    def _build_ui(self) -> None:
        # Main container with padding
        self.main_container = ctk.CTkFrame(self.root, corner_radius=CARD_RADIUS, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # Header Frame
        header = ctk.CTkFrame(self.main_container, corner_radius=CARD_RADIUS)
        header.pack(fill="x", pady=(0, 15), ipady=8)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=15, pady=5)

        title_lbl = ctk.CTkLabel(
            title_box,
            text="Lunifier",
            font=get_ui_font(22, "bold")
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            title_box,
            text="Seamless Logitech Easy-Switch Flow",
            font=get_ui_font(12),
            text_color="#90caf9"
        )
        subtitle_lbl.pack(anchor="w")

        # Service Status Pill & Toggle Button
        status_box = ctk.CTkFrame(header, fg_color="transparent")
        status_box.pack(side="right", padx=15, pady=5)

        self.status_badge = ctk.CTkLabel(
            status_box,
            text="STOPPED",
            font=get_ui_font(11, "bold"),
            fg_color="#3e2723",
            text_color="#ef5350",
            corner_radius=BTN_RADIUS,
            width=95,
            height=30
        )
        self.status_badge.pack(side="left", padx=(0, 10))

        self.toggle_btn = ctk.CTkButton(
            status_box,
            text="Start Service",
            font=get_ui_font(12, "bold"),
            corner_radius=BTN_RADIUS,
            width=130,
            height=32,
            command=self._toggle_daemon
        )
        self.toggle_btn.pack(side="right")

        # Tabview for modular settings
        self.tabs = ctk.CTkTabview(self.main_container, corner_radius=CARD_RADIUS)
        self.tabs.pack(fill="both", expand=True, pady=(0, 15))

        self.tab_flow = self.tabs.add("  Screen & Switching  ")
        self.tab_devices = self.tabs.add("  Connected Devices  ")
        self.tab_bt = self.tabs.add("  Bluetooth Inter-Host Link  ")
        self.tab_logs = self.tabs.add("  Live Logs  ")

        self.flow_scroll = ctk.CTkScrollableFrame(self.tab_flow, fg_color="transparent")
        self.flow_scroll.pack(fill="both", expand=True)
        self._build_flow_tab(self.flow_scroll)
        self._build_devices_tab(self.tab_devices)
        self._build_bt_tab(self.tab_bt)
        self._build_logs_tab(self.tab_logs)
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # Bottom Action Bar
        bottom_bar = ctk.CTkFrame(self.main_container, fg_color="transparent")
        bottom_bar.pack(fill="x")

        self.save_btn = ctk.CTkButton(
            bottom_bar,
            text="Save Configuration",
            font=get_ui_font(13, "bold"),
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            corner_radius=BTN_RADIUS,
            command=self._save_config,
            height=38,
            width=160
        )
        self.save_btn.pack(side="right", padx=5)

        self.test_btn = ctk.CTkButton(
            bottom_bar,
            text="Test Switch Channel Now",
            font=get_ui_font(13),
            corner_radius=BTN_RADIUS,
            command=self._test_switch,
            height=38,
            width=190
        )
        self.test_btn.pack(side="right", padx=5)

    def _build_flow_tab(self, parent) -> None:
        # Easy-Switch Channel Card
        ch_card = ctk.CTkFrame(parent, corner_radius=CARD_RADIUS)
        ch_card.pack(fill="x", padx=5, pady=8, ipady=5)

        ctk.CTkLabel(
            ch_card,
            text="Easy-Switch Channel Mapping",
            font=get_ui_font(14, "bold")
        ).pack(anchor="w", padx=15, pady=(10, 8))

        row1 = ctk.CTkFrame(ch_card, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(row1, text="This Computer (Current Channel):", font=get_ui_font(13)).pack(side="left")
        self.my_ch_var = ctk.StringVar(value="Channel 1")
        self.my_ch_menu = ctk.CTkOptionMenu(
            row1,
            variable=self.my_ch_var,
            values=["Channel 1", "Channel 2", "Channel 3"],
            corner_radius=BTN_RADIUS,
            width=140
        )
        self.my_ch_menu.pack(side="right")

        # Screen Border Channel Routing Card
        edge_card = ctk.CTkFrame(parent, corner_radius=CARD_RADIUS)
        edge_card.pack(fill="x", padx=5, pady=8, ipady=5)

        ctk.CTkLabel(
            edge_card,
            text="Screen Border Channel Routing",
            font=get_ui_font(14, "bold")
        ).pack(anchor="w", padx=15, pady=(10, 2))

        ctk.CTkLabel(
            edge_card,
            text="Select target Easy-Switch channel when cursor reaches each screen border:",
            font=get_ui_font(11),
            text_color="#b0bec5"
        ).pack(anchor="w", padx=15, pady=(0, 8))

        # Multi-Monitor Configuration Frame
        mon_card = ctk.CTkFrame(edge_card, fg_color="transparent")
        mon_card.pack(fill="x", padx=15, pady=(2, 6))

        mon_top_row = ctk.CTkFrame(mon_card, fg_color="transparent")
        mon_top_row.pack(fill="x")

        ctk.CTkLabel(mon_top_row, text="Target Monitor:", font=get_ui_font(13, "bold")).pack(side="left")

        mon_options = []
        self._mon_id_map = {}
        for m in self.monitors:
            primary_tag = " (Primary)" if m.is_primary else ""
            label = f"Monitor {m.index}: {m.width}x{m.height}{primary_tag}"
            mon_options.append(label)
            self._mon_id_map[label] = str(m.id)

        if not mon_options:
            mon_options = ["Monitor 0: Primary"]
            self._mon_id_map["Monitor 0: Primary"] = "0"

        self.mon_selector_var = ctk.StringVar(value=mon_options[0])
        self.mon_selector_menu = ctk.CTkOptionMenu(
            mon_top_row,
            variable=self.mon_selector_var,
            values=mon_options,
            corner_radius=BTN_RADIUS,
            width=240,
            command=self._on_monitor_selected
        )
        self.mon_selector_menu.pack(side="right")

        mon_switch_row = ctk.CTkFrame(mon_card, fg_color="transparent")
        mon_switch_row.pack(fill="x", pady=(6, 0))

        self.mon_enable_var = ctk.BooleanVar(value=True)
        self.mon_enable_switch = ctk.CTkSwitch(
            mon_switch_row,
            text="Enable border transitions on this monitor",
            font=get_ui_font(12),
            variable=self.mon_enable_var,
            corner_radius=BTN_RADIUS,
            command=self._on_monitor_enable_toggle
        )
        self.mon_enable_switch.pack(side="left")

        channel_options = ["Disabled", "Channel 1", "Channel 2", "Channel 3"]
        self.edge_vars = {}
        self.edge_menus = {}

        border_rows = [
            ("Left Border", "left"),
            ("Right Border", "right"),
            ("Top Border", "top"),
            ("Bottom Border", "bottom")
        ]
        for edge_title, edge_key in border_rows:
            erow = ctk.CTkFrame(edge_card, fg_color="transparent")
            erow.pack(fill="x", padx=15, pady=4)
            ctk.CTkLabel(erow, text=f"{edge_title} (Switch to):", font=get_ui_font(13)).pack(side="left")
            evar = ctk.StringVar(value="Disabled")
            menu = ctk.CTkOptionMenu(
                erow,
                variable=evar,
                values=channel_options,
                corner_radius=BTN_RADIUS,
                width=140,
                command=lambda _, k=edge_key: self._on_edge_menu_changed(k)
            )
            menu.pack(side="right")
            self.edge_vars[edge_key] = evar
            self.edge_menus[edge_key] = menu

        delay_header = ctk.CTkFrame(edge_card, fg_color="transparent")
        delay_header.pack(fill="x", padx=15, pady=(8, 0))
        ctk.CTkLabel(delay_header, text="Hold Delay (Anti-Accidental Dwell):", font=get_ui_font(13)).pack(side="left")
        self.hold_lbl = ctk.CTkLabel(delay_header, text="250 ms", font=get_ui_font(12, "bold"), text_color="#64b5f6")
        self.hold_lbl.pack(side="right")

        self.hold_slider = ctk.CTkSlider(
            edge_card,
            from_=50,
            to=1000,
            number_of_steps=19,
            command=self._on_hold_slider_change
        )
        self.hold_slider.pack(fill="x", padx=15, pady=(6, 4))

        # Central active zone slider
        zone_header = ctk.CTkFrame(edge_card, fg_color="transparent")
        zone_header.pack(fill="x", padx=15, pady=(4, 0))
        ctk.CTkLabel(zone_header, text="Active Border Zone (Central %):", font=get_ui_font(13)).pack(side="left")
        self.zone_lbl = ctk.CTkLabel(zone_header, text="50%", font=get_ui_font(12, "bold"), text_color="#81c784")
        self.zone_lbl.pack(side="right")

        self.zone_slider = ctk.CTkSlider(
            edge_card,
            from_=10,
            to=100,
            number_of_steps=18,
            command=self._on_zone_slider_change
        )
        self.zone_slider.pack(fill="x", padx=15, pady=(4, 6))
        for target in (self.zone_slider, getattr(self.zone_slider, "_canvas", None)):
            if target:
                target.bind("<Button-1>", self._on_zone_slider_interact, add="+")
                target.bind("<B1-Motion>", self._on_zone_slider_interact, add="+")
                target.bind("<MouseWheel>", self._on_zone_slider_wheel, add="+")
                target.bind("<Button-4>", lambda e: self._on_zone_slider_wheel_linux(1), add="+")
                target.bind("<Button-5>", lambda e: self._on_zone_slider_wheel_linux(-1), add="+")

        # Border Knock Mode
        knock_row = ctk.CTkFrame(edge_card, fg_color="transparent")
        knock_row.pack(fill="x", padx=15, pady=(4, 2))
        self.knock_switch = ctk.CTkSwitch(
            knock_row,
            text="Enable 'Border Knock' (Double-touch border to switch)",
            font=get_ui_font(13),
            corner_radius=BTN_RADIUS,
            command=self._on_knock_toggle
        )
        self.knock_switch.pack(side="left")

        kw_row = ctk.CTkFrame(edge_card, fg_color="transparent")
        kw_row.pack(fill="x", padx=15, pady=(2, 4))
        ctk.CTkLabel(kw_row, text="Knock Window (ms):", font=get_ui_font(12)).pack(side="left")
        self.knock_win_entry = ctk.CTkEntry(kw_row, width=100, corner_radius=BTN_RADIUS, placeholder_text="1000")
        self.knock_win_entry.pack(side="right")

        cd_row = ctk.CTkFrame(edge_card, fg_color="transparent")
        cd_row.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(cd_row, text="Cooldown after switch (ms):", font=get_ui_font(13)).pack(side="left")
        self.cooldown_entry = ctk.CTkEntry(cd_row, width=100, corner_radius=BTN_RADIUS, placeholder_text="2500")
        self.cooldown_entry.pack(side="right")

        # Switching Backend selector (Linux / Diagnostic)
        backend_row = ctk.CTkFrame(edge_card, fg_color="transparent")
        backend_row.pack(fill="x", padx=15, pady=(4, 6))
        ctk.CTkLabel(backend_row, text="Switching Backend (Linux):", font=get_ui_font(13)).pack(side="left")
        self.backend_var = ctk.StringVar(value="auto")
        self.backend_menu = ctk.CTkOptionMenu(
            backend_row,
            variable=self.backend_var,
            values=["auto", "solaar", "direct"],
            corner_radius=BTN_RADIUS,
            width=130
        )
        self.backend_menu.pack(side="right")

    def _build_devices_tab(self, parent) -> None:
        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.pack(fill="x", padx=5, pady=(5, 10))

        ctk.CTkLabel(
            top_bar,
            text="Detected Logitech Hardware",
            font=get_ui_font(14, "bold")
        ).pack(side="left", anchor="w")

        self.rescan_btn = ctk.CTkButton(
            top_bar,
            text="Rescan Devices",
            font=get_ui_font(12),
            corner_radius=BTN_RADIUS,
            width=130,
            command=self._refresh_devices_async
        )
        self.rescan_btn.pack(side="right")

        # Connection Support Selector (Unifying, Bluetooth, Both)
        filter_bar = ctk.CTkFrame(parent, corner_radius=CARD_RADIUS)
        filter_bar.pack(fill="x", padx=5, pady=(0, 8), ipady=3)

        ctk.CTkLabel(
            filter_bar,
            text="Connection Support:",
            font=get_ui_font(13, "bold")
        ).pack(side="left", padx=12)

        self.conn_support_var = ctk.StringVar(value="Both (Unifying & Bluetooth)")
        self.conn_support_menu = ctk.CTkOptionMenu(
            filter_bar,
            variable=self.conn_support_var,
            values=["Both (Unifying & Bluetooth)", "Unifying Only", "Bluetooth Only"],
            corner_radius=BTN_RADIUS,
            width=220,
            command=self._on_connection_support_changed
        )
        self.conn_support_menu.pack(side="right", padx=12)

        # Scrollable container for detected devices
        self.device_list_frame = ctk.CTkScrollableFrame(parent, corner_radius=CARD_RADIUS, height=280)
        self.device_list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        note_box = ctk.CTkFrame(parent, corner_radius=CARD_RADIUS, fg_color="#1e1e1e")
        note_box.pack(fill="x", padx=5, pady=8, ipady=6)
        ctk.CTkLabel(
            note_box,
            text="Supports Logitech MX Keys, M370, POP Mouse, MX Master 3/3S, M720 Triathlon, and all Easy-Switch devices across Bluetooth, Unifying, and Bolt receivers.",
            font=get_ui_font(11),
            text_color="#b0bec5",
            wraplength=580
        ).pack(padx=12)

    def _build_bt_tab(self, parent) -> None:
        bt_card = ctk.CTkFrame(parent, corner_radius=CARD_RADIUS)
        bt_card.pack(fill="x", padx=5, pady=8, ipady=5)

        ctk.CTkLabel(
            bt_card,
            text="Peer-to-Peer Inter-Host Sync (Zero Local Network)",
            font=get_ui_font(14, "bold")
        ).pack(anchor="w", padx=15, pady=(10, 8))

        self.p2p_switch = ctk.CTkSwitch(
            bt_card,
            text="Enable Bluetooth RFCOMM Peer Link (Cursor Alignment & Clipboard)",
            font=get_ui_font(13),
            corner_radius=BTN_RADIUS,
            command=self._on_p2p_toggle
        )
        self.p2p_switch.pack(anchor="w", padx=15, pady=8)

        mac_row = ctk.CTkFrame(bt_card, fg_color="transparent")
        mac_row.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(mac_row, text="Partner Bluetooth MAC Address:", font=get_ui_font(13)).pack(side="left")
        self.peer_mac_entry = ctk.CTkEntry(mac_row, width=180, corner_radius=BTN_RADIUS, placeholder_text="00:11:22:33:44:55")
        self.peer_mac_entry.pack(side="right")

        port_row = ctk.CTkFrame(bt_card, fg_color="transparent")
        port_row.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(port_row, text="RFCOMM Channel / Port:", font=get_ui_font(13)).pack(side="left")
        self.port_entry = ctk.CTkEntry(port_row, width=90, corner_radius=BTN_RADIUS, placeholder_text="4")
        self.port_entry.pack(side="right")

        self.clip_switch = ctk.CTkSwitch(
            bt_card,
            text="Synchronize text clipboard over Bluetooth upon edge crossing",
            font=get_ui_font(13),
            corner_radius=BTN_RADIUS
        )
        self.clip_switch.pack(anchor="w", padx=15, pady=8)

        desc_box = ctk.CTkFrame(parent, corner_radius=CARD_RADIUS, fg_color="#1e1e1e")
        desc_box.pack(fill="x", padx=5, pady=8, ipady=6)
        ctk.CTkLabel(
            desc_box,
            text="Autonomous Mode vs Bluetooth Sync:\n"
                 "- Autonomous Mode (Partner MAC empty): Switches hardware whenever cursor reaches the border with ZERO inter-PC connection.\n"
                 "- Bluetooth Sync Mode: Directly pairs the two computers over Bluetooth RFCOMM to align cursor entry height and synchronize clipboard text without Wi-Fi.",
            font=get_ui_font(11),
            text_color="#b0bec5",
            justify="left",
            wraplength=580
        ).pack(padx=12)

    def _on_hold_slider_change(self, value: float) -> None:
        ms = int(value)
        self.hold_lbl.configure(text=f"{ms} ms")

    def _show_border_overlay(self) -> None:
        if not hasattr(self, 'overlay_mgr'):
            return
        pct = int(self.zone_slider.get()) if hasattr(self, 'zone_slider') else 50
        # If transitions on current monitor are disabled, hide overlay
        if hasattr(self, 'mon_enable_var') and not self.mon_enable_var.get():
            self.overlay_mgr.hide()
            return
        active_edges = []
        if hasattr(self, 'edge_vars'):
            for e, evar in self.edge_vars.items():
                if evar.get() and evar.get() != "Disabled":
                    active_edges.append(e)
        if not active_edges:
            active_edges = ["left", "right", "top", "bottom"]
        self.overlay_mgr.show(pct, edges=active_edges, monitor_id=self.selected_monitor_id)

    def _get_current_active_edges(self) -> List[str]:
        edges = []
        if hasattr(self, 'edge_vars'):
            for e, evar in self.edge_vars.items():
                if evar.get() and evar.get() != "Disabled":
                    edges.append(e)
        if not edges:
            edges = self.config.get_active_edges()
        if len(edges) <= 1:
            return ["left", "right", "top", "bottom"]
        return edges

    def _on_zone_slider_change(self, value: float) -> None:
        pct = int(value)
        self.zone_lbl.configure(text=f"{pct}%")
        self.config.border_active_zone_pct = pct
        self._show_border_overlay()

    def _on_zone_slider_interact(self, event=None) -> None:
        try:
            val = int(self.zone_slider.get())
            self._on_zone_slider_change(val)
        except Exception:
            pass

    def _on_zone_slider_wheel(self, event) -> None:
        try:
            delta = 5 if getattr(event, 'delta', 0) > 0 else -5
            current = int(self.zone_slider.get())
            new_val = max(10, min(100, current + delta))
            self.zone_slider.set(new_val)
            self._on_zone_slider_change(new_val)
        except Exception:
            pass

    def _on_zone_slider_wheel_linux(self, direction: int) -> None:
        try:
            delta = 5 * direction
            current = int(self.zone_slider.get())
            new_val = max(10, min(100, current + delta))
            self.zone_slider.set(new_val)
            self._on_zone_slider_change(new_val)
        except Exception:
            pass

    def _on_monitor_selected(self, choice: str) -> None:
        # Save current UI state for previous monitor
        if hasattr(self, 'selected_monitor_id') and self.selected_monitor_id:
            if self.selected_monitor_id not in self.monitor_edge_vars:
                self.monitor_edge_vars[self.selected_monitor_id] = {}
            for edge_key, evar in self.edge_vars.items():
                self.monitor_edge_vars[self.selected_monitor_id][edge_key] = evar.get()
            self.monitor_enabled_vars[self.selected_monitor_id] = self.mon_enable_var.get()

        new_mid = self._mon_id_map.get(choice, "0")
        self.selected_monitor_id = new_mid

        # Restore state for newly selected monitor
        enabled = self.monitor_enabled_vars.get(new_mid, True)
        self.mon_enable_var.set(enabled)
        for edge_key, evar in self.edge_vars.items():
            val = self.monitor_edge_vars.get(new_mid, {}).get(edge_key, "Disabled")
            evar.set(val)

        self._update_edge_menus_state()
        self._show_border_overlay()

    def _on_monitor_enable_toggle(self) -> None:
        enabled = self.mon_enable_var.get()
        if hasattr(self, 'selected_monitor_id'):
            self.monitor_enabled_vars[self.selected_monitor_id] = enabled
        self._update_edge_menus_state()
        self._show_border_overlay()

    def _update_edge_menus_state(self) -> None:
        enabled = self.mon_enable_var.get() if hasattr(self, 'mon_enable_var') else True
        state = "normal" if enabled else "disabled"
        for menu in self.edge_menus.values():
            menu.configure(state=state)

    def _on_edge_menu_changed(self, edge_key: str) -> None:
        if hasattr(self, 'selected_monitor_id') and self.selected_monitor_id:
            if self.selected_monitor_id not in self.monitor_edge_vars:
                self.monitor_edge_vars[self.selected_monitor_id] = {}
            self.monitor_edge_vars[self.selected_monitor_id][edge_key] = self.edge_vars[edge_key].get()
        self._show_border_overlay()

    def _on_log_level_changed(self, value: str) -> None:
        val = str(value).lower()
        lvl = "none" if val == "off" else ("debug" if val == "debug" else "normal")
        self.config.log_level = lvl
        set_log_level(lvl)
        log("GUI", f"Log level set to: {lvl.upper()}")
        try:
            self.config.save()
        except Exception:
            pass

    def _on_connection_support_changed(self, value: str) -> None:
        mode_map = {
            "Both (Unifying & Bluetooth)": "both",
            "Unifying Only": "unifying",
            "Bluetooth Only": "bluetooth"
        }
        mode = mode_map.get(value, "both")
        self.config.connection_support = mode
        log("GUI", f"Connection support set to: {mode}. Cleaning device cache...")
        self.hidpp.clear_cache()
        self.hidpp.connection_support = mode
        self._refresh_devices_async()
        try:
            self.config.save()
        except Exception:
            pass

    def _on_knock_toggle(self) -> None:
        enabled = bool(self.knock_switch.get())
        self.knock_win_entry.configure(state="normal" if enabled else "disabled")

    def _on_p2p_toggle(self) -> None:
        enabled = bool(self.p2p_switch.get())
        state = "normal" if enabled else "disabled"
        self.peer_mac_entry.configure(state=state)
        self.port_entry.configure(state=state)

    def _load_config_values(self) -> None:
        self.my_ch_var.set(f"Channel {self.config.my_channel}")

        # Load per-monitor configurations
        self.monitors = get_monitors()
        self.monitor_edge_vars = {}
        self.monitor_enabled_vars = {}

        for m in self.monitors:
            mid = str(m.id)
            mcfg = self.config.get_monitor_config(mid)
            self.monitor_enabled_vars[mid] = mcfg.get("enabled", True)
            self.monitor_edge_vars[mid] = {}
            for edge_key in ["left", "right", "top", "bottom"]:
                ch = mcfg.get("edges", {}).get(edge_key)
                self.monitor_edge_vars[mid][edge_key] = f"Channel {ch}" if ch is not None else "Disabled"

        if "0" not in self.monitor_edge_vars:
            mcfg = self.config.get_monitor_config("0")
            self.monitor_enabled_vars["0"] = mcfg.get("enabled", True)
            self.monitor_edge_vars["0"] = {
                edge_key: (f"Channel {mcfg.get('edges', {}).get(edge_key)}" if mcfg.get("edges", {}).get(edge_key) is not None else "Disabled")
                for edge_key in ["left", "right", "top", "bottom"]
            }

        # Populate current UI with monitor 0
        self.selected_monitor_id = "0"
        for label, mid in self._mon_id_map.items():
            if mid == "0":
                self.mon_selector_var.set(label)
                break

        self.mon_enable_var.set(self.monitor_enabled_vars.get("0", True))
        for edge_key, evar in self.edge_vars.items():
            evar.set(self.monitor_edge_vars.get("0", {}).get(edge_key, "Disabled"))
        self._update_edge_menus_state()

        # Log Level
        lvl_map = {"none": "Off", "off": "Off", "debug": "Debug", "normal": "Normal"}
        cfg_lvl = getattr(self.config, 'log_level', 'normal').lower()
        if hasattr(self, 'log_level_var'):
            self.log_level_var.set(lvl_map.get(cfg_lvl, "Normal"))
        set_log_level(cfg_lvl)

        hold_ms = self.config.hold_delay_ms
        self.hold_slider.set(hold_ms)
        self.hold_lbl.configure(text=f"{hold_ms} ms")

        zone_pct = getattr(self.config, 'border_active_zone_pct', 50)
        self.zone_slider.set(zone_pct)
        self.zone_lbl.configure(text=f"{zone_pct}%")

        if getattr(self.config, 'knock_enabled', False):
            self.knock_switch.select()
        else:
            self.knock_switch.deselect()

        self.knock_win_entry.delete(0, "end")
        self.knock_win_entry.insert(0, str(getattr(self.config, 'knock_timeout_ms', 1000)))
        self._on_knock_toggle()

        self.cooldown_entry.delete(0, "end")
        self.cooldown_entry.insert(0, str(self.config.cooldown_ms))

        self.backend_var.set(getattr(self.config, 'switch_backend', 'auto'))

        if self.config.bt_p2p_enabled:
            self.p2p_switch.select()
        else:
            self.p2p_switch.deselect()

        self.peer_mac_entry.delete(0, "end")
        if self.config.bt_peer_address:
            self.peer_mac_entry.insert(0, self.config.bt_peer_address)

        self.port_entry.delete(0, "end")
        self.port_entry.insert(0, str(self.config.bt_rfcomm_port))

        if self.config.sync_clipboard:
            self.clip_switch.select()
        else:
            self.clip_switch.deselect()

        conn_mode = getattr(self.config, 'connection_support', 'both').lower()
        rev_map = {
            "both": "Both (Unifying & Bluetooth)",
            "unifying": "Unifying Only",
            "bluetooth": "Bluetooth Only"
        }
        if hasattr(self, 'conn_support_var'):
            self.conn_support_var.set(rev_map.get(conn_mode, "Both (Unifying & Bluetooth)"))
        self.hidpp.connection_support = conn_mode

        self._on_p2p_toggle()

    def _save_config(self) -> None:
        try:
            self.config.my_channel = int(self.my_ch_var.get().split()[-1])

            # Sync current UI values into active monitor state
            if hasattr(self, 'selected_monitor_id') and self.selected_monitor_id:
                self.monitor_enabled_vars[self.selected_monitor_id] = self.mon_enable_var.get()
                if self.selected_monitor_id not in self.monitor_edge_vars:
                    self.monitor_edge_vars[self.selected_monitor_id] = {}
                for edge_key, evar in self.edge_vars.items():
                    self.monitor_edge_vars[self.selected_monitor_id][edge_key] = evar.get()

            # Save monitor configurations into self.config.monitor_configs
            for mid, edges_dict in self.monitor_edge_vars.items():
                parsed_edges = {}
                for edge_key, val in edges_dict.items():
                    if val == "Disabled" or not val:
                        parsed_edges[edge_key] = None
                    else:
                        try:
                            parsed_edges[edge_key] = int(val.split()[-1])
                        except Exception:
                            parsed_edges[edge_key] = None
                enabled = self.monitor_enabled_vars.get(mid, True)
                self.config.set_monitor_config(mid, enabled, parsed_edges)

            # Ensure legacy edge_channels and trigger_edge are kept in sync
            if "0" in self.config.monitor_configs:
                self.config.edge_channels = dict(self.config.monitor_configs["0"].get("edges", {}))
                active = self.config.get_active_edges()
                if active:
                    self.config.trigger_edge = active[0]
                    self.config.target_channel = self.config.get_target_channel_for_edge(active[0]) or 2

            self.config.hold_delay_ms = int(self.hold_slider.get())
            self.config.border_active_zone_pct = int(self.zone_slider.get())
            self.config.knock_enabled = bool(self.knock_switch.get())
            self.config.knock_timeout_ms = int(self.knock_win_entry.get() or "1000")
            self.config.cooldown_ms = int(self.cooldown_entry.get() or "2500")
            self.config.switch_backend = self.backend_var.get()

            if hasattr(self, 'log_level_var'):
                v = self.log_level_var.get().lower()
                lvl_val = "none" if v == "off" else ("debug" if v == "debug" else "normal")
                self.config.log_level = lvl_val
                set_log_level(lvl_val)

            mode_map = {
                "Both (Unifying & Bluetooth)": "both",
                "Unifying Only": "unifying",
                "Bluetooth Only": "bluetooth"
            }
            if hasattr(self, 'conn_support_var'):
                self.config.connection_support = mode_map.get(self.conn_support_var.get(), "both")
                self.hidpp.connection_support = self.config.connection_support

            self.config.bt_p2p_enabled = bool(self.p2p_switch.get())
            self.config.bt_peer_address = self.peer_mac_entry.get().strip()
            self.config.bt_rfcomm_port = int(self.port_entry.get() or "4")
            self.config.sync_clipboard = bool(self.clip_switch.get())
            self.config.save()

            if self.app and self.app.edge_detector:
                self.app.edge_detector.monitor_configs = self.config.monitor_configs
                self.app.edge_detector.refresh_screen_bounds()
                self.app.edge_detector.active_edges = self.config.get_active_edges()
                self.app.edge_detector.hold_delay_ms = self.config.hold_delay_ms
                self.app.edge_detector.active_zone_pct = self.config.border_active_zone_pct
                self.app.edge_detector.knock_enabled = self.config.knock_enabled
                self.app.edge_detector.knock_timeout_ms = self.config.knock_timeout_ms
                self.app.edge_detector.cooldown_ms = self.config.cooldown_ms

            messagebox.showinfo("Lunifier", "Settings successfully saved!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def _schedule_device_poll(self) -> None:
        """
        Periodically polls devices in background every 4 seconds to dynamically
        detect changes (e.g., Unifying to Bluetooth channel swap) without UI freeze.
        Only runs active hardware scan if the 'Connected Devices' tab is currently visible.
        """
        def poll():
            current_tab = ""
            try:
                current_tab = self.tabs.get()
            except Exception:
                pass

            # Only query hardware if Connected Devices tab is open, or on initial load
            if "Devices" in current_tab and not self._is_scanning:
                self._is_scanning = True
                def worker():
                    try:
                        devs = self.hidpp.scan_devices(self.config.devices, force_rescan=False)
                        self.root.after(0, lambda: self._populate_devices(devs))
                    finally:
                        self._is_scanning = False
                threading.Thread(target=worker, daemon=True).start()

            try:
                self.root.after(4000, self._schedule_device_poll)
            except Exception:
                pass

        self.root.after(4000, poll)

    def _refresh_devices_async(self) -> None:
        self.rescan_btn.configure(state="disabled", text="Scanning...")
        self._is_scanning = True

        def worker():
            try:
                devs = self.hidpp.scan_devices(self.config.devices, force_rescan=True)
                self.root.after(0, lambda: self._populate_devices(devs, force_redraw=True))
            finally:
                self._is_scanning = False

        threading.Thread(target=worker, daemon=True).start()

    def _populate_devices(self, devs: List[LogitechDevice], force_redraw: bool = False) -> None:
        # Build lightweight signature of detected devices to avoid unnecessary widget destruction & re-creation
        sig_parts = [f"{d.name}:{d.transport.value}:{d.device_index}:{d.change_host_feature_index}" for d in devs]
        sig = "|".join(sig_parts)
        if not force_redraw and self._last_rendered_device_sig == sig:
            self.rescan_btn.configure(state="normal", text="Rescan Devices")
            return
        self._last_rendered_device_sig = sig

        for child in self.device_list_frame.winfo_children():
            child.destroy()

        if not devs:
            empty_lbl = ctk.CTkLabel(
                self.device_list_frame,
                text="No supported Logitech devices detected.\nMake sure MX Keys and mouse are connected.",
                font=get_ui_font(12),
                text_color="#9e9e9e"
            )
            empty_lbl.pack(pady=30)
        else:
            for d in devs:
                card = ctk.CTkFrame(self.device_list_frame, corner_radius=CARD_RADIUS, fg_color="#2b2b2b")
                card.pack(fill="x", padx=5, pady=4, ipady=4)

                left = ctk.CTkFrame(card, fg_color="transparent")
                left.pack(side="left", padx=10)

                ctk.CTkLabel(
                    left,
                    text=d.name,
                    font=get_ui_font(13, "bold")
                ).pack(anchor="w")

                f_str = f"0x{d.change_host_feature_index:02x}" if d.change_host_feature_index else "Auto"
                ctk.CTkLabel(
                    left,
                    text=f"Slot/Index: 0x{d.device_index:02x} | CHANGE_HOST Feature: {f_str}",
                    font=get_ui_font(11),
                    text_color="#b0bec5"
                ).pack(anchor="w")

                # Protocol Badge
                badge_color = "#1565c0" if d.transport.value == "Bluetooth" else "#e65100"
                badge = ctk.CTkLabel(
                    card,
                    text=d.transport.value.upper(),
                    font=get_ui_font(10, "bold"),
                    fg_color=badge_color,
                    corner_radius=BTN_RADIUS,
                    width=85,
                    height=24
                )
                badge.pack(side="right", padx=12)

        self.rescan_btn.configure(state="normal", text="Rescan Devices")

    def _test_switch(self) -> None:
        my_ch = self.config.my_channel
        if hasattr(self, 'my_ch_var') and self.my_ch_var.get():
            try:
                my_ch = int(self.my_ch_var.get().split()[-1])
            except Exception:
                pass

        target = 2
        active_targets = []
        if hasattr(self, 'edge_vars'):
            for evar in self.edge_vars.values():
                val = evar.get()
                if val and val != "Disabled":
                    try:
                        active_targets.append(int(val.split()[-1]))
                    except Exception:
                        pass

        if active_targets:
            target = active_targets[0]
        else:
            active_edges = self.config.get_active_edges()
            if active_edges:
                target = self.config.get_target_channel_for_edge(active_edges[0]) or 2
            elif self.config.target_channel:
                target = self.config.target_channel

        if target == my_ch:
            target = 1 if my_ch != 1 else 2

        if messagebox.askyesno("Confirm Switch", f"Send switch command for all devices to Channel {target}?\n\n(Current PC is Channel {my_ch}, Backend: {self.backend_var.get()}, Support: {self.config.connection_support})"):
            log("GUI", f"Initiating manual test switch to Channel {target} (Backend: {self.backend_var.get()}, Support: {self.config.connection_support})...")
            
            def run_switch_worker():
                res = self.hidpp.switch_all_to_channel(target, self.config.devices, backend=self.backend_var.get(), connection_support=self.config.connection_support)
                status_text = "\n".join([f"• {k}: {'OK' if v else 'FAILED'}" for k, v in res.items()])
                log("GUI", f"Test switch completed:\n{status_text}")
                self.root.after(0, lambda: messagebox.showinfo(f"Switch to Channel {target} Results", status_text or "No devices found."))

            threading.Thread(target=run_switch_worker, daemon=True).start()

    def _build_logs_tab(self, parent) -> None:
        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.pack(fill="x", padx=5, pady=(5, 8))

        ctk.CTkLabel(
            top_bar,
            text="Live Diagnostic & Event Logs",
            font=get_ui_font(14, "bold")
        ).pack(side="left", anchor="w")

        ctk.CTkButton(
            top_bar,
            text="Clear Logs",
            font=get_ui_font(12),
            corner_radius=BTN_RADIUS,
            width=90,
            command=self._clear_logs
        ).pack(side="right", padx=(5, 0))

        ctk.CTkButton(
            top_bar,
            text="Copy Logs",
            font=get_ui_font(12),
            corner_radius=BTN_RADIUS,
            width=90,
            command=self._copy_logs
        ).pack(side="right", padx=5)

        # Log Level Dropdown
        lvl_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        lvl_frame.pack(side="right", padx=(0, 15))
        ctk.CTkLabel(lvl_frame, text="Log Level:", font=get_ui_font(12)).pack(side="left", padx=(0, 6))
        self.log_level_var = ctk.StringVar(value="Normal")
        self.log_level_menu = ctk.CTkOptionMenu(
            lvl_frame,
            variable=self.log_level_var,
            values=["Normal", "Debug", "Off"],
            corner_radius=BTN_RADIUS,
            width=100,
            command=self._on_log_level_changed
        )
        self.log_level_menu.pack(side="left")

        self.log_textbox = ctk.CTkTextbox(
            parent,
            corner_radius=CARD_RADIUS,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="none",
            height=320
        )
        self.log_textbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_textbox.configure(state="disabled")

        add_log_listener(self._append_log_message)

    def _append_log_message(self, message: str) -> None:
        def update_ui():
            if hasattr(self, 'log_textbox') and self.log_textbox.winfo_exists():
                try:
                    self.log_textbox.configure(state="normal")
                    self.log_textbox.insert("end", message + "\n")
                    self.log_textbox.see("end")
                    self.log_textbox.configure(state="disabled")
                except Exception:
                    pass
        try:
            self.root.after(0, update_ui)
        except Exception:
            pass

    def _clear_logs(self) -> None:
        if hasattr(self, 'log_textbox') and self.log_textbox.winfo_exists():
            self.log_textbox.configure(state="normal")
            self.log_textbox.delete("1.0", "end")
            self.log_textbox.configure(state="disabled")

    def _copy_logs(self) -> None:
        if hasattr(self, 'log_textbox') and self.log_textbox.winfo_exists():
            text = self.log_textbox.get("1.0", "end").strip()
            if text:
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                if hasattr(self, 'status_lbl'):
                    self.status_lbl.configure(text="Logs copied to clipboard!", text_color="#81c784")

    def _on_window_close(self) -> None:
        try:
            remove_log_listener(self._append_log_message)
        except Exception:
            pass
        if hasattr(self, 'overlay_mgr'):
            try:
                self.overlay_mgr.destroy()
            except Exception:
                pass
        self.root.destroy()

    def _toggle_daemon(self) -> None:
        if self.app and self.app._running:
            self.app.stop()
            self.status_badge.configure(
                text="STOPPED",
                fg_color="#3e2723",
                text_color="#ef5350"
            )
            self.toggle_btn.configure(text="Start Service", fg_color="#1976d2")
        elif self.app:
            self._save_config()
            self.app._setup_subsystems()
            threading.Thread(target=self.app.run, daemon=True).start()
            self.status_badge.configure(
                text="ACTIVE",
                fg_color="#1b5e20",
                text_color="#81c784"
            )
            self.toggle_btn.configure(text="Stop Service", fg_color="#d32f2f")


# Backward compatibility alias
LogiFlowBTGUI = LunifierGUI


def launch_gui(app_instance=None):
    root = ctk.CTk()
    gui = LunifierGUI(root, app_instance)
    root.mainloop()
