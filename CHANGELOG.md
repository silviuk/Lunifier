# Changelog

All notable changes to the **Lunifier** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.6] - 2026-09-23

### Fixed & Improved
- **Bluetooth Device Detection & Switching (Windows)**:
  - Fixed Bluetooth Logitech device enumeration by opening endpoints with query access (`0`) instead of exclusive read/write access, bypassing Windows `hidbth.sys` / `mouhid.sys` sharing violations.
  - Added support for Bluetooth Low Energy GATT HID paths (`{00001812-...}`) and device PID name mapping (e.g. M720 Triathlon, MX Master 3/3S, MX Keys/Mini, K380, K780, Craft, Lift).
  - Enhanced device endpoint selection to prioritize vendor TLCs (`UsagePage 0xFF43`) and collections with long output report capabilities.
  - Implemented multi-tiered Win32 write fallback (`Overlapped WriteFile` -> synchronous `WriteFile` -> `HidD_SetOutputReport` -> `HidD_SetFeature`) and 20ms connection-interval repeat bursts for reliable host switching over Bluetooth.
- **Edge Detector Border Bounceback Loop Prevention**:
  - Immediately repositioned cursor inward (160px) and armed the return guard upon screen border trigger, ensuring the cursor is never left pinned at the border edge even if hardware switching takes longer.
  - Increased physical mouse return detection threshold to 50px to eliminate false-trigger loops caused by optical sensor jitter or tiny hand twitches.
- **Unifying Receiver Keyboard Switching Reliability**:
  - Replaced concurrent parallel packet transmission to the same receiver with serialized device switching and a 30ms inter-device pause.
  - Added Short Report (`0x10`) switching fallback on `col01` and duplicate Long Report wake bursts to ensure battery-saving wireless keyboards reliably switch alongside the mouse.
- **Linux Native GTK4/Libadwaita v2.1.6 Parity**:
  - Reorganized window layout: renamed "Connected Devices" tab to **"Advanced"**, moved "Edge Trigger Sensitivity" and "Hardware & Backend Options" to "Advanced", and added a dedicated "Save" button to the top header bar.
  - Implemented visual orange screen border indicator (`#FF5722`, 6px thickness) with 1.5-second auto-hide timer when adjusting active zone percentage or monitor border settings.
  - Applied immediate inward cursor stepping (160px) and return guard arming prior to async hardware switching, preventing border bounceback loops.
  - Increased physical mouse movement return threshold from 15px to 50px ($dx^2 + dy^2 > 2500$).
  - Added serialized device switching (30ms delay) and wake bursts for multi-device Unifying/Bolt receivers.
  - Added `--minimized` argument support and updated `~/.config/autostart/lunifier.desktop` to launch minimized on login.
  - Updated Linux packaging metadata in `pyproject.toml`, `lunifier/__init__.py`, and About dialog from 2.1.3 to 2.1.6.

---

## [2.1.5] - 2026-09-23

### Fixed & Improved
- **Light & Dark Mode Contrast & Legibility**:
  - Eliminated dark text on blue accent buttons in Light mode by enforcing pure white text in button control templates.
  - Upgraded status badges (RUNNING / STOPPED) to high-contrast solid color-coded pills (`#16A34A` vibrant green / `#DC2626` crimson red) with bold white centered text.
  - Replaced low-contrast light green/red status labels with dynamic theme-aware high-contrast colors (`#15803D` / `#DC2626` in light mode, `#4ADE80` / `#F87171` in dark mode).
- **Uniform Button & Status Badge Alignment**:
  - Centered all button text horizontally and vertically across the application.
  - Aligned running status badge and start/stop service button with identical dimensions (130x32px), matching corner radius (4px), and centered typography.
- **Tab Layout Reorganization**:
  - Renamed "Connected Devices" tab to **"Advanced"** and wrapped contents in a smooth scroll viewer.
  - Relocated "Edge Trigger Sensitivity" and "Hardware & Logging Options" cards from "Screen & Switching" into the "Advanced" tab, keeping "Screen & Switching" focused exclusively on Host Identity and Display/Border configuration.
  - Relocated "Save Configuration" button to the top header row alongside the service status badge and toggle button, removing the redundant footer button.

---

## [2.1.4] - 2026-09-22

### Fixed
- **Non-Blocking HID++ Device Scanning**: Overhauled `HidppEngine` with asynchronous Win32 Overlapped I/O and strict 75ms timeouts per slot, eliminating device scan hangs on Logitech receivers.
- **Hardware Switching Reliability**: Routed receiver queries exclusively to `Col02` (Long Reports) and short reports to `Col01`, ensuring paired devices (MX Keys, M720 Triathlon) are recognized and switched without kernel blocking.
- **Asynchronous Edge Trigger Dispatch**: Dispatched hardware switching in background threads via `Task.Run()`, preventing the screen border detection loop from stalling.
- **Smarter Return Guard**: Clamped return guard to at most 1000ms and only armed guard when at least one hardware device successfully switched.
- **Default Windows Hostname**: Automatically resolved default hostname from `Environment.MachineName` instead of hardcoded `"Host"`.
- **Uniform 32px UI Controls Layout**: Standardized all text fields, dropdowns, and adjacent action buttons to a uniform height of 32px with centered vertical content alignment.

---

## [2.1.3] - 2026-09-22

### Fixed
- **Screen Border Detection & Switching Reliability**:
  - Auto-starts service on application launch so border detection is immediately active.
  - Fixed dwell hold timer reset in `EdgeDetector` so resting at border correctly accumulates hold time towards `HoldDelayMs`.
  - Added fallback trigger validation when dwelling at border for `>= 300ms`.
  - Increased edge detection tolerance from 2px to 5px to reliably trigger on 4K and high-DPI displays.
  - Added real-time arrival logging reporting monitor ID, coordinates, border zone ratio, and countdown timer.
- **Dynamic Light/Dark Mode Theming & Readability**:
  - Added `ThemeManager` dynamically synchronizing with Windows `AppsUseLightTheme` setting.
  - Designed custom WPF `ControlTemplate` for `ComboBox` and dropdown popups, eliminating white-on-white text and unreadable controls.
  - Applied Windows 11 DWM title bar dark/light mode attribute.
- **Seamless Inline UI Feedback (No Intrusive Dialogs)**:
  - Replaced blocking modal dialogs for Save Configuration, Copy Logs, and Bluetooth Pairing with clean inline status indicators.
- **High-Quality Anti-Aliased Icon Rendering**:
  - Enabled `RenderOptions.BitmapScalingMode="HighQuality"` and `SnapsToDevicePixels="True"` on About tab icon, eliminating jagged edges.
- **Persistent Log File Support**:
  - Added automatic logging to `%APPDATA%\Lunifier\lunifier.log` for troubleshooting and runtime diagnostics.

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
