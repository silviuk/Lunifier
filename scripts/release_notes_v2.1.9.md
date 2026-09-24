# Lunifier 2.1.9 Release Notes

**Lunifier 2.1.9** addresses critical edge dwell triggering reliability across Windows and Linux, fixes multiple monitor border overlay rendering and resolution scaling, introduces dynamic accent color support with vector-smooth rounded convex border indicators, and adds an integrated "Start minimized to system tray" option.

---

### Highlights & Fixes in v2.1.9

#### 1. Screen Border Dwell Hold & Switching Fix (Top Priority)
* **Continuous Cursor History**: Eliminated premature history bypasses so mouse motion is continuously recorded leading up to border contact.
* **Reliable Dwell Hold Triggering**: Holding the cursor against a configured screen border for the configured dwell duration (`HoldDelayMs`, default 250ms) now directly and reliably triggers the hardware switch sequence across Windows and Linux.
* **Return Guard & Cooldown Synchronized**: Cleaned state resets so return guards and cooldown timers do not block intentional switching.

#### 2. Multi-Monitor Border Overlay & Resolution Fix
* **Eliminated Phantom Bars on Disabled Screens**: In multi-monitor configurations where only one screen is enabled for border switching, secondary and disabled monitors no longer display extraneous border bars when adjusting settings.
* **Per-Monitor Overlay Windows**: Replaced virtual desktop spanning with dedicated per-monitor overlay window positioning, completely eliminating cross-monitor DPI distortion and misplaced bars in the middle of screens.
* **Strict Active Channel Filter**: Overlays are exclusively displayed for monitors that have active channels assigned.

#### 3. Dynamic Accent Colors & Vector-Smooth Convex Bars
* **Windows Accent Color**: Border indicator bars now dynamically inherit your Windows personal accent color (`HKCU\Software\Microsoft\Windows\DWM\AccentColor` / `SystemParameters.WindowGlassBrush`), falling back to vibrant Logitech orange (`#FF5722`).
* **Linux GNOME Accent Color**: Linux indicators query GNOME accent colors via `gsettings`, falling back to `#FF5722`.
* **Rounded & Convex Geometry**: Border indicators feature rounded corners (`R=3px`) and a subtle convex bulge (`B=3.5px`) towards the screen center, rendered using DirectX vector `PathGeometry` with sub-pixel anti-aliasing (completely free of jagged edges).

#### 4. "Start Minimized to System Tray" Option
* Added an explicit **"Start minimized to system tray"** setting in both Windows WPF and Linux Adwaita user interfaces and saved persistently in `config.json` (`start_minimized`).
* When enabled, Lunifier starts directly into the system tray without flashing or showing the main window on startup.

---

### Understanding Dwell Hold Delay vs. Switch Cooldown

* **Dwell Hold Delay (`HoldDelayMs`, default 250ms)**:
  * **What it is**: The minimum amount of continuous time your mouse cursor must remain pressed against a configured screen border before a switch is triggered.
  * **Why it is necessary**: Without a hold delay (delay = 0ms), touching the screen boundary triggers an immediate switch. This causes accidental switches when interacting with window title bars, tabs, corner buttons, or scrollbars near screen edges. Dwell holding verifies deliberate intent to leave the screen.
  * **How it affects switching**: Lower values (50–100ms) make switching feel instantaneous; higher values (300–500ms) require deliberate pressure against the screen edge.

* **Switch Cooldown (`CooldownMs`, default 500ms)**:
  * **What it is**: The lockout/grace period *after* a switch successfully completes, during which the screen borders are temporarily inactive.
  * **Why it is necessary**: Prevents "ping-pong" bounceback loops where moving into the new screen immediately trips a border on the target machine and bounces right back. Also gives Bluetooth and RF receivers time to complete packet transmission without RF collisions.
  * **How it affects switching**: After switching, borders are safely locked for 500ms so you can move your cursor inward on the target screen. Once 500ms elapses, normal border switching is re-armed.

---

### Package Hashes (SHA-256)

| File | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.1.9.exe` | 6.27 MB | `EA8BEB9FF4F9B0F6255C4A99B3BF164619978687AB7AA5C315F38670609184A8` |
| `Lunifier-Windows-2.1.9.zip` | 6.73 MB | `8FF2078457B51C04B99DB7B5167BD8DE3D8707F721237D2C499D410FB55D16E0` |
| `Lunifier-2.1.9.0.msix` | 6.77 MB | `309E0112794CF8764ADD58981CF1E324BFA003612856907A25C2AB554DB292D3` |
| `lunifier_2.1.9_all.deb` | 174.1 KB | `CD4D89B18AC097BF47E71A2D42AA13B8097F3D8ACC327E4DB9423C946574A4FE` |
| `Lunifier-Linux-2.1.9.tar.gz` | 244.3 KB | `0E6DD3BBFD8575A76F8DE73A378B1177D312E564686FF1AF6B2BAD51E9F563B7` |
