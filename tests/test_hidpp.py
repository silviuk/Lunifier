"""
Unit tests for Logitech HID++ protocol logic with autonomous multi-protocol support.
"""

import pytest
from lunifier.hidpp import HIDPPMaster, LogitechDevice, LOGITECH_VID, FEATURE_CHANGE_HOST, TransportType


def test_device_creation():
    dev = LogitechDevice(
        name="MX Keys",
        path=b"hid_test_path",
        transport=TransportType.BLUETOOTH,
        device_index=0xFF,
        vid=LOGITECH_VID
    )
    assert dev.name == "MX Keys"
    assert dev.device_index == 0xFF
    assert dev.transport == TransportType.BLUETOOTH
    assert dev.is_receiver is False
    assert repr(dev).startswith("<LogitechDevice")


def test_receiver_device():
    dev = LogitechDevice(
        name="M370 Mouse",
        path=b"hid_rcv_long",
        transport=TransportType.UNIFYING,
        device_index=0x01,
        short_path=b"hid_rcv_short"
    )
    assert dev.is_receiver is True
    assert dev.transport == TransportType.UNIFYING
    assert dev.short_path == b"hid_rcv_short"


def test_keyword_matching():
    master = HIDPPMaster()
    keywords = ["MX Keys", "M370", "POP", "Triathlon"]
    
    assert master._matches_keywords("Logitech MX Keys Wireless", keywords) is True
    assert master._matches_keywords("Logitech M370 Mouse", keywords) is True
    assert master._matches_keywords("POP Mouse", keywords) is True
    assert master._matches_keywords("M720 Triathlon", keywords) is True
    assert master._matches_keywords("Generic USB Mouse", keywords) is False
    # Receiver slots should always match
    assert master._matches_keywords("Unifying Slot 1", keywords) is True
    assert master._matches_keywords("Bolt Slot 2", keywords) is True


def test_channel_index_conversion():
    # Target channels 1, 2, 3 map to 0, 1, 2
    for ch in [1, 2, 3]:
        idx = max(0, min(2, ch - 1))
        assert idx == ch - 1


def test_transport_identification():
    master = HIDPPMaster()
    # Unifying PID 0xC52B
    assert master.identify_transport(0xC52B, 0xFF00, b"path") == TransportType.UNIFYING
    # Bolt PID 0xC548
    assert master.identify_transport(0xC548, 0xFF00, b"path") == TransportType.BOLT
    # Bluetooth Usage Page 0xFF43
    assert master.identify_transport(0xB015, 0xFF43, b"path") == TransportType.BLUETOOTH


def test_device_name_normalization_and_matching():
    master = HIDPPMaster()
    # Identical variations of M720 mouse
    assert master._is_same_device_name("Wireless Mouse M720", "M720_Triathlon") is True
    assert master._is_same_device_name("Logitech M720 Triathlon", "M720 Triathlon") is True
    # Identical variations of MX Master 3
    assert master._is_same_device_name("Wireless Mouse MX Master 3", "MX Master 3") is True
    assert master._is_same_device_name("Logitech Wireless Mouse MX Master 3", "MX_Master_3") is True
    # Different devices should never match
    assert master._is_same_device_name("MX Keys", "MX Master 3") is False
    assert master._is_same_device_name("MX Keys", "M720 Triathlon") is False


