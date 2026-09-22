# Lunifier 2.1.4 Release Notes

**Lunifier v2.1.4** delivers critical performance and reliability upgrades for Logitech hardware switching, non-blocking receiver device scanning, uniform UI controls layout, and Windows hostname resolution on Windows 11 native (.NET 9 WPF).

## What's New & Fixed in v2.1.4

### 1. Non-Blocking HID++ Device Scanning & Hardware Switching
- **Fixed Device Scan Hang**: Overhauled `HidppEngine` to use asynchronous Win32 Overlapped I/O with strict 75ms timeouts per slot when scanning receiver paired devices (`MI_02&Col02`). Eliminated synchronous blocking `ReadFile` kernel calls that previously froze the scanning and edge detector threads.
- **Dedicated HID++ Collection Routing**: Receiver paired device queries now route exclusively to Logitech Long Report endpoints (`UsagePage == 0xFF00 && Usage == 0x0002` / `Col02`). Short report commands are additionally sent to `Col01`. Non-HID++ collections (`MI_00`, `MI_01`) are safely filtered out.
- **Asynchronous Border Switch Dispatch**: Hardware switching from `OnEdgeTriggered` is now dispatched in background threads (`Task.Run`), ensuring the screen border detection thread never stalls or misses cursor movements.
- **Smarter Return Guard Activation**: The cursor park and return guard are now only engaged if at least one Logitech device confirms a successful switch, preventing user lockout if hardware switching fails.
- **Cooldown Clamping & Live Feedback**: Return guard duration is clamped to a maximum of 1000ms upon mouse return, and border touches during cooldown are logged in Live Logs with remaining milliseconds for full diagnostic transparency.

### 2. Windows System Hostname Default
- **Automatic Hostname Resolution**: The default hostname is now dynamically resolved from Windows (`Environment.MachineName`) instead of the hardcoded `"Host"` label, matching user expectations across P2P inter-host links.

### 3. Uniform UI Layout & Input Alignment
- **32px Control Height Standard**: Standardized all text fields (`TextBox`), dropdowns (`ComboBox`), and adjacent action buttons (`Button`) to a uniform height of `32px` with centered vertical content alignment across all tabs.
- **Multiline Log Viewer Optimization**: Preserved full adaptive scaling and text wrapping for the Live Logs box (`LogsBox`) while giving input controls clean, modern spacing.

---

## Release Artifacts & Checksums

| Package | Platform / Target | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.1.4.exe` | Windows Inno Setup Installer | `37A6C7133D144532500A33BC8287ABB92B6DB120535CF818EC809C08BC2927A5` |
| `Lunifier-Windows-2.1.4.zip` | Windows Portable x64 | `285BFBA456A4FA69E03F0B566ABEAF1170565029E874D71C28C0FBB4017E08F9` |
| `Lunifier-2.1.4.0.msix` | Windows Store / Enterprise MSIX | `C382F9FE7583813D975CF47A22A7B87854F752CDD0A3E4E90705994EA8CB3469` |
| `lunifier_2.1.4_all.deb` | Debian / Ubuntu Package | `2F2F4557D1BB7A39CED346C2B63E607FDFA091891695CD767A739ACE64F82315` |
| `Lunifier-Linux-2.1.4.tar.gz` | Linux Portable Tarball | `2A841928EF0D4E9D3AF7D9AB81B2B3E8D161AB0687D7E598DB834C39B15EC88E` |
