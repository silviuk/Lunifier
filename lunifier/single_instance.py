"""
Single Instance & Inter-Process Communication (IPC) Manager for Lunifier.
Ensures only one instance of Lunifier runs at any time, and allows secondary
invocations (e.g. from app launcher or CLI) to send commands to the active instance.
"""

import sys
import socket
import threading
from typing import Callable, Optional
from .logger import log

DEFAULT_PORT = 42425


class SingleInstanceManager:
    """
    Enforces a single running instance of Lunifier via a local TCP socket.
    If another instance is already active, forwards commands (such as SHOW, SWITCH:X)
    to it and prevents duplicate processes.
    """
    def __init__(self, port: int = DEFAULT_PORT, on_command: Optional[Callable[[str], None]] = None):
        self.port = port
        self.on_command = on_command
        self.sock: Optional[socket.socket] = None
        self._running: bool = False
        self._server_thread: Optional[threading.Thread] = None

    def acquire(self) -> bool:
        """
        Attempts to acquire the single-instance lock.
        Returns True if this is the only running instance.
        Returns False if another instance is already running.
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Ensure socket can be quickly rebound if cleanly shut down
            if sys.platform != "win32":
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("127.0.0.1", self.port))
            self.sock.listen(5)
            self._running = True
            self._server_thread = threading.Thread(target=self._listen_loop, name="SingleInstanceIPC", daemon=True)
            self._server_thread.start()
            log("SingleInstance", f"Acquired primary instance lock on port {self.port}")
            return True
        except (OSError, socket.error):
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
            return False

    def send_command(self, command: str, timeout: float = 2.0) -> bool:
        """
        Sends a command string to the active primary instance.
        Returns True if the active instance acknowledged the command.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect(("127.0.0.1", self.port))
                s.sendall(command.encode("utf-8") + b"\n")
                resp = s.recv(1024)
                return resp.strip() == b"OK"
        except Exception:
            return False

    def _listen_loop(self) -> None:
        while self._running and self.sock:
            try:
                conn, _ = self.sock.accept()
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except Exception:
                break

    def _handle_client(self, conn: socket.socket) -> None:
        with conn:
            try:
                conn.settimeout(3.0)
                data = conn.recv(1024).decode("utf-8").strip()
                if data:
                    conn.sendall(b"OK\n")
                    log("SingleInstance", f"Received IPC command: {data}")
                    if self.on_command:
                        self.on_command(data)
            except Exception:
                pass

    def release(self) -> None:
        """Releases the socket and stops the IPC server."""
        self._running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        log("SingleInstance", "Released instance lock.")
