"""
Feature configuration and edition detection for Lunifier Linux.
Supports full edition and '-nobtsync' edition (standalone border switching
without Bluetooth RFCOMM inter-host sync, while retaining full support for
Logitech Bluetooth keyboards and mice).
"""

import os
import sys

NO_BTSYNC: bool = (
    os.environ.get("LUNIFIER_NO_BTSYNC", "0") in ("1", "true", "True")
    or "--no-btsync" in sys.argv
    or "-nobtsync" in sys.argv
    or "nobtsync" in sys.argv[0].lower()
)
