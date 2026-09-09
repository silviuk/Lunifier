"""
Bluetooth RFCOMM Peer-to-Peer Inter-Host Link.
Zero-network connection between Windows and Linux hosts for Flow synchronization.
"""

import sys
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
        """
        :param host_name: Name of this host
        :param peer_mac: Bluetooth MAC of the partner host (e.g. "00:1A:7D:DA:71:13")
        :param rfcomm_port: RFCOMM channel (default 4)
        :param on_switch_received: Callback when partner switches mouse here: func(exit_edge, ratio, clipboard)
        :param on_peer_status_changed: Callback func(is_connected: bool)
        """
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
