"""
Bluetooth RFCOMM Peer-to-Peer Inter-Host Link.
Zero-network connection between Windows and Linux hosts for Flow synchronization.
"""

import sys
import json
import time
import socket
import threading
from typing import Optional, Callable, Dict, Any, List

from .logger import log


def discover_potential_partners(timeout: float = 3.5) -> List[Dict[str, str]]:
    """
    Discovers potential partner computers over Bluetooth:
    - Scans paired Bluetooth devices from OS (Windows registry / Linux bluetoothctl).
    - Scans nearby broadcasting devices via Bleak BLE scanner.
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
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(lambda: asyncio.run(_run_ble_scan())).result()
            else:
                loop.run_until_complete(_run_ble_scan())
        except Exception:
            asyncio.run(_run_ble_scan())
    except Exception as e:
        log("BluetoothLink", f"BLE scanner notice: {e}")

    # Sort results: Paired devices first, then alphabetically by name
    res = list(devices.values())
    res.sort(key=lambda x: (0 if x["source"] == "Paired" else 1, x["name"].lower()))
    return res


class BluetoothLink:
    def __init__(self,
                 host_name: str,
                 peer_mac: str = "",
                 rfcomm_port: int = 4,
                 on_switch_received: Optional[Callable[[str, float, Optional[str]], None]] = None,
                 on_peer_status_changed: Optional[Callable[[bool], None]] = None,
                 on_pair_request: Optional[Callable[[str, str], bool]] = None,
                 on_pair_response: Optional[Callable[[bool, str, str], None]] = None):
        """
        :param host_name: Name of this host
        :param peer_mac: Bluetooth MAC of the partner host (e.g. "00:1A:7D:DA:71:13")
        :param rfcomm_port: RFCOMM channel (default 4)
        :param on_switch_received: Callback when partner switches mouse here: func(exit_edge, ratio, clipboard)
        :param on_peer_status_changed: Callback func(is_connected: bool)
        :param on_pair_request: Callback func(from_host: str, from_mac: str) -> bool (returns True if user accepts)
        :param on_pair_response: Callback func(accepted: bool, from_host: str, info: str)
        """
        self.host_name = host_name
        self.peer_mac = peer_mac.strip().upper()
        self.rfcomm_port = rfcomm_port
        self.on_switch_received = on_switch_received
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

    @property
    def is_connected(self) -> bool:
        return self._is_connected

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
        Sends a JSON-encoded message line over the active Bluetooth connection.
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
            log("BluetoothLink", f"Send error: {e}")
            self._close_conn()
            return False

    def notify_switch_out(self, exit_edge: str, ratio: float, clipboard_text: Optional[str] = None) -> bool:
        """
        Informs partner host that the mouse has crossed into its screen.
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

    def _server_loop(self) -> None:
        """
        Listens for incoming Bluetooth RFCOMM connections.
        """
        while self._running:
            try:
                self._server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                bind_addr = "00:00:00:00:00:00" if sys.platform != "win32" else ""
                self._server_sock.bind((bind_addr, self.rfcomm_port))
                self._server_sock.listen(1)
                log("BluetoothLink", f"Server listening on RFCOMM channel {self.rfcomm_port}...")

                while self._running:
                    try:
                        conn, peer_info = self._server_sock.accept()
                        remote_mac = peer_info[0] if isinstance(peer_info, (list, tuple)) and peer_info else ""
                        setattr(conn, "_peer_mac", remote_mac)
                        log("BluetoothLink", f"Incoming peer connection accepted from {peer_info}")
                        self._set_active_conn(conn)
                        self._handle_connection(conn)
                    except Exception as ex:
                        if self._running:
                            log("BluetoothLink", f"Server accept error: {ex}")
                        break
            except Exception as e:
                if self._running:
                    log("BluetoothLink", f"Server bind error on port {self.rfcomm_port}: {e}. Retrying in 5s...")
                    time.sleep(5)
            finally:
                if self._server_sock:
                    try:
                        self._server_sock.close()
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
                    # Partner not in range or server not ready; retry in 5s
                    pass
            time.sleep(5)

    def _handle_connection(self, conn: socket.socket) -> None:
        """
        Reads messages from the active connection.
        """
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
            log("BluetoothLink", f"Connection ended: {e}")
        finally:
            self._close_conn()

    def request_pairing(self, target_mac: str, on_error: Optional[Callable[[str], None]] = None) -> None:
        """
        Connects to partner host and sends PAIR_REQUEST to initiate handshake.
        """
        def worker():
            mac = target_mac.strip().upper()
            try:
                log("BluetoothLink", f"Initiating pairing handshake with {mac} on RFCOMM port {self.rfcomm_port}...")
                s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                s.settimeout(8.0)
                s.connect((mac, self.rfcomm_port))
                s.settimeout(None)
                setattr(s, "_peer_mac", mac)
                self.peer_mac = mac
                self._set_active_conn(s)
                # Send PAIR_REQUEST payload
                req = {
                    "type": "PAIR_REQUEST",
                    "from_host": self.host_name,
                    "from_mac": "",
                    "timestamp": time.time()
                }
                self.send_message(req)
                log("BluetoothLink", f"Sent PAIR_REQUEST to {mac}. Awaiting partner confirmation...")
                self._handle_connection(s)
            except Exception as ex:
                log("BluetoothLink", f"Pairing request failed to connect to {mac}: {ex}")
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
        elif mtype == "PAIR_REQUEST":
            from_host = msg.get("from_host", "Partner Computer")
            conn = self._active_conn
            from_mac = msg.get("from_mac") or getattr(conn, "_peer_mac", "")
            log("BluetoothLink", f"Received PAIR_REQUEST from '{from_host}' (MAC: {from_mac})")
            accepted = False
            if self.on_pair_request:
                try:
                    accepted = bool(self.on_pair_request(from_host, from_mac))
                except Exception as ex:
                    log("BluetoothLink", f"Error in on_pair_request: {ex}")
            if accepted:
                if from_mac:
                    self.peer_mac = from_mac.upper()
                self.send_message({
                    "type": "PAIR_ACCEPT",
                    "from_host": self.host_name,
                    "timestamp": time.time()
                })
                log("BluetoothLink", f"Accepted pairing with '{from_host}'. Binding confirmed.")
            else:
                self.send_message({
                    "type": "PAIR_REJECT",
                    "from_host": self.host_name,
                    "reason": "Declined by user",
                    "timestamp": time.time()
                })
                log("BluetoothLink", f"Rejected pairing request from '{from_host}'.")
        elif mtype == "PAIR_ACCEPT":
            from_host = msg.get("from_host", "Partner Computer")
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
