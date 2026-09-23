# Lunifier 2.1.6 Release Notes

**Lunifier v2.1.6** brings comprehensive feature parity, critical reliability fixes, and layout synchronization across Windows and Linux.

## What's New & Improved in v2.1.6 (Windows & Linux)

### 1. Bluetooth Low Energy & Direct Bluetooth Device Switching
- **Windows**: Fixed device discovery by opening HID endpoints with query access (`0`) instead of exclusive access, eliminating `ERROR_ACCESS_DENIED` and `ERROR_SHARING_VIOLATION` from Windows `hidbth.sys` / `mouhid.sys`. Added full recognition of Bluetooth Low Energy GATT paths (`{00001812-...}`) and prioritized vendor TLCs (`UsagePage 0xFF43`). Implemented multi-tiered Win32 write fallback (`Overlapped WriteFile` -> synchronous `WriteFile` -> `HidD_SetOutputReport` -> `HidD_SetFeature`) and 20ms connection-interval repeat bursts.
- **Linux**: Enhanced direct Bluetooth and `/dev/hidraw` device handling.
- **Both**: Added friendly device PID name mapping (M720 Triathlon, MX Master 3/3S, MX Keys/Mini, K380, K780, Craft, Lift, etc.).

### 2. Edge Detector Border Bounceback Loop Prevention
- **Immediate Inward Stepping & Guard Arming**: Cursor is immediately repositioned 160px inward and the return guard is armed as soon as the edge trigger fires before asynchronous hardware switching completes, preventing cursor pinning at border coordinates while hardware responds.
- **50px Deliberate Return Threshold**: Increased physical mouse movement detection threshold to 50px (`dx² + dy² > 2500`) to prevent sensor noise and hand tremors from accidentally disarming the return guard.

### 3. Unifying & Bolt Receiver Keyboard Switching Reliability
- **Sequential Dongle Switching**: Replaced concurrent parallel packet transmission to the same receiver with serialized device switching and a 30ms inter-device pause, eliminating 2.4GHz RF packet collisions on single-radio USB dongles.
- **Dual-Report Wake Bursts**: Sends both Long Report (`0x11`) and Short Report (`0x10`) on `col01`, waking sleeping battery-saving keyboards so they switch alongside the mouse every time.

### 4. Start Minimized at Boot / Login
- **Windows**: Added `--minimized` command-line switch support to start Lunifier silently in the system tray without showing the main window. Updated autostart registry configuration and Inno Setup installer tasks.
- **Linux**: Added `--minimized` and `--daemon` argument handling in launcher, and updated `~/.config/autostart/lunifier.desktop` to launch minimized on desktop login.

### 5. Modern Native UI & Layout Synchronization
- **Advanced Tab Reorganization**: Synchronized layout across Windows and Linux—renamed "Connected Devices" to **"Advanced"**, moved "Edge Trigger Sensitivity" and "Hardware & Logging Options" into "Advanced", and added a dedicated "Save" button to the top header row.
- **Visual Screen Border Indicator**: Implemented live orange border overlays (`#FF5722`, 6px thickness) with a 1.5-second auto-hide timer whenever adjusting the active zone percentage slider, changing border edge assignments, selecting a monitor, or saving configuration (WPF canvas overlay on Windows, non-blocking X11 `override_redirect` windows on Linux).
- **Package Version Parity**: Synchronized all Windows (`Lunifier.Windows.csproj`, `AppxManifest.xml`, `installer.iss`) and Linux (`pyproject.toml`, `lunifier/__init__.py`, About window) project files to 2.1.6.

---

## Artifact Checksums (SHA-256)

| File | Description | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.1.6.exe` | Windows Inno Setup Installer | `61A57DD0371912EC2C8000CFAE7AD7494A1C773C7AEB1B9BB667D95BB7BA3F09` |
| `Lunifier-Windows-2.1.6.zip` | Windows Portable x64 | `44192E35CD7422392569E4AE7D3DBEC6F758C1F99E0B08B3C01036067A5F9C19` |
| `Lunifier-2.1.6.0.msix` | Windows Store / Enterprise MSIX | `CC0FBA98A08DC8FD79E4F1D8967569509E235EB0F8654D06B4EF2434667770BE` |
| `lunifier_2.1.6_all.deb` | Debian / Ubuntu Package | `EAF5BCD04989077C5D621BCC8DEABCEDC58E1A302DD2B61350C785AF03A6465E` |
| `Lunifier-Linux-2.1.6.tar.gz` | Linux Portable Tarball | `F3B138796711B62215E2EA9CA0139AA03E3CE9192D2E8710FAFAD900BFC7E03C` |


