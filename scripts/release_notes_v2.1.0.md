# Lunifier 2.1.0 Release Notes

**Lunifier v2.1.0** brings major enhancements, features, and fixes ported from the 1.0.8 line directly into the native 2.0 architecture (.NET 9 WPF on Windows 11 and GTK4 + Libadwaita on Linux).

---

## What's New in v2.1.0

### 1. Zero-Network Bluetooth-Only Timed Advertising & Filtering
- **Strictly Bluetooth RFCOMM/BLE Transport**: Operates with **zero network/Wi-Fi/LAN traffic**, providing airtight security and isolation.
- **Timed Peer Advertising**: User-triggered "Advertise Lunifier" button with configurable countdown timer (30s, 60s, 120s, 300s) that automatically disables upon timeout.
- **Strict Peer Filtering**: Scanning sends RFCOMM discovery probes and detects **only** partner PCs running Lunifier with advertising actively turned on, filtering out unrelated Bluetooth devices (phones, headphones, accessories).
- **One-Click Secure Handshake**: Automated mutual pairing handshake over Bluetooth exchanging ephemeral discovery tokens and establishing an authenticated connection.
- Synchronizes screen border alignments and bidirectional clipboard contents over the encrypted Bluetooth connection.

### 2. Global Hotkeys for Channel Switching
- Instant manual switching via global hotkeys (`Ctrl+Alt+1`, `Ctrl+Alt+2`, `Ctrl+Alt+3`) registered via Win32 `RegisterHotKey` on Windows.

### 3. System Tray & Single-Instance Process Enforcement
- **Windows System Tray**: Native `NotifyIcon` integration with minimize-to-tray on close, context menu (Open, Start/Stop Service, Exit), and double-click window restore.
- **Single-Instance Enforcement**: Global named Mutex (`Global\Lunifier_SingleInstance_Mutex`) and Event (`Global\Lunifier_ShowWindow_Event`) that restores and focuses the active window if launched a second time.

### 4. System Autostart Integration
- **Windows**: Toggle for `Software\Microsoft\Windows\CurrentVersion\Run` registry entry.
- **Linux**: Toggle for XDG autostart entry (`~/.config/autostart/lunifier.desktop`).

### 5. Unified Master Scalable Vector Graphics (SVG) Iconography
- Official circular metallic badge with diagonal communication link, indicator beads, 4-lobed orange propeller/star, and pure white core.
- Deployed across Windows WPF resources and Linux FreeDesktop `/usr/share/icons/hicolor/` scalable and all 8 mipmaps (`16x16` up to `512x512`).

### 6. Built-in About Page
- Comprehensive About tab with version 2.1.0 metadata, features overview, author, MIT license, and repository links.

---

## Package Hashes (SHA-256)

| Package | Format | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.1.0.exe` | Windows Inno Setup Installer | `CFF4F117E3031781CB990BD608B8DFDDB400D9015F3FC72A798403E288D41191` |
| `Lunifier-Windows-2.1.0.zip` | Windows Portable x64 | `AA897EAF4327DBEE284F6B27F3BAFDF694728A7C649D74C3E6F2EA77E53D9A22` |
| `Lunifier-2.1.0.0.msix` | Windows Store / Enterprise MSIX | `14FD7DC0082D3F13319ABFCBB21706A8C95931B27959133856031F415CB41461` |
| `lunifier_2.1.0_all.deb` | Debian / Ubuntu Package | `459B58EDC4FA18B7EF3F89EABA77459E3AAAA4E1C9A7F4F94D7D088D03C773E8` |
| `Lunifier-Linux-2.1.0.tar.gz` | Linux Portable Tarball | `D07C2A389D1ECE47545DEEE3406D92FFE8513B9AE098A43D6A1E3BE21FD4BF2A` |
