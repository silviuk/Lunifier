# Lunifier 2.1.6 Release Notes

**Lunifier v2.1.6** brings critical fixes for Bluetooth device detection and switching, resolves border bounceback trigger loops, ensures 100% reliable Unifying receiver keyboard switching, and adds `--minimized` startup support at boot time.

## What's New & Improved in v2.1.6

### 1. Robust Bluetooth Device Detection & Host Switching
- **Query-Access HID Enumeration**: Fixed device discovery on Windows by opening endpoints with query access (`0`) instead of exclusive read/write access. This completely prevents OS sharing violations (`ERROR_ACCESS_DENIED` / `ERROR_SHARING_VIOLATION` from `hidbth.sys` / `mouhid.sys`).
- **BLE GATT HOGP & PID Mapping**: Full detection of Windows Bluetooth Low Energy endpoints (`{00001812-...}`) and friendly device name mapping (M720 Triathlon, MX Master 3/3S, MX Keys/Mini, K380, K780, Craft, Lift, etc.).
- **Endpoint Capability Ranking**: Top-level collections are prioritized based on vendor capabilities (`UsagePage 0xFF43`) and report lengths.
- **Multi-Tiered Win32 Write Fallback**: Implemented automatic fallback chain (`Overlapped WriteFile` -> synchronous `WriteFile` -> `HidD_SetOutputReport` -> `HidD_SetFeature`) and 20ms connection-interval repeat bursts to guarantee delivery over Bluetooth.

### 2. Edge Detector Border Bounceback Loop Prevention
- **Immediate Step-Back & Guard Arming**: Cursor is immediately repositioned 160px inward and the return guard is armed as soon as the edge trigger fires, preventing cursor pinning at border coordinates while hardware switching executes.
- **50px Deliberate Return Threshold**: Increased physical mouse movement detection threshold to 50px (`dx² + dy² > 2500`) to prevent sensor noise and hand tremors from accidentally disarming the return guard.

### 3. Unifying Receiver Keyboard Switching Reliability
- **Sequential Dongle Switching**: Replaced concurrent parallel packet transmission to the same receiver with serialized device switching and a 30ms inter-device pause, eliminating 2.4GHz RF collisions on single-radio USB dongles.
- **Dual-Report Wake Bursts**: Sends both Long Report (`0x11`) and Short Report (`0x10`) on `col01`, waking sleeping battery-saving keyboards so they switch alongside the mouse every time.

### 4. Start Minimized at Boot Time
- **`--minimized` Flag Support**: Added `--minimized` and `--daemon` command-line switches to start Lunifier silently in the system tray without showing the main window.
- **Autostart & Installer Updates**: Automatically configures the Windows autostart registry entry and installer startup task with `--minimized`.

### 5. Linux Native Libadwaita UI Parity & Visual Border Overlay
- **Advanced Tab Reorganization**: Synchronized layout with Windows v2.1.6—renamed "Connected Devices" to **"Advanced"**, moved "Edge Trigger Sensitivity" and "Hardware & Backend Options" into "Advanced", and added a dedicated "Save" button to the top header bar.
- **Visual Screen Border Indicator**: Implemented live orange border overlays (`#FF5722`, 6px thickness) with a 1.5-second auto-hide timer using non-blocking X11 `override_redirect` windows whenever adjusting the active zone percentage or monitor border edges.
- **Edge Loop Guard & Serialized Switching**: Stepped cursor 160px inward and armed return guard immediately on border trigger; serialized multi-device receiver switching with 30ms spacing; bumped return threshold to 50px.
- **Fixed Package Version**: Corrected Linux package metadata across `pyproject.toml`, `lunifier/__init__.py`, and About window to 2.1.6.

---

## Artifact Checksums (SHA-256)

| File | Description | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.1.6.exe` | Windows Inno Setup Installer | `61A57DD0371912EC2C8000CFAE7AD7494A1C773C7AEB1B9BB667D95BB7BA3F09` |
| `Lunifier-Windows-2.1.6.zip` | Windows Portable x64 | `44192E35CD7422392569E4AE7D3DBEC6F758C1F99E0B08B3C01036067A5F9C19` |
| `Lunifier-2.1.6.0.msix` | Windows Store / Enterprise MSIX | `31F96BC67A350DD757D990093EDFBBE863FE9BEEC4B003AC9DEC5EEC2D2DA731` |
| `lunifier_2.1.6_all.deb` | Debian / Ubuntu Package | `EAF5BCD04989077C5D621BCC8DEABCEDC58E1A302DD2B61350C785AF03A6465E` |
| `Lunifier-Linux-2.1.6.tar.gz` | Linux Portable Tarball | `F3B138796711B62215E2EA9CA0139AA03E3CE9192D2E8710FAFAD900BFC7E03C` |

