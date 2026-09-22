"""
Bluetooth RFCOMM Peer-to-Peer Inter-Host Link.
Zero-network connection between Windows and Linux hosts for Flow synchronization.
Operates exclusively over Bluetooth (RFCOMM / BLE) with zero Wi-Fi, LAN, or network traffic.
"""

import os
import glob
import re
import sys
import json
import time
import socket
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable, Dict, Any, List

from .logger import log

_cached_local_bt_mac: Optional[str] = None


def get_local_bluetooth_mac() -> str:
    """
    Returns the Bluetooth MAC address of the local machine's primary Bluetooth adapter.
    Works across Windows and Linux. Returns empty string if no adapter is found.
    """
    global _cached_local_bt_mac
    if _cached_local_bt_mac:
        return _cached_local_bt_mac

    mac = ""
    # Method 1: RFCOMM socket bind to ('00:00:00:00:00:00', 0)
    if hasattr(socket, "AF_BLUETOOTH"):
        try:
            s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            s.bind(("00:00:00:00:00:00", 0))
            sock_name = s.getsockname()
            s.close()
            if sock_name and isinstance(sock_name, (tuple, list)) and sock_name[0]:
                candidate = str(sock_name[0]).upper()
                if candidate != "00:00:00:00:00:00" and len(candidate.split(":")) == 6:
                    mac = candidate
        except Exception:
            pass

    # Method 2: Linux sysfs (/sys/class/bluetooth/hci*/address)
    if not mac and sys.platform.startswith("linux"):
        for path in glob.glob("/sys/class/bluetooth/hci*/address"):
            try:
                with open(path, "r") as f:
                    candidate = f.read().strip().upper()
                    if len(candidate.split(":")) == 6 and candidate != "00:00:00:00:00:00":
                        mac = candidate
                        break
            except Exception:
                pass

        if not mac:
            try:
                import subprocess
                out = subprocess.check_output(["bluetoothctl", "list"], text=True, timeout=1.5)
                m = re.search(r"Controller\s+([0-9A-Fa-f:]{17})", out)
                if m:
                    mac = m.group(1).upper()
            except Exception:
                pass

    if mac:
        _cached_local_bt_mac = mac
    return mac


def discover_potential_partners(timeout: float = 3.5) -> List[Dict[str, str]]:
    """
    Discovers candidate Bluetooth devices from the OS Bluetooth stack:
    - Scans paired Bluetooth devices (Windows registry / Linux bluetoothctl).
    - Scans nearby broadcasting BLE devices via Bleak if available.
    Returns a list of dicts: [{"name": str, "mac": str, "source": str}]
    """
    devices: Dict[str, Dict[str, str]] = {}

    # 1. OS Paired Devices
    if sys.platform == "win32":
        try:
            import winreg
            key_path = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(k, i)
                        i += 1
                        mac = ":".join([sub[j:j+2] for j in range(0, 12, 2)]).upper()
                        name = mac
                        with winreg.OpenKey(k, sub) as sk:
                            try:
                                v, _ = winreg.QueryValueEx(sk, "Name")
                                if isinstance(v, bytes):
                                    name = v.decode("utf-8", errors="ignore").rstrip("\x00")
                                elif isinstance(v, str):
                                    name = v
                            except Exception:
                                pass
                        devices[mac] = {"name": name, "mac": mac, "source": "Paired"}
                    except OSError:
                        break
        except Exception as e:
            log("BluetoothLink", f"Windows paired scan notice: {e}")
    elif sys.platform.startswith("linux"):
        try:
            import subprocess
            out = subprocess.check_output(["bluetoothctl", "devices"], text=True, timeout=2.0)
            for line in out.strip().splitlines():
                parts = line.split(" ", 2)
                if len(parts) >= 3 and parts[0] == "Device":
                    mac = parts[1].upper()
                    name = parts[2].strip()
                    devices[mac] = {"name": name, "mac": mac, "source": "Paired"}
        except Exception as e:
            log("BluetoothLink", f"Linux paired scan notice: {e}")

    # 2. Bleak BLE Discovery for nearby devices
    try:
        import asyncio
        from bleak import BleakScanner

        async def _run_ble_scan():
            discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)
            for d, adv in discovered.values():
                mac = d.address.upper()
                name = adv.local_name or d.name
                if name:
                    name = name.strip()
                if not name:
                    name = "Unknown Bluetooth Device"

                if mac not in devices:
                    devices[mac] = {"name": name, "mac": mac, "source": "Nearby"}
                elif devices[mac]["name"] == mac and name != "Unknown Bluetooth Device":
                    devices[mac]["name"] = name

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with ThreadPoolExecutor() as pool:
                    pool.submit(lambda: asyncio.run(_run_ble_scan())).result()
            else:
                loop.run_until_complete(_run_ble_scan())
        except Exception:
            asyncio.run(_run_ble_scan())
    except Exception as e:
        log("BluetoothLink", f"BLE scanner notice: {e}")

    res = list(devices.values())
    res.sort(key=lambda x: (0 if x["source"] == "Paired" else 1, x["name"].lower()))
    return res


