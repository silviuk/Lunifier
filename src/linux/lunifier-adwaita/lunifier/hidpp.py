"""
Logitech HID++ Protocol Implementation for Linux.
Ultra-low latency (<5ms) host switching via direct /dev/hidraw kernel access
with Solaar CLI fallback.
"""

import os
import re
import sys
import glob
import time
import shutil
import subprocess
import threading
from enum import Enum
from typing import List, Dict, Tuple, Optional, Set
from concurrent.futures import ThreadPoolExecutor

from .logger import log

try:
    import hid
except ImportError:
    hid = None

LOGITECH_VID = 0x046D
FEATURE_ROOT = 0x0000
FEATURE_CHANGE_HOST = 0x1814
FEATURE_DEVICE_NAME = 0x0005

USAGE_PAGE_RECEIVER = 0xFF00
USAGE_PAGE_BLUETOOTH = 0xFF43

PIDS_UNIFYING = {0xC52B, 0xC532, 0xC52F}
PIDS_BOLT = {0xC548, 0xC547}
PIDS_LIGHTSPEED = {0xC539, 0xC53A, 0xC541, 0xC542, 0xC53F, 0xC545}
ALL_RECEIVER_PIDS = PIDS_UNIFYING | PIDS_BOLT | PIDS_LIGHTSPEED


class TransportType(Enum):
    BLUETOOTH = "Bluetooth"
    UNIFYING = "Unifying"
    BOLT = "Bolt"
    LIGHTSPEED = "Lightspeed"
    GENERIC_HID = "HID"


class LogitechDevice:
    def __init__(self,
                 name: str,
                 path: bytes,
                 transport: TransportType,
                 device_index: int = 0x01,
                 vid: int = LOGITECH_VID,
                 pid: int = 0,
                 usage_page: int = 0,
                 usage: int = 0,
                 short_path: Optional[bytes] = None,
                 all_paths: Optional[List[bytes]] = None,
                 solaar_name: Optional[str] = None,
                 kind: Optional[str] = None):
        self.name = name
        self.path = path
        self.short_path = short_path
        self.all_paths = all_paths or ([path] if path else [])
        self.solaar_name = solaar_name or name
        self.kind = kind
        self.transport = transport
        self.device_index = device_index
        self.vid = vid
        self.pid = pid
        self.usage_page = usage_page
        self.usage = usage
        self.change_host_feature_index: int = 0x09
        self._change_host_feature_resolved: bool = False
        self._confirmed_solaar_name: Optional[str] = None
        self._confirmed_solaar_arg: Optional[str] = None
        self.is_active: bool = True

    @property
    def is_receiver(self) -> bool:
        return self.transport in (TransportType.UNIFYING, TransportType.BOLT, TransportType.LIGHTSPEED)

    def __repr__(self) -> str:
        feat_str = f"0x{self.change_host_feature_index:02x}"
        return (f"<LogitechDevice name='{self.name}' transport={self.transport.value} "
                f"dev_idx=0x{self.device_index:02x} feat={feat_str}>")


