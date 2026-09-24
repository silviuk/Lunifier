# Changelog

All notable changes to the **Lunifier** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.2.0] - 2026-09-24

### Fixed & Improved (Windows & Linux)

- **HID++ Receiver Endpoint Classification & Direct NVRAM Query (Top Priority - Fixed Windows Switching)**:
  - Fixed a critical regression where receiver devices (Unifying, Bolt, Lightspeed) on Windows were incorrectly bound to OS-level mouse or consumer control collections (`mi_01&col01` and `mi_01&col02`) rather than dedicated HID++ endpoints (`mi_02&col02` and `mi_02&col01`), resulting in immediate Win32 Error 87 (`ERROR_INVALID_PARAMETER`) failures on host switch commands.
  - Endpoint discovery now strictly validates `UsagePage == 0xFF00` or `0xFF43` and prevents generic mouse/keyboard interface collisions.
  - Implemented instant hardware pairing discovery directly from receiver NVRAM memory via short report query (`0x10 0xFF 0x83 0xB5`), correctly parsing device WPIDs and device types (keyboards vs mice).
  - Dynamically routes 20-byte HID++ 2.0 Change Host feature packets to long report endpoints (`col02`) and 7-byte reports to short endpoints (`col01`).
  - Added extended WPID mappings for Logitech MX Keys Mini, Lift Vertical Mouse, MX Master 3S, and MX Anywhere 3.

- **Linux UI Redesign: Centered Tab Bar & Clean Spacing**:
  - Moved the `Adw.ViewSwitcher` tab navigation out of the congested header bar into a dedicated, centered horizontal container one level lower.
  - Full tab titles ("Screen & Switching", "Advanced", "Bluetooth P2P Link", "Live Logs", "About") and icons are now cleanly spaced, completely visible, and never crowded by window buttons or header controls.

- **Linux Live Logs Overhaul: In-Tab Log Level Selector, Copy Logs & Font Sizing**:
  - Added an integrated "Logging Level" dropdown selector directly within the Live Logs page controls bar, keeping diagnostics accessible without navigating to the Advanced tab.
  - Added a dedicated **"Copy Logs"** button in the Live Logs header bar with clipboard copy and instant temporary visual feedback ("Copied!").
  - Reduced log display font size by one size (compact 8.5pt monospace) for clean, readable, high-density diagnostic output.
  - Fixed unescaped XML markup entities (`&amp;`) across GTK4/Libadwaita preference group headers.
  - Replaced the constrained preferences group layout with a dynamic `Gtk.Box` container, allowing the log viewer (`Gtk.ScrolledWindow` + `Gtk.TextView`) to automatically scale and expand to fill all remaining window space.

- **New Standalone `-nobtsync` Packages (Windows & Linux)**:
  - Released dedicated `-nobtsync` packages for users who only want screen-edge Easy-Switching without computer-to-computer Bluetooth RFCOMM communication.
  - Omitted the "Bluetooth Inter-Host Link" tab completely from the user interface and disabled all RFCOMM listeners and background threads.
  - **Full Logitech Bluetooth Peripheral Support Maintained**: Keyboards and mice paired over Bluetooth continue to switch seamlessly via direct HID++ OS pipes; only inter-host peer-to-peer sync is excluded.
  - Packaged for Windows as `Lunifier-Setup-2.2.0-nobtsync.exe`, `Lunifier-Windows-2.2.0-nobtsync.zip`, and `Lunifier-2.2.0.0-nobtsync.msix`.
  - Packaged for Linux as `lunifier_2.2.0-nobtsync_all.deb` and `Lunifier-Linux-2.2.0-nobtsync.tar.gz`.

---

## [2.1.9] - 2026-09-24

### Fixed & Improved (Windows & Linux)

- **Edge Dwell Switching & Continuous History Fix (Top Priority)**:
  - Fixed edge detector dwell triggering where cursor dwell holds on screen borders were blocked by stale approach vectors or skipped history entries.
  - Continuous cursor history recording is now strictly maintained on every tick without being bypassed.
  - Satisfying the configured dwell hold duration (`HoldDelayMs`) now directly and reliably triggers channel switching across both Windows and Linux.

- **Multi-Monitor Border Overlay & Resolution Fix**:
  - Fixed bug where adjusting active border zones caused 4 orange bars to erroneously appear on disabled or unconfigured secondary monitors.
  - Replaced virtual desktop spanning with per-monitor overlay window positioning, completely eliminating cross-monitor DPI distortion and misplaced bars in the middle of screens.
  - Overlays are now strictly constrained to monitors with actively configured border channels.