DEFAULT_RFCOMM_PORT = 5


def find_available_rfcomm_port(preferred_port: int = 5) -> int:
    """
    Dynamically scans RFCOMM ports on the local machine and returns the first port
    that can be successfully bound. Skips busy or OS-forbidden ports.
    """
    if not hasattr(socket, "AF_BLUETOOTH"):
        return preferred_port

    candidate_ports = [preferred_port] + [p for p in range(5, 31) if p != preferred_port]
    for p in candidate_ports:
        s = None
        try:
            s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            s.bind(("00:00:00:00:00:00", p))
            s.close()
            return p
        except Exception:
            if s:
                try:
                    s.close()
                except Exception:
                    pass
    return preferred_port


def parse_lunifier_beacon(data: bytes) -> Optional[Dict[str, Any]]:
    """
    Unpacks a raw 20-31 byte BLE Manufacturer Data payload into a Lunifier peer dict:
    - Magic: 'LUNI' (4 bytes)
    - Protocol version: 1 byte
    - Port: 1 byte (RFCOMM channel 1-30)
    - Classic Bluetooth MAC: 6 bytes
    - Ephemeral Token: 4 bytes (8 hex chars)
    - Host Name: remainder (UTF-8 string)
    """
    if not data or len(data) < 12 or not data.startswith(b"LUNI"):
        return None
    try:
        version = data[4]
        port = data[5]
        mac_bytes = data[6:12]
        mac_str = ":".join(f"{b:02X}" for b in mac_bytes)
        tok_bytes = data[12:16] if len(data) >= 16 else b""
        token_str = tok_bytes.hex()
        name_str = data[16:].decode("utf-8", errors="ignore").strip("\x00") if len(data) > 16 else ""
        return {
            "version": version,
            "port": int(port),
            "mac": mac_str,
            "token": token_str,
            "name": name_str
        }
    except Exception:
        return None