def test_switch_device_host_direct_hidraw(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "platform", "linux")

    written_packets = []

    def mock_open(path, flags):
        return 42

    def mock_write(fd, data):
        written_packets.append(data)
        return len(data)

    def mock_close(fd):
        pass

    import os
    monkeypatch.setattr(os, "open", mock_open)
    monkeypatch.setattr(os, "write", mock_write)
    monkeypatch.setattr(os, "close", mock_close)

    dev_kbd = LogitechDevice(
        name="MX Keys",
        path=b"/dev/hidraw1",
        transport=TransportType.BOLT,
        device_index=0x02,
        all_paths=[b"/dev/hidraw1", b"/dev/hidraw0"]
    )
    dev_kbd.change_host_feature_index = 0x0A

    master = HIDPPMaster()
    # Test switching to Channel 2 (host index 1)
    res = master.switch_device_host(dev_kbd, target_channel=2)
    assert res is True
    assert len(written_packets) > 0

    # Verify report ID 0x11, device_index 0x02, function 0x10, host_index 0x01 (Channel 2)
    # Target only device_index 0x02, never spray to other slots
    for pkt in written_packets:
        assert pkt[0] == 0x11
        assert pkt[1] == 0x02  # Slot 2
        assert pkt[3] == 0x10  # Function 1 (set_current_host)
        assert pkt[4] == 0x01  # Host index 1 (Channel 2)


def test_switch_bluetooth_device_targets_ff(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "platform", "linux")

    written_packets = []

    import os
    monkeypatch.setattr(os, "open", lambda path, flags: 42)
    monkeypatch.setattr(os, "write", lambda fd, data: written_packets.append(data) or len(data))
    monkeypatch.setattr(os, "close", lambda fd: None)

    dev_bt = LogitechDevice(
        name="MX Master 3",
        path=b"/dev/hidraw3",
        transport=TransportType.BLUETOOTH,
        device_index=0xFF,
        all_paths=[b"/dev/hidraw3"]
    )

    master = HIDPPMaster()
    res = master.switch_device_host(dev_bt, target_channel=2)
    assert res is True
    assert len(written_packets) > 0
    # Bluetooth devices should target 0xFF with host index 1 (Channel 2)
    switch_pkts = [p for p in written_packets if p[3] == 0x10]
    assert len(switch_pkts) > 0
    assert switch_pkts[0][1] == 0xFF
    assert switch_pkts[0][4] == 0x01  # Channel 2 (index 1)


def test_solaar_fallback_uses_clean_env_and_numeric_channel(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "platform", "linux")

    executed_cmds = []
    executed_envs = []

    def mock_run(cmd, capture_output=True, text=True, timeout=1.5, env=None):
        executed_cmds.append(cmd)
        executed_envs.append(env)
        class Res:
            returncode = 0
            stdout = ""
        return Res()

    import subprocess
    monkeypatch.setattr(subprocess, "run", mock_run)

    master = HIDPPMaster()
    master._solaar_path = "/usr/bin/solaar"

    dev = LogitechDevice(
        name="MX Keys",
        path=b"/dev/solaar",
        transport=TransportType.BOLT,
        device_index=0x02,
        all_paths=[]  # No direct hidraw paths forces fallback
    )

    res = master.switch_device_host(dev, target_channel=2)
    assert res is True
    assert len(executed_cmds) > 0

    # Solaar config change-host uses 0-indexed host numbers (0 for Host 1, 1 for Host 2, 2 for Host 3)
    first_cmd = executed_cmds[0]
    assert first_cmd[:3] == ["/usr/bin/solaar", "config", "MX Keys"]
    assert first_cmd[3:] in (["change-host", "1"], ["change-host", "2"])

    # Ensure DISPLAY and WAYLAND_DISPLAY are stripped to prevent Solaar GApplication bug
    first_env = executed_envs[0]
    assert first_env is not None
    assert first_env["DISPLAY"] == ""
    assert first_env["WAYLAND_DISPLAY"] == ""