- **Accent Color & Vector-Smooth Convex Border Indicators**:
  - Windows border indicator bars now dynamically inherit the Windows Accent Color (`HKCU\Software\Microsoft\Windows\DWM\AccentColor` / `SystemParameters.WindowGlassBrush`), falling back to vibrant Logitech orange (`#FF5722`).
  - Linux border indicators query GNOME accent colors via `gsettings`, falling back to `#FF5722`.
  - Indicators are rendered with rounded ends (`R=3px`) and a subtle convex bulge (`B=3.5px`) towards the screen center using DirectX vector `PathGeometry` with sub-pixel anti-aliasing (zero jagged edges).

- **Start Minimized Configuration & UI**:
  - Added "Start minimized to system tray" option in GUI and persistent configuration (`start_minimized`) across Windows WPF and Linux Adwaita.
  - Applications launch directly into system tray without flashing the main window when enabled.

---

## [2.1.8] - 2026-09-24

### Size, Performance & Packaging Overhaul (Windows & Linux)

- **Size Optimizations & Dead Code Removal**:
  - Removed obsolete legacy v1.x root `lunifier/` Tkinter directory, `run_lunifier.py`, and `Lunifier.spec`.
  - Removed redundant `System.Text.Json` NuGet dependency from `Lunifier.Windows.csproj` (leveraging built-in runtime assembly).
  - Excluded debug symbol `.pdb` files from portable zip, MSIX staging, and Inno Setup installer distributions.
  - Reduced final package sizes across Windows (.exe installer reduced to 6.27MB, MSIX to 6.77MB).

- **Performance & CPU Usage Optimizations**:
  - Replaced dynamic queue allocations in Windows `EdgeDetector.cs` with a zero-allocation 64-item ring buffer and cached default monitor configuration.
  - Added interior bounding box fast-path check in `EdgeDetector.cs`, skipping all edge collision math whenever the cursor is safely inside the screen interior.
  - Eliminated Linux 15ms `xdotool` subprocess execution hazard in `edge_detector.py` by caching command availability.
  - Unified inward cursor step-back displacement to 60px across Windows and Linux, preventing pointer jumping jank.

- **Visual Polish & Theme Consistency**:
  - Replaced hardcoded version strings with dynamic assembly/package version resolution across Windows WPF and Linux Adwaita About and Footer displays.
  - Converted device lists and Bluetooth peer lists in Windows WPF to dynamic theme brush references (`SetResourceReference`), guaranteeing instant contrast updates across Dark and Light mode transitions.
  - Applied responsive minimum widths and symmetric padding to header control buttons.

- **Packaging & Dependency Checks**:
  - Inno Setup installer now verifies whether Microsoft .NET 9 Desktop Runtime (x64) is present and prompts with an official download link if missing.
  - Linux Debian package updated with `python3-evdev` and `bluez` recommendations, and user systemd service configured to launch with `--minimized`.
  - Full suite of 52 unit tests passing cleanly.

---

## [2.1.7] - 2026-09-24

### Fixed & Improved (Windows & Linux)

- **Keyboard Switching Reliability**:
  - Implemented multi-burst wake transmissions (spaced 25ms apart) in `SwitchDeviceHost` for keyboards and Bluetooth devices on both Windows and Linux to wake sleeping RF receivers from low-power state.
  - Prioritized keyboards before mice when switching devices on the same receiver, ensuring sleeping keyboards receive wake/switch bursts before the active mouse.
  - Added receiver NVRAM pre-scan table query (`0x10, 0xFF, 0x83, 0xB5`) to detect all paired receiver slots and WPIDs without RF timeouts, retaining cached receiver devices so sleeping devices are never lost during rescan.

- **Default Switch Cooldown Reduced to 500ms**:
  - Lowered default cooldown from 2500ms to 500ms across Windows and Linux, allowing smooth and prompt switching without long delays between border touches.
  - Expanded slider range to 200ms–5000ms.

- **Eliminated Mouse Pointer Jank & Hiccups**:
  - Lowered background edge detector thread priority from `AboveNormal` to `Normal`, preventing thread contention with Windows DWM and mouse input subsystems.
  - Tightened border trigger tolerance from 5px to 2px, preventing cursor interaction with window scrollbars from triggering border events.
  - Removed arbitrary 300ms hold-delay bypass that falsely triggered switching when scrolling or dragging near screen edges.
  - Reduced inward stepback displacement from 160px to 60px, eliminating jarring cursor jumps while retaining loop prevention.

