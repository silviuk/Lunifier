# Changelog

All notable changes to the **Lunifier** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
