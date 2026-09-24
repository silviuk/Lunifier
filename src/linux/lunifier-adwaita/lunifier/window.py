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
from gi.repository import Gtk, Adw, GLib, Gio, Gdk

from .config import AppConfig
from .hidpp import HIDPPMaster
from .logger import log, add_log_listener, remove_log_listener, set_log_level
from .monitors import get_monitors, MonitorInfo
from .app import LunifierApp
from .bt_link import discover_advertising_lunifier_peers, get_local_bluetooth_mac
from .overlay import BorderOverlayManager
from .tray import LunifierTray
from .features import NO_BTSYNC
from . import __version__


class LunifierAdwaitaWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.no_btsync = NO_BTSYNC
        self.config = AppConfig.load()
        self.app_service = LunifierApp(self.config)
        self.hidpp = self.app_service.hidpp
        self.overlay = BorderOverlayManager(parent=self)
        self.tray = LunifierTray(on_show=self.show_and_present, on_quit=self.quit_application)
        self._is_quitting = False

        self.monitors: List[MonitorInfo] = get_monitors()
        self.selected_monitor_id = "0"
        self._is_loading_config = True

        self.set_title("Lunifier")
        self.set_default_size(780, 980)

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

        # Save configuration button in header
        self.save_btn = Gtk.Button(label="Save")
        self.save_btn.connect("clicked", self._on_save_clicked)
        header.pack_end(self.save_btn)

        # Service toggle button in header
        self.service_btn = Gtk.Button(label="Start Service")
        self.service_btn.add_css_class("suggested-action")
        self.service_btn.connect("clicked", self._toggle_service)
        header.pack_end(self.service_btn)

        # View Switcher & Stack (one level lower, cleanly visible and spaced out)
        self.stack = Adw.ViewStack()
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)

        switcher_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        switcher_box.set_halign(Gtk.Align.CENTER)
        switcher_box.set_margin_top(6)
        switcher_box.set_margin_bottom(6)
        switcher = Adw.ViewSwitcher(stack=self.stack)
        switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        switcher_box.append(switcher)
        main_box.append(switcher_box)

        main_box.append(self.stack)

        # --- Tab 1: Screen & Switching ---
        self._build_screen_page()

        # --- Tab 2: Advanced ---
        self._build_advanced_page()

        # --- Tab 3: Bluetooth Inter-Host Link (omitted in -nobtsync edition) ---
        if not self.no_btsync:
            self._build_bluetooth_page()

        # --- Tab 4: Live Logs ---
        self._build_logs_page()

        # --- Tab 5: About ---
        self._build_about_page()

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

        self.autostart_row = Adw.SwitchRow(title="Start Lunifier automatically on login")
        self.autostart_row.set_active(self.config.is_autostart_enabled())
        grp_host.add(self.autostart_row)

        self.start_minimized_row = Adw.SwitchRow(title="Start minimized to system tray")
        self.start_minimized_row.set_active(getattr(self.config, "start_minimized", False))
        grp_host.add(self.start_minimized_row)

        # Group 2: Monitor Border Configuration
        grp_monitors = Adw.PreferencesGroup(title="Display &amp; Border Configuration", description="Configure borders per physical monitor")
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

    def _build_advanced_page(self):
        page = Adw.PreferencesPage()
        self.stack.add_titled(page, "advanced", "Advanced")
        self.stack.get_page(page).set_icon_name("preferences-system-symbolic")

        grp_devices = Adw.PreferencesGroup(title="Connected Logitech Devices")
        page.add(grp_devices)

        # Refresh button & actions
        row_actions = Adw.ActionRow(title="Hardware Device Controls")
        btn_refresh = Gtk.Button(label="Rescan Devices")
        btn_refresh.connect("clicked", lambda b: self._rescan_devices())
        row_actions.add_suffix(btn_refresh)
        grp_devices.add(row_actions)

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
        grp_devices.add(row_test)

        self.grp_devices_list = Adw.PreferencesGroup(title="Detected Hardware Devices")
        page.add(self.grp_devices_list)

        # Group 2: Trigger Sensitivity
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
        self.cooldown_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 200, 5000, 100)
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

        # Group 3: Hardware & Backend
        grp_hw = Adw.PreferencesGroup(title="Hardware &amp; Backend Options")
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
        self.log_level_row.connect("notify::selected", self._on_advanced_log_level_changed)
        grp_hw.add(self.log_level_row)

    def _build_bluetooth_page(self):
        page = Adw.PreferencesPage()
        self.stack.add_titled(page, "bluetooth", "Bluetooth P2P Link")
        self.stack.get_page(page).set_icon_name("bluetooth-active-symbolic")

        # 1. Timed Advertising Group
        grp_adv = Adw.PreferencesGroup(
            title="Host A: Advertise This Computer (Quick Pair)",
            description="Step 1: Click on ONE computer to make it discoverable over Bluetooth for 60 seconds (no Wi-Fi needed). Automatically turns off after duration."
        )
        page.add(grp_adv)

        row_local_mac = Adw.ActionRow(title="This Computer's Bluetooth Address")
        box_local_mac = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.local_mac_entry = Gtk.Entry()
        self.local_mac_entry.set_text(get_local_bluetooth_mac() or "(No adapter detected)")
        self.local_mac_entry.set_editable(False)
        self.local_mac_entry.set_can_focus(True)
        box_local_mac.append(self.local_mac_entry)
        self.btn_copy_mac = Gtk.Button(label="Copy")

        def _on_copy_mac(btn):
            txt = self.local_mac_entry.get_text().strip()
            if txt and not txt.startswith("("):
                cb = Gdk.Display.get_default().get_clipboard()
                cb.set(txt)
                btn.set_label("Copied!")
                GLib.timeout_add(1500, lambda: btn.set_label("Copy") or False)

        self.btn_copy_mac.connect("clicked", _on_copy_mac)
        box_local_mac.append(self.btn_copy_mac)
        row_local_mac.add_suffix(box_local_mac)
        grp_adv.add(row_local_mac)

        self.adv_duration_row = Adw.ComboRow(title="Advertising Duration")
        duration_model = Gtk.StringList.new(["30 seconds", "60 seconds", "120 seconds", "300 seconds"])
        self.adv_duration_row.set_model(duration_model)
        self.adv_duration_row.set_selected(1)  # 60s
        grp_adv.add(self.adv_duration_row)

        row_adv_action = Adw.ActionRow(title="Advertising Control")
        box_adv = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.adv_status_label = Gtk.Label(label="Idle")
        box_adv.append(self.adv_status_label)
        self.adv_btn = Gtk.Button(label="Advertise Lunifier")
        self.adv_btn.connect("clicked", self._toggle_advertising)
        box_adv.append(self.adv_btn)
        row_adv_action.add_suffix(box_adv)
        grp_adv.add(row_adv_action)

        # 2. Peer Discovery & Pairing Group
        grp_disc = Adw.PreferencesGroup(
            title="Host B: Find &amp; Link Advertising Computer (Quick Pair)",
            description="Step 2: On your OTHER computer, scan for Host A and connect. Both computers will automatically authenticate and enable the Peer Link below:"
        )
        page.add(grp_disc)

        row_scan = Adw.ActionRow(title="Discovery Action")
        box_scan = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.scan_spinner = Gtk.Spinner()
        box_scan.append(self.scan_spinner)
        self.scan_status_label = Gtk.Label(label="Ready to scan")
        box_scan.append(self.scan_status_label)
        self.scan_bt_btn = Gtk.Button(label="Scan for Lunifier Hosts")
        self.scan_bt_btn.connect("clicked", self._scan_bt_hosts)
        box_scan.append(self.scan_bt_btn)
        row_scan.add_suffix(box_scan)
        grp_disc.add(row_scan)

        self.grp_discovered_peers = Adw.PreferencesGroup(title="Discovered Lunifier Hosts")
        page.add(self.grp_discovered_peers)
        self._discovered_peer_rows = []

        # 3. Connection Settings Group
        grp_conn = Adw.PreferencesGroup(
            title="Peer Link Status &amp; Settings (Zero Network Bluetooth)",
            description="Underlying Bluetooth RFCOMM link state. Automatically configured and enabled by Quick Pair above, or you can manage it manually:"
        )
        page.add(grp_conn)

        self.bt_enabled_row = Adw.SwitchRow(title="Enable Bluetooth RFCOMM P2P Link")
        self.bt_enabled_row.set_active(self.config.bt_p2p_enabled)
        grp_conn.add(self.bt_enabled_row)

        self.bt_peer_mac_row = Adw.EntryRow(title="Partner Host Bluetooth MAC")
        self.bt_peer_mac_row.set_text(self.config.bt_peer_address)
        grp_conn.add(self.bt_peer_mac_row)

        self.bt_port_row = Adw.SpinRow.new_with_range(1, 30, 1)
        self.bt_port_row.set_title("RFCOMM Channel Port")
        self.bt_port_row.set_value(self.config.bt_rfcomm_port)
        grp_conn.add(self.bt_port_row)

        self.sync_cursor_row = Adw.SwitchRow(title="Synchronize cursor position at entry edge")
        self.sync_cursor_row.set_active(self.config.sync_cursor_position)
        grp_conn.add(self.sync_cursor_row)

        self.sync_clipboard_row = Adw.SwitchRow(title="Synchronize clipboard text across hosts")
        self.sync_clipboard_row.set_active(self.config.sync_clipboard)
        grp_conn.add(self.sync_clipboard_row)

    def _build_logs_page(self):
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page_box.set_margin_top(12)
        page_box.set_margin_bottom(12)
        page_box.set_margin_start(16)
        page_box.set_margin_end(16)
        page_box.set_vexpand(True)
        page_box.set_hexpand(True)

        self.stack.add_titled(page_box, "logs", "Live Logs")
        self.stack.get_page(page_box).set_icon_name("text-x-generic-symbolic")

        # Top controls bar: Log level dropdown and Clear logs button
        controls_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        controls_bar.set_valign(Gtk.Align.CENTER)

        lbl_level = Gtk.Label(label="Logging Level:")
        lbl_level.add_css_class("heading")
        controls_bar.append(lbl_level)

        log_level_strings = ["Normal (Standard logs)", "Debug (Verbose diagnostics)", "None (Logging disabled)"]
        self.logs_level_dropdown = Gtk.DropDown.new_from_strings(log_level_strings)
        ll_idx = 0 if self.config.log_level == "normal" else (1 if self.config.log_level == "debug" else 2)
        self.logs_level_dropdown.set_selected(ll_idx)
        self.logs_level_dropdown.connect("notify::selected", self._on_logs_level_changed)
        controls_bar.append(self.logs_level_dropdown)

        # Spacer to push action buttons to the right
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        controls_bar.append(spacer)

        def _on_copy_logs(btn):
            start_iter = self.log_buffer.get_start_iter()
            end_iter = self.log_buffer.get_end_iter()
            txt = self.log_buffer.get_text(start_iter, end_iter, True)
            if txt:
                cb = Gdk.Display.get_default().get_clipboard()
                cb.set(txt)
                btn.set_label("Copied!")
                GLib.timeout_add(1500, lambda: btn.set_label("Copy Logs") or False)

        btn_copy = Gtk.Button(label="Copy Logs")
        btn_copy.connect("clicked", _on_copy_logs)
        controls_bar.append(btn_copy)

        btn_clear = Gtk.Button(label="Clear Logs")
        btn_clear.connect("clicked", lambda b: self.log_buffer.set_text(""))
        controls_bar.append(btn_clear)

        page_box.append(controls_bar)

        # Scrolled text view for logs - scales to fill all remaining window space
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.add_css_class("card")

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_view.set_top_margin(10)
        self.log_view.set_bottom_margin(10)
        self.log_view.set_left_margin(12)
        self.log_view.set_right_margin(12)

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"textview.log-view-small text { font-size: 8.5pt; font-family: monospace; }")
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.log_view.add_css_class("log-view-small")

        self.log_buffer = self.log_view.get_buffer()
        scrolled.set_child(self.log_view)

        page_box.append(scrolled)

    def _on_logs_level_changed(self, dropdown, pspec):
        if getattr(self, "_is_loading_config", False):
            return
        sel = dropdown.get_selected()
        lvl = "normal" if sel == 0 else ("debug" if sel == 1 else "none")
        self.config.log_level = lvl
        set_log_level(lvl)
        if hasattr(self, "log_level_row") and self.log_level_row.get_selected() != sel:
            self.log_level_row.set_selected(sel)

    def _on_advanced_log_level_changed(self, row, pspec):
        if getattr(self, "_is_loading_config", False):
            return
        sel = row.get_selected()
        lvl = "normal" if sel == 0 else ("debug" if sel == 1 else "none")
        self.config.log_level = lvl
        set_log_level(lvl)
        if hasattr(self, "logs_level_dropdown") and self.logs_level_dropdown.get_selected() != sel:
            self.logs_level_dropdown.set_selected(sel)

    def _build_about_page(self):
        page = Adw.PreferencesPage()
        self.stack.add_titled(page, "about", "About")
        self.stack.get_page(page).set_icon_name("help-about-symbolic")

        grp = Adw.PreferencesGroup()
        page.add(grp)

        edition = " (No-BtSync Edition)" if self.no_btsync else ""
        row_about = Adw.ActionRow(title=f"Lunifier {__version__}{edition} Native", subtitle="Logitech Easy-Switch Screen Flow (GTK4 + Libadwaita)")
        icon_img = Gtk.Image.new_from_icon_name("lunifier")
        icon_img.set_pixel_size(48)
        row_about.add_prefix(icon_img)
        grp.add(row_about)

        grp_info = Adw.PreferencesGroup(title="Application Details")
        page.add(grp_info)

        overview_sub = (
            "Autonomous multi-monitor border switching for Logitech Easy-Switch keyboards and mice."
            if self.no_btsync else
            "Autonomous multi-monitor border switching for Logitech Easy-Switch keyboards and mice with zero-network Bluetooth P2P sync."
        )
        row_desc = Adw.ActionRow(
            title="Overview",
            subtitle=overview_sub
        )
        grp_info.add(row_desc)

        row_author = Adw.ActionRow(title="Developer", subtitle="Silviu Vlasceanu")
        grp_info.add(row_author)

        row_license = Adw.ActionRow(title="License", subtitle="MIT License")
        grp_info.add(row_license)

        row_repo = Adw.ActionRow(title="Website / GitHub", subtitle="https://github.com/silviuk/Lunifier")
        btn_repo = Gtk.LinkButton.new_with_label("https://github.com/silviuk/Lunifier", "Visit")
        row_repo.add_suffix(btn_repo)
        grp_info.add(row_repo)

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

    def _show_overlay_for_current_monitor(self):
        if self._is_loading_config or not hasattr(self, "overlay"):
            return
        edges_dict = {}
        active = self.config.get_all_active_monitor_borders()
        for mid, edge, _ in active:
            edges_dict.setdefault(str(mid), []).append(edge)

        # If no borders configured yet for this monitor, preview all 4 edges
        if not edges_dict or str(self.selected_monitor_id) not in edges_dict:
            edges_dict[str(self.selected_monitor_id)] = ["left", "right", "top", "bottom"]

        self.overlay.show(
            active_zone_pct=self.config.border_active_zone_pct,
            edges=edges_dict,
            monitor_id=str(self.selected_monitor_id)
        )

    def _on_save_clicked(self, btn):
        self._save_all_settings()
        if getattr(self.app_service, "_running", False):
            self.app_service.config = self.config
            self.app_service._setup_subsystems()
        self.save_btn.set_label("✓ Saved")
        GLib.timeout_add(1500, lambda: self.save_btn.set_label("Save") or False)
        self._show_overlay_for_current_monitor()

    def _on_monitor_selected(self, row, param):
        if self._is_loading_config:
            return
        self._save_current_monitor_state()
        idx = row.get_selected()
        if 0 <= idx < len(self.monitors):
            self.selected_monitor_id = str(idx)
            self._update_monitor_ui(self.selected_monitor_id)
            self._show_overlay_for_current_monitor()

    def _on_monitor_enabled_changed(self, row, param):
        self._save_current_monitor_state()
        self._show_overlay_for_current_monitor()

    def _on_border_changed(self, row, param):
        self._save_current_monitor_state()
        self._show_overlay_for_current_monitor()

    def _on_active_zone_changed(self, scale):
        val = int(scale.get_value())
        self.active_zone_row.set_subtitle(f"Central {val}%")
        self.config.border_active_zone_pct = val
        self._show_overlay_for_current_monitor()

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

        if not self.no_btsync and hasattr(self, "bt_enabled_row"):
            self.config.bt_p2p_enabled = self.bt_enabled_row.get_active()
            self.config.bt_peer_address = self.bt_peer_mac_row.get_text().strip()
            self.config.bt_rfcomm_port = int(self.bt_port_row.get_value())
            self.config.sync_cursor_position = self.sync_cursor_row.get_active()
            self.config.sync_clipboard = self.sync_clipboard_row.get_active()

        self.config.set_autostart(self.autostart_row.get_active())
        self.config.start_minimized = self.start_minimized_row.get_active()

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

    def _toggle_advertising(self, btn):
        bt = getattr(self.app_service, "bt_link", None)
        if not bt:
            return

        if bt.is_advertising:
            bt.stop_advertising()
            self.adv_btn.set_label("Advertise Lunifier")
            self.adv_btn.remove_css_class("destructive-action")
            self.adv_status_label.set_text("Idle")
        else:
            sel = self.adv_duration_row.get_selected()
            durations = [30, 60, 120, 300]
            duration = durations[sel] if 0 <= sel < len(durations) else 60

            def on_tick(remaining):
                def update():
                    self.adv_status_label.set_text(f"Advertising ({remaining}s)...")
                    return False
                GLib.idle_add(update)

            def on_expired():
                def update():
                    self.adv_btn.set_label("Advertise Lunifier")
                    self.adv_btn.remove_css_class("destructive-action")
                    self.adv_status_label.set_text("Idle")
                    return False
                GLib.idle_add(update)

            bt.start_advertising(duration_seconds=duration, on_tick=on_tick, on_expired=on_expired)
            self.adv_btn.set_label("Stop Advertising")
            self.adv_btn.add_css_class("destructive-action")
            self.adv_status_label.set_text(f"Advertising ({duration}s)...")

    def _scan_bt_hosts(self, btn):
        self.scan_bt_btn.set_sensitive(False)
        self.scan_spinner.start()
        self.scan_status_label.set_text("Scanning for Lunifier hosts...")

        def worker():
            peers = discover_advertising_lunifier_peers(
                timeout=4.0,
                rfcomm_port=int(self.bt_port_row.get_value()),
                host_name=self.config.host_name
            )
            GLib.idle_add(self._render_discovered_peers, peers)

        threading.Thread(target=worker, daemon=True).start()

    def _render_discovered_peers(self, peers):
        self.scan_spinner.stop()
        self.scan_bt_btn.set_sensitive(True)
        self.scan_status_label.set_text(f"Found {len(peers)} host(s)")

        for r in self._discovered_peer_rows:
            try:
                self.grp_discovered_peers.remove(r)
            except Exception:
                pass
        self._discovered_peer_rows.clear()

        if not peers:
            empty_row = Adw.ActionRow(title="No advertising Lunifier hosts detected")
            empty_row.set_subtitle("Ensure partner host has pressed 'Advertise Lunifier'")
            self.grp_discovered_peers.add(empty_row)
            self._discovered_peer_rows.append(empty_row)
            return

        for p in peers:
            row = Adw.ActionRow(title=p.get("name", "Lunifier Host"))
            mac = p.get("mac", "")
            token = p.get("token", "")
            port = p.get("port", 5)
            exp = p.get("expires_in", 0)
            row.set_subtitle(f"MAC: {mac} | Port: {port} | Token: {token[:8]} | Active: {exp}s remaining")

            pair_btn = Gtk.Button(label="Pair & Connect")
            pair_btn.add_css_class("suggested-action")
            pair_btn.connect("clicked", lambda b, m=mac, pt=port, t=token: self._pair_peer(m, pt, t, b))
            row.add_suffix(pair_btn)

            self.grp_discovered_peers.add(row)
            self._discovered_peer_rows.append(row)

    def _pair_peer(self, mac: str, port: int, token: str, btn: Gtk.Button):
        btn.set_sensitive(False)
        btn.set_label("Pairing...")

        bt = getattr(self.app_service, "bt_link", None)
        if not bt:
            btn.set_label("Error")
            return

        def on_result(success, reason):
            def update():
                if success:
                    btn.set_label("Paired!")
                    self.bt_peer_mac_row.set_text(mac)
                    self.bt_port_row.set_value(port)
                    self.bt_enabled_row.set_active(True)
                    self._save_all_settings()
                    self.app_service.config = self.config
                    self.app_service._setup_subsystems()
                    if getattr(self.app_service, "_running", False):
                        self.app_service.bt_link.start()
                else:
                    btn.set_label("Failed")
                    btn.set_sensitive(True)
                return False
            GLib.idle_add(update)

        def on_err(err):
            on_result(False, err)

        bt.request_pairing(mac, port=port, adv_token=token, on_error=on_err)

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

    def show_and_present(self):
        self.set_visible(True)
        self.present()

    def quit_application(self):
        self._is_quitting = True
        self._save_all_settings()
        if hasattr(self, "overlay"):
            self.overlay.close()
        if getattr(self.app_service, "_running", False):
            self.app_service.stop()
        remove_log_listener(self._on_log_message)
        app = self.get_application()
        if app:
            app.quit()
        else:
            self.destroy()

    def _on_close(self, *args):
        if getattr(self, "_is_quitting", False):
            return False

        self._save_all_settings()
        if hasattr(self, "overlay"):
            self.overlay.close()

        # If background service is running, keep it active and hide window into system tray
        if getattr(self.app_service, "_running", False):
            self.set_visible(False)
            log("GUI", "Main window closed: Lunifier service remains active in background with system tray icon.")
            return True  # Prevent window destruction

        remove_log_listener(self._on_log_message)
        return False


class LunifierAdwaitaApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.silviuk.Lunifier",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )

    def do_activate(self):
        win = self.get_active_window()
        if not win:
            windows = self.get_windows()
            if windows:
                win = windows[0]
            else:
                win = LunifierAdwaitaWindow(application=self)
        win.set_visible(True)
        win.present()
