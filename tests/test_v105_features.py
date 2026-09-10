"""
Unit tests for Lunifier v1.0.5 features:
- Autostart configuration
- Single-instance IPC management
- Global Hotkey management
- Configuration persistence
"""

import os
import sys
import tempfile
import pytest

from lunifier.config import AppConfig
from lunifier.single_instance import SingleInstanceManager
from lunifier.hotkeys import GlobalHotKeyManager
from lunifier.autostart import is_autostart_enabled, set_autostart_enabled


def test_v105_config_defaults():
    cfg = AppConfig()
    assert hasattr(cfg, "autostart_enabled")
    assert cfg.autostart_enabled is False
    assert hasattr(cfg, "tray_double_click_action")
    assert cfg.tray_double_click_action == "open_gui"
    assert hasattr(cfg, "hotkeys_enabled")
    assert cfg.hotkeys_enabled is True
    assert cfg.hotkey_ch1 == "<ctrl>+<alt>+1"
    assert cfg.hotkey_ch2 == "<ctrl>+<alt>+2"
    assert cfg.hotkey_ch3 == "<ctrl>+<alt>+3"


def test_v105_config_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_file = os.path.join(tmpdir, "config.json")
        cfg = AppConfig(
            autostart_enabled=True,
            tray_double_click_action="switch_2",
            hotkeys_enabled=False,
            hotkey_ch1="<ctrl>+<shift>+1"
        )
        cfg.save(cfg_file)

        loaded = AppConfig.load(cfg_file)
        assert loaded.autostart_enabled is True
        assert loaded.tray_double_click_action == "switch_2"
        assert loaded.hotkeys_enabled is False
        assert loaded.hotkey_ch1 == "<ctrl>+<shift>+1"


def test_single_instance_ipc():
    received = []

    def on_cmd(cmd: str):
        received.append(cmd)

    # Primary instance on test port
    test_port = 42435
    inst1 = SingleInstanceManager(port=test_port, on_command=on_cmd)
    assert inst1.acquire() is True

    # Secondary instance attempts to acquire same port
    inst2 = SingleInstanceManager(port=test_port)
    assert inst2.acquire() is False

    # Secondary sends IPC command to primary
    assert inst2.send_command("SHOW") is True
    assert inst2.send_command("SWITCH:2") is True

    import time
    time.sleep(0.1)

    assert "SHOW" in received
    assert "SWITCH:2" in received

    inst1.release()
    inst2.release()


def test_hotkeys_lifecycle():
    switched = []

    def on_switch(ch: int):
        switched.append(ch)

    mgr = GlobalHotKeyManager(on_switch_channel=on_switch)
    # Test manual trigger callback
    mgr._on_hotkey_triggered(2)
    assert switched == [2]

    # Test clean start/stop
    mgr.start("<ctrl>+<alt>+1", "<ctrl>+<alt>+2", "<ctrl>+<alt>+3")
    mgr.stop()
    assert mgr._listener is None


def test_autostart_functions():
    # Calling is_autostart_enabled should return a boolean without throwing
    val = is_autostart_enabled()
    assert isinstance(val, bool)
