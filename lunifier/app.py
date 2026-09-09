"""
Main Coordinator Application for Lunifier.
Integrates Edge Detection, Logitech HID++ Switching, Bluetooth Inter-Host Link, and Cursor Repositioning.
"""

import os
import sys
import time
import signal
import argparse
from typing import Optional

from .config import AppConfig, DEFAULT_CONFIG_PATH
from .hidpp import HIDPPMaster
from .edge_detector import ScreenEdgeDetector
from .cursor_manager import CursorManager
from .clipboard import ClipboardManager
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

        # 1. Edge detector (monitors all active configured screen borders)
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

        # 2. Bluetooth P2P Link (optional inter-host sync)
        if self.config.bt_p2p_enabled or self.config.bt_peer_address:
            self.bt_link = BluetoothLink(
                host_name=self.config.host_name,
                peer_mac=self.config.bt_peer_address,
                rfcomm_port=self.config.bt_rfcomm_port,
                on_switch_received=self._handle_incoming_switch,
                on_peer_status_changed=self._handle_peer_status_changed
            )

        # Warm up device cache in background so switches execute with 0ms scan delay
        import threading
        threading.Thread(target=lambda: self.hidpp.scan_devices(self.config.devices, force_rescan=True, connection_support=self.config.connection_support), daemon=True).start()

    def _handle_edge_triggered(self, edge: str, x: int, y: int, ratio: float, monitor_id: Optional[str] = None, target_channel: Optional[int] = None) -> None:
        """
        Called when cursor dwells at a configured screen border.
        Executes hardware switch instantly with zero blocking to that edge's target channel.
        """
        if target_channel is None:
            if monitor_id is not None:
                target_channel = self.config.get_target_channel_for_monitor_edge(monitor_id, edge)
            if target_channel is None:
                target_channel = self.config.get_target_channel_for_edge(edge)

        if target_channel is None:
            log("Lunifier", f"No target channel configured for edge '{edge}' on monitor {monitor_id or '0'}.")
            return

        log("Lunifier", f">>> SCREEN BORDER REACHED: '{edge.upper()}' at ({x}, {y}) (Ratio: {ratio:.2f}) <<<")
        log("Lunifier", f"Instantly switching MX Keys & mouse to Channel {target_channel} (Backend: {self.config.switch_backend}, Support: {self.config.connection_support})...")

        # 1. Fire hardware switch immediately in parallel
        t0 = time.perf_counter()
        results = self.hidpp.switch_all_to_channel(target_channel, self.config.devices, backend=self.config.switch_backend, connection_support=self.config.connection_support)
        elapsed_total = (time.perf_counter() - t0) * 1000.0
        for dev_name, success in results.items():
            status = "SUCCESS" if success else "FAILED"
            log("Lunifier", f"Device '{dev_name}' -> Channel {target_channel}: {status}")
        log("Lunifier", f"Hardware switch sequence completed in {elapsed_total:.1f}ms")

        # 2. Async notify partner host over Bluetooth link (non-blocking)
        if self.bt_link and self.bt_link.is_connected:
            def notify_peer():
                clipboard_content = None
                if self.config.sync_clipboard:
                    clipboard_content = ClipboardManager.get_text()
                self.bt_link.notify_switch_out(edge, ratio, clipboard_content)
            import threading
            threading.Thread(target=notify_peer, daemon=True).start()

        # 3. Pull cursor inward from boundary to prevent ghost re-triggers while working on partner host
        step_back = 80
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
        log("Lunifier", f"Repositioned cursor {step_back}px inward to ({new_x}, {new_y}) to prevent border bounceback")

    def _handle_incoming_switch(self, partner_exit_edge: str, ratio: float, clipboard_text: Optional[str]) -> None:
        """
        Called when partner host notifies that the mouse is switching into this screen.
        """
        log("Lunifier", f"<<< INCOMING TRANSFER from partner (Exit Edge: '{partner_exit_edge}', Ratio: {ratio:.2f}) <<<")

        # 1. Sync clipboard if text received
        if self.config.sync_clipboard and clipboard_text:
            ok = ClipboardManager.set_text(clipboard_text)
            log("Lunifier", f"Updated local clipboard from partner: {'OK' if ok else 'FAILED'}")

        # 2. Position cursor at entry edge
        bounds = self.edge_detector._screen_bounds if self.edge_detector else {"left": 0, "top": 0, "right": 1920, "bottom": 1080}
        entry_edge = self.config.entry_edge
        if not entry_edge:
            # Opposite of partner's exit edge
            opposites = {"right": "left", "left": "right", "top": "bottom", "bottom": "top"}
            entry_edge = opposites.get(partner_exit_edge, "left")

        self.cursor_mgr.position_cursor_at_entry(entry_edge, ratio, bounds)

    def _handle_peer_status_changed(self, connected: bool) -> None:
        status = "CONNECTED" if connected else "DISCONNECTED"
        log("Lunifier", f"Partner host Bluetooth link: {status}")

    def scan_devices(self) -> None:
        log("Lunifier", "=== Scanning for Logitech Devices (VID 0x046D) ===")
        devs = self.hidpp.scan_devices(self.config.devices, force_rescan=True)
        if not devs:
            log("Lunifier", "No matching Logitech Easy-Switch devices found.")
            log("Lunifier", "Make sure MX Keys and mouse are connected via Bluetooth or Bolt/Unifying receiver.")
        else:
            log("Lunifier", f"Found {len(devs)} supported device(s):")
            for i, d in enumerate(devs, 1):
                conn_type = d.transport.value
                feat = f"0x{d.change_host_feature_index:02x}" if d.change_host_feature_index else "Auto-detect"
                log("Lunifier", f" [{i}] {d.name} | Protocol: {conn_type} (Device Index: 0x{d.device_index:02x}) | Feature 0x1814: {feat}")
        log("Lunifier", "===================================================")

    def switch_now(self, target_channel: int) -> None:
        log("Lunifier", f"Manually switching all devices to Channel {target_channel} (Backend: {self.config.switch_backend})...")
        t0 = time.perf_counter()
        results = self.hidpp.switch_all_to_channel(target_channel, self.config.devices, backend=self.config.switch_backend)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        for dev_name, success in results.items():
            status = "SUCCESS" if success else "FAILED"
            log("Lunifier", f" - {dev_name}: {status}")
        log("Lunifier", f"Manual switch completed in {elapsed_ms:.1f}ms")

    def run(self) -> None:
        self._running = True

        # Handle termination signals
        def sig_handler(signum, frame):
            log("Lunifier", "Termination signal received. Stopping...")
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, sig_handler)
            signal.signal(signal.SIGTERM, sig_handler)
        except Exception:
            pass

        zone_info = f"Central {self.config.border_active_zone_pct}%" if self.config.border_active_zone_pct < 100 else "Full (100%)"
        log("Lunifier", "==================================================")
        log("Lunifier", " Lunifier Daemon Running")
        log("Lunifier", f" Host: {self.config.host_name} (Channel {self.config.my_channel})")
        log("Lunifier", f" Target Host Channel: {self.config.target_channel}")
        log("Lunifier", f" Trigger Edge: '{self.config.trigger_edge.upper()}' (Hold: {self.config.hold_delay_ms}ms)")
        log("Lunifier", f" Target Devices: {', '.join(self.config.devices)}")
        log("Lunifier", f" Active Border Zone: {zone_info}")
        if self.config.knock_enabled:
            log("Lunifier", f" Border Knock Mode: Double-touch required ({self.config.knock_timeout_ms}ms window)")
        log("Lunifier", f" Switching Backend: {self.config.switch_backend.upper()}")
        if self.config.bt_peer_address:
            log("Lunifier", f" Inter-Host BT Peer: {self.config.bt_peer_address}")
        else:
            log("Lunifier", " Inter-Host Mode: Autonomous Hardware Edge Switch")
        log("Lunifier", "==================================================")

        # Start edge detector
        if self.edge_detector:
            self.edge_detector.start()

        # Start Bluetooth link if configured
        if self.bt_link:
            self.bt_link.start()

        # Keep main thread alive
        try:
            while self._running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        self._running = False
        if self.edge_detector:
            self.edge_detector.stop()
        if self.bt_link:
            self.bt_link.stop()
        print("[Lunifier] Shutdown complete.")


