# Changelog

All notable changes to the **Lunifier** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.2] - 2026-09-22

### Added
- **Over-the-Air Live BLE Advertisement Broadcaster & Watcher**:
  - Implemented live Bluetooth Low Energy (BLE) advertisement packets containing Lunifier beacon data (magic `LUNI`, protocol version, RFCOMM channel, Classic BT MAC, ephemeral token, host name).
  - Built-in on Windows via native WinRT `BluetoothLEAdvertisementPublisher` and `BluetoothLEAdvertisementWatcher` (.NET 9 Win10/11 projection).
  - Built-in on Linux via BlueZ `bluetoothctl` / D-Bus.
  - Enables advertising hosts to be discovered over the air instantly by scanning hosts without prior pairing.
- **Dynamic RFCOMM Port Allocation & Port Auto-Binding Fallback**:
  - Automatically detects available RFCOMM channels and binds to candidate ports in range `[preferred, 5..30]`.
  - Gracefully recovers if port 4, 7, or any other port is reserved or in use by another application or the Windows Bluetooth stack (`[WinError 10048]` / `10013`).
  - Automatically migrates legacy config from port 4 to port 5.
  - Discovery beacon and RFCOMM probe replies report the actual bound listening port; pairing clients automatically connect to and save the target's reported port.

### Fixed
- **Bluetooth Server Bind Log Spam**:
  - Eliminated periodic 5-second `Bluetooth link server bind error: [WinError 10048]` log spam by automatically selecting an available port on startup.
- **Window Sizing on Windows and Linux**:
  - Increased default window dimensions (Windows: 780x1020, Linux: 780x980) so all configuration cards and bottom action buttons fit comfortably without vertical squeezing.

---

## [2.1.1] - 2026-09-22

### Added
- **Local Bluetooth Address Field & 1-Click Copy Across Windows & Linux Native**:
  - Added a copyable entry field showing the local machine's primary Bluetooth adapter MAC address directly in the "Host A: Advertise This Computer" card.
  - Implemented in Windows C# .NET 9 (`BluetoothPeer.GetLocalBluetoothMac()`) via native Winsock socket bind and in Linux GTK4/Adwaita via sysfs and `bluetoothctl list`.
  - Added a `Copy` button with 1-click clipboard integration and visual feedback (`✓ Copied`).

### Fixed
- **Windows Bluetooth RFCOMM Server Socket Bind**:
  - Universally bound the RFCOMM server socket to `"00:00:00:00:00:00"` (`BDADDR_ANY`), completely eliminating the `bad bluetooth address` Winsock error and periodic retry loop log spam.
- **Window Sizing & Responsive Content Fitting**:
  - Increased default window height to `980` on Windows and `920` on Linux, ensuring full visibility of the bottom action buttons ("Test Switch Channel Now", "Save Configuration") without vertical squeezing across various display scaling factors.

### Changed
- **Bluetooth Quick Pairing & Settings UX Clarity**:
  - Clarified UI cards into "Host A: Advertise This Computer (Quick Pair)", "Host B: Find & Link Advertising Computer (Quick Pair)", and "Peer Link Status & Settings (Zero Network Bluetooth)".
  - Added explicit instructions distinguishing the automated 1-click Quick Pairing wizard from the persistent underlying RFCOMM link configuration and manual fallback handshake.

---

## [2.1.0] - 2026-09-22

### Added
- **Native Zero-Network Bluetooth-Only Timed Advertising & Filtering**:
  - Exclusively Bluetooth RFCOMM/BLE transport with **zero network/Wi-Fi/LAN traffic**.
  - **Timed Peer Advertising**: User-triggered "Advertise Lunifier" with live countdown timer (30s, 60s, 120s, 300s) that automatically disables upon timeout.
  - **Strict Peer Filtering**: Scanning sends Bluetooth RFCOMM discovery probes and detects **only** partner PCs running Lunifier that currently have "Advertise Lunifier" active, filtering out unrelated phones, headsets, and other Bluetooth devices.
  - **One-Click Secure Handshake**: Automated mutual pairing handshake over Bluetooth exchanging host names, tokens, and establishing an authenticated session.
  - Implemented in native C# / .NET 9 (`BluetoothPeer.cs`) on Windows and Python / Libadwaita (`bt_link.py`) on Linux.
- **Global Hotkeys**:
  - Global system hotkeys (`Ctrl+Alt+1`, `Ctrl+Alt+2`, `Ctrl+Alt+3`) for instant manual channel switching on Windows via Win32 `RegisterHotKey`.
- **System Tray Integration**:
  - Windows `NotifyIcon` system tray integration with minimize-to-tray on close, context menu (Open, Start/Stop Service, Exit), and double-click restore.
- **Single-Instance Process Enforcement**:
  - Named Mutex (`Global\Lunifier_SingleInstance_Mutex`) and Event (`Global\Lunifier_ShowWindow_Event`) restoring and focusing existing window when launched a second time.
- **System Autostart Integration**:
  - Native Windows Registry `Run` autostart toggle in settings.
  - Native Linux XDG autostart (`~/.config/autostart/lunifier.desktop`) toggle.
- **Unified Master Scalable Vector Graphics (SVG)**:
  - Official vector icon (`icon.svg`) with circular metallic badge, 4-lobed orange propeller/star, communication beads, and pure white core.
  - Deployed across Windows WPF resources and Linux FreeDesktop `/usr/share/icons/hicolor/` scalable and all 8 mipmaps (`16x16` through `512x512`).
- **About Tab & Dialog**:
  - Comprehensive About page with version 2.1.0 metadata, features overview, author, MIT license, and repository links.
- **Native 2.1 Packages**:
  - Windows Inno Setup installer: `Lunifier-Setup-2.1.0.exe`
  - Windows Portable: `Lunifier-Windows-2.1.0.zip`
  - Windows Store MSIX: `Lunifier-2.1.0.0.msix`
  - Linux Debian package: `lunifier_2.1.0_all.deb`
  - Linux Portable: `Lunifier-Linux-2.1.0.tar.gz`

---

## [2.0.1] - 2026-09-10

### Added
- Initial native architecture release:
  - Native .NET 9 WPF engine for Windows 11 with zero Python dependency.
  - Native GTK4 + Libadwaita engine for Ubuntu 24.04+ GNOME.
  - Multi-monitor border switching with edge knock detection.

---

## [1.0.8] - 2026-09-21

### Changed
- Unified Scalable Vector Graphics iconography across Windows and Linux.
- Linux Python typing compatibility fixes (`NameError: name 'Dict' is not defined`).