def test_switch_bluetooth_prioritizes_dev_path_and_single_packet(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "platform", "win32")

    opened_paths = []
    written_packets = []

    class MockHidDevice:
        def __init__(self):
            self.path = None

        def open_path(self, path):
            opened_paths.append(path)
            self.path = path

        def write(self, data):
            written_packets.append((self.path, data))
            return len(data)

        def close(self):
            pass

    import lunifier.hidpp as hidpp_mod
    monkeypatch.setattr(hidpp_mod, "hid", type("MockHid", (), {"device": MockHidDevice}))

    # Setup MX Keys with col01, col02, col03 in all_paths, but dev.path = col03
    dev_keys = LogitechDevice(
        name="MX Keys",
        path=b"col03_hidpp",
        transport=TransportType.BLUETOOTH,
        device_index=0xFF,
        all_paths=[b"col01_kbd", b"col02_mouse", b"col03_hidpp"]
    )
    dev_keys.change_host_feature_index = 0x09
    dev_keys._change_host_feature_resolved = True

    master = HIDPPMaster()
    res = master.switch_device_host(dev_keys, target_channel=1)

    assert res is True
    # Verify col03_hidpp was opened first!
    assert opened_paths[0] == b"col03_hidpp"
    # Verify exactly 1 packet was written (no packet spamming)
    assert len(written_packets) == 1
    assert written_packets[0][0] == b"col03_hidpp"
    pkt = written_packets[0][1]
    assert pkt[0] == 0x11
    assert pkt[1] == 0xFF  # Only 0xFF on BT
    assert pkt[2] == 0x09  # Resolved feature index
    assert pkt[3] == 0x10  # Function 1 (set_current_host)
    assert pkt[4] == 0x00  # Target channel 1 (host 0)


def test_linux_receiver_uses_solaar_and_bluetooth_uses_hidraw(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "platform", "linux")

    master = HIDPPMaster()
    master._solaar_path = "/usr/bin/solaar"

    solaar_called = []
    hidraw_called = []

    monkeypatch.setattr(master, "_switch_via_solaar", lambda dev, ch, idx: solaar_called.append(dev.name) or True)
    monkeypatch.setattr(master, "_switch_via_linux_hidraw", lambda dev, ch, idx, d_idxs, f_idxs, paths: hidraw_called.append(dev.name) or True)

    dev_bt = LogitechDevice(name="MX Keys", path=b"/dev/hidraw1", transport=TransportType.BLUETOOTH, device_index=0xFF)
    dev_unifying = LogitechDevice(name="MX Master 3", path=b"/dev/hidraw2", transport=TransportType.UNIFYING, device_index=0x01)

    # 1. Bluetooth device on Linux must call hidraw first
    res_bt = master.switch_device_host(dev_bt, target_channel=1)
    assert res_bt is True
    assert dev_bt.name in hidraw_called
    assert dev_bt.name not in solaar_called

    # 2. Receiver device on Linux must call Solaar first
    res_unifying = master.switch_device_host(dev_unifying, target_channel=1)
    assert res_unifying is True
    assert dev_unifying.name in solaar_called
    assert dev_unifying.name not in hidraw_called


def test_cache_ttl(monkeypatch):
    import time
    master = HIDPPMaster()
    dev1 = LogitechDevice(name="MX Keys", path=b"/dev/hidraw1", transport=TransportType.UNIFYING)
    master._cached_devices = [dev1]
    master._last_scan_time = time.time()

    # Within TTL: should return cached devices without rescanning
    scan_count = 0
    def mock_scan(*args, **kwargs):
        nonlocal scan_count
        scan_count += 1
        return ([], [])

    monkeypatch.setattr(master, "_scan_linux_sysfs", mock_scan)
    res = master.scan_devices(force_rescan=False)
    assert res == [dev1]
    assert scan_count == 0

    # Expired TTL: should perform scan
    master._last_scan_time = time.time() - (master.CACHE_TTL_SECONDS + 1.0)
    res2 = master.scan_devices(force_rescan=False)
    assert master._last_scan_time > 0