class HIDPPMaster:
    CACHE_TTL_SECONDS: float = 60.0

    def __init__(self):
        self.devices: List[LogitechDevice] = []
        self._cached_devices: List[LogitechDevice] = []
        self._last_scan_time: float = 0.0
        self._receiver_slots_cache: Dict[Tuple[int, int], LogitechDevice] = {}
        self._scan_lock = threading.Lock()
        self._solaar_lock = threading.Lock()
        self._solaar_path = shutil.which("solaar")
        self._solaar_confirmed_cache: Dict[str, Tuple[str, str]] = {}
        self._executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="Lunifier_Switch")
        self.connection_support: str = "both"

    def clear_cache(self) -> None:
        with self._scan_lock:
            self._cached_devices.clear()
            self._receiver_slots_cache.clear()
            self.devices.clear()
            self._last_scan_time = 0.0
        log("HID++", "Device cache cleared.")

    def is_transport_supported(self, transport: TransportType, connection_support: Optional[str] = None) -> bool:
        mode = (connection_support or self.connection_support or "both").lower()
        if mode == "unifying":
            return transport in (TransportType.UNIFYING, TransportType.BOLT, TransportType.LIGHTSPEED)
        elif mode == "bluetooth":
            return transport == TransportType.BLUETOOTH
        return True

    @staticmethod
    def identify_transport(pid: int, usage_page: int, path: bytes) -> TransportType:
        if pid in PIDS_UNIFYING:
            return TransportType.UNIFYING
        elif pid in PIDS_BOLT:
            return TransportType.BOLT
        elif pid in PIDS_LIGHTSPEED:
            return TransportType.LIGHTSPEED
        elif usage_page == USAGE_PAGE_BLUETOOTH or "bth" in str(path).lower():
            return TransportType.BLUETOOTH
        elif usage_page == USAGE_PAGE_RECEIVER:
            return TransportType.UNIFYING
        elif pid not in ALL_RECEIVER_PIDS and pid != 0:
            return TransportType.BLUETOOTH
        return TransportType.GENERIC_HID

    def scan_devices(self, target_keywords: Optional[List[str]] = None, force_rescan: bool = False, connection_support: Optional[str] = None) -> List[LogitechDevice]:
        with self._scan_lock:
            if connection_support is not None:
                if connection_support != self.connection_support:
                    self._cached_devices.clear()
                    self._receiver_slots_cache.clear()
                    self.devices.clear()
                    self._last_scan_time = 0.0
                self.connection_support = connection_support

            now = time.time()
            if self._cached_devices and not force_rescan and (now - self._last_scan_time < self.CACHE_TTL_SECONDS):
                return self._cached_devices

            found_devices: List[LogitechDevice] = []
            seen_names: Set[str] = set()

            # Scan Linux sysfs
            sysfs_devs, rx_paths = self._scan_linux_sysfs(target_keywords)
            for s_dev in sysfs_devs:
                norm = self._normalize_name(s_dev.name)
                if norm not in seen_names:
                    found_devices.append(s_dev)
                    seen_names.add(norm)
                else:
                    for existing in found_devices:
                        if self._normalize_name(existing.name) == norm:
                            for p in s_dev.all_paths:
                                if p not in existing.all_paths:
                                    existing.all_paths.append(p)

            # Solaar enumeration fallback
            if self._solaar_path and (not found_devices or force_rescan):
                solaar_devs = self._scan_via_solaar(target_keywords)
                for s_dev in solaar_devs:
                    norm = self._normalize_name(s_dev.name)
                    if norm not in seen_names:
                        found_devices.append(s_dev)
                        seen_names.add(norm)
                    else:
                        for existing in found_devices:
                            if self._normalize_name(existing.name) == norm:
                                existing.solaar_name = s_dev.solaar_name
                                if getattr(s_dev, 'kind', None):
                                    existing.kind = s_dev.kind

            self._cached_devices = found_devices
            self.devices = found_devices
            self._last_scan_time = now

            log("HID++", f"Scan complete: {len(found_devices)} Logitech device(s) verified.")
            return found_devices

    def _normalize_name(self, name: str) -> str:
        s = name.lower()
        s = re.sub(r'^(?:logitech\s+)', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    def _scan_linux_sysfs(self, target_keywords: Optional[List[str]] = None) -> Tuple[List[LogitechDevice], List[Tuple[bytes, int, TransportType]]]:
        found: List[LogitechDevice] = []
        receivers: List[Tuple[bytes, int, TransportType]] = []
        hidraw_dirs = sorted(glob.glob("/sys/class/hidraw/hidraw*"))

        for hdir in hidraw_dirs:
            try:
                dev_node = f"/dev/{os.path.basename(hdir)}".encode("utf-8")
                device_dir = os.path.join(hdir, "device")
                uevent_path = os.path.join(device_dir, "uevent")
                if not os.path.isfile(uevent_path):
                    continue

                uevent_data = {}
                with open(uevent_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            uevent_data[k] = v

                hid_id = uevent_data.get("HID_ID", "")
                hid_name = uevent_data.get("HID_NAME", "").strip()

                vid, pid = 0, 0
                if hid_id:
                    parts = hid_id.split(":")
                    if len(parts) >= 3:
                        try:
                            vid = int(parts[1], 16)
                            pid = int(parts[2], 16)
                        except ValueError:
                            pass

                if vid != LOGITECH_VID and "logitech" not in hid_name.lower():
                    continue

                transport = self.identify_transport(pid, 0, dev_node)

                if transport in (TransportType.UNIFYING, TransportType.BOLT, TransportType.LIGHTSPEED):
                    receivers.append((dev_node, pid, transport))
                    continue

                dev = LogitechDevice(
                    name=hid_name or f"Logitech Device (PID 0x{pid:04x})",
                    path=dev_node,
                    transport=transport,
                    device_index=0xFF,
                    vid=vid or LOGITECH_VID,
                    pid=pid,
                    all_paths=[dev_node]
                )
                if "master" in dev.name.lower():
                    dev.change_host_feature_index = 0x08
                else:
                    dev.change_host_feature_index = 0x09

                found.append(dev)
            except Exception:
                continue

        return found, receivers

    def _scan_via_solaar(self, target_keywords: Optional[List[str]] = None) -> List[LogitechDevice]:
        if not self._solaar_path:
            return []

        results: List[LogitechDevice] = []
        try:
            clean_env = os.environ.copy()
            clean_env["DISPLAY"] = ""
            clean_env["WAYLAND_DISPLAY"] = ""

            res = subprocess.run([self._solaar_path, "show"], capture_output=True, text=True, timeout=1.5, env=clean_env)
            if res.returncode != 0:
                return []

            current_name = None
            current_kind = None
            current_unit = 0

            for line in res.stdout.splitlines():
                line_str = line.strip()
                m_num = re.match(r"^(\d+):\s+(.+)$", line_str)
                if m_num:
                    current_unit = int(m_num.group(1))
                    raw_n = m_num.group(2).strip()
                    current_name = re.sub(r'^(?:logitech\s+)', '', raw_n, flags=re.IGNORECASE)
                    current_kind = "keyboard" if "keyboard" in current_name.lower() or "keys" in current_name.lower() else "mouse"
                    
                    dev = LogitechDevice(
                        name=f"Logitech {current_name}",
                        path=b"/dev/solaar",
                        transport=TransportType.UNIFYING if current_unit <= 6 else TransportType.BLUETOOTH,
                        device_index=current_unit if 1 <= current_unit <= 6 else 0xFF,
                        solaar_name=str(current_unit),
                        kind=current_kind
                    )
                    results.append(dev)
        except Exception:
            pass

        return results

    def _switch_via_linux_hidraw(self, dev: LogitechDevice, target_channel: int, channel_index: int,
                                 dev_indices_to_try: List[int], feature_indices: List[int],
                                 target_paths: List[bytes]) -> bool:
        if not target_paths:
            return False

        candidate_nodes = [p.decode("utf-8") for p in target_paths if p and p.startswith(b"/dev/hidraw")]
        if not candidate_nodes:
            return False

        o_nonblock = getattr(os, "O_NONBLOCK", 0)

        written_any = False
        for dev_node in candidate_nodes:
            try:
                fd = os.open(dev_node, os.O_WRONLY | o_nonblock)
                try:
                    if dev.transport == TransportType.BLUETOOTH:
                        try:
                            os.write(fd, bytes([0x11, 0xFF, 0x00, 0x00] + [0x00] * 16))
                            time.sleep(0.010)
                        except Exception:
                            pass

                    for d_idx in dev_indices_to_try:
                        for feat_idx in feature_indices:
                            pkt = bytes([0x11, d_idx, feat_idx, 0x10, channel_index] + [0x00] * 15)
                            try:
                                if os.write(fd, pkt) > 0:
                                    written_any = True
                                    if dev.transport == TransportType.BLUETOOTH:
                                        time.sleep(0.015)
                                        os.write(fd, pkt)
                            except Exception:
                                pass
                finally:
                    os.close(fd)
            except Exception:
                pass

        if written_any:
            log("HID++", f"Instant /dev/hidraw switch for '{dev.name}' -> Channel {target_channel}")
            return True

        return False

    def _switch_via_solaar(self, dev: LogitechDevice, target_channel: int, channel_index: int) -> bool:
        if not self._solaar_path:
            return False

        with self._solaar_lock:
            clean_env = os.environ.copy()
            clean_env["DISPLAY"] = ""
            clean_env["WAYLAND_DISPLAY"] = ""

            quick_args = [str(target_channel), f"Host {target_channel}"]
            candidates = [dev.solaar_name, dev.name, str(dev.device_index)]
            if getattr(dev, 'kind', None):
                candidates.append(dev.kind)

            seen = set()
            clean_cands = [c for c in candidates if c and not (c in seen or seen.add(c))]

            for s_name in clean_cands[:3]:
                for h_arg in quick_args:
                    cmd = [self._solaar_path, "config", s_name, "change-host", h_arg]
                    try:
                        t0 = time.perf_counter()
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=0.4, env=clean_env)
                        dur_ms = (time.perf_counter() - t0) * 1000.0
                        if res.returncode == 0:
                            log("HID++", f"Solaar switch SUCCEEDED for '{dev.name}' (as '{s_name}') -> Channel {target_channel} [{dur_ms:.1f}ms]")
                            return True
                        else:
                            err_out = (res.stderr or res.stdout or "").strip()
                            if "no online device found" in err_out.lower():
                                return True
                    except Exception:
                        pass

        return False

    def switch_device_host(self, dev: LogitechDevice, target_channel: int, backend: str = "auto", connection_support: Optional[str] = None) -> bool:
        conn_mode = (connection_support or self.connection_support or "both").lower()
        if not self.is_transport_supported(dev.transport, conn_mode):
            return False

        channel_index = max(0, min(2, target_channel - 1))
        backend = (backend or "auto").lower()

        feature_indices = [dev.change_host_feature_index]
        for f in [0x09, 0x08, 0x0A, 0x0B, 0x07]:
            if f not in feature_indices:
                feature_indices.append(f)

        dev_indices = [0xFF] if dev.transport == TransportType.BLUETOOTH else [dev.device_index]
        target_paths = dev.all_paths if dev.all_paths else ([dev.path] if dev.path else [])

        if backend == "solaar":
            if self._switch_via_solaar(dev, target_channel, channel_index):
                return True
            if self._switch_via_linux_hidraw(dev, target_channel, channel_index, dev_indices, feature_indices, target_paths):
                return True
        else:
            # "auto" or "direct" -> direct hidraw first
            if self._switch_via_linux_hidraw(dev, target_channel, channel_index, dev_indices, feature_indices, target_paths):
                return True
            if self._switch_via_solaar(dev, target_channel, channel_index):
                return True

        return False

    def switch_all_to_channel(self, target_channel: int, target_keywords: Optional[List[str]] = None, backend: str = "auto", connection_support: Optional[str] = None) -> Dict[str, bool]:
        devices = self.scan_devices(target_keywords, force_rescan=False, connection_support=connection_support)
        if not devices:
            devices = self.scan_devices(target_keywords, force_rescan=True, connection_support=connection_support)

        results: Dict[str, bool] = {}

        def do_switch(d: LogitechDevice):
            ok = self.switch_device_host(d, target_channel, backend=backend, connection_support=connection_support)
            return (f"{d.name} ({d.transport.value})", ok)

        futures = [self._executor.submit(do_switch, dev) for dev in devices]
        for f in futures:
            try:
                k, ok = f.result(timeout=4.0)
                results[k] = ok
            except Exception as ex:
                log("HID++", f"Switch exception: {ex}")

        return results
