# Lunifier 2.0 Protocol Specification

## 1. Logitech HID++ 2.0 Change Host (Feature 0x1814)

### Report Structure
Logitech devices support HID++ 2.0 long reports (20 bytes, Report ID `0x11`):
```
[0x11, <device_index>, <feature_index>, <function_id | sw_id>, <param0>, <param1>, ...]
```
- **Report ID**: `0x11` (Long Report - 20 bytes)
- **Device Index**:
  - `0xFF`: Direct Bluetooth / BLE connections
  - `0x01` - `0x06`: Wireless receiver (Unifying / Bolt / Lightspeed) paired slot indices
- **Feature Index**:
  - Dynamically discovered via Root Feature (`0x0000`) query for Feature ID `0x1814` (`CHANGE_HOST`).
  - Standard defaults: `0x09` (MX Keys series), `0x08` (MX Master series), `0x0A`, `0x0B`.
- **Function ID / Software ID**:
  - Function `0x10`: `set_current_host`
- **Parameter 0**:
  - Target host index: `0` (Channel 1), `1` (Channel 2), `2` (Channel 3).

### Short Report Fallback (Unifying Col01)
Report ID `0x10` (7 bytes):
```
[0x10, <device_index>, <feature_index>, 0x1E, <host_index>, 0x00, 0x00]
```

---

## 2. Inter-Host Bluetooth RFCOMM P2P Protocol

- **Transport**: Win32 Winsock `AF_BTH` / Linux BlueZ `AF_BLUETOOTH`
- **Protocol**: `SOCK_STREAM`, RFCOMM Channel (default: `4`)
- **Encoding**: UTF-8 encoded JSON strings delimited by newline `\n`

### Messages

#### SWITCH_OUT
Sent by the departing host when the cursor dwells at or crosses an active border:
```json
{
  "type": "SWITCH_OUT",
  "from_host": "HostA",
  "exit_edge": "right",
  "ratio": 0.52,
  "clipboard": "optional copied text",
  "timestamp": 1725960000.123
}
```
Receiving host repositions cursor at the corresponding entry edge (e.g. `left` with ratio `0.52`) and updates clipboard if enabled.