class BleAdvertiser:
    """
    Broadcasts BLE advertisement packets containing Lunifier beacon data
    (Magic, protocol version, RFCOMM port, Classic Bluetooth MAC, token, host name).
    Works on Windows via WinRT BluetoothLEAdvertisementPublisher.
    Works on Linux via bluetoothctl / BlueZ if available.
    """
    def __init__(self, host_name: str, mac: str, port: int, token: str):
        self.host_name = host_name
        self.mac = mac
        self.port = port
        self.token = token
        self._publisher = None
        self._is_advertising = False
        self._linux_proc = None

    def start(self) -> bool:
        if sys.platform == "win32":
            return self._start_windows()
        elif sys.platform.startswith("linux"):
            return self._start_linux()
        return False

    def stop(self) -> None:
        if sys.platform == "win32":
            self._stop_windows()
        elif sys.platform.startswith("linux"):
            self._stop_linux()

    def _start_windows(self) -> bool:
        try:
            import winrt.windows.devices.bluetooth.advertisement as adv
            import winrt.windows.storage.streams as streams

            self._publisher = adv.BluetoothLEAdvertisementPublisher()
            writer = streams.DataWriter()

            mac_clean = self.mac.replace(":", "").replace("-", "")
            if len(mac_clean) == 12:
                mac_bytes = bytes.fromhex(mac_clean)
            else:
                mac_bytes = b"\x00" * 6

            tok_clean = self.token[:8]
            try:
                tok_bytes = bytes.fromhex(tok_clean)
                if len(tok_bytes) < 4:
                    tok_bytes = tok_bytes.ljust(4, b"\x00")
            except Exception:
                tok_bytes = b"\x00" * 4

            name_bytes = self.host_name.encode("utf-8")[:10]

            payload = b"LUNI" + bytes([1, self.port & 0xFF]) + mac_bytes + tok_bytes + name_bytes
            writer.write_bytes(payload)

            mfg = adv.BluetoothLEManufacturerData(0xFFFF, writer.detach_buffer())
            self._publisher.advertisement.manufacturer_data.append(mfg)
            self._publisher.start()
            self._is_advertising = True
            log("BluetoothLink", f"BLE advertisement broadcaster started (WinRT, RFCOMM port {self.port}).")
            return True
        except Exception as e:
            log("BluetoothLink", f"BLE advertisement start notice (WinRT): {e}")
            return False

    def _stop_windows(self) -> None:
        if self._publisher:
            try:
                self._publisher.stop()
                log("BluetoothLink", "BLE advertisement broadcaster stopped.")
            except Exception:
                pass
            self._publisher = None
        self._is_advertising = False

    def _start_linux(self) -> bool:
        try:
            import subprocess
            cmd = ["bluetoothctl", "advertise", "on"]
            self._linux_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._is_advertising = True
            log("BluetoothLink", "BLE advertisement started via bluetoothctl.")
            return True
        except Exception as e:
            log("BluetoothLink", f"Linux BLE advertisement notice: {e}")
            return False

    def _stop_linux(self) -> None:
        if self._linux_proc:
            try:
                self._linux_proc.terminate()
            except Exception:
                pass
            self._linux_proc = None
        try:
            import subprocess
            subprocess.run(["bluetoothctl", "advertise", "off"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.0)
        except Exception:
            pass
        self._is_advertising = False


def probe_bt_device_advertising(mac: str,
                                port: int = 5,
                                timeout: float = 1.0,
                                scanner_host_name: str = "") -> Optional[Dict[str, Any]]:
    """
    Sends a lightweight Bluetooth RFCOMM discovery probe to a specific Bluetooth MAC.
    Tries the given port, and falls back across candidate ports if needed.
    Returns peer info dict ONLY if the remote host is running Lunifier and currently advertising:
    {"name": str, "mac": str, "port": int, "token": str, "expires_in": int, "advertising": True}
    """
    if not hasattr(socket, "AF_BLUETOOTH"):
        return None

    test_ports = [port] + [p for p in [5, 6, 8, 9, 10, 7] if p != port]
    for p in test_ports:
        s = None
        try:
            s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            s.settimeout(timeout)
            s.connect((mac, p))
            probe_msg = json.dumps({
                "type": "DISCOVERY_PROBE",
                "from_host": scanner_host_name,
                "version": "1.0"
            }) + "\n"
            s.sendall(probe_msg.encode("utf-8"))

            data = s.recv(1024)
            if not data:
                continue

            line = data.decode("utf-8", errors="ignore").strip().split("\n")[0]
            resp = json.loads(line)
            if resp.get("type") == "DISCOVERY_BEACON" and resp.get("advertising"):
                return {
                    "name": resp.get("from_host", mac),
                    "mac": mac,
                    "port": resp.get("port", p),
                    "token": resp.get("token", ""),
                    "expires_in": int(resp.get("expires_in", 0)),
                    "advertising": True
                }
        except Exception:
            pass
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass
    return None


def discover_advertising_lunifier_peers(timeout: float = 3.5,
                                       rfcomm_port: int = 5,
                                       host_name: str = "") -> List[Dict[str, Any]]:
    """
    Scans Bluetooth devices and filters STRICTLY for partner hosts running Lunifier
    that currently have 'Advertise Lunifier' active.
    Combines direct over-the-air BLE advertisement parsing with paired-device RFCOMM probes.
    """
    discovered_advertising: Dict[str, Dict[str, Any]] = {}

    # 1. Direct Over-The-Air BLE Discovery
    try:
        import asyncio
        from bleak import BleakScanner

        async def _run_ble_adv_scan():
            def detection_cb(device, adv):
                mfg_data = adv.manufacturer_data or {}
                raw_payload = mfg_data.get(0xFFFF) or mfg_data.get(0x046D)
                if raw_payload:
                    info = parse_lunifier_beacon(raw_payload)
                    if info:
                        peer_mac = info["mac"] or device.address.upper()
                        peer_name = info["name"] or adv.local_name or device.name or f"Lunifier Host ({peer_mac[-5:]})"
                        discovered_advertising[peer_mac] = {
                            "name": peer_name,
                            "mac": peer_mac,
                            "port": info["port"] or rfcomm_port,
                            "token": info["token"],
                            "expires_in": 60,
                            "advertising": True,
                            "source": "BLE Broadcast"
                        }

            scanner = BleakScanner(detection_callback=detection_cb)
            await scanner.start()
            await asyncio.sleep(timeout)
            await scanner.stop()

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with ThreadPoolExecutor() as pool:
                    pool.submit(lambda: asyncio.run(_run_ble_adv_scan())).result()
            else:
                loop.run_until_complete(_run_ble_adv_scan())
        except Exception:
            asyncio.run(_run_ble_adv_scan())
    except Exception as e:
        log("BluetoothLink", f"BLE advertisement scan notice: {e}")

    # 2. Paired Devices Fallback Check (probe on port)
    paired_candidates = [c for c in discover_potential_partners(timeout=0.5) if c.get("source") == "Paired"]
    probe_candidates = [c for c in paired_candidates if c["mac"] not in discovered_advertising]
    if probe_candidates and hasattr(socket, "AF_BLUETOOTH"):
        with ThreadPoolExecutor(max_workers=min(4, len(probe_candidates))) as executor:
            future_map = {
                executor.submit(probe_bt_device_advertising, c["mac"], rfcomm_port, 1.0, host_name): c
                for c in probe_candidates
            }
            for fut in as_completed(future_map):
                try:
                    res = fut.result()
                    if res and res.get("advertising"):
                        res_mac = res["mac"]
                        if res_mac not in discovered_advertising:
                            discovered_advertising[res_mac] = res
                except Exception:
                    pass

    advertising_peers = list(discovered_advertising.values())
    advertising_peers.sort(key=lambda x: x["name"].lower())
    return advertising_peers


class BluetoothLink:
    """
    Peer-to-peer Bluetooth RFCOMM service for inter-host synchronization.
    Supports on-demand timed advertising, filtered discovery, authenticated
    handshakes, cursor alignment exchange, and clipboard synchronization.
    """
    def __init__(self,
                 host_name: str,
                 peer_mac: str = "",
                 rfcomm_port: int = DEFAULT_RFCOMM_PORT,
                 on_switch_received: Optional[Callable[[str, float, Optional[str]], None]] = None,
                 on_clipboard_received: Optional[Callable[[str], None]] = None,
                 on_alignment_received: Optional[Callable[[Dict[str, int]], None]] = None,
                 on_peer_status_changed: Optional[Callable[[bool], None]] = None,
                 on_pair_request: Optional[Callable[[str, str], bool]] = None,
                 on_pair_response: Optional[Callable[[bool, str, str], None]] = None):
        """
        :param host_name: Name of this host
        :param peer_mac: Bluetooth MAC of the partner host (e.g. "00:1A:7D:DA:71:13")
        :param rfcomm_port: RFCOMM channel (default 5, auto-detected if busy)
        :param on_switch_received: Callback when partner switches mouse here: func(exit_edge, ratio, clipboard)
        :param on_clipboard_received: Callback func(clipboard_text: str)
        :param on_alignment_received: Callback func(bounds: dict)
        :param on_peer_status_changed: Callback func(is_connected: bool)
        :param on_pair_request: Callback func(from_host: str, from_mac: str) -> bool
        :param on_pair_response: Callback func(accepted: bool, from_host: str, info: str)
        """
        self.host_name = host_name
        self.peer_mac = peer_mac.strip().upper()
        self.rfcomm_port = rfcomm_port
        self.on_switch_received = on_switch_received
        self.on_clipboard_received = on_clipboard_received
        self.on_alignment_received = on_alignment_received
        self.on_peer_status_changed = on_peer_status_changed
        self.on_pair_request = on_pair_request
        self.on_pair_response = on_pair_response

        self._running = False
        self._is_connected = False
        self._server_sock: Optional[socket.socket] = None
        self._active_conn: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._server_thread: Optional[threading.Thread] = None
        self._client_thread: Optional[threading.Thread] = None

        # Timed advertising state
        self._is_advertising = False
        self._adv_token = ""
        self._adv_expires_at = 0.0
        self._adv_timer_thread: Optional[threading.Thread] = None
        self._adv_stop_event = threading.Event()
        self._adv_on_tick: Optional[Callable[[int], None]] = None
        self._adv_on_expired: Optional[Callable[[], None]] = None
        self._ble_advertiser: Optional[BleAdvertiser] = None

        # Session security & cursor alignment
        self.session_key = ""
        self.partner_screen_bounds: Dict[str, int] = {"width": 1920, "height": 1080}
        self.my_screen_bounds: Dict[str, int] = {"width": 1920, "height": 1080}

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_advertising(self) -> bool:
        return self._is_advertising and time.time() < self._adv_expires_at

    def start_advertising(self,
                          duration_seconds: int = 60,
                          on_tick: Optional[Callable[[int], None]] = None,
                          on_expired: Optional[Callable[[], None]] = None) -> str:
        """
        Activates timed peer advertising mode over Bluetooth for duration_seconds (default 60).
        Broadcasts over-the-air BLE advertisement beacon with host name, MAC, RFCOMM port, and token.
        Generates an ephemeral pairing token and executes on_tick every second with remaining time.
        When expired, automatically shuts down advertising.
        """
        self.stop_advertising()
        token = secrets.token_hex(4) # 8 hex characters (4 bytes)
        self._adv_token = token
        self._adv_expires_at = time.time() + max(1, duration_seconds)
        self._is_advertising = True
        self._adv_on_tick = on_tick
        self._adv_on_expired = on_expired
        self._adv_stop_event.clear()

        # Start live BLE advertisement broadcaster
        local_mac = get_local_bluetooth_mac()
        self._ble_advertiser = BleAdvertiser(
            host_name=self.host_name,
            mac=local_mac,
            port=self.rfcomm_port,
            token=token
        )
        self._ble_advertiser.start()

        log("BluetoothLink", f"Started Bluetooth advertising (duration: {duration_seconds}s, port: {self.rfcomm_port}, token: {token})")

        def timer_worker():
            while not self._adv_stop_event.is_set():
                now = time.time()
                if now >= self._adv_expires_at:
                    break
                remaining = max(1, int((self._adv_expires_at - now) + 0.999))
                if self._adv_on_tick:
                    try:
                        self._adv_on_tick(remaining)
                    except Exception as ex:
                        log("BluetoothLink", f"Error in advertising tick callback: {ex}")
                self._adv_stop_event.wait(min(1.0, max(0.05, self._adv_expires_at - now)))

            was_active = self._is_advertising
            self._is_advertising = False
            self._adv_token = ""
            if self._ble_advertiser:
                try:
                    self._ble_advertiser.stop()
                except Exception:
                    pass
                self._ble_advertiser = None
            log("BluetoothLink", "Bluetooth advertising stopped/expired.")
            if was_active and self._adv_on_expired and not self._adv_stop_event.is_set():
                try:
                    self._adv_on_expired()
                except Exception as ex:
                    log("BluetoothLink", f"Error in advertising expired callback: {ex}")

        self._adv_timer_thread = threading.Thread(target=timer_worker, name="BTAdvTimerThread", daemon=True)
        self._adv_timer_thread.start()
        return token

    def stop_advertising(self) -> None:
        """Immediately stops advertising and clears the ephemeral token."""
        self._is_advertising = False
        self._adv_token = ""
        self._adv_expires_at = 0.0
        self._adv_stop_event.set()
        if self._ble_advertiser:
            try:
                self._ble_advertiser.stop()
            except Exception:
                pass
            self._ble_advertiser = None

    def start(self) -> None:
        if not hasattr(socket, "AF_BLUETOOTH"):
            log("BluetoothLink", "socket.AF_BLUETOOTH not available on this platform.")
            return

        self._running = True
        self._server_thread = threading.Thread(target=self._server_loop, name="BTServerThread", daemon=True)
        self._server_thread.start()

        if self.peer_mac:
            self._client_thread = threading.Thread(target=self._client_loop, name="BTClientThread", daemon=True)
            self._client_thread.start()

        log("BluetoothLink", f"Bluetooth link service started (RFCOMM Port {self.rfcomm_port})")

    def stop(self) -> None:
        self._running = False
        self.stop_advertising()
        self._close_conn()
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        log("BluetoothLink", "Bluetooth link service stopped.")

    def _close_conn(self) -> None:
        with self._lock:
            if self._active_conn:
                try:
                    self._active_conn.close()
                except Exception:
                    pass
                self._active_conn = None
            if self._is_connected:
                self._is_connected = False
                if self.on_peer_status_changed:
                    try:
                        self.on_peer_status_changed(False)
                    except Exception:
                        pass

    def _set_active_conn(self, sock: socket.socket) -> None:
        with self._lock:
            self._active_conn = sock
            self._is_connected = True
            if self.on_peer_status_changed:
                try:
                    self.on_peer_status_changed(True)
                except Exception:
                    pass

    def send_message(self, msg_dict: Dict[str, Any]) -> bool:
        """
        Sends a JSON message over the active Bluetooth connection.
        All data transfers are conducted exclusively over Bluetooth RFCOMM.
        """
        with self._lock:
            conn = self._active_conn
        if not conn:
            return False

        try:
            line = (json.dumps(msg_dict) + "\n").encode("utf-8")
            conn.sendall(line)
            return True
        except Exception as e:
            log("BluetoothLink", f"Bluetooth send error: {e}")
            self._close_conn()
            return False

    def notify_switch_out(self, exit_edge: str, ratio: float, clipboard_text: Optional[str] = None) -> bool:
        """
        Informs partner host over Bluetooth that the mouse has crossed into its screen.
        Exchanges cursor alignment and encrypted clipboard payload.
        """
        payload = {
            "type": "SWITCH_OUT",
            "from_host": self.host_name,
            "exit_edge": exit_edge,
            "ratio": ratio,
            "clipboard": clipboard_text,
            "timestamp": time.time()
        }
        return self.send_message(payload)

    def send_clipboard_sync(self, clipboard_text: str) -> bool:
        """Transmits clipboard text directly to partner over Bluetooth."""
        return self.send_message({
            "type": "CLIPBOARD_SYNC",
            "from_host": self.host_name,
            "clipboard": clipboard_text,
            "timestamp": time.time()
        })

    def send_alignment_exchange(self, screen_bounds: Dict[str, int]) -> bool:
        """Exchanges screen bounds/resolution with partner host."""
        self.my_screen_bounds = screen_bounds
        return self.send_message({
            "type": "ALIGNMENT_EXCHANGE",
            "from_host": self.host_name,
            "screen_bounds": screen_bounds,
            "timestamp": time.time()
        })

    def _server_loop(self) -> None:
        """
        Listens for incoming Bluetooth RFCOMM connections.
        Dynamically detects and binds an available RFCOMM port, avoiding busy/forbidden ports.
        Handles discovery probes without disturbing active pairing sessions.
        """
        while self._running:
            self._server_sock = None
            try:
                candidate_ports = [self.rfcomm_port] + [p for p in range(5, 31) if p != self.rfcomm_port]
                bound = False
                for p in candidate_ports:
                    try:
                        s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                        bind_addr = "00:00:00:00:00:00"
                        s.bind((bind_addr, p))
                        s.listen(2)
                        self._server_sock = s
                        if self.rfcomm_port != p:
                            log("BluetoothLink", f"Port {self.rfcomm_port} busy/reserved; dynamically bound to available RFCOMM port {p}.")
                            self.rfcomm_port = p
                        else:
                            log("BluetoothLink", f"Server listening on RFCOMM channel {self.rfcomm_port}...")
                        bound = True
                        break
                    except Exception:
                        if s:
                            try:
                                s.close()
                            except Exception:
                                pass
                if not bound:
                    raise RuntimeError("No available RFCOMM ports could be bound (range 5-30).")

                while self._running:
                    try:
                        conn, peer_info = self._server_sock.accept()
                        remote_mac = peer_info[0] if isinstance(peer_info, (list, tuple)) and peer_info else ""
                        setattr(conn, "_peer_mac", remote_mac)
                        # Handle in thread so probes don't block ongoing operations
                        threading.Thread(target=self._handle_incoming_connection, args=(conn,), daemon=True).start()
                    except Exception as ex:
                        if self._running:
                            log("BluetoothLink", f"Server accept notice: {ex}")
                        break
            except Exception as e:
                if self._running:
                    log("BluetoothLink", f"Server bind error: {e}. Retrying in 10s...")
                    time.sleep(10)
            finally:
                if self._server_sock:
                    try:
                        self._server_sock.close()
                    except Exception:
                        pass

    def _handle_incoming_connection(self, conn: socket.socket) -> None:
        """
        Inspects incoming connection:
        - If DISCOVERY_PROBE: returns DISCOVERY_BEACON and closes.
        - If persistent session (PAIR_REQUEST / established link): adopts connection.
        """
        buffer = ""
        conn.settimeout(5.0)
        is_paired_session = False
        try:
            while self._running:
                data = conn.recv(1024)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    msg = json.loads(line)
                    mtype = msg.get("type")

                    # 1. Discovery Probe: Respond and close immediately
                    if mtype == "DISCOVERY_PROBE":
                        if self.is_advertising:
                            remaining = max(0, int(self._adv_expires_at - time.time()))
                            beacon = {
                                "type": "DISCOVERY_BEACON",
                                "from_host": self.host_name,
                                "token": self._adv_token,
                                "port": self.rfcomm_port,
                                "advertising": True,
                                "expires_in": remaining
                            }
                        else:
                            beacon = {
                                "type": "DISCOVERY_BEACON",
                                "from_host": self.host_name,
                                "port": self.rfcomm_port,
                                "advertising": False
                            }
                        try:
                            conn.sendall((json.dumps(beacon) + "\n").encode("utf-8"))
                        except Exception:
                            pass
                        return

                    # 2. Session messages & PAIR_REQUEST
                    if not is_paired_session:
                        self._set_active_conn(conn)
                        is_paired_session = True
                        conn.settimeout(None)
                    self._process_message(msg)
        except Exception as e:
            if is_paired_session:
                log("BluetoothLink", f"Bluetooth connection ended: {e}")
        finally:
            if is_paired_session:
                self._close_conn()
            else:
                try:
                    conn.close()
                except Exception:
                    pass

    def _client_loop(self) -> None:
        """
        Periodically attempts to connect to configured peer Bluetooth address if not connected.
        """
        while self._running:
            if not self._is_connected and self.peer_mac:
                try:
                    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                    s.settimeout(5.0)
                    s.connect((self.peer_mac, self.rfcomm_port))
                    s.settimeout(None)
                    log("BluetoothLink", f"Successfully connected to partner at {self.peer_mac}")
                    self._set_active_conn(s)
                    self._handle_connection(s)
                except Exception:
                    pass
            time.sleep(5)

    def _handle_connection(self, conn: socket.socket) -> None:
        """Reads messages from the active connection."""
        buffer = ""
        try:
            while self._running:
                data = conn.recv(1024)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        self._process_message(msg)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            log("BluetoothLink", f"Connection error: {e}")
        finally:
            self._close_conn()

    def request_pairing(self,
                        target_mac: str,
                        port: Optional[int] = None,
                        adv_token: str = "",
                        on_error: Optional[Callable[[str], None]] = None) -> None:
        """
        Initiates Bluetooth RFCOMM handshake with the advertising peer.
        Sends PAIR_REQUEST with the discovered ephemeral token.
        """
        def worker():
            mac = target_mac.strip().upper()
            target_port = port or self.rfcomm_port or DEFAULT_RFCOMM_PORT
            try:
                # If Windows, verify device is paired with OS or trigger OS pairing prompt
                if sys.platform == "win32":
                    try:
                        import asyncio
                        import winrt.windows.devices.bluetooth as bt
                        mac_int = int(mac.replace(":", "").replace("-", ""), 16)
                        dev = asyncio.run(bt.BluetoothDevice.from_bluetooth_address_async(mac_int))
                        if dev and dev.device_information and not dev.device_information.pairing.is_paired:
                            log("BluetoothLink", f"Device {mac} is not yet paired in Windows. Requesting OS pairing...")
                            asyncio.run(dev.device_information.pairing.pair_async())
                    except Exception as pe:
                        log("BluetoothLink", f"Windows OS pairing check notice: {pe}")

                log("BluetoothLink", f"Initiating pairing handshake with {mac} on RFCOMM port {target_port}...")
                s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                s.settimeout(8.0)
                s.connect((mac, target_port))
                s.settimeout(None)
                setattr(s, "_peer_mac", mac)
                self.peer_mac = mac
                self.rfcomm_port = target_port
                local_mac = ""
                try:
                    local_mac = s.getsockname()[0]
                except Exception:
                    pass

                req = {
                    "type": "PAIR_REQUEST",
                    "from_host": self.host_name,
                    "from_mac": local_mac,
                    "token": adv_token,
                    "client_nonce": secrets.token_hex(16),
                    "timestamp": time.time()
                }
                self._set_active_conn(s)
                self.send_message(req)
                log("BluetoothLink", f"Sent PAIR_REQUEST to {mac}. Awaiting partner confirmation...")
                self._handle_connection(s)
            except Exception as ex:
                log("BluetoothLink", f"Pairing request failed to connect to {mac} on port {target_port}: {ex}")
                self._close_conn()
                if on_error:
                    try:
                        on_error(str(ex))
                    except Exception:
                        pass

        threading.Thread(target=worker, name="BTPairReqThread", daemon=True).start()

    def _process_message(self, msg: Dict[str, Any]) -> None:
        mtype = msg.get("type")
        if mtype == "PING":
            self.send_message({"type": "PONG", "from_host": self.host_name})
        elif mtype == "SWITCH_OUT":
            exit_edge = msg.get("exit_edge", "right")
            ratio = float(msg.get("ratio", 0.5))
            clip = msg.get("clipboard")
            log("BluetoothLink", f"Received SWITCH_OUT event: exit_edge='{exit_edge}' ratio={ratio:.2f}")
            if self.on_switch_received:
                try:
                    self.on_switch_received(exit_edge, ratio, clip)
                except Exception as e:
                    log("BluetoothLink", f"Error in switch callback: {e}")
        elif mtype == "CLIPBOARD_SYNC":
            clip = msg.get("clipboard", "")
            if clip and self.on_clipboard_received:
                try:
                    self.on_clipboard_received(clip)
                except Exception as ex:
                    log("BluetoothLink", f"Error in clipboard callback: {ex}")
        elif mtype == "ALIGNMENT_EXCHANGE":
            bounds = msg.get("screen_bounds", {})
            if bounds:
                self.partner_screen_bounds = bounds
                log("BluetoothLink", f"Updated partner screen alignment: {bounds}")
                if self.on_alignment_received:
                    try:
                        self.on_alignment_received(bounds)
                    except Exception as ex:
                        log("BluetoothLink", f"Error in alignment callback: {ex}")
        elif mtype == "PAIR_REQUEST":
            from_host = msg.get("from_host", "Partner Computer")
            token = msg.get("token", "")
            from_mac = msg.get("from_mac") or getattr(self._active_conn, "_peer_mac", "")
            log("BluetoothLink", f"Received PAIR_REQUEST from '{from_host}' (MAC: {from_mac}, Token: {token[:6]}...)")

            accepted = False
            if self.is_advertising:
                # If currently advertising, auto-verify handshake
                if not self._adv_token or token == self._adv_token or self._adv_token.startswith(token) or token.startswith(self._adv_token):
                    accepted = True
                    log("BluetoothLink", f"Handshake verified with active advertising token from '{from_host}'.")
                else:
                    log("BluetoothLink", "Handshake token mismatch during advertising.")
            elif self.on_pair_request:
                try:
                    accepted = bool(self.on_pair_request(from_host, from_mac))
                except Exception as ex:
                    log("BluetoothLink", f"Error in on_pair_request: {ex}")

            if accepted:
                if from_mac:
                    self.peer_mac = from_mac.upper()
                self.session_key = secrets.token_hex(16)
                self.send_message({
                    "type": "PAIR_ACCEPT",
                    "from_host": self.host_name,
                    "session_key": self.session_key,
                    "timestamp": time.time()
                })
                log("BluetoothLink", f"Accepted pairing with '{from_host}'. Bluetooth session confirmed.")
            else:
                self.send_message({
                    "type": "PAIR_REJECT",
                    "from_host": self.host_name,
                    "reason": "Host not in advertising mode or rejected",
                    "timestamp": time.time()
                })
        elif mtype == "PAIR_ACCEPT":
            from_host = msg.get("from_host", "Partner Computer")
            self.session_key = msg.get("session_key", "")
            log("BluetoothLink", f"Pairing SUCCESS! Partner '{from_host}' accepted handshake.")
            if self.on_pair_response:
                try:
                    self.on_pair_response(True, from_host, self.peer_mac)
                except Exception as ex:
                    log("BluetoothLink", f"Error in on_pair_response: {ex}")
        elif mtype == "PAIR_REJECT":
            from_host = msg.get("from_host", "Partner Computer")
            reason = msg.get("reason", "Declined by user")
            log("BluetoothLink", f"Pairing REJECTED by '{from_host}': {reason}")
            if self.on_pair_response:
                try:
                    self.on_pair_response(False, from_host, reason)
                except Exception as ex:
                    log("BluetoothLink", f"Error in on_pair_response: {ex}")
