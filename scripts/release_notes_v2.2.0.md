# Lunifier 2.2.0 Release Notes

**Lunifier 2.2.0** resolves the Windows HID++ host switching failure for Logitech wireless receivers (Unifying, Bolt, Lightspeed), brings a redesigned centered tab bar to the Linux Libadwaita interface for crystal-clear readability, adds an integrated logging level selector directly into the Live Logs tab, and makes the log viewer dynamically scale to fill the full window space.

---

### Highlights & Fixes in v2.2.0

#### 1. Windows HID++ Receiver Switching Fixed (Top Priority)
- **Root Cause Identified & Fixed**: Standard Windows HID driver enumerates multiple USB collections per physical dongle (`mi_00` for keyboard, `mi_01` for mouse and consumer control, and `mi_02` for HID++ protocol communication). Stricter endpoint validation prevents generic consumer/mouse endpoints (`UsagePage 0x0001`/`0x000C`) from polluting the receiver dispatch table, eliminating Win32 Error 87 (`ERROR_INVALID_PARAMETER`).
- **Instant Receiver NVRAM Decoding**: Implements internal receiver pairing table querying (`0x10 0xFF 0x83 0xB5`), retrieving paired WPIDs with 0ms latency even when devices are sleeping.
- **Dynamic Endpoint Routing**: Seamlessly routes 20-byte HID++ 2.0 Change Host feature packets (`0x11`) to long report endpoints (`col02`) and 7-byte reports (`0x10`) to short endpoints (`col01`).
- **Expanded Hardware Support**: Added WPID definitions for MX Keys Mini, Lift Vertical Mouse, MX Master 3S, and MX Anywhere 3.

#### 2. Linux UI Redesign: Centered Tab Bar & Clean Spacing
- Moved the `Adw.ViewSwitcher` tab navigation out of the congested header bar into a dedicated, centered horizontal container one level lower.
- All 5 tabs ("Screen & Switching", "Advanced", "Bluetooth P2P Link", "Live Logs", "About") now have abundant space, with full labels and icons clearly readable without clipping or crowding.

#### 3. Linux Live Logs: Integrated Log Level & Full-Window Scaling
- Added an integrated "Logging Level" dropdown selector directly in the Live Logs controls bar, bidirectionally synchronized with the Advanced tab and applied instantly.
- Replaced the constrained preferences group layout with a dynamic `Gtk.Box` container, allowing the log viewer (`Gtk.ScrolledWindow` + `Gtk.TextView`) to dynamically expand and fill all remaining window space.

---

### Package Checksums (SHA-256)

| Asset | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.2.0.exe` | 6.30 MB | `61D95AC36328E2C885841FFC952734C3C647FB2240689E483C96ACB419B66B46` |
| `Lunifier-Windows-2.2.0.zip` | 6.74 MB | `BE275CED124914C61DB694CCD722688904D95FF0B577F35E3A214025E4637A3A` |
| `Lunifier-2.2.0.0.msix` | 6.78 MB | `7B2608A12EF6926EBB12F15201AD5B999153804C87E3F9A96C3A996ED5E6F8EF` |
| `lunifier_2.2.0_all.deb` | 174.4 KB | `4C39F1A409B390DA142BCC3CD9BC91B22EBD54AB0A9E91B0AFA071C66D125918` |
| `Lunifier-Linux-2.2.0.tar.gz` | 244.3 KB | `E3010B3078152FB6853159D32FD8D90D2AB520579C3A97CBD72BF56989D797FE` |
