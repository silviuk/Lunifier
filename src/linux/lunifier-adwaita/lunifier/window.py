"""
Modern Native Linux User Interface built with GTK4 + Libadwaita.
Provides the native GNOME 46+ desktop experience for Ubuntu 24.04+.
"""

import sys
import threading
from typing import Optional, List

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

from .config import AppConfig
from .hidpp import HIDPPMaster
from .logger import log, add_log_listener, remove_log_listener, set_log_level
from .monitors import get_monitors, MonitorInfo
from .app import LunifierApp


class LunifierAdwaitaWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.config = AppConfig.load()
        self.app_service = LunifierApp(self.config)
        self.hidpp = self.app_service.hidpp

        self.monitors: List[MonitorInfo] = get_monitors()
        self.selected_monitor_id = "0"
        self._is_loading_config = True

        self.set_title("Lunifier")
        self.set_default_size(720, 840)

        self._build_ui()
        self._populate_ui()
        self._is_loading_config = False

        add_log_listener(self._on_log_message)
        self.connect("close-request", self._on_close)

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Title widget in header
        title_widget = Adw.WindowTitle(title="Lunifier", subtitle="Logitech Easy-Switch Flow")
        header.set_title_widget(title_widget)

        # Service toggle button in header
        self.service_btn = Gtk.Button(label="Start Service")
        self.service_btn.add_css_class("suggested-action")
        self.service_btn.connect("clicked", self._toggle_service)
        header.pack_end(self.service_btn)

        # View Switcher & Stack
        self.stack = Adw.ViewStack()
        
        # View switcher bar at top (or in header bar)
        switcher = Adw.ViewSwitcher(stack=self.stack)
        switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)

        main_box.append(self.stack)

        # --- Tab 1: Screen & Switching ---
        self._build_screen_page()

        # --- Tab 2: Connected Devices ---
        self._build_devices_page()

        # --- Tab 3: Bluetooth Inter-Host Link ---
        self._build_bluetooth_page()

        # --- Tab 4: Live Logs ---
        self._build_logs_page()

    def _build_screen_page(self):
        page = Adw.PreferencesPage()
        self.stack.add_titled(page, "screen", "Screen & Switching")
        self.stack.get_page(page).set_icon_name("video-display-symbolic")

        # Group 1: Host Identity
        grp_host = Adw.PreferencesGroup(title="Host Identity", description="Identify this system and assigned Easy-Switch slot")
        page.add(grp_host)

        self.host_name_row = Adw.EntryRow(title="Host Name")
        self.host_name_row.set_text(self.config.host_name)
        grp_host.add(self.host_name_row)

        self.my_channel_row = Adw.ComboRow(title="This Host Channel")
        channel_model = Gtk.StringList.new(["Channel 1 (Slot 1)", "Channel 2 (Slot 2)", "Channel 3 (Slot 3)"])
        self.my_channel_row.set_model(channel_model)
        self.my_channel_row.set_selected(max(0, min(2, self.config.my_channel - 1)))
        grp_host.add(self.my_channel_row)

        # Group 2: Monitor Border Configuration
        grp_monitors = Adw.PreferencesGroup(title="Display & Border Configuration", description="Configure borders per physical monitor")
        page.add(grp_monitors)

        self.monitor_combo_row = Adw.ComboRow(title="Selected Monitor")
        mon_names = [m.name for m in self.monitors]
        self.monitor_model = Gtk.StringList.new(mon_names)
        self.monitor_combo_row.set_model(self.monitor_model)
        self.monitor_combo_row.connect("notify::selected", self._on_monitor_selected)
        grp_monitors.add(self.monitor_combo_row)

        self.monitor_enabled_row = Adw.SwitchRow(title="Enable border switching for this monitor")
        self.monitor_enabled_row.connect("notify::active", self._on_monitor_enabled_changed)
        grp_monitors.add(self.monitor_enabled_row)

        border_options = ["Disabled", "Channel 1 (Slot 1)", "Channel 2 (Slot 2)", "Channel 3 (Slot 3)"]
        self.border_model = Gtk.StringList.new(border_options)

        self.left_border_row = Adw.ComboRow(title="Left Border")
        self.left_border_row.set_model(self.border_model)
        self.left_border_row.connect("notify::selected", self._on_border_changed)
        grp_monitors.add(self.left_border_row)

        self.right_border_row = Adw.ComboRow(title="Right Border")
        self.right_border_row.set_model(self.border_model)
        self.right_border_row.connect("notify::selected", self._on_border_changed)
        grp_monitors.add(self.right_border_row)

        self.top_border_row = Adw.ComboRow(title="Top Border")
        self.top_border_row.set_model(self.border_model)
        self.top_border_row.connect("notify::selected", self._on_border_changed)
        grp_monitors.add(self.top_border_row)

        self.bottom_border_row = Adw.ComboRow(title="Bottom Border")
        self.bottom_border_row.set_model(self.border_model)
        self.bottom_border_row.connect("notify::selected", self._on_border_changed)
        grp_monitors.add(self.bottom_border_row)

        # Group 3: Trigger Sensitivity
        grp_sens = Adw.PreferencesGroup(title="Edge Trigger Sensitivity", description="Fine-tune boundary dwell timing and active span")
        page.add(grp_sens)

        # Active Zone row
        self.active_zone_row = Adw.ActionRow(title="Active Border Zone", subtitle=f"Central {self.config.border_active_zone_pct}%")
        self.active_zone_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 100, 5)
        self.active_zone_scale.set_value(self.config.border_active_zone_pct)
        self.active_zone_scale.set_hexpand(True)
        self.active_zone_scale.set_size_request(200, -1)
        self.active_zone_scale.connect("value-changed", self._on_active_zone_changed)
        self.active_zone_row.add_suffix(self.active_zone_scale)
        grp_sens.add(self.active_zone_row)

        # Hold Delay row
        self.hold_delay_row = Adw.ActionRow(title="Dwell Hold Delay", subtitle=f"{self.config.hold_delay_ms} ms")
        self.hold_delay_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 50, 1000, 25)
        self.hold_delay_scale.set_value(self.config.hold_delay_ms)
        self.hold_delay_scale.set_hexpand(True)
        self.hold_delay_scale.set_size_request(200, -1)
        self.hold_delay_scale.connect("value-changed", self._on_hold_delay_changed)
        self.hold_delay_row.add_suffix(self.hold_delay_scale)
        grp_sens.add(self.hold_delay_row)

        # Cooldown row
        self.cooldown_row = Adw.ActionRow(title="Switch Cooldown", subtitle=f"{self.config.cooldown_ms} ms")
        self.cooldown_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 500, 5000, 100)
        self.cooldown_scale.set_value(self.config.cooldown_ms)
        self.cooldown_scale.set_hexpand(True)
        self.cooldown_scale.set_size_request(200, -1)
        self.cooldown_scale.connect("value-changed", self._on_cooldown_changed)
        self.cooldown_row.add_suffix(self.cooldown_scale)
        grp_sens.add(self.cooldown_row)

        # Knock rows
        self.knock_switch_row = Adw.SwitchRow(title="Require double-touch 'Border Knock' to switch")
        self.knock_switch_row.set_active(self.config.knock_enabled)
        grp_sens.add(self.knock_switch_row)

        self.knock_timeout_row = Adw.SpinRow.new_with_range(200, 3000, 50)
        self.knock_timeout_row.set_title("Knock Timeout (ms)")
        self.knock_timeout_row.set_value(self.config.knock_timeout_ms)
        grp_sens.add(self.knock_timeout_row)

        # Group 4: Hardware & Backend
        grp_hw = Adw.PreferencesGroup(title="Hardware & Backend Options")
        page.add(grp_hw)

        self.switch_backend_row = Adw.ComboRow(title="Switching Backend")
        backend_model = Gtk.StringList.new(["Auto (Adaptive hidraw + Solaar)", "Solaar CLI Prioritized", "Direct /dev/hidraw Prioritized"])
        self.switch_backend_row.set_model(backend_model)
        be_idx = 0 if self.config.switch_backend == "auto" else (1 if self.config.switch_backend == "solaar" else 2)
        self.switch_backend_row.set_selected(be_idx)
        grp_hw.add(self.switch_backend_row)

        self.conn_support_row = Adw.ComboRow(title="Connection Support")
        conn_model = Gtk.StringList.new(["Both (Wireless Receivers & Bluetooth)", "Unifying / Bolt / Receivers Only", "Bluetooth Connections Only"])
        self.conn_support_row.set_model(conn_model)
        cs_idx = 0 if self.config.connection_support == "both" else (1 if self.config.connection_support == "unifying" else 2)
        self.conn_support_row.set_selected(cs_idx)
        grp_hw.add(self.conn_support_row)

        self.log_level_row = Adw.ComboRow(title="Logging Level")
        log_model = Gtk.StringList.new(["Normal (Standard logs)", "Debug (Verbose diagnostics)", "None (Logging disabled)"])
        self.log_level_row.set_model(log_model)
        ll_idx = 0 if self.config.log_level == "normal" else (1 if self.config.log_level == "debug" else 2)
        self.log_level_row.set_selected(ll_idx)
        grp_hw.add(self.log_level_row)

    def _build_devices_page(self):
        page = Adw.PreferencesPage()
        self.stack.add_titled(page, "devices", "Connected Devices")
        self.stack.get_page(page).set_icon_name("input-keyboard-symbolic")

        grp = Adw.PreferencesGroup(title="Logitech Easy-Switch Peripherals")
        page.add(grp)

        # Refresh button & actions
        row_actions = Adw.ActionRow(title="Hardware Device Controls")
        btn_refresh = Gtk.Button(label="Rescan Devices")
        btn_refresh.connect("clicked", lambda b: self._rescan_devices())
        row_actions.add_suffix(btn_refresh)
        grp.add(row_actions)

        # Test Switch Buttons
        row_test = Adw.ActionRow(title="Manual Test Switch")
        box_test = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        btn_ch1 = Gtk.Button(label="Channel 1")
        btn_ch1.connect("clicked", lambda b: self._test_switch(1))
        box_test.append(btn_ch1)

        btn_ch2 = Gtk.Button(label="Channel 2")
        btn_ch2.connect("clicked", lambda b: self._test_switch(2))
        box_test.append(btn_ch2)

        btn_ch3 = Gtk.Button(label="Channel 3")
        btn_ch3.connect("clicked", lambda b: self._test_switch(3))
        box_test.append(btn_ch3)

        row_test.add_suffix(box_test)
        grp.add(row_test)

        self.grp_devices_list = Adw.PreferencesGroup(title="Detected Hardware Devices")
        page.add(self.grp_devices_list)

    def _build_bluetooth_page(self):
        page = Adw.PreferencesPage()
        self.stack.add_titled(page, "bluetooth", "Bluetooth P2P Link")
        self.stack.get_page(page).set_icon_name("bluetooth-active-symbolic")

        grp = Adw.PreferencesGroup(
            title="Zero-Network Bluetooth Inter-Host Link",
            description="Coordinates seamless handoff and clipboard synchronization without WiFi or LAN"
        )
        page.add(grp)

        self.bt_enabled_row = Adw.SwitchRow(title="Enable Bluetooth RFCOMM P2P Link")
        self.bt_enabled_row.set_active(self.config.bt_p2p_enabled)
        grp.add(self.bt_enabled_row)

        self.bt_peer_mac_row = Adw.EntryRow(title="Partner Host Bluetooth MAC")
        self.bt_peer_mac_row.set_text(self.config.bt_peer_address)
        grp.add(self.bt_peer_mac_row)

        self.bt_port_row = Adw.SpinRow.new_with_range(1, 30, 1)
        self.bt_port_row.set_title("RFCOMM Channel Port")
        self.bt_port_row.set_value(self.config.bt_rfcomm_port)
        grp.add(self.bt_port_row)

        self.sync_cursor_row = Adw.SwitchRow(title="Synchronize cursor position at entry edge")
        self.sync_cursor_row.set_active(self.config.sync_cursor_position)
        grp.add(self.sync_cursor_row)

        self.sync_clipboard_row = Adw.SwitchRow(title="Synchronize clipboard text across hosts")
        self.sync_clipboard_row.set_active(self.config.sync_clipboard)
        grp.add(self.sync_clipboard_row)

    def _build_logs_page(self):
        page = Adw.PreferencesPage()
        self.stack.add_titled(page, "logs", "Live Logs")
        self.stack.get_page(page).set_icon_name("text-x-generic-symbolic")

        grp = Adw.PreferencesGroup(title="System & Switch Events")
        page.add(grp)

        actions_row = Adw.ActionRow(title="Log Controls")
        btn_clear = Gtk.Button(label="Clear Logs")
        btn_clear.connect("clicked", lambda b: self.log_buffer.set_text(""))
        actions_row.add_suffix(btn_clear)
        grp.add(actions_row)

        # Scrolled text view for logs
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(400)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        self.log_buffer = self.log_view.get_buffer()
        scrolled.set_child(self.log_view)

        log_row = Adw.ActionRow()
        log_row.set_child(scrolled)
        grp.add(log_row)

    def _populate_ui(self):
        self._update_monitor_ui(self.selected_monitor_id)
        self._rescan_devices()

    def _update_monitor_ui(self, monitor_id: str):
        m_cfg = self.config.get_monitor_config(monitor_id)
        self.monitor_enabled_row.set_active(m_cfg.get("enabled", True))

        edges = m_cfg.get("edges", {})
        self._set_border_row(self.left_border_row, edges.get("left"))
        self._set_border_row(self.right_border_row, edges.get("right"))
        self._set_border_row(self.top_border_row, edges.get("top"))
        self._set_border_row(self.bottom_border_row, edges.get("bottom"))

    def _set_border_row(self, row: Adw.ComboRow, channel_val: Optional[int]):
        if channel_val is None:
            row.set_selected(0)
        else:
            row.set_selected(max(1, min(3, int(channel_val))))

    def _get_border_row_val(self, row: Adw.ComboRow) -> Optional[int]:
        sel = row.get_selected()
        return sel if sel > 0 else None

    def _save_current_monitor_state(self):
        if self._is_loading_config:
            return
        edges = {
            "left": self._get_border_row_val(self.left_border_row),
            "right": self._get_border_row_val(self.right_border_row),
            "top": self._get_border_row_val(self.top_border_row),
            "bottom": self._get_border_row_val(self.bottom_border_row)
        }
        enabled = self.monitor_enabled_row.get_active()
        self.config.set_monitor_config(self.selected_monitor_id, enabled, edges)

    def _on_monitor_selected(self, row, param):
        if self._is_loading_config:
            return
        self._save_current_monitor_state()
        idx = row.get_selected()
        if 0 <= idx < len(self.monitors):
            self.selected_monitor_id = str(idx)
            self._update_monitor_ui(self.selected_monitor_id)

    def _on_monitor_enabled_changed(self, row, param):
        self._save_current_monitor_state()

    def _on_border_changed(self, row, param):
        self._save_current_monitor_state()

    def _on_active_zone_changed(self, scale):
        val = int(scale.get_value())
        self.active_zone_row.set_subtitle(f"Central {val}%")
        self.config.border_active_zone_pct = val

    def _on_hold_delay_changed(self, scale):
        val = int(scale.get_value())
        self.hold_delay_row.set_subtitle(f"{val} ms")
        self.config.hold_delay_ms = val

    def _on_cooldown_changed(self, scale):
        val = int(scale.get_value())
        self.cooldown_row.set_subtitle(f"{val} ms")
        self.config.cooldown_ms = val

    def _toggle_service(self, btn):
        if getattr(self.app_service, "_running", False):
            self.app_service.stop()
            self.service_btn.set_label("Start Service")
            self.service_btn.remove_css_class("destructive-action")
            self.service_btn.add_css_class("suggested-action")
        else:
            self._save_all_settings()
            self.app_service.config = self.config
            self.app_service._setup_subsystems()
            self.app_service.start()
            self.service_btn.set_label("Stop Service")
            self.service_btn.remove_css_class("suggested-action")
            self.service_btn.add_css_class("destructive-action")

    def _save_all_settings(self):
        self._save_current_monitor_state()
        self.config.host_name = self.host_name_row.get_text().strip()
        self.config.my_channel = self.my_channel_row.get_selected() + 1
        self.config.knock_enabled = self.knock_switch_row.get_active()
        self.config.knock_timeout_ms = int(self.knock_timeout_row.get_value())

        be_sel = self.switch_backend_row.get_selected()
        self.config.switch_backend = "auto" if be_sel == 0 else ("solaar" if be_sel == 1 else "direct")

        cs_sel = self.conn_support_row.get_selected()
        self.config.connection_support = "both" if cs_sel == 0 else ("unifying" if cs_sel == 1 else "bluetooth")

        ll_sel = self.log_level_row.get_selected()
        self.config.log_level = "normal" if ll_sel == 0 else ("debug" if ll_sel == 1 else "none")

        self.config.bt_p2p_enabled = self.bt_enabled_row.get_active()
        self.config.bt_peer_address = self.bt_peer_mac_row.get_text().strip()
        self.config.bt_rfcomm_port = int(self.bt_port_row.get_value())
        self.config.sync_cursor_position = self.sync_cursor_row.get_active()
        self.config.sync_clipboard = self.sync_clipboard_row.get_active()

        self.config.save()

    def _rescan_devices(self):
        def worker():
            devs = self.hidpp.scan_devices(self.config.devices, force_rescan=True, connection_support=self.config.connection_support)
            GLib.idle_add(self._render_devices_list, devs)
        threading.Thread(target=worker, daemon=True).start()

    def _render_devices_list(self, devices):
        # Safely remove previously tracked rows from the PreferencesGroup
        if not hasattr(self, "_device_rows"):
            self._device_rows = []

        for r in self._device_rows:
            try:
                self.grp_devices_list.remove(r)
            except Exception:
                pass
        self._device_rows.clear()

        if not devices:
            empty_row = Adw.ActionRow(title="No compatible Logitech devices currently detected")
            empty_row.set_subtitle("Ensure devices are paired and powered on")
            self.grp_devices_list.add(empty_row)
            self._device_rows.append(empty_row)
            return

        for dev in devices:
            row = Adw.ActionRow(title=dev.name)
            trans = dev.transport.value if hasattr(dev.transport, 'value') else str(dev.transport)
            row.set_subtitle(f"Transport: {trans} | Slot: 0x{dev.device_index:02X} | Feature 0x1814: 0x{dev.change_host_feature_index:02X}")
            self.grp_devices_list.add(row)
            self._device_rows.append(row)

    def _test_switch(self, channel: int):
        log("GUI", f"Initiating manual test switch to Channel {channel}...")
        threading.Thread(
            target=lambda: self.hidpp.switch_all_to_channel(channel, self.config.devices, backend=self.config.switch_backend, connection_support=self.config.connection_support),
            daemon=True
        ).start()

    def _on_log_message(self, message: str):
        def append_text():
            end_iter = self.log_buffer.get_end_iter()
            self.log_buffer.insert(end_iter, message + "\n")
            # Auto scroll
            adj = self.log_view.get_vadjustment()
            if adj:
                adj.set_value(adj.get_upper() - adj.get_page_size())
            return False
        GLib.idle_add(append_text)

    def _on_close(self, *args):
        self._save_all_settings()
        if getattr(self.app_service, "_running", False):
            self.app_service.stop()
        remove_log_listener(self._on_log_message)
        return False


class LunifierAdwaitaApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.silviuk.Lunifier",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = LunifierAdwaitaWindow(application=self)
        win.present()