- **Light Theme Contrast & Legibility Overhaul**:
  - Fixed button text rendering in Light mode by injecting an explicit white TextBlock style in `Button.ContentPresenter.Resources`, permanently eliminating black text on blue buttons.
  - Replaced low-contrast light sky blue (`#38BDF8`) and light gray (`#94A3B8`) in device and peer lists with theme-aware high-contrast colors (`#0284C7` and `#334155` in light mode).
  - Darkened secondary text (`#334155`), section headers (`#0369A1`), and log box text (`#0F172A`) in light mode for full WCAG AAA legibility against white and light gray cards.

- **Linux Background Service Persistence & System Tray**:
  - Implemented D-Bus StatusNotifierItem (SNI) + DBusMenu system tray integration in Linux (`tray.py`).
  - Closing the main window now keeps the Lunifier service running smoothly in the background and hides the window to the system tray instead of terminating.
  - Added system tray menu items to restore/present the main window or cleanly quit the application.

---

## [2.1.6] - 2026-09-23

### Fixed & Improved (Windows & Linux)

- **Bluetooth Low Energy & Direct Bluetooth Device Switching**:
  - **Windows**: Fixed device enumeration by opening HID endpoints with query access (`0`) instead of exclusive read/write access, eliminating `ERROR_ACCESS_DENIED` and `ERROR_SHARING_VIOLATION` from Windows `hidbth.sys` / `mouhid.sys`. Added BLE GATT HOGP path recognition (`{00001812-...}`) and endpoint capability ranking. Implemented multi-tiered Win32 write fallback (`Overlapped WriteFile` -> synchronous `WriteFile` -> `HidD_SetOutputReport` -> `HidD_SetFeature`) and 20ms connection-interval repeat bursts.
  - **Linux**: Enhanced direct Bluetooth and `/dev/hidraw` device handling.
  - **Both**: Added friendly device PID name mapping (M720 Triathlon, MX Master 3/3S, MX Keys/Mini, K380, K780, Craft, Lift, etc.).

- **Edge Detector Border Bounceback Loop Prevention**:
  - **Both**: Repositioned cursor immediately 160px inward and armed the return guard upon screen border trigger before asynchronous hardware switching completes, preventing cursor pinning at borders while hardware responds.
  - **Both**: Increased physical mouse movement detection threshold from 15px to 50px ($dx^2 + dy^2 > 2500$) to prevent optical sensor jitter or tiny hand tremors from triggering false switch loops.

- **Unifying & Bolt Receiver Keyboard Switching Reliability**:
  - **Both**: Replaced parallel transmission to devices on the same USB dongle with serialized switching (30ms spacing) to eliminate 2.4GHz RF packet collisions.
  - **Both**: Added dual-report wake bursts (both Long Report `0x11` and Short Report `0x10`) to wake sleeping battery-saving keyboards so they reliably switch simultaneously with the mouse.

- **Start Minimized at Boot / Login**:
  - **Windows**: Added `--minimized` command-line switch support to start Lunifier cleanly in the system tray without showing the main window. Updated autostart registry configuration and Inno Setup installer tasks.
  - **Linux**: Added `--minimized` and `--daemon` argument handling in launcher, and updated `~/.config/autostart/lunifier.desktop` to launch minimized on desktop login.

- **Modern Native UI & Layout Synchronization**:
  - **Both**: Renamed "Connected Devices" tab to **"Advanced"**, and relocated "Edge Trigger Sensitivity" and "Hardware & Logging Options" into "Advanced" with smooth scrolling.
  - **Both**: Relocated "Save Configuration" / "Save" button to the top header row alongside the service status badge and toggle button.
  - **Both**: Multi-monitor visual screen border indicator displays live orange overlays (`#FF5722`, 6px thickness) with a 1.5-second auto-hide timer whenever adjusting the active zone percentage, changing border edge assignments, selecting a monitor, or saving configuration (WPF canvas overlay on Windows, X11 `override_redirect` windows on Linux).

- **Package Version Parity & Build Artifacts**:
  - Bumped version across all Windows (`Lunifier.Windows.csproj`, `AppxManifest.xml`, `installer.iss`) and Linux (`pyproject.toml`, `lunifier/__init__.py`, About window) project files to 2.1.6.
  - Rebuilt and verified all distribution packages: `.exe` installer, `.zip` portable, `.msix` package, `.deb` package, and `.tar.gz` portable tarball.

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