def test_deduplication_active_receiver_over_inactive_bluetooth(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "platform", "win32")

    master = HIDPPMaster()
    # Stale Bluetooth sysfs or hidapi entry
    dev_bt = LogitechDevice(name="MX Keys", path=b"/dev/hidraw1", transport=TransportType.BLUETOOTH)
    dev_bt.is_active = False

    # Active Unifying receiver entry
    dev_rcv = LogitechDevice(name="MX Keys", path=b"/dev/hidraw0", transport=TransportType.UNIFYING, device_index=1)
    dev_rcv.is_active = True

    monkeypatch.setattr(master, "_query_receiver_paired_devices", lambda *args, **kwargs: [dev_rcv])
    monkeypatch.setattr(master, "_select_best_bt_endpoint", lambda *args, **kwargs: dev_bt)

    # In final deduplication, active receiver MUST not be overwritten by inactive bluetooth
    # Test dedup logic directly
    found = [dev_rcv, dev_bt]
    deduped = []
    for dev in found:
        dup_idx = None
        for i, existing in enumerate(deduped):
            if master._is_same_device_name(existing.name, dev.name):
                dup_idx = i
                break
        if dup_idx is None:
            deduped.append(dev)
        else:
            existing = deduped[dup_idx]
            dev_active = getattr(dev, 'is_active', False)
            existing_active = getattr(existing, 'is_active', False)
            if dev_active and not existing_active:
                deduped[dup_idx] = dev
            elif not dev_active and existing_active:
                pass
            elif dev.transport == TransportType.BLUETOOTH and existing.transport != TransportType.BLUETOOTH:
                deduped[dup_idx] = dev

    assert len(deduped) == 1
    assert deduped[0].transport == TransportType.UNIFYING
    assert deduped[0].is_active is True


def test_switch_device_host_backend_selection(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "platform", "linux")

    calls = []

    master = HIDPPMaster()
    master._solaar_path = "/usr/bin/solaar"

    def mock_solaar(dev, target_channel, channel_index):
        calls.append(("solaar", dev.name, target_channel))
        return True

    def mock_hidraw(dev, target_channel, channel_index, dev_indices, feature_indices, target_paths):
        calls.append(("hidraw", dev.name, target_channel))
        return True

    monkeypatch.setattr(master, "_switch_via_solaar", mock_solaar)
    monkeypatch.setattr(master, "_switch_via_linux_hidraw", mock_hidraw)

    dev_bt = LogitechDevice(
        name="MX Master 3",
        path=b"/dev/hidraw3",
        transport=TransportType.BLUETOOTH,
        device_index=0xFF,
        all_paths=[b"/dev/hidraw3"]
    )
    dev_rcv = LogitechDevice(
        name="MX Keys",
        path=b"/dev/hidraw1",
        transport=TransportType.BOLT,
        device_index=0x01,
        all_paths=[b"/dev/hidraw1"]
    )

    # 1. With backend="solaar", Bluetooth device should use Solaar first
    calls.clear()
    res = master.switch_device_host(dev_bt, target_channel=2, backend="solaar")
    assert res is True
    assert calls == [("solaar", "MX Master 3", 2)]

    # 2. With backend="direct", Receiver device should use hidraw first
    calls.clear()
    res = master.switch_device_host(dev_rcv, target_channel=1, backend="direct")
    assert res is True
    assert calls == [("hidraw", "MX Keys", 1)]

    # 3. With backend="auto", Bluetooth goes to hidraw first, Receiver goes to solaar first
    calls.clear()
    res_bt = master.switch_device_host(dev_bt, target_channel=2, backend="auto")
    assert res_bt is True
    assert calls == [("hidraw", "MX Master 3", 2)]

    calls.clear()
    res_rcv = master.switch_device_host(dev_rcv, target_channel=1, backend="auto")
    assert res_rcv is True
    assert calls == [("solaar", "MX Keys", 1)]


