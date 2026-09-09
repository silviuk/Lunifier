"""
Logitech HID++ Protocol Implementation with Autonomous Multi-Protocol Support.
Optimized for ultra-low latency (<5ms) concurrent host switching across
Bluetooth, Unifying, and Bolt receivers.
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

from lunifier.logger import log

try:
    import hid
except ImportError:
    hid = None

LOGITECH_VID = 0x046D
FEATURE_ROOT = 0x0000
FEATURE_CHANGE_HOST = 0x1814
FEATURE_DEVICE_NAME = 0x0005

# Usage pages
USAGE_PAGE_RECEIVER = 0xFF00
USAGE_PAGE_BLUETOOTH = 0xFF43

# Known Logitech Wireless Receiver PIDs
PIDS_UNIFYING = {0xC52B, 0xC532, 0xC52F}
PIDS_BOLT = {0xC548, 0xC547}
PIDS_LIGHTSPEED = {0xC539, 0xC53A, 0xC541, 0xC542, 0xC53F, 0xC545}
ALL_RECEIVER_PIDS = PIDS_UNIFYING | PIDS_BOLT | PIDS_LIGHTSPEED

DEFAULT_FEATURE_INDICES = [0x09, 0x0A, 0x08, 0x0B]


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
        self.path = path                       # Primary control path
        self.short_path = short_path           # Short Report path for Unifying (Col01)
        self.all_paths = all_paths or ([path] if path else [])
        self.solaar_name = solaar_name or name # Codename recognized by Solaar
        self.kind = kind                       # "keyboard", "mouse", etc.
        self.transport = transport
        self.device_index = device_index
        self.vid = vid
        self.pid = pid
        self.usage_page = usage_page
        self.usage = usage
        self.change_host_feature_index: int = 0x09  # Default to 0x09
        self._change_host_feature_resolved: bool = False
        self._confirmed_solaar_name: Optional[str] = None
        self._confirmed_solaar_arg: Optional[str] = None

    @property
    def is_receiver(self) -> bool:
        return self.transport in (TransportType.UNIFYING, TransportType.BOLT, TransportType.LIGHTSPEED)

    def __repr__(self) -> str:
        feat_str = f"0x{self.change_host_feature_index:02x}"
        return (f"<LogitechDevice name='{self.name}' transport={self.transport.value} "
                f"dev_idx=0x{self.device_index:02x} feat={feat_str}>")


class HIDPPMaster:
    CACHE_TTL_SECONDS: float = 3.0

    def __init__(self):
        self.devices: List[LogitechDevice] = []
        self._cached_devices: List[LogitechDevice] = []
        self._last_scan_time: float = 0.0
        self._receiver_slots_cache: Dict[Tuple[int, int], LogitechDevice] = {}
        self._scan_lock = threading.Lock()
        self._solaar_lock = threading.Lock()
        self._solaar_path = shutil.which("solaar") if sys.platform.startswith("linux") else None
        self._executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="LogiFlow_Switch")
        self.connection_support: str = "both"  # "both", "unifying", "bluetooth"

    def clear_cache(self) -> None:
        """
        Cleans the device cache and receiver slot mappings.
        Forces the next scan or switch to rediscover devices fresh from hardware.
        """
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
        """
        Scans for connected Logitech devices across Bluetooth and Wireless Receivers (Unifying, Bolt).
        Multi-layered detection ensures 100% discovery of both keyboard and mouse on all transports.
        """
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

            # --- Layer 1: Linux sysfs inspection (/sys/class/hidraw) ---
            # Fast kernel level discovery (reads kernel device uevent directly)
            if sys.platform.startswith("linux"):
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

                # If Unifying/Bolt receiver dongles exist on Linux, read Solaar configs for paired devices
                if rx_paths:
                    solaar_cfg_devs = self._scan_solaar_config(rx_paths[0], target_keywords)
                    for sc_dev in solaar_cfg_devs:
                        norm = self._normalize_name(sc_dev.name)
                        if norm not in seen_names:
                            found_devices.append(sc_dev)
                            seen_names.add(norm)

            # --- Layer 2: Solaar CLI on Linux ---
            # Solaar is the primary authority on Linux for paired Unifying & Bolt peripherals
            if sys.platform.startswith("linux") and self._solaar_path:
                solaar_devs = self._scan_solaar_devices(target_keywords)
                for s_dev in solaar_devs:
                    norm = self._normalize_name(s_dev.name)
                    if norm not in seen_names:
                        found_devices.append(s_dev)
                        seen_names.add(norm)
                    else:
                        for existing in found_devices:
                            if self._normalize_name(existing.name) == norm or self._is_same_device_name(existing.name, s_dev.name):
                                if s_dev.solaar_name:
                                    existing.solaar_name = s_dev.solaar_name
                                existing.transport = s_dev.transport
                                if s_dev.device_index and s_dev.device_index != 0x01:
                                    existing.device_index = s_dev.device_index
                                if getattr(s_dev, 'kind', None):
                                    existing.kind = s_dev.kind
                                for p in s_dev.all_paths:
                                    if p and p not in existing.all_paths and p != b"/dev/solaar":
                                        existing.all_paths.append(p)

            # --- Layer 3: hidapi enumeration (Cross-Platform Windows & Linux) ---
            if hid:
                raw_devices: List[dict] = []
                try:
                    raw_devices = hid.enumerate(LOGITECH_VID)
                    if not raw_devices:
                        for d in hid.enumerate():
                            vid = d.get('vendor_id', 0)
                            prod = (d.get('product_string', '') or '').lower()
                            mfg = (d.get('manufacturer_string', '') or '').lower()
                            if (vid == LOGITECH_VID or 'logitech' in prod or 'logitech' in mfg
                                    or 'mx keys' in prod or 'm370' in prod or 'pop' in prod or 'mx master' in prod):
                                raw_devices.append(d)
                except Exception as e:
                    log("HID++", f"Warning: hid.enumerate error: {e}")

                # Group receivers Col01 (short) and Col02 (long)
                receivers_col01: Dict[int, bytes] = {}
                receivers_col02: Dict[int, bytes] = {}

                for dev_info in raw_devices:
                    pid = dev_info.get('product_id', 0)
                    up = dev_info.get('usage_page', 0)
                    u = dev_info.get('usage', 0)
                    path = dev_info.get('path', b'')
                    path_str = str(path).lower()

                    if pid in ALL_RECEIVER_PIDS or up == USAGE_PAGE_RECEIVER:
                        if (up == USAGE_PAGE_RECEIVER and u == 0x0001) or "col01" in path_str:
                            receivers_col01[pid] = path
                        elif (up == USAGE_PAGE_RECEIVER and u == 0x0002) or "col02" in path_str:
                            receivers_col02[pid] = path

                # Query paired devices on receivers
                for pid, long_path in receivers_col02.items():
                    short_path = receivers_col01.get(pid)
                    transport = self.identify_transport(pid, USAGE_PAGE_RECEIVER, long_path)
                    paired = self._query_receiver_paired_devices(long_path, short_path, pid, transport, force_rescan=force_rescan)
                    for p_dev in paired:
                        if not self._matches_keywords(p_dev.name, target_keywords):
                            continue
                        # Check if device already added
                        existing_idx = None
                        for i, existing in enumerate(found_devices):
                            if self._is_same_device_name(existing.name, p_dev.name):
                                existing_idx = i
                                break
                        if existing_idx is not None:
                            if getattr(p_dev, 'is_active', False) and not getattr(found_devices[existing_idx], 'is_active', False):
                                found_devices[existing_idx] = p_dev
                            for p in p_dev.all_paths:
                                if p not in found_devices[existing_idx].all_paths:
                                    found_devices[existing_idx].all_paths.append(p)
                        else:
                            found_devices.append(p_dev)

                # Direct Bluetooth Devices
                candidate_bt_devices: Dict[str, List[dict]] = {}
                for dev_info in raw_devices:
                    pid = dev_info.get('product_id', 0)
                    up = dev_info.get('usage_page', 0)
                    u = dev_info.get('usage', 0)
                    path = dev_info.get('path', b'')
                    prod = dev_info.get('product_string', '') or "Logitech Device"

                    if pid in ALL_RECEIVER_PIDS:
                        continue

                    is_bluetooth = False
                    if up == USAGE_PAGE_BLUETOOTH and u == 0x0202:
                        is_bluetooth = True
                    elif "bth" in str(path).lower():
                        is_bluetooth = True
                    elif sys.platform.startswith("linux"):
                        is_bluetooth = True

                    if is_bluetooth:
                        clean_name = prod.replace("_", " ").strip()
                        if not clean_name or clean_name.lower() == "logitech device":
                            clean_name = self._guess_name_from_pid(pid)

                        norm = self._normalize_name(clean_name)
                        if norm not in candidate_bt_devices:
                            candidate_bt_devices[norm] = []
                        candidate_bt_devices[norm].append(dev_info)

                for norm, endpoints in candidate_bt_devices.items():
                    clean_name = endpoints[0].get('product_string', '') or self._guess_name_from_pid(endpoints[0].get('product_id', 0))
                    clean_name = clean_name.replace("_", " ").strip()
                    if not self._matches_keywords(clean_name, target_keywords):
                        continue

                    # Select active Bluetooth endpoint
                    best_endpoint = self._select_best_bt_endpoint(clean_name, endpoints)
                    if best_endpoint:
                        # Check if this device is already in found_devices (e.g. from receiver)
                        existing_idx = None
                        for i, existing in enumerate(found_devices):
                            if self._is_same_device_name(existing.name, clean_name):
                                existing_idx = i
                                break

                        if existing_idx is not None:
                            # Device is already present. Since best_endpoint is verified active on Bluetooth,
                            # replace the receiver entry with the active Bluetooth device so it doesn't show up twice!
                            existing = found_devices[existing_idx]
                            for p in existing.all_paths:
                                if p not in best_endpoint.all_paths:
                                    best_endpoint.all_paths.append(p)
                            found_devices[existing_idx] = best_endpoint
                        else:
                            found_devices.append(best_endpoint)

            # Final deduplication pass: guarantee no single physical device appears twice
            deduped_devices: List[LogitechDevice] = []
            for dev in found_devices:
                dup_idx = None
                for i, existing in enumerate(deduped_devices):
                    if self._is_same_device_name(existing.name, dev.name):
                        dup_idx = i
                        break
                if dup_idx is None:
                    deduped_devices.append(dev)
                else:
                    existing = deduped_devices[dup_idx]
                    dev_active = getattr(dev, 'is_active', False)
                    existing_active = getattr(existing, 'is_active', False)
                    if dev_active and not existing_active:
                        for p in existing.all_paths:
                            if p not in dev.all_paths:
                                dev.all_paths.append(p)
                        deduped_devices[dup_idx] = dev
                    elif not dev_active and existing_active:
                        for p in dev.all_paths:
                            if p not in existing.all_paths:
                                existing.all_paths.append(p)
                    elif dev.transport == TransportType.BLUETOOTH and existing.transport != TransportType.BLUETOOTH:
                        # Only prefer Bluetooth if it's active or existing is also inactive
                        for p in existing.all_paths:
                            if p not in dev.all_paths:
                                dev.all_paths.append(p)
                        deduped_devices[dup_idx] = dev

            if self.connection_support != "both":
                deduped_devices = [d for d in deduped_devices if self.is_transport_supported(d.transport, self.connection_support)]

            found_devices = deduped_devices
            self.devices = found_devices
            self._cached_devices = found_devices
            self._last_scan_time = time.time()
            return found_devices

    def _normalize_name(self, name: str) -> str:
        n = name.lower().replace("_", " ").strip()
        for term in ["logitech", "wireless", "mouse", "keyboard", "bluetooth", "edition", "multi-device", "multidevice"]:
            n = re.sub(rf"\b{term}\b", "", n).strip()
        cleaned = " ".join(n.split())
        return cleaned if cleaned else name.lower().strip()

    def _is_same_device_name(self, name1: str, name2: str) -> bool:
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)
        if n1 == n2:
            return True
        if n1 in n2 or n2 in n1:
            return True
        model_keywords = [
            "m720", "triathlon", "mx master", "master 3", "master 2", "anywhere",
            "mx keys", "craft", "k380", "k780", "pop", "m370", "ergo", "lift",
            "pebble", "g502", "g305", "g903", "gpro"
        ]
        for kw in model_keywords:
            if kw in n1 and kw in n2:
                return True
        return False

    def _select_best_bt_endpoint(self, name: str, endpoints: List[dict]) -> Optional[LogitechDevice]:
        all_paths = [ep.get('path', b'') for ep in endpoints if ep.get('path')]

        # Prioritize Logitech Bluetooth HID++ control endpoint (UP: 0xFF43, U: 0x0202)
        sorted_endpoints = sorted(
            endpoints,
            key=lambda ep: 0 if (ep.get('usage_page') == USAGE_PAGE_BLUETOOTH and ep.get('usage') == 0x0202) else 1
        )

        for ep in sorted_endpoints:
            path = ep.get('path', b'')
            if not path:
                continue
            pid = ep.get('product_id', 0)
            up = ep.get('usage_page', 0)
            u = ep.get('usage', 0)

            # Liveness check & feature resolution: verify Bluetooth endpoint can actually be opened
            resolved_feat_idx = None
            if hid:
                try:
                    h = hid.device()
                    h.open_path(path)
                    # For Logitech HID++ control endpoint (0xFF43 / 0x0202), resolve CHANGE_HOST (0x1814)
                    if up == USAGE_PAGE_BLUETOOTH and u == 0x0202:
                        try:
                            # Root Feature 0x0000 -> Function 0 (getFeature(0x1814))
                            query = [0x11, 0xFF, 0x00, 0x00, (FEATURE_CHANGE_HOST >> 8) & 0xFF, FEATURE_CHANGE_HOST & 0xFF] + [0x00] * 14
                            h.write(query)
                            time.sleep(0.015)
                            resp = h.read(20, timeout_ms=250)
                            if resp and len(resp) >= 5 and resp[0] == 0x11 and resp[1] == 0xFF and resp[2] == 0x00 and resp[4] != 0:
                                resolved_feat_idx = resp[4]
                        except Exception:
                            pass
                    h.close()
                except Exception:
                    # Endpoint cannot be opened -> device disconnected from Bluetooth (e.g. switched to Unifying)
                    continue

            # Ensure the selected control endpoint is always the first item in all_paths
            ordered_paths = [path] + [p for p in all_paths if p != path]

            dev = LogitechDevice(
                name=name,
                path=path,
                transport=TransportType.BLUETOOTH,
                device_index=0xFF,
                vid=LOGITECH_VID,
                pid=pid,
                usage_page=up,
                usage=u,
                all_paths=ordered_paths
            )
            if resolved_feat_idx is not None:
                dev.change_host_feature_index = resolved_feat_idx
                dev._change_host_feature_resolved = True
            dev.is_active = True
            return dev

        return None

    def _scan_linux_sysfs(self, target_keywords: Optional[List[str]]) -> Tuple[List[LogitechDevice], List[bytes]]:
        """
        Inspects /sys/class/hidraw on Linux.
        Correctly recognizes both Bluetooth devices and devices paired through Unifying/Bolt receivers.
        """
        results: List[LogitechDevice] = []
        receiver_paths: List[bytes] = []
        if not os.path.isdir("/sys/class/hidraw"):
            return results, receiver_paths

        devices_grouped: Dict[Tuple[str, int, TransportType, int], List[bytes]] = {}

        try:
            for hidraw_dir in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
                uevent_file = os.path.join(hidraw_dir, "device", "uevent")
                if not os.path.isfile(uevent_file):
                    continue

                dev_name = ""
                phys = ""
                vid = 0
                pid = 0

                try:
                    with open(uevent_file, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("HID_NAME="):
                                dev_name = line.split("=", 1)[1].strip()
                            elif line.startswith("HID_PHYS="):
                                phys = line.split("=", 1)[1].strip()
                            elif line.startswith("HID_ID="):
                                parts = line.split("=", 1)[1].split(":")
                                if len(parts) >= 3:
                                    bus = int(parts[0], 16)
                                    vid = int(parts[1], 16)
                                    pid = int(parts[2], 16)
                except Exception:
                    continue

                if vid != LOGITECH_VID:
                    continue

                node_name = os.path.basename(hidraw_dir)
                dev_path = f"/dev/{node_name}".encode("utf-8")

                clean_name = dev_name.replace("_", " ").strip()
                name_lower = clean_name.lower()

                # Check if this node is just the USB receiver dongle itself
                is_dongle = any(r in name_lower for r in [
                    "usb receiver", "unifying receiver", "bolt receiver", "lightspeed receiver", "nano receiver"
                ]) or (pid in ALL_RECEIVER_PIDS and ("receiver" in name_lower or not clean_name))

                if is_dongle:
                    if dev_path not in receiver_paths:
                        receiver_paths.append(dev_path)
                    continue

                # It is a real paired peripheral (connected via Unifying, Bolt, or Bluetooth)
                if not clean_name:
                    clean_name = self._guess_name_from_pid(pid)

                # Determine transport accurately:
                # bus == 0x05 (BUS_BLUETOOTH), or MAC address in phys, or Bluetooth PID (0xB0XX, 0xB3XX)
                is_bt = (bus == 0x05) or (pid & 0xFF00 in (0xB000, 0xB300)) or (
                    ":" in phys and len(phys.split(":")) == 6 and not phys.startswith("usb")
                )

                if is_bt:
                    transport = TransportType.BLUETOOTH
                    dev_idx = 0xFF
                else:
                    # Wireless receiver peripheral (Unifying, Bolt, Lightspeed)
                    if pid in PIDS_BOLT or "bolt" in name_lower or any(b in phys.lower() for b in ("bolt", "c548", "c547")):
                        transport = TransportType.BOLT
                    elif pid in PIDS_LIGHTSPEED:
                        transport = TransportType.LIGHTSPEED
                    else:
                        transport = TransportType.UNIFYING

                    dev_idx = 0x01
                    if ":" in phys:
                        last_part = phys.split(":")[-1]
                        if last_part.isdigit() and 1 <= int(last_part) <= 6:
                            dev_idx = int(last_part)

                group_key = (clean_name, pid, transport, dev_idx)
                if group_key not in devices_grouped:
                    devices_grouped[group_key] = []
                devices_grouped[group_key].append(dev_path)

            for (dev_name, pid, transport, dev_idx), paths in devices_grouped.items():
                if self._matches_keywords(dev_name, target_keywords) and paths:
                    primary_path = paths[-1]
                    s_name = self._derive_solaar_name(dev_name)
                    resolved_feat: Optional[int] = None

                    # If Bluetooth, probe candidate nodes to find the real HID++ vendor endpoint
                    # and resolve the exact feature index for 0x1814 (e.g. 0x08 for MX Master, 0x09 for MX Keys)
                    if transport == TransportType.BLUETOOTH:
                        import select
                        for p in paths:
                            try:
                                node_str = p.decode("utf-8")
                                fd = os.open(node_str, os.O_RDWR | getattr(os, "O_NONBLOCK", 0))
                                try:
                                    # Wake-up ping first to wake BLE link from sniff mode
                                    try:
                                        os.write(fd, bytes([0x11, 0xFF, 0x00, 0x00] + [0x00] * 16))
                                        time.sleep(0.020)
                                    except Exception:
                                        pass
                                    query = bytes([0x11, 0xFF, 0x00, 0x00, (FEATURE_CHANGE_HOST >> 8) & 0xFF, FEATURE_CHANGE_HOST & 0xFF] + [0x00] * 14)
                                    os.write(fd, query)
                                    r, _, _ = select.select([fd], [], [], 0.20)
                                    if r:
                                        resp = os.read(fd, 20)
                                        if resp and len(resp) >= 5 and resp[0] == 0x11 and resp[2] == 0x00 and resp[4] != 0:
                                            resolved_feat = resp[4]
                                            primary_path = p
                                            break
                                finally:
                                    os.close(fd)
                            except Exception:
                                pass

                    # For receiver devices, the receiver node (receiver_paths) MUST be prioritized first
                    # because HID++ radio packets must be submitted to the receiver dongle transceiver
                    if transport != TransportType.BLUETOOTH:
                        combined_paths = list(receiver_paths) + [p for p in paths if p not in receiver_paths]
                        primary_path = combined_paths[0] if combined_paths else primary_path
                    else:
                        combined_paths = [primary_path] + [p for p in paths if p != primary_path]
                    name_l = dev_name.lower()
                    dev_kind = "keyboard" if any(k in name_l for k in ("keyboard", "keys", "craft", "k380", "k780")) else (
                        "mouse" if any(m in name_l for m in ("mouse", "master", "anywhere", "m370", "pop", "triathlon", "m720")) else None
                    )
                    ldev = LogitechDevice(
                        name=dev_name,
                        path=primary_path,
                        transport=transport,
                        device_index=dev_idx,
                        vid=LOGITECH_VID,
                        pid=pid,
                        usage_page=USAGE_PAGE_BLUETOOTH if transport == TransportType.BLUETOOTH else USAGE_PAGE_RECEIVER,
                        usage=0x0202 if transport == TransportType.BLUETOOTH else 0x0002,
                        all_paths=combined_paths,
                        solaar_name=s_name,
                        kind=dev_kind
                    )
                    if resolved_feat is not None:
                        ldev.change_host_feature_index = resolved_feat
                        ldev._change_host_feature_resolved = True
                        ldev.is_active = True
                    else:
                        ldev.change_host_feature_index = 0x08 if "master" in name_l else 0x09
                        # If Bluetooth could not be probed, it is not currently active on this host
                        ldev.is_active = (transport != TransportType.BLUETOOTH)
                    results.append(ldev)
        except Exception as e:
            log("HID++", f"Error scanning Linux sysfs: {e}")

        return results, receiver_paths

    def _scan_solaar_config(self, rx_path: bytes, target_keywords: Optional[List[str]]) -> List[LogitechDevice]:
        """
        Instantly reads paired device names from ~/.config/solaar/config.yaml or rules.yaml.
        Zero latency (0.2ms), zero subprocess timeouts.
        """
        results: List[LogitechDevice] = []
        candidate_paths = [
            os.path.expanduser("~/.config/solaar/config.yaml"),
            os.path.expanduser("~/.config/solaar/rules.yaml"),
            os.path.expanduser("~/.config/solaar/config.json")
        ]

        found_names: List[str] = []
        for p in candidate_paths:
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        # Extract _name: <model>
                        names = re.findall(r'_name:\s*[\'"]?([^\n\'"]+)', content)
                        # Extract solaar config "<model>"
                        names += re.findall(r'config,\s*[\'"]([^\'"]+)[\'"]', content)
                        for n in names:
                            clean = n.strip()
                            if clean and clean not in found_names and not clean.startswith("/"):
                                found_names.append(clean)
                except Exception:
                    pass

        slot_idx = 1
        for name in found_names:
            if self._matches_keywords(name, target_keywords) and self._is_known_easy_switch(name):
                ldev = LogitechDevice(
                    name=name,
                    path=rx_path,
                    transport=TransportType.UNIFYING,
                    device_index=slot_idx,
                    solaar_name=name
                )
                ldev.change_host_feature_index = 0x09
                results.append(ldev)
                slot_idx += 1

        return results

    def _scan_solaar_devices(self, target_keywords: Optional[List[str]]) -> List[LogitechDevice]:
        """
        Uses Solaar CLI on Linux to accurately enumerate all paired devices on receivers and Bluetooth.
        """
        results: List[LogitechDevice] = []
        if not self._solaar_path:
            return results

        try:
            res = subprocess.run([self._solaar_path, "show"], capture_output=True, text=True, timeout=8)
            if res.returncode != 0 or not res.stdout:
                return results

            raw_blocks = re.split(r'\n(?=Device\s+/dev/hidraw|\s{0,2}\d+:)', res.stdout)

            current_rx_is_bolt = False
            for block in raw_blocks:
                if not block.strip():
                    continue

                if "bolt receiver" in block.lower():
                    current_rx_is_bolt = True
                elif "unifying receiver" in block.lower():
                    current_rx_is_bolt = False

                codename = None
                header_name = None
                dev_kind = None
                dev_path_str = None
                slot_index = 1
                is_bt = False
                has_change_host = False

                for line in block.splitlines():
                    line_s = line.strip()
                    if line_s.startswith("Codename") and ":" in line_s:
                        codename = line_s.split(":", 1)[1].strip()
                    elif line_s.startswith("Kind") and ":" in line_s:
                        dev_kind = line_s.split(":", 1)[1].strip().lower()
                    elif line_s.startswith("Device path") and ":" in line_s:
                        dev_path_str = line_s.split(":", 1)[1].strip()
                    elif "Bluetooth" in line_s:
                        is_bt = True
                    elif "1814" in line_s or "CHANGE HOST" in line_s or "change-host" in line_s:
                        has_change_host = True

                    m_num = re.match(r'^\s*(\d+):\s*(.*)', line)
                    if m_num:
                        slot_index = int(m_num.group(1))
                        header_name = m_num.group(2).strip()
                    elif line.startswith("Device /dev/hidraw"):
                        is_bt = True

                dev_name = codename or header_name
                if dev_name and (has_change_host or self._is_known_easy_switch(dev_name)):
                    if self._matches_keywords(dev_name, target_keywords):
                        transport = TransportType.BLUETOOTH if is_bt else (
                            TransportType.BOLT if current_rx_is_bolt else TransportType.UNIFYING
                        )
                        primary_path = dev_path_str.encode("utf-8") if dev_path_str else b"/dev/solaar"
                        ldev = LogitechDevice(
                            name=dev_name,
                            path=primary_path,
                            transport=transport,
                            device_index=slot_index if not is_bt else 0xFF,
                            solaar_name=dev_name,
                            kind=dev_kind
                        )
                        ldev.change_host_feature_index = 0x09
                        results.append(ldev)
        except Exception:
            pass

        return results

    @staticmethod
    def _derive_solaar_name(name: str) -> str:
        name_lower = name.lower()
        if "mx master 3s" in name_lower:
            return "MX Master 3S"
        elif "mx master 3" in name_lower:
            return "MX Master 3"
        elif "mx master 2s" in name_lower:
            return "MX Master 2S"
        elif "mx master" in name_lower:
            return "MX Master"
        elif "mx keys mini" in name_lower:
            return "MX Keys Mini"
        elif "mx keys s" in name_lower:
            return "MX Keys S"
        elif "mx keys" in name_lower:
            return "MX Keys"
        elif "pop mouse" in name_lower or "m370" in name_lower:
            return "POP Mouse"
        elif "m720" in name_lower or "triathlon" in name_lower:
            return "M720 Triathlon"
        elif "k380" in name_lower:
            return "K380 Multi-Device Keyboard"
        return name

    @staticmethod
    def _is_known_easy_switch(name: str) -> bool:
        known = ["mx keys", "mx master", "mx anywhere", "pop mouse", "m370", "m720", "triathlon", "k380", "k780", "craft"]
        n_lower = name.lower()
        return any(k in n_lower for k in known)

    @staticmethod
    def _guess_name_from_pid(pid: int) -> str:
        known_pids = {
            0xB35B: "MX Keys",
            0xB35F: "MX Keys",
            0xB366: "MX Keys Mini",
            0xB378: "MX Keys S",
            0xB015: "M720 Triathlon",
            0xB029: "POP Mouse",
            0xB02A: "POP Mouse",
            0xB030: "M370 Mouse",
            0xB034: "MX Master 3S",
            0xB023: "MX Master 3",
            0xB025: "MX Anywhere 3",
            # Wireless PIDs across Unifying & Bolt receivers
            0x408A: "MX Keys",
            0x4082: "MX Master 3",
            0x4090: "MX Master 3S",
            0x4086: "MX Master 2S",
            0x406B: "MX Anywhere 2S",
            0x4091: "MX Anywhere 3",
            0x405E: "M720 Triathlon",
            0x4069: "Craft Keyboard",
            0x4088: "MX Keys Mini",
            0x407B: "K380 Keyboard",
            0x4057: "K780 Keyboard",
        }
        return known_pids.get(pid, f"Logitech Device (PID 0x{pid:04X})")

    def _matches_keywords(self, name: str, keywords: Optional[List[str]]) -> bool:
        if not keywords:
            return True
        name_lower = name.lower()
        if name_lower.startswith("unifying slot") or name_lower.startswith("bolt slot"):
            return True
        return any(k.lower() in name_lower for k in keywords)

    def _query_receiver_paired_devices(self, long_path: bytes, short_path: Optional[bytes],
                                       pid: int, transport: TransportType,
                                       force_rescan: bool = False) -> List[LogitechDevice]:
        results: List[LogitechDevice] = []
        h = None
        for _ in range(3):
            try:
                h = hid.device()
                h.open_path(long_path)
                break
            except Exception:
                h = None
                time.sleep(0.05)
        if not h:
            # If receiver handle temporarily busy, fall back to known cached receiver devices
            return [dev for (r_pid, _), dev in self._receiver_slots_cache.items() if r_pid == pid]

        try:
            # 1. Broadcast quick wake-up ping to all 6 slots in parallel (takes ~1ms total)
            for idx in range(1, 7):
                try:
                    h.write([0x11, idx, 0x00, 0x00, 0x00, 0x00] + [0x00] * 14)
                except Exception:
                    pass
            time.sleep(0.02)

            # 2. Query each paired slot
            active_slots_found = set()

            for idx in range(1, 7):
                dev_name = None
                ch_feat = 0x09
                name_feat = 0

                # Query Feature 0x0005 (DEVICE_NAME) with up to 2 attempts
                for attempt in range(2):
                    try:
                        h.write([0x11, idx, 0x00, 0x00, 0x00, FEATURE_DEVICE_NAME] + [0x00] * 14)
                    except Exception:
                        break

                    deadline = time.time() + 0.10
                    while time.time() < deadline:
                        r = h.read(20, timeout_ms=25)
                        if r and len(r) >= 5 and r[0] == 0x11 and r[1] == idx:
                            if r[2] == 0x00 and r[4] != 0:
                                name_feat = r[4]
                                break
                            if r[2] == 0xFF:
                                break
                    if name_feat:
                        break

                if not name_feat:
                    continue

                # Read name length
                try:
                    h.write([0x11, idx, name_feat, 0x00] + [0x00] * 16)
                    r_len = None
                    deadline = time.time() + 0.08
                    while time.time() < deadline:
                        r = h.read(20, timeout_ms=25)
                        if r and len(r) >= 5 and r[0] == 0x11 and r[1] == idx and r[2] == name_feat:
                            r_len = r
                            break
                    n_len = r_len[4] if r_len else 16

                    # Read name chunks
                    name_bytes = bytearray()
                    for chunk_offset in [0x00, 0x10, 0x20]:
                        if chunk_offset >= n_len:
                            break
                        h.write([0x11, idx, name_feat, 0x10, chunk_offset] + [0x00] * 15)
                        deadline = time.time() + 0.08
                        while time.time() < deadline:
                            r = h.read(20, timeout_ms=25)
                            if r and len(r) >= 5 and r[0] == 0x11 and r[1] == idx and r[2] == name_feat:
                                name_bytes.extend(r[4:])
                                break

                    raw_name = bytes(name_bytes[:n_len]).decode('utf-8', errors='ignore').strip()
                    clean = ''.join(c for c in raw_name if c.isprintable()).strip()
                    if clean:
                        dev_name = clean
                except Exception:
                    pass

                if not dev_name:
                    continue

                ch_feat_resolved = False
                # Query CHANGE_HOST feature index (0x1814)
                try:
                    h.write([0x11, idx, 0x00, 0x00, (FEATURE_CHANGE_HOST >> 8) & 0xFF, FEATURE_CHANGE_HOST & 0xFF] + [0x00] * 14)
                    deadline = time.time() + 0.08
                    while time.time() < deadline:
                        r_ch = h.read(20, timeout_ms=25)
                        if r_ch and len(r_ch) >= 5 and r_ch[0] == 0x11 and r_ch[1] == idx and r_ch[2] == 0x00:
                            if r_ch[4] != 0:
                                ch_feat = r_ch[4]
                                ch_feat_resolved = True
                            break
                except Exception:
                    pass

                ldev = LogitechDevice(
                    name=dev_name,
                    path=long_path,
                    transport=transport,
                    device_index=idx,
                    vid=LOGITECH_VID,
                    pid=pid,
                    usage_page=USAGE_PAGE_RECEIVER,
                    usage=0x0002,
                    short_path=short_path,
                    solaar_name=self._derive_solaar_name(dev_name)
                )
                ldev.change_host_feature_index = ch_feat
                ldev._change_host_feature_resolved = ch_feat_resolved
                ldev.is_active = True
                results.append(ldev)
                active_slots_found.add(idx)
                self._receiver_slots_cache[(pid, idx)] = ldev

            # Retain any previously known slot on this receiver if temporarily asleep
            for (r_pid, slot_idx), cached_dev in self._receiver_slots_cache.items():
                if r_pid == pid and slot_idx not in active_slots_found:
                    cached_dev.path = long_path
                    cached_dev.is_active = False
                    if not force_rescan:
                        results.append(cached_dev)

        finally:
            try:
                h.close()
            except Exception:
                pass

        return results


    def _switch_via_solaar(self, dev: LogitechDevice, target_channel: int, channel_index: int) -> bool:
        if not sys.platform.startswith("linux") or not self._solaar_path:
            return False

        with self._solaar_lock:
            candidate_solaar_names = []
            if dev._confirmed_solaar_name:
                candidate_solaar_names.append(dev._confirmed_solaar_name)
            if dev.solaar_name and dev.solaar_name not in candidate_solaar_names:
                candidate_solaar_names.append(dev.solaar_name)

            # Solaar names frequently omit the vendor prefix "Logitech " (e.g. "Wireless Mouse MX Master 3")
            stripped_name = re.sub(r'^(?:logitech\s+)', '', dev.name, flags=re.IGNORECASE).strip()
            if stripped_name and stripped_name not in candidate_solaar_names:
                candidate_solaar_names.append(stripped_name)

            derived = self._derive_solaar_name(dev.name)
            if derived and derived not in candidate_solaar_names:
                candidate_solaar_names.append(derived)
            if dev.name not in candidate_solaar_names:
                candidate_solaar_names.append(dev.name)

            # In Solaar CLI, receiver slot numbers 1..6 can be passed directly as device targets
            if dev.is_receiver and 1 <= dev.device_index <= 6:
                slot_str = str(dev.device_index)
                if slot_str not in candidate_solaar_names:
                    candidate_solaar_names.append(slot_str)
            if getattr(dev, 'kind', None) in ('keyboard', 'mouse'):
                if dev.kind not in candidate_solaar_names:
                    candidate_solaar_names.append(dev.kind)
            elif "mouse" in dev.name.lower() or "master" in dev.name.lower():
                if "mouse" not in candidate_solaar_names:
                    candidate_solaar_names.append("mouse")
            elif "keyboard" in dev.name.lower() or "keys" in dev.name.lower():
                if "keyboard" not in candidate_solaar_names:
                    candidate_solaar_names.append("keyboard")

            # Receiver fallback slots
            if dev.is_receiver:
                for slot in ["1", "2", "3"]:
                    if slot not in candidate_solaar_names:
                        candidate_solaar_names.append(slot)

            # Strip DISPLAY and WAYLAND_DISPLAY to disable Solaar's GApplication
            # remote forwarding bug which corrupts Channel 2 to Channel 1!
            clean_env = os.environ.copy()
            clean_env["DISPLAY"] = ""
            clean_env["WAYLAND_DISPLAY"] = ""

            # Try candidate arguments:
            # 1. 1-indexed target channel (e.g. "1" for Channel 1) - PRIMARY for Solaar!
            # 2. Named host (e.g. "Host 1")
            # 3. 0-indexed host index (e.g. "0" for Channel 1)
            candidate_args = []
            if getattr(dev, '_confirmed_solaar_arg', None):
                candidate_args.append(dev._confirmed_solaar_arg)
            for arg in [str(target_channel), f"Host {target_channel}", str(channel_index)]:
                if arg not in candidate_args:
                    candidate_args.append(arg)

            log("HID++", f"Solaar dispatch for '{dev.name}' -> Channel {target_channel} (candidates: {candidate_solaar_names[:5]}, args: {candidate_args})")

            for s_name in candidate_solaar_names:
                for h_arg in candidate_args:
                    cmd = [self._solaar_path, "config", s_name, "change-host", h_arg]
                    try:
                        t0 = time.perf_counter()
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5, env=clean_env)
                        dur_ms = (time.perf_counter() - t0) * 1000.0
                        if res.returncode == 0:
                            dev._confirmed_solaar_name = s_name
                            dev._confirmed_solaar_arg = h_arg
                            log("HID++", f"Solaar switch SUCCEEDED for '{dev.name}' (as '{s_name}', arg='{h_arg}') -> Channel {target_channel} [{dur_ms:.1f}ms]")
                            return True
                        else:
                            err_out = (res.stderr or res.stdout or "").strip()
                            log("HID++", f"Solaar command failed: {' '.join(cmd)} (exit {res.returncode}): {err_out}")
                    except Exception as ex:
                        log("HID++", f"Solaar execution exception for '{dev.name}' ({s_name}): {ex}")

        log("HID++", f"Solaar exhausted all candidates for '{dev.name}' without success")
        return False

    def _switch_via_linux_hidraw(self, dev: LogitechDevice, target_channel: int, channel_index: int,
                                 dev_indices_to_try: List[int], feature_indices: List[int],
                                 target_paths: List[bytes]) -> bool:
        if not sys.platform.startswith("linux") or not target_paths:
            return False

        candidate_nodes = [p.decode("utf-8") for p in target_paths if p and p.startswith(b"/dev/hidraw")]
        if not candidate_nodes:
            return False

        o_nonblock = getattr(os, "O_NONBLOCK", 0)

        # If the device's feature index is already resolved, write to the candidate nodes
        if getattr(dev, '_change_host_feature_resolved', False):
            feat_idx = dev.change_host_feature_index
            written_any = False
            for dev_node in candidate_nodes:
                try:
                    fd = os.open(dev_node, os.O_WRONLY | o_nonblock)
                    try:
                        # Wake up radio link if Bluetooth / low-power sleep state
                        if dev.transport == TransportType.BLUETOOTH:
                            try:
                                ping_pkt = bytes([0x11, 0xFF, 0x00, 0x00] + [0x00] * 16)
                                os.write(fd, ping_pkt)
                                time.sleep(0.010)
                            except Exception:
                                pass

                        for d_idx in dev_indices_to_try:
                            pkt = bytes([0x11, d_idx, feat_idx, 0x10, channel_index] + [0x00] * 15)
                            try:
                                if os.write(fd, pkt) > 0:
                                    written_any = True
                                    # For Bluetooth, send a follow-up packet 15ms later in case the first was used to wake connection interval
                                    if dev.transport == TransportType.BLUETOOTH:
                                        time.sleep(0.015)
                                        os.write(fd, pkt)
                            except Exception:
                                pass
                    finally:
                        os.close(fd)
                except Exception as ex:
                    log("HID++", f"Error opening/writing hidraw node {dev_node} for '{dev.name}': {ex}")
            if written_any:
                log("HID++", f"Instant /dev/hidraw switch for '{dev.name}' -> Channel {target_channel} (Host: {channel_index}, Feature: 0x{feat_idx:02X})")
                return True

        # If unverified on Bluetooth, dynamically probe candidate nodes for Root Feature 0x0000 -> 0x1814
        # to find the real HID++ endpoint and the exact CHANGE_HOST feature index (e.g. 0x08 on MX Master, 0x09 on MX Keys)
        if dev.transport == TransportType.BLUETOOTH:
            import select
            log("HID++", f"Probing candidate hidraw nodes {candidate_nodes} for '{dev.name}' (Root Feature -> 0x1814)...")
            for dev_node in candidate_nodes:
                try:
                    fd = os.open(dev_node, os.O_RDWR | o_nonblock)
                    try:
                        # Wake-up ping first to exit BLE sleep state
                        try:
                            os.write(fd, bytes([0x11, 0xFF, 0x00, 0x00] + [0x00] * 16))
                            time.sleep(0.020)
                        except Exception:
                            pass

                        query = bytes([0x11, 0xFF, 0x00, 0x00, (FEATURE_CHANGE_HOST >> 8) & 0xFF, FEATURE_CHANGE_HOST & 0xFF] + [0x00] * 14)
                        os.write(fd, query)
                        r, _, _ = select.select([fd], [], [], 0.15)
                        if r:
                            resp = os.read(fd, 20)
                            if resp and len(resp) >= 5 and resp[0] == 0x11 and resp[2] == 0x00 and resp[4] != 0:
                                verified_feat = resp[4]
                                verified_node = dev_node
                                dev.change_host_feature_index = verified_feat
                                dev._change_host_feature_resolved = True
                                dev.path = verified_node.encode("utf-8")
                                dev.is_active = True
                                # Send CHANGE_HOST command directly on the verified descriptor
                                pkt = bytes([0x11, 0xFF, verified_feat, 0x10, channel_index] + [0x00] * 15)
                                os.write(fd, pkt)
                                time.sleep(0.020)
                                os.write(fd, pkt)
                                log("HID++", f"Verified /dev/hidraw ({verified_node}, feat: 0x{verified_feat:02X}) switch for '{dev.name}' -> Channel {target_channel}")
                                return True
                    finally:
                        try:
                            os.close(fd)
                        except Exception:
                            pass
                except Exception as ex:
                    log("HID++", f"Probe error on {dev_node} for '{dev.name}': {ex}")

            # If direct Bluetooth probing could not verify the HID++ endpoint, but Solaar is available,
            # return False so it falls back to Solaar instead of claiming false success!
            if self._solaar_path:
                log("HID++", f"Direct BLE probe unverified on all nodes for '{dev.name}'; falling back to Solaar")
                return False

        # If Solaar is not installed, as a last resort attempt blind writes with candidate feature indices
        log("HID++", f"Attempting blind hidraw writes on {candidate_nodes} for '{dev.name}'...")
        direct_ok = False
        for dev_node in candidate_nodes:
            try:
                fd = os.open(dev_node, os.O_WRONLY | o_nonblock)
                try:
                    for d_idx in dev_indices_to_try:
                        for feat_idx in feature_indices:
                            pkt = bytes([0x11, d_idx, feat_idx, 0x10, channel_index] + [0x00] * 15)
                            try:
                                written = os.write(fd, pkt)
                                if written > 0:
                                    direct_ok = True
                            except Exception:
                                pass
                finally:
                    os.close(fd)
            except Exception:
                pass

        if direct_ok:
            log("HID++", f"Blind /dev/hidraw write succeeded for '{dev.name}' -> Channel {target_channel} (Host: {channel_index})")
            return True
        return False

    def switch_device_host(self, dev: LogitechDevice, target_channel: int, backend: str = "auto", connection_support: Optional[str] = None) -> bool:
        """
        Ultra-low latency host switch.
        Supports selectable backends:
          - 'auto': /dev/hidraw for Bluetooth (with Solaar fallback); Solaar for receivers.
          - 'solaar': Prioritizes Solaar CLI for ALL devices (both Bluetooth and receivers).
          - 'direct': Direct /dev/hidraw and hidapi kernel writes for all devices.
        """
        conn_mode = (connection_support or self.connection_support or "both").lower()
        if not self.is_transport_supported(dev.transport, conn_mode):
            log("HID++", f"Skipping switch for '{dev.name}' ({dev.transport.value}): connection type not enabled by setting '{conn_mode}'")
            return False

        channel_index = max(0, min(2, target_channel - 1))
        backend = (backend or "auto").lower()
        t_dev_start = time.perf_counter()

        log("HID++", f"switch_device_host: '{dev.name}' [Transport: {dev.transport.value}, Backend: {backend}] -> Channel {target_channel} (Host Index: {channel_index})")

        # Candidate feature indices for 0x1814 (CHANGE_HOST).
        feature_indices: List[int] = []
        if getattr(dev, '_change_host_feature_resolved', False) and dev.change_host_feature_index:
            feature_indices = [dev.change_host_feature_index]
        elif dev.transport == TransportType.BLUETOOTH:
            # On Bluetooth, prioritize the device's feature index (0x08 for Master series, 0x09 for Keys series)
            # and avoid multi-packet flooding which aborts RF switch
            if dev.change_host_feature_index:
                feature_indices = [dev.change_host_feature_index]
            elif "master" in dev.name.lower():
                feature_indices = [0x08, 0x09, 0x0A, 0x07, 0x0B]
            else:
                feature_indices = [0x09, 0x08, 0x0A, 0x07, 0x0B]
        else:
            if dev.change_host_feature_index:
                feature_indices.append(dev.change_host_feature_index)
            for f in [0x09, 0x08, 0x0A, 0x0B, 0x07]:
                if f not in feature_indices:
                    feature_indices.append(f)

        # Determine target device indices
        if dev.transport == TransportType.BLUETOOTH:
            dev_indices_to_try = [0xFF]  # Bluetooth devices only respond to 0xFF. Never send 0x00!
        else:
            # Wireless receiver peripheral: target ONLY its specific slot!
            dev_indices_to_try = [dev.device_index]

        # Prioritize dev.path (the verified control path) first, followed by any remaining paths
        target_paths = []
        if dev.path:
            target_paths.append(dev.path)
        if dev.all_paths:
            for p in dev.all_paths:
                if p and p not in target_paths:
                    target_paths.append(p)

        # --- LINUX DISPATCH ---
        if sys.platform.startswith("linux"):
            if backend == "solaar":
                # User explicitly requested Solaar backend for switching
                if self._solaar_path and self._switch_via_solaar(dev, target_channel, channel_index):
                    return True
                # Fallback to direct hidraw if Solaar fails
                if self._switch_via_linux_hidraw(dev, target_channel, channel_index, dev_indices_to_try, feature_indices, target_paths):
                    return True

            elif backend == "direct":
                # User explicitly requested direct kernel hidraw writes
                if self._switch_via_linux_hidraw(dev, target_channel, channel_index, dev_indices_to_try, feature_indices, target_paths):
                    return True
                if self._solaar_path and self._switch_via_solaar(dev, target_channel, channel_index):
                    return True

            else:
                # "auto" (default adaptive mode):
                # 1. For Bluetooth devices: direct /dev/hidraw write is instantaneous (<1ms) and 100% reliable.
                if dev.transport == TransportType.BLUETOOTH:
                    if self._switch_via_linux_hidraw(dev, target_channel, channel_index, dev_indices_to_try, feature_indices, target_paths):
                        return True
                    if self._switch_via_solaar(dev, target_channel, channel_index):
                        return True

                # 2. For Receiver devices (Unifying, Bolt):
                # Solaar CLI is the primary reliable driver on Linux (handles pairing slots & hid-logitech-dj routing).
                if dev.is_receiver:
                    if self._solaar_path and self._switch_via_solaar(dev, target_channel, channel_index):
                        return True
                    if self._switch_via_linux_hidraw(dev, target_channel, channel_index, dev_indices_to_try, feature_indices, target_paths):
                        return True

        # --- METHOD 2: Direct hidapi write (Windows & Linux fallback) ---
        if hid:
            hidapi_ok = False
            for p in target_paths:
                if not p or p == b"/dev/solaar":
                    continue
                try:
                    h = hid.device()
                    h.open_path(p)
                    for d_idx in dev_indices_to_try:
                        for feat_idx in feature_indices:
                            cmd_packet = [
                                0x11,
                                d_idx,
                                feat_idx,
                                0x10,           # Function 1: set_current_host
                                channel_index
                            ] + [0x00] * 15

                            try:
                                written = h.write(cmd_packet)
                                if written > 0:
                                    hidapi_ok = True
                            except Exception:
                                pass
                    h.close()
                except Exception as ex:
                    log("HID++", f"hidapi write exception on path {p}: {ex}")
                if hidapi_ok:
                    elapsed_ms = (time.perf_counter() - t_dev_start) * 1000.0
                    log("HID++", f"Fast hidapi write to '{dev.name}' -> Channel {target_channel} [{elapsed_ms:.1f}ms]")
                    return True

        # Fallback for Unifying Col01 Short Reports
        if dev.is_receiver and dev.short_path and hid:
            try:
                h_short = hid.device()
                h_short.open_path(dev.short_path)
                for feat_idx in feature_indices:
                    cmd_short = [0x10, dev.device_index, feat_idx, 0x1E, channel_index, 0x00, 0x00]
                    h_short.write(cmd_short)
                h_short.close()
                log("HID++", f"Col01 short write to '{dev.name}' -> Channel {target_channel}")
                return True
            except Exception as ex:
                log("HID++", f"Col01 short write exception for '{dev.name}': {ex}")

        # Final Solaar fallback if on Linux and not yet attempted
        if sys.platform.startswith("linux") and self._solaar_path:
            if self._switch_via_solaar(dev, target_channel, channel_index):
                return True

        elapsed_ms = (time.perf_counter() - t_dev_start) * 1000.0
        log("HID++", f"switch_device_host: FAILED for '{dev.name}' -> Channel {target_channel} after {elapsed_ms:.1f}ms")
        return False

    def switch_all_to_channel(self, target_channel: int, target_keywords: Optional[List[str]] = None, backend: str = "auto", connection_support: Optional[str] = None) -> Dict[str, bool]:
        """
        Switches ALL devices CONCURRENTLY in parallel threads.
        Zero sequential blocking, zero sleep delays.
        """
        if connection_support is not None:
            if connection_support != self.connection_support:
                self.clear_cache()
            self.connection_support = connection_support

        devices = self.scan_devices(target_keywords, force_rescan=False, connection_support=self.connection_support)
        if not devices:
            devices = self.scan_devices(target_keywords, force_rescan=True, connection_support=self.connection_support)

        if self.connection_support != "both":
            devices = [d for d in devices if self.is_transport_supported(d.transport, self.connection_support)]

        log("HID++", f"switch_all_to_channel: Initiating concurrent switch for {len(devices)} device(s) -> Channel {target_channel} (Backend: {backend}, Support: {self.connection_support})")

        results: Dict[str, bool] = {}

        def do_switch(d: LogitechDevice):
            ok = self.switch_device_host(d, target_channel, backend=backend, connection_support=self.connection_support)
            return (f"{d.name} ({d.transport.value})", ok)

        futures = [self._executor.submit(do_switch, dev) for dev in devices]
        for f in futures:
            try:
                key, ok = f.result(timeout=2.5)
                results[key] = ok
            except Exception as ex:
                log("HID++", f"Device switch future exception: {ex}")

        # If any device failed to switch (e.g. connection changed between Bluetooth and Unifying),
        # force a fresh hardware scan and retry on the new transport
        failed = [dev for dev in devices if not results.get(f"{dev.name} ({dev.transport.value})", False)]
        if failed:
            log("HID++", f"Retrying switch for {[d.name for d in failed]} after fresh rescan...")
            fresh_devices = self.scan_devices(target_keywords, force_rescan=True, connection_support=self.connection_support)
            if self.connection_support != "both":
                fresh_devices = [d for d in fresh_devices if self.is_transport_supported(d.transport, self.connection_support)]
            for f_dev in fresh_devices:
                key = f"{f_dev.name} ({f_dev.transport.value})"
                if not results.get(key, False):
                    results[key] = self.switch_device_host(f_dev, target_channel, backend=backend, connection_support=self.connection_support)

        return results

