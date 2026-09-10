"""
Bluetooth RFCOMM Peer-to-Peer Inter-Host Link for Linux.
"""

import json
import time
import socket
import threading
from typing import Optional, Callable, Dict, Any

from .logger import log


class BluetoothLink:
    def __init__(self,
                 host_name: str,
                 peer_mac: str = "",
                 rfcomm_port: int = 4,
                 on_switch_received: Optional[Callable[[str, float, Optional[str]], None]] = None,
                 on_peer_status_changed: Optional[Callable[[bool], None]] = None):
        self.host_name = host_name
        self.peer_mac = peer_mac.strip().upper()
        self.rfcomm_port = rfcomm_port
        self.on_switch_received = on_switch_received
        self.on_peer_status_changed = on_peer_status_changed

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
        self._server_thread = threading.Thread(target=self._server_loop, name="LinuxBTServerThread", daemon=True)
        self._server_thread.start()

        if self.peer_mac:
            self._client_thread = threading.Thread(target=self._client_loop, name="LinuxBTClientThread", daemon=True)
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
        while self._running:
            try:
                self._server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                self._server_sock.bind(("00:00:00:00:00:00", self.rfcomm_port))
                self._server_sock.listen(1)

                while self._running:
                    try:
                        conn, peer_info = self._server_sock.accept()
                        log("BluetoothLink", f"Incoming connection from {peer_info}")
                        self._set_active_conn(conn)
                        self._handle_connection(conn)
                    except Exception:
                        break
            except Exception as e:
                if self._running:
                    time.sleep(5)
            finally:
                if self._server_sock:
                    try:
                        self._server_sock.close()
                    except Exception:
                        pass

    def _client_loop(self) -> None:
        while self._running:
            if not self._is_connected and self.peer_mac:
                sock = None
                try:
                    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                    sock.settimeout(4.0)
                    sock.connect((self.peer_mac, self.rfcomm_port))
                    sock.settimeout(None)
                    log("BluetoothLink", f"Connected to partner host {self.peer_mac}")
                    self._set_active_conn(sock)
                    self._handle_connection(sock)
                except Exception:
                    if sock:
                        try:
                            sock.close()
                        except Exception:
                            pass
                    time.sleep(4.0)
            else:
                time.sleep(2.0)

    def _handle_connection(self, conn: socket.socket) -> None:
        buf = ""
        conn.settimeout(1.0)
        while self._running and self._is_connected:
            try:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk.decode("utf-8", errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._process_message(line)
            except socket.timeout:
                continue
            except Exception:
                break
        self._close_conn()

    def _process_message(self, line: str) -> None:
        try:
            msg = json.loads(line)
            if msg.get("type") == "SWITCH_OUT":
                exit_edge = msg.get("exit_edge", "right")
                ratio = float(msg.get("ratio", 0.5))
                clip = msg.get("clipboard")
                if self.on_switch_received:
                    self.on_switch_received(exit_edge, ratio, clip)
        except Exception as e:
            log("BluetoothLink", f"Parse error: {e}")