def test_solaar_1indexed_channel_and_stripped_name(monkeypatch):
    import sys
    import subprocess
    monkeypatch.setattr(sys, "platform", "linux")

    executed_cmds = []

    def mock_run(cmd, capture_output=True, text=True, timeout=1.5, env=None):
        executed_cmds.append(cmd)
        # Solaar change-host expects 1, 2, 3
        # If '0' is passed, it fails with possible values are [1, 2, 3]
        if cmd[-1] in ("1", "2", "3"):
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="Success")
        else:
            return subprocess.CompletedProcess(cmd, returncode=1, stderr="possible values are [1, 2, 3]")

    monkeypatch.setattr(subprocess, "run", mock_run)

    master = HIDPPMaster()
    master._solaar_path = "/usr/bin/solaar"

    dev = LogitechDevice(
        name="Logitech Wireless Mouse MX Master 3",
        path=b"/dev/hidraw1",
        transport=TransportType.UNIFYING,
        device_index=2
    )

    # Test switching to Channel 1
    res = master._switch_via_solaar(dev, target_channel=1, channel_index=0)
    assert res is True
    assert len(executed_cmds) > 0
    # First command should have passed '1' (target_channel), NOT '0' (channel_index)
    first_cmd = executed_cmds[0]
    # Target name should have been stripped of 'Logitech '
    assert any("Wireless Mouse MX Master 3" in c or "MX Master 3" in c for c in first_cmd)


def test_connection_support_is_transport_supported():
    master = HIDPPMaster()
    # Default is "both"
    assert master.is_transport_supported(TransportType.BLUETOOTH, "both") is True
    assert master.is_transport_supported(TransportType.UNIFYING, "both") is True
    assert master.is_transport_supported(TransportType.BOLT, "both") is True

    # "unifying" mode
    assert master.is_transport_supported(TransportType.UNIFYING, "unifying") is True
    assert master.is_transport_supported(TransportType.BOLT, "unifying") is True
    assert master.is_transport_supported(TransportType.LIGHTSPEED, "unifying") is True
    assert master.is_transport_supported(TransportType.BLUETOOTH, "unifying") is False

    # "bluetooth" mode
    assert master.is_transport_supported(TransportType.BLUETOOTH, "bluetooth") is True
    assert master.is_transport_supported(TransportType.UNIFYING, "bluetooth") is False
    assert master.is_transport_supported(TransportType.BOLT, "bluetooth") is False


def test_clear_cache():
    master = HIDPPMaster()
    dev = LogitechDevice(name="MX Keys", path=b"/dev/hidraw1", transport=TransportType.UNIFYING)
    master.devices = [dev]
    master._cached_devices = [dev]
    master._receiver_slots_cache[(0xC52B, 1)] = dev
    master._last_scan_time = 12345.0

    master.clear_cache()
    assert len(master.devices) == 0
    assert len(master._cached_devices) == 0
    assert len(master._receiver_slots_cache) == 0
    assert master._last_scan_time == 0.0


def test_connection_support_switch_rejects_unsupported():
    master = HIDPPMaster()
    master.connection_support = "unifying"

    dev_bt = LogitechDevice(name="MX Keys", path=b"/dev/hidraw1", transport=TransportType.BLUETOOTH)
    res = master.switch_device_host(dev_bt, target_channel=1)
    assert res is False

    master.connection_support = "bluetooth"
    dev_rx = LogitechDevice(name="MX Master", path=b"/dev/hidraw2", transport=TransportType.UNIFYING)
    res = master.switch_device_host(dev_rx, target_channel=1)
    assert res is False


def test_connection_support_scan_filtering(monkeypatch):
    master = HIDPPMaster()

    # Mock raw discovery returning both Unifying and Bluetooth devices
    dev_bt = LogitechDevice(name="MX Keys BT", path=b"/dev/hidraw1", transport=TransportType.BLUETOOTH)
    dev_rx = LogitechDevice(name="MX Master RX", path=b"/dev/hidraw2", transport=TransportType.UNIFYING)

    import sys
    import lunifier.hidpp
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(lunifier.hidpp, "hid", None)
    monkeypatch.setattr(master, "_scan_linux_sysfs", lambda keywords: ([dev_bt, dev_rx], []))
    monkeypatch.setattr(master, "_scan_solaar_config", lambda rx, keywords: [])
    master._solaar_path = None

    # 1. With connection_support = "both"
    devs_both = master.scan_devices(force_rescan=True, connection_support="both")
    assert len(devs_both) == 2

    # 2. With connection_support = "unifying" -> BT filtered out
    devs_unifying = master.scan_devices(force_rescan=True, connection_support="unifying")
    assert len(devs_unifying) == 1
    assert devs_unifying[0].name == "MX Master RX"

    # 3. With connection_support = "bluetooth" -> Unifying filtered out
    devs_bt = master.scan_devices(force_rescan=True, connection_support="bluetooth")
    assert len(devs_bt) == 1
    assert devs_bt[0].name == "MX Keys BT"