# Backward compatibility alias
LogiFlowBTApp = LunifierApp


def interactive_configure(config: AppConfig, path: Optional[str] = None) -> None:
    """
    Terminal-based setup for headless or non-GUI environments.
    """
    cfg_file = path or DEFAULT_CONFIG_PATH
    print("\n=== Lunifier Terminal Configuration ===")
    print(f"Config File: {cfg_file}\n")

    # Current channel
    prompt = f"This computer's Easy-Switch channel [1, 2, or 3] (current: {config.my_channel}): "
    val = input(prompt).strip()
    if val in ("1", "2", "3"):
        config.my_channel = int(val)

    # Multi-border edge channel configuration
    print("\nConfigure target Easy-Switch channel when cursor hits screen borders:")
    print("(Enter 1, 2, 3 or 'none'/'0' to disable border trigger)")

    # Left border
    left_cur = config.edge_channels.get("left")
    left_str = str(left_cur) if left_cur is not None else "Disabled"
    prompt = f"Left Border Target Channel (current: {left_str}): "
    val = input(prompt).strip().lower()
    if val in ("1", "2", "3"):
        config.edge_channels["left"] = int(val)
    elif val in ("none", "0", "disable", "disabled"):
        config.edge_channels["left"] = None

    # Right border
    right_cur = config.edge_channels.get("right")
    right_str = str(right_cur) if right_cur is not None else "Disabled"
    prompt = f"Right Border Target Channel (current: {right_str}): "
    val = input(prompt).strip().lower()
    if val in ("1", "2", "3"):
        config.edge_channels["right"] = int(val)
        config.target_channel = int(val)
    elif val in ("none", "0", "disable", "disabled"):
        config.edge_channels["right"] = None

    # Top border
    top_cur = config.edge_channels.get("top")
    top_str = str(top_cur) if top_cur is not None else "Disabled"
    prompt = f"Top Border Target Channel (current: {top_str}): "
    val = input(prompt).strip().lower()
    if val in ("1", "2", "3"):
        config.edge_channels["top"] = int(val)
    elif val in ("none", "0", "disable", "disabled"):
        config.edge_channels["top"] = None

    # Bottom border
    bot_cur = config.edge_channels.get("bottom")
    bot_str = str(bot_cur) if bot_cur is not None else "Disabled"
    prompt = f"Bottom Border Target Channel (current: {bot_str}): "
    val = input(prompt).strip().lower()
    if val in ("1", "2", "3"):
        config.edge_channels["bottom"] = int(val)
    elif val in ("none", "0", "disable", "disabled"):
        config.edge_channels["bottom"] = None

    active_edges = config.get_active_edges()
    if active_edges:
        config.trigger_edge = active_edges[0]
        config.target_channel = config.get_target_channel_for_edge(active_edges[0]) or 2

    # Hold delay
    prompt = f"Hold dwell delay in ms [e.g. 250] (current: {config.hold_delay_ms}): "
    val = input(prompt).strip()
    if val.isdigit() and int(val) >= 50:
        config.hold_delay_ms = int(val)

    # Active central zone percentage
    prompt = f"Central active zone percentage along border [10-100] (current: {config.border_active_zone_pct}%): "
    val = input(prompt).strip()
    if val.isdigit() and 10 <= int(val) <= 100:
        config.border_active_zone_pct = int(val)

    # Border knock activation
    prompt = f"Enable double-touch border knock to switch? [y/N] (current: {'y' if config.knock_enabled else 'n'}): "
    val = input(prompt).strip().lower()
    if val in ("y", "yes", "true", "1"):
        config.knock_enabled = True
        prompt_k = f"Knock time window in ms [e.g. 1000] (current: {config.knock_timeout_ms}): "
        val_k = input(prompt_k).strip()
        if val_k.isdigit() and int(val_k) >= 200:
            config.knock_timeout_ms = int(val_k)
    elif val in ("n", "no", "false", "0"):
        config.knock_enabled = False

    # Switching backend selection on Linux
    prompt = f"Switching backend on Linux [auto, solaar, direct] (current: {config.switch_backend}): "
    val_b = input(prompt).strip().lower()
    if val_b in ("auto", "solaar", "direct"):
        config.switch_backend = val_b

    config.save(cfg_file)
    print(f"\n[OK] Configuration successfully saved to {cfg_file}")
    print("You can now start the background service with:")
    print("  lunifier --daemon\n")


