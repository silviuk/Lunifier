# Changelog

All notable changes to the **Lunifier** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.9] - 2026-09-22

### Added
- **Local Bluetooth Address Field & 1-Click Copy**:
  - Added a copyable entry field showing the local machine's primary Bluetooth adapter MAC address directly in the "Host A: Advertise This Computer" card.
  - Added a `📋 Copy Address` button with clipboard integration and visual feedback (`✓ Copied`).
  - Added a `🔄` adapter refresh button and implemented universal local Bluetooth MAC resolution across Windows (Winsock socket bind) and Linux (sysfs `/sys/class/bluetooth/hci*/address` and `bluetoothctl list`).

### Fixed
- **Windows Bluetooth RFCOMM Server Socket Bind**:
  - Resolved `bad bluetooth address` error on Windows Winsock by universally binding to `"00:00:00:00:00:00"` (`BDADDR_ANY`) instead of an empty string.
  - Eliminated the periodic 5-second server retry loop log spam and enabled reliable discovery probe detection and pairing between peer hosts.
- **Window Sizing & Layout Responsive Optimization**:
  - Made default window geometry dynamically scale to `780x1020` on both Windows and Linux, fitting comfortably without exceeding available screen heights.
  - Wrapped the Bluetooth Inter-Host Link page in a `CTkScrollableFrame` so content scrolls smoothly on smaller screens and displays with DPI scaling, completely preventing the "Test Switch Channel Now" and "Save Configuration" buttons from being squeezed or clipped.

### Changed
- **Bluetooth Pairing & Link Configuration Clarity**:
  - Clarified UI cards into "Host A: Advertise This Computer (Quick Pair)", "Host B: Find & Link Advertising Computer (Quick Pair)", and "Peer Link Status & Settings (Zero Network Bluetooth)".
  - Added explicit instructions distinguishing the automated 1-click Quick Pairing wizard from the persistent underlying RFCOMM link configuration and manual fallback handshake.

---

## [1.0.8] - 2026-09-21

### Changed
- **Unified Scalable Vector Graphics Iconography Across Windows & Linux**:
  - Replaced the mismatched Linux icon with the official Lunifier icon from the Windows package.
  - Recreated the icon as a master Scalable Vector Graphics (SVG) vector asset (`lunifier/resources/icon.svg`) featuring the metallic dark circular badge, diagonal inter-host communication link with status indicator beads, 4-lobed orange propeller/star, and pure white center.
  - Deployed full multi-resolution mipmap suite (`16x16` up to `512x512`) and scalable SVG into Linux FreeDesktop hicolor theme paths (`/usr/share/icons/hicolor/scalable/apps/lunifier.svg`, `/usr/share/pixmaps/`) and `lunifier.desktop`.
  - Upgraded `lunifier.icons.render_scalable_icon()` with native vector SVG rasterization (`resvg_py`/`cairosvg`) and high-fidelity fallback rendering across high-DPI displays.

### Fixed
- **Linux Python Typing Compatibility**:
  - Resolved `NameError: name 'Dict' is not defined` during module initialization (`lunifier.app`) on Python 3.10–3.12 (standard Debian/Ubuntu distributions).
  - Added `from __future__ import annotations` and explicit imports for `Dict, Any, List` in `lunifier.app`.
  - Added automated type annotation inspection test in build and test validation suite to prevent regression across all Python runtime versions.
- **File Encoding**:
  - Removed unintended UTF-8 BOM (`\xef\xbb\xbf`) prefix from `lunifier/logger.py`.

---

## [1.0.7] - 2026-09-20

### Added
- **Scalable Vector Graphics Icon Pipeline**:
  - Implemented mathematical vector rendering with supersampled anti-aliasing and CairoSVG rasterization in `lunifier.icons`.
  - Added multi-resolution mipmap caching (`16px`, `24px`, `32px`, `48px`, `64px`, `128px`, `256px`, `512px`).
  - High-DPI display scaling support for window title bars, OS taskbars, Alt+Tab previews, and system tray across Windows and Linux.
- **Bluetooth-Only Timed Peer Discovery & Linking**:
  - Strictly Bluetooth RFCOMM/BLE transport with **zero network/Wi-Fi/LAN traffic**.
  - **Timed Peer Advertising**: User-triggered **"Advertise Lunifier"** mode with live countdown timer (30s, 60s, 120s, 300s) that automatically disables upon timeout.
  - **Strict Peer Filtering**: Scanning sends Bluetooth RFCOMM discovery probes and detects **only** partner PCs running Lunifier that currently have "Advertise Lunifier" active, filtering out unrelated phones, headsets, and other Bluetooth devices.
  - **One-Click Secure Handshake**: Automated mutual pairing handshake over Bluetooth verifying ephemeral discovery tokens and establishing an authenticated session.
  - **Inter-Host Sync**: Synchronizes cursor border alignments and bidirectional clipboard contents over the encrypted Bluetooth connection.
- **Unit Test Coverage**: Added `tests/test_scalable_icons.py` and `tests/test_bt_advertising.py` (64 passing unit tests).

---

## [1.0.6] - 2026-09-14

### Added
- **Unified Branding & Master Iconography**:
  - Official Lunifier star-squircle logo unified across Windows, Linux, dialogs, tray, and taskbar.
  - Windows `AppUserModelID` registration (`silviuk.lunifier.app.1.0`) preventing taskbar icon fallback.
  - Quick Switch mini window popup branded icon.
- **Store & WinGet Automation**:
  - Automated deployment workflow `.github/workflows/publish-store-and-winget.yml`.
  - Microsoft Store Partner Center integration.
  - Official WinGet manifest submission to `microsoft/winget-pkgs#434714`.

---

## [1.0.5] - 2026-09-10

### Added
- System autostart integration for Windows Run Registry and Linux XDG autostart (`~/.config/autostart/`).
- Native Ayatana / AppIndicator3 tray support on Ubuntu GNOME.
- Responsive dark/light theme adaptation matching system appearance.
- Non-blocking inline notification banners replacing modal confirmation dialogs.

---

## [1.0.4] - 2026-09-08

### Added
- Global keyboard shortcuts (`Ctrl+Alt+1`, `Ctrl+Alt+2`, `Ctrl+Alt+3`) for instant channel switching.
- Configurable tray icon double-click action (`open_gui`, `switch_1`, `switch_2`, `switch_3`, `mini_window`).
- Single-instance process lock on Windows and Linux preventing duplicate instances.
- Quick Switch mini window popup with outside-click dismissal.

---

## [1.0.0] - 2026-09-01

### Added
- Initial release of Lunifier: Autonomous screen-edge switching for Logitech Easy-Switch devices (MX Keys, MX Master series, M720 Triathlon, POP) via HID++ protocol.