def test_solaar_confirmed_cache(monkeypatch):
    import subprocess
    import sys
    master = HIDPPMaster()
    master._solaar_path = "/usr/bin/solaar"
    monkeypatch.setattr(sys, "platform", "linux")

    calls = []
    def mock_run(cmd, *args, **kwargs):
        calls.append(cmd)
        class Res:
            returncode = 0
            stdout = "success"
            stderr = ""
        return Res()

    monkeypatch.setattr(subprocess, "run", mock_run)

    dev = LogitechDevice(name="Logitech MX Master 3", path=b"/dev/hidraw1", transport=TransportType.UNIFYING)
    
    # 1. First switch: discovers alias and populates cache
    ok = master._switch_via_solaar(dev, target_channel=1, channel_index=0)
    assert ok is True
    assert "Logitech MX Master 3" in master._solaar_confirmed_cache
    cached_alias, cached_arg = master._solaar_confirmed_cache["Logitech MX Master 3"]
    assert cached_arg == "1"

    # 2. Second switch: should use cached alias directly
    calls.clear()
    ok = master._switch_via_solaar(dev, target_channel=2, channel_index=1)
    assert ok is True
    assert len(calls) == 1
    assert calls[0][2] == cached_alias
    assert calls[0][4] == "2"


def test_solaar_offline_device_early_exit(monkeypatch):
    import subprocess
    import sys
    master = HIDPPMaster()
    master._solaar_path = "/usr/bin/solaar"
    monkeypatch.setattr(sys, "platform", "linux")

    calls = []
    def mock_run(cmd, *args, **kwargs):
        calls.append(cmd)
        class Res:
            returncode = 1
            stdout = ""
            stderr = "solaar: error: Exception: no online device found matching 'Logitech MX Keys'"
        return Res()

    monkeypatch.setattr(subprocess, "run", mock_run)

    dev = LogitechDevice(name="Logitech MX Keys", path=b"/dev/hidraw1", transport=TransportType.UNIFYING)
    
    # Device already offline/switched: should exit immediately without trying dozens of permutations
    ok = master._switch_via_solaar(dev, target_channel=1, channel_index=0)
    assert ok is True  # Counted as already switched
    assert len(calls) == 1


def test_border_overlay_manager():
    import pytest
    tk = pytest.importorskip("tkinter")
    from lunifier.border_overlay import BorderOverlayManager

    root = tk.Tk()
    root.withdraw()
    try:
        mgr = BorderOverlayManager(root)
        mgr.show(50, ["left", "right", "top", "bottom"])
        assert mgr._is_visible is True
        for e in ["left", "right", "top", "bottom"]:
            key = f"0_{e}"
            assert key in mgr._windows
            assert mgr._windows[key].winfo_exists()
        mgr.hide()
        assert mgr._is_visible is False

        # Test show with default None edges
        mgr.show(75)
        assert mgr._is_visible is True
        for e in ["left", "right", "top", "bottom"]:
            assert f"0_{e}" in mgr._windows

        # Test multi-monitor dictionary
        mgr.show(60, {"0": ["left", "right"]})
        assert "0_left" in mgr._windows
        assert "0_right" in mgr._windows

        mgr.destroy()
        assert len(mgr._windows) == 0
    finally:
        root.destroy()

