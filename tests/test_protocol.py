"""
Unit tests for Bluetooth RFCOMM message protocol and serialization.
"""

import json
from lunifier.bt_link import BluetoothLink


def test_message_serialization():
    link = BluetoothLink(host_name="TestHost", peer_mac="00:11:22:33:44:55")
    
    received_msgs = []
    def on_switch(edge, ratio, clip):
        received_msgs.append((edge, ratio, clip))
        
    link.on_switch_received = on_switch

    # Simulate receiving a valid SWITCH_OUT json
    raw_json = json.dumps({
        "type": "SWITCH_OUT",
        "from_host": "PartnerHost",
        "exit_edge": "right",
        "ratio": 0.75,
        "clipboard": "Hello over Bluetooth!"
    })

    link._process_message(json.loads(raw_json))

    assert len(received_msgs) == 1
    edge, ratio, clip = received_msgs[0]
    assert edge == "right"
    assert ratio == 0.75
    assert clip == "Hello over Bluetooth!"