def main():
    parser = argparse.ArgumentParser(description="Lunifier - Seamless cross-platform Logitech Easy-Switch Flow")
    parser.add_argument("--scan", action="store_true", help="Scan and list connected Logitech devices")
    parser.add_argument("--switch", type=int, choices=[1, 2, 3], help="Immediately switch devices to Channel 1, 2, or 3")
    parser.add_argument("--backend", type=str, choices=["auto", "solaar", "direct"], help="Select switching backend (auto, solaar, direct)")
    parser.add_argument("--daemon", action="store_true", help="Run in background daemon mode")
    parser.add_argument("--gui", action="store_true", help="Launch the GUI settings and status window")
    parser.add_argument("--setup", "--configure", dest="setup", action="store_true", help="Interactive terminal configuration")
    parser.add_argument("--config", type=str, help="Path to custom config.json file")

    args = parser.parse_args()
    config = AppConfig.load(args.config)
    if args.backend:
        config.switch_backend = args.backend
    app = LunifierApp(config)

    if args.scan:
        app.scan_devices()
    elif args.switch is not None:
        app.switch_now(args.switch)
    elif args.setup:
        interactive_configure(config, args.config)
    elif args.daemon:
        app.run()
    elif args.gui or len(sys.argv) == 1:
        try:
            from .gui import launch_gui
            launch_gui(app)
        except (ImportError, ModuleNotFoundError) as e:
            print("\n" + "=" * 60)
            print("[Lunifier] GUI Error: Missing GUI dependencies.")
            print(f"Details: {e}")
            print("=" * 60)
            print("\nThe Lunifier GUI requires 'tkinter' and 'customtkinter'.")
            print("To install on Linux:")
            print("  sudo apt install -y python3-tk")
            print("  pip3 install --user customtkinter   # or: pip3 install --break-system-packages customtkinter")
            print("=" * 60)
            print("\nTIP: You can also configure everything directly in terminal without GUI:")
            print("  lunifier --setup")
            print("=" * 60 + "\n")
            sys.exit(1)
    else:
        app.run()


if __name__ == "__main__":
    main()
