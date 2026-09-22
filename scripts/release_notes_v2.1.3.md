# Lunifier 2.1.3 Release Notes

**Lunifier v2.1.3** fixes key usability and reliability items on Windows native (.NET 9 WPF) and updates packages across both Windows and Linux native architectures.

## What's New & Fixed in v2.1.3

### 1. Screen Border Detection & Switching Reliability
- **Immediate Service Start**: Automatically activates the background edge detection and Bluetooth peer service upon GUI launch, removing the need for manual service toggling.
- **Accurate Dwell Hold Timer**: Fixed an issue where slight cursor rest at the screen border reset the hold timer in `EdgeDetector`, preventing the dwell time from completing.
- **High-DPI & 4K Tolerance**: Expanded edge touch tolerance to 5 pixels, ensuring reliable border contact on high-resolution displays.
- **Real-Time Edge Arrival Logs**: Moving the cursor to a configured border now immediately logs the monitor ID, coordinates, active zone ratio, and dwell hold timer in the Live Logs tab and `%APPDATA%\Lunifier\lunifier.log`.
- **Dwell Fallback Validation**: Guaranteed edge triggering when resting at the border for `>= 300ms`.

### 2. Full Dynamic Light/Dark Mode Theming
- **Windows System Mode Sync**: Added `ThemeManager` which listens to Windows theme preference changes (`AppsUseLightTheme`) and switches dynamically between Dark Slate and Clean Light palettes.
- **Custom ComboBox & Popups**: Replaced default Win32 WPF dropdown controls with styled, high-contrast templates for clear legibility in both dark and light modes (no white-on-white text).
- **Immersive Title Bar**: Integrated Windows 11 DWM title bar dark/light theming (`DwmSetWindowAttribute`).

### 3. Non-Blocking Dialogs & Polished UI Flow
- Replaced modal dialog boxes on **Save Configuration**, **Copy Logs**, and **Bluetooth Pairing** with clean inline status indicators and auto-resetting feedback timers.

### 4. High-Quality Icon Rendering
- Added `RenderOptions.BitmapScalingMode="HighQuality"` and `SnapsToDevicePixels="True"` to the About tab brand icon, removing aliasing and jagged edges.

---

## Release Artifacts & Checksums

| Package | Platform / Target | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.1.3.exe` | Windows Inno Setup Installer | `AF0CAF66276F48FAF49BDFEE30CD90FDADED6F69AFC28ED9B8AEFABBEEDB89DF` |
| `Lunifier-Windows-2.1.3.zip` | Windows Portable x64 | `2DCDEAE02F0B438E17EB61C38B7AB890EABB0F182F5DCFF22FD11F0CA36CF0A8` |
| `Lunifier-2.1.3.0.msix` | Windows Store / Enterprise MSIX | `2BE0673FB149FE28B9876E2F0E859F2751BE68C9647DEAB9326FB385A9272CC0` |
| `lunifier_2.1.3_all.deb` | Debian / Ubuntu Package | `3E1A872475BC545A1A793376AFAD0548E1950539A88A553B41BBC916D0317132` |
| `Lunifier-Linux-2.1.3.tar.gz` | Linux Portable Tarball | `CA28B822BAB5E97AE6D2F4FCF31F2EA0A09589A68AB0D3932DDB6BB1F922CCEA` |
