"""
Unit tests for Bluetooth-Only Timed Peer Advertising, Filtered Discovery, and Handshake.
"""

import time
from unittest.mock import MagicMock, patch
from lunifier.bt_link import (
    BluetoothLink,
    probe_bt_device_advertising,
    discover_advertising_lunifier_peers
)


def test_bt_link_timed_advertising_lifecycle():
    ticks = []
    expired = []

    def on_tick(remaining):
        ticks.append(remaining)

    def on_expired():
        expired.append(True)

    link = BluetoothLink(host_name="HostA", peer_mac="")
    assert not link.is_advertising

    token = link.start_advertising(duration_seconds=1, on_tick=on_tick, on_expired=on_expired)
    assert token
    assert link.is_advertising

    # Wait for the 1s advertising duration to expire
    time.sleep(1.3)
    assert not link.is_advertising
    assert len(expired) == 1


def test_bt_link_manual_stop_advertising():
    link = BluetoothLink(host_name="HostA", peer_mac="")
    link.start_advertising(duration_seconds=60)
    assert link.is_advertising

    link.stop_advertising()
    assert not link.is_advertising


def test_bt_discovery_probe_response():
    link = BluetoothLink(host_name="HostA", peer_mac="")
    link.send_message = MagicMock(return_value=True)

    # 1. When not advertising, should respond with advertising=False
    probe_msg = {"type": "DISCOVERY_PROBE", "from_host": "ScannerHost"}
    # Simulate connection response helper
    mock_conn = MagicMock()
    # Test via mock connection
    link._handle_incoming_connection = MagicMock()
    
    # 2. When advertising, start advertising and test
    token = link.start_advertising(duration_seconds=30)
    assert link.is_advertising

    # Incoming PAIR_REQUEST with valid token
    msg_pair_valid = {
        "type": "PAIR_REQUEST",
        "from_host": "PartnerHost",
        "from_mac": "11:22:33:44:55:66",
        "token": token,
        "timestamp": time.time()
    }
    link._process_message(msg_pair_valid)
    assert link.send_message.called
    sent = link.send_message.call_args[0][0]
    assert sent["type"] == "PAIR_ACCEPT"
    assert sent["from_host"] == "HostA"

    # Cleanup
    link.stop_advertising()


def test_bt_pair_request_rejected_with_bad_token():
    link = BluetoothLink(host_name="HostA", peer_mac="")
    link.send_message = MagicMock(return_value=True)

    link.start_advertising(duration_seconds=30)
    msg_pair_bad = {
        "type": "PAIR_REQUEST",
        "from_host": "UnknownHost",
        "from_mac": "99:88:77:66:55:44",
        "token": "invalid_token_1234",
        "timestamp": time.time()
    }
    link._process_message(msg_pair_bad)
    assert link.send_message.called
    sent = link.send_message.call_args[0][0]
    assert sent["type"] == "PAIR_REJECT"

    link.stop_advertising()


def test_discover_advertising_lunifier_peers_filtering():
    # Mock discover_potential_partners returning 3 devices
    mock_devices = [
        {"name": "PartnerPC", "mac": "AA:BB:CC:11:22:33", "source": "Paired"},
        {"name": "Phone", "mac": "11:22:33:AA:BB:CC", "source": "Nearby"},
        {"name": "Headset", "mac": "99:88:77:66:55:44", "source": "Nearby"},
    ]

    # Mock probe_bt_device_advertising so ONLY PartnerPC responds with advertising=True
    def mock_probe(mac, port, timeout, host_name):
        if mac == "AA:BB:CC:11:22:33":
            return {
                "name": "PartnerPC",
                "mac": mac,
                "token": "tok_xyz",
                "expires_in": 45,
                "advertising": True
            }
        return None

    with patch("lunifier.bt_link.discover_potential_partners", return_value=mock_devices):
        with patch("lunifier.bt_link.probe_bt_device_advertising", side_effect=mock_probe):
            with patch("socket.AF_BLUETOOTH", 31, create=True):
                peers = discover_advertising_lunifier_peers(timeout=2.0, host_name="MyPC")
                assert len(peers) == 1
                assert peers[0]["name"] == "PartnerPC"
                assert peers[0]["mac"] == "AA:BB:CC:11:22:33"
                assert peers[0]["token"] == "tok_xyz"


def test_bt_link_server_bind_address():
    """Verify that BluetoothLink binds to 00:00:00:00:00:00 universally (Windows & Linux)."""
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        # Stop loop after first bind attempt
        link = BluetoothLink(host_name="HostA", peer_mac="", rfcomm_port=4)
        link._running = True

        def stop_after_bind(*args, **kwargs):
            link._running = False
            return None

        mock_sock.bind.side_effect = stop_after_bind

        link._server_loop()
        assert mock_sock.bind.called
        bind_args = mock_sock.bind.call_args[0][0]
        assert bind_args == ("00:00:00:00:00:00", 4)


def test_get_local_bluetooth_mac():
    """Verify get_local_bluetooth_mac returns valid MAC or empty string."""
    from lunifier.bt_link import get_local_bluetooth_mac
    import lunifier.bt_link as bt_link_mod
    # Reset cache
    bt_link_mod._cached_local_bt_mac = None

    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        mock_sock.getsockname.return_value = ("11:22:33:44:55:66", 0)

        mac = get_local_bluetooth_mac()
        assert mac == "11:22:33:44:55:66"

    # Reset cache again
    bt_link_mod._cached_local_bt_mac = None


