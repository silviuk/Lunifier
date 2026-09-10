"""
Unit tests for Lunifier v1.0.4 enhancements:
- Border Knock release state tracking
- Thicker modern border overlay (12px)
- Bluetooth peer discovery & handshake protocol
- System tray & quick switch window structures
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from lunifier.edge_detector import ScreenEdgeDetector
from lunifier.border_overlay import BorderOverlayManager
from lunifier.bt_link import BluetoothLink, discover_potential_partners
from lunifier.tray import LunifierTray, QuickSwitchWindow


def test_border_overlay_thickness():
    assert BorderOverlayManager.LINE_THICKNESS == 12
    assert BorderOverlayManager.LINE_COLOR == "#FF5722"
    assert BorderOverlayManager.BORDER_COLOR == "#D84315"
    assert BorderOverlayManager.GLOW_COLOR == "#FFE082"


def test_knock_detection_requires_release():
    triggered = []
    def on_trigger(edge, x, y, ratio, mid, ch):
        triggered.append((edge, ch))

    detector = ScreenEdgeDetector(
        trigger_edge="right",
        hold_delay_ms=50,
        knock_enabled=True,
        knock_timeout_ms=1000,
        on_trigger_callback=on_trigger
    )

    # Initial state
    assert detector.knock_enabled is True
    assert detector._last_knock_edge is None
    assert detector._knock_waiting_release is False

    # Simulate 1st knock: Cursor hits edge and dwells
    detector._last_knock_edge = "0_right"
    detector._last_knock_time = time.time()
    detector._knock_waiting_release = True

    # If cursor stays on edge, _knock_waiting_release is True, so 2nd knock cannot fire
    assert detector._knock_waiting_release is True

    # Cursor leaves edge
    detector._knock_waiting_release = False
    assert detector._knock_waiting_release is False
    assert detector._last_knock_edge == "0_right"

    # Now cursor hits edge a 2nd time within timeout -> legitimate 2nd knock!
    now = time.time()
    is_second_knock = (
        detector._last_knock_edge == "0_right" and
        not detector._knock_waiting_release and
        ((now - detector._last_knock_time) * 1000 <= detector.knock_timeout_ms)
    )
    assert is_second_knock is True


def test_bt_link_handshake_callbacks():
    accepted_requests = []
    def on_request(from_host, from_mac):
        accepted_requests.append((from_host, from_mac))
        return True

    responses = []
    def on_response(accepted, from_host, info):
        responses.append((accepted, from_host, info))

    link = BluetoothLink(
        host_name="HostA",
        peer_mac="11:22:33:44:55:66",
        on_pair_request=on_request,
        on_pair_response=on_response
    )

    # Test processing PAIR_REQUEST
    link.send_message = MagicMock(return_value=True)
    msg_req = {
        "type": "PAIR_REQUEST",
        "from_host": "HostB",
        "from_mac": "AA:BB:CC:DD:EE:FF",
        "timestamp": time.time()
    }
    link._process_message(msg_req)
    assert len(accepted_requests) == 1
    assert accepted_requests[0] == ("HostB", "AA:BB:CC:DD:EE:FF")
    link.send_message.assert_called_once()
    sent_payload = link.send_message.call_args[0][0]
    assert sent_payload["type"] == "PAIR_ACCEPT"
    assert sent_payload["from_host"] == "HostA"

    # Test processing PAIR_ACCEPT
    msg_acc = {
        "type": "PAIR_ACCEPT",
        "from_host": "HostB",
        "timestamp": time.time()
    }
    link._process_message(msg_acc)
    assert len(responses) == 1
    assert responses[0][0] is True
    assert responses[0][1] == "HostB"

    # Test processing PAIR_REJECT
    msg_rej = {
        "type": "PAIR_REJECT",
        "from_host": "HostB",
        "reason": "User declined"
    }
    link._process_message(msg_rej)
    assert len(responses) == 2
    assert responses[1][0] is False
    assert responses[1][1] == "HostB"
    assert responses[1][2] == "User declined"


def test_discover_potential_partners_structure():
    with patch("bleak.BleakScanner.discover", return_value={}):
        devices = discover_potential_partners(timeout=0.1)
        assert isinstance(devices, list)
        for d in devices:
            assert "name" in d
            assert "mac" in d
            assert "source" in d


def test_tray_initialization():
    switched = []
    def on_switch(ch, t_type):
        switched.append((ch, t_type))

    tray = LunifierTray(
        root=MagicMock(),
        on_switch_channel=on_switch,
        on_show_main=MagicMock()
    )

    # Test switch dispatch
    tray._on_quick_switch_both(2)
    time.sleep(0.05)
    assert (2, "both") in switched

    tray._on_quick_switch_device(1, "keyboard")
    time.sleep(0.05)
    assert (1, "keyboard") in switched
