# Lunifier 2.1.7 Release Notes

**Lunifier 2.1.7** introduces major reliability enhancements for peripheral switching, eliminates cursor stutter/jank during screen boundary tracking, refines light mode visual contrast across all controls and device lists, and ensures the Linux service persists in the background with system tray integration.

---

### Highlights & Fixes in v2.1.7

#### 1. Keyboard Switching Reliability
* **Multi-Burst Wake Transmission**: Battery-saving keyboards (MX Keys, Craft, ERGO K860, etc.) often sleep between keystrokes. When switching, Lunifier now emits 3 successive burst packets spaced 25ms apart to wake the peripheral's RF transceiver and guarantee acknowledgement.
* **Keyboard-First Switching Order**: When multiple devices share a Unifying or Logi Bolt USB receiver, keyboards are now commanded *before* the active mouse, preventing RF queue bottlenecks.
* **Dongle NVRAM Pairing Pre-Scan**: Reads the receiver internal pairing table (`0x10, 0xFF, 0x83, 0xB5`) to detect paired slots and WPIDs without RF timeouts, ensuring sleeping devices are permanently retained across rescans.

#### 2. Default Cooldown Reduced to 500ms
* Lowered default switch cooldown from 2500ms to **500ms** across Windows and Linux.
* Enables responsive and prompt re-switching without annoying delays when touching border boundaries. Slider range expanded to 200ms–5000ms.

#### 3. Eliminated Mouse Pointer Jank & Stutter
* Changed background edge tracking thread priority from `AboveNormal` to `Normal` to prevent scheduler preemption of Windows DWM and mouse driver polling.
* Tightened edge tolerance from 5px to **2px**, preventing cursor encounters with scrollbars and window edges from falsely triggering boundary hits.
* Removed the arbitrary 300ms hold bypass that caused unintended switches while scrolling or dragging windows.
* Decreased inward cursor stepback from 160px to **60px**, eliminating jarring cursor repositioning.

#### 4. Light Mode Contrast & Styling Overhaul
* Permanently eliminated black text on blue accent buttons by scoping an explicit white `TextBlock` style within `Button.ContentPresenter.Resources`.
* Replaced low-contrast light sky blue (`#38BDF8`) and light gray (`#94A3B8`) in device and peer lists with dynamic theme-aware colors (`#0284C7` and `#334155` in light mode).
* Improved overall light theme palette: secondary text (`#334155`), section headers (`#0369A1`), and live logs (`#0F172A`) for high WCAG AAA readability.

#### 5. Linux Background Service Persistence & System Tray
* Added native D-Bus **StatusNotifierItem (SNI)** and **DBusMenu** integration (`tray.py`).
* Closing the Linux main window now hides the window and keeps the Lunifier service running smoothly in the background.
* System tray menu allows restoring/presenting the main window or cleanly quitting the application.

---

### Package Hashes (SHA-256)

| File | SHA-256 Checksum |
| :--- | :--- |
| `Lunifier-Setup-2.1.7.exe` | `47D191A9D1C56A1351D624BCC4A0E77AF16503C086B57EC28289190DFCB69067` |
| `Lunifier-Windows-2.1.7.zip` | `73D9D40DBBAF7D5EF44B4755FE23E990C92A4D95AE85698A7497CDE41BD6788F` |
| `Lunifier-2.1.7.0.msix` | `DB46B13E0022C7CDEA916FF40505117F819FAD4E00074C1A3F9471E497ED968E` |
| `lunifier_2.1.7_all.deb` | `815614af9bea066ef534d3acbdf5c1eca7e66dfe35b040e1bf1509b76864a9e4` |
| `Lunifier-Linux-2.1.7.tar.gz` | `7b521cdbdce2601671f011aaa91b62afeb74a4c9ca208bc6ac9c2103bf8ba74d` |
