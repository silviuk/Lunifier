"""
Main Coordinator Daemon for Lunifier Linux.
"""

import time
import threading
from typing import Optional

from .config import AppConfig
from .hidpp import HIDPPMaster
from .edge_detector import ScreenEdgeDetector
from .clipboard import CursorManager, ClipboardManager
from .bt_link import BluetoothLink
from .logger import log


class LunifierApp:
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig.load()
        self.hidpp = HIDPPMaster()
        self.cursor_mgr = CursorManager()
        self.bt_link: Optional[BluetoothLink] = None
        self.edge_detector: Optional[ScreenEdgeDetector] = None

        self._running = False
        self.hidpp.connection_support = getattr(self.config, 'connection_support', 'both')
        self._setup_subsystems()

    def _setup_subsystems(self) -> None:
        self.hidpp.connection_support = getattr(self.config, 'connection_support', 'both')

        if self.edge_detector and getattr(self.edge_detector, "_running", False):
            try:
                self.edge_detector.stop()
            except Exception:
                pass

        active_edges = self.config.get_active_edges()
        self.edge_detector = ScreenEdgeDetector(
            trigger_edge=self.config.trigger_edge,
            active_edges=active_edges,
            hold_delay_ms=self.config.hold_delay_ms,
            cooldown_ms=self.config.cooldown_ms,
            active_zone_pct=self.config.border_active_zone_pct,
            knock_enabled=self.config.knock_enabled,
            knock_timeout_ms=self.config.knock_timeout_ms,
            monitor_configs=self.config.monitor_configs,
            on_trigger_callback=self._handle_edge_triggered
        )

        if self.config.bt_p2p_enabled or self.config.bt_peer_address:
            self.bt_link = BluetoothLink(
                host_name=self.config.host_name,
                peer_mac=self.config.bt_peer_address,
                rfcomm_port=self.config.bt_rfcomm_port,
                on_switch_received=self._handle_incoming_switch,
                on_peer_status_changed=self._handle_peer_status_changed
            )

        threading.Thread(
            target=lambda: self.hidpp.scan_devices(self.config.devices, force_rescan=True, connection_support=self.config.connection_support),
            daemon=True
        ).start()

    def _handle_edge_triggered(self, edge: str, x: int, y: int, ratio: float, monitor_id: Optional[str] = None, target_channel: Optional[int] = None) -> None:
        if target_channel is None:
            if monitor_id is not None:
                target_channel = self.config.get_target_channel_for_monitor_edge(monitor_id, edge)
            if target_channel is None:
                target_channel = self.config.get_target_channel_for_edge(edge)

        if target_channel is None:
            return

        log("Lunifier", f">>> SCREEN BORDER REACHED: '{edge.upper()}' on Monitor {monitor_id or '0'} (Ratio: {ratio:.2f}) <<<")
        log("Lunifier", f"Switching devices to Channel {target_channel} (Backend: {self.config.switch_backend})...")

        t0 = time.perf_counter()
        results = self.hidpp.switch_all_to_channel(
            target_channel, self.config.devices,
            backend=self.config.switch_backend,
            connection_support=self.config.connection_support
        )
        elapsed_total = (time.perf_counter() - t0) * 1000.0

        for dev_name, success in results.items():
            log("Lunifier", f"Device '{dev_name}' -> Channel {target_channel}: {'SUCCESS' if success else 'FAILED'}")
        log("Lunifier", f"Hardware switch sequence completed in {elapsed_total:.1f}ms")

        if self.bt_link and self.bt_link.is_connected:
            def notify_peer():
                clipboard_content = ClipboardManager.get_text() if self.config.sync_clipboard else None
                self.bt_link.notify_switch_out(edge, ratio, clipboard_content)
            threading.Thread(target=notify_peer, daemon=True).start()

        step_back = 160
        new_x, new_y = x, y
        if edge == "right":
            new_x = x - step_back
        elif edge == "left":
            new_x = x + step_back
        elif edge == "top":
            new_y = y + step_back
        elif edge == "bottom":
            new_y = y - step_back

        self.cursor_mgr.set_cursor_pos(new_x, new_y)
        if self.edge_detector:
            self.edge_detector.notify_switched_out(edge, new_x, new_y)

    def _handle_incoming_switch(self, partner_exit_edge: str, ratio: float, clipboard_text: Optional[str]) -> None:
        log("Lunifier", f"<<< INCOMING TRANSFER from partner (Exit Edge: '{partner_exit_edge}', Ratio: {ratio:.2f}) <<<")

        if self.config.sync_clipboard and clipboard_text:
            ClipboardManager.set_text(clipboard_text)

        bounds = self.edge_detector._screen_bounds if self.edge_detector else {"left": 0, "top": 0, "right": 1920, "bottom": 1080}
        entry_edge = self.config.entry_edge
        if not entry_edge:
            opposites = {"right": "left", "left": "right", "top": "bottom", "bottom": "top"}
            entry_edge = opposites.get(partner_exit_edge, "left")

        self.cursor_mgr.position_cursor_at_entry(entry_edge, ratio, bounds)
        if self.edge_detector:
            self.edge_detector.notify_switched_in(entry_edge)

    def _handle_peer_status_changed(self, connected: bool) -> None:
        log("Lunifier", f"Partner host Bluetooth link: {'CONNECTED' if connected else 'DISCONNECTED'}")

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        if self.edge_detector:
            self.edge_detector.start()
        if self.bt_link:
            self.bt_link.start()

        log("Lunifier", "==================================================")
        log("Lunifier", " Lunifier Linux Daemon Running")
        log("Lunifier", f" Host: {self.config.host_name} (Channel {self.config.my_channel})")
        log("Lunifier", f" Active Border Zone: Central {self.config.border_active_zone_pct}%")
        log("Lunifier", f" Knock Mode: {'ENABLED' if self.config.knock_enabled else 'DISABLED'}")
        log("Lunifier", "==================================================")

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self.edge_detector:
            self.edge_detector.stop()
        if self.bt_link:
            self.bt_link.stop()
        log("Lunifier", "Lunifier Daemon stopped.")
