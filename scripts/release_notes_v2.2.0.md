# Lunifier 2.2.0 Release Notes

**Lunifier 2.2.0** resolves mouse switching failures and memory leaks on Windows, introduces the new **Standalone No-BtSync Edition** (`-nobtsync`) for both Windows and Linux, brings a redesigned centered tab bar to the Linux Libadwaita interface for crystal-clear readability, adds an integrated logging level selector and "Copy Logs" button directly into the Live Logs tab, and makes the log viewer dynamically scale to fill the full window space.

---

### Highlights & Fixes in v2.2.0

#### 1. Windows Mouse Switching & Receiver Endpoint Resolution (Top Priority)
- **WPID Table & Dongle Key Matching**: Fixed inverted WPID table mappings (identifying MX Master 3 as `0x4082`, MX Master 3S as `0x4090`, MX Master 2S as `0x4086`, and Craft Keyboard as `0x4069`). Standardized endpoint grouping per physical USB receiver dongle by stripping OS collection suffixes, correctly pairing short (`col01`) and long (`col02`) report handles.
- **Instant Receiver NVRAM Decoding**: Implements pre-query endpoint queue draining and decodes the internal receiver pairing table (`0x10 0xFF 0x83 0xB5`), retrieving paired WPIDs with 0ms latency even when devices are in low-power sleep mode.
- **Candidate Feature Bursting**: When devices are sleeping or their Change Host feature index is not yet resolved, sends candidate feature indices (`0x08`, `0x09`, `0x0A`) with short spacing without premature loop break, guaranteeing mice (which use feature index `0x08`) switch reliably.
- **Switch Concurrency Guard**: Added switch concurrency protection to ensure rapid screen border crossings do not launch overlapping switch operations or race on receiver USB handles.

#### 2. Windows Performance & Memory Optimization
- **UI Log Ring Buffer**: Implemented ring-buffered truncation in the WPF Live Logs viewer, capping character storage at 40,000 characters and preventing Dispatcher thread lockups and memory growth during extended background operation.
- **Cooldown Log Throttling**: Throttled border cooldown debug logging to at most once per 500ms, eliminating high-frequency dispatcher flooding.
- **Automatic Log File Rotation**: Added 5 MB file size bounding and automatic `.old` log rotation to prevent unbounded disk growth.

#### 3. Standalone No-BtSync Edition (`-nobtsync`) for Windows & Linux
- **Dedicated Packages**: For users who want screen-edge Logitech Easy-Switching without computer-to-computer Bluetooth RFCOMM communication.
- **Clean UI & Zero RFCOMM Overhead**: Omits the "Bluetooth Inter-Host Link" tab entirely and disables all background RFCOMM discovery and listener threads.
- **Full Logitech Bluetooth Peripheral Support Maintained**: Direct Bluetooth Logitech mice and keyboards switch natively via OS HID++ pipes; only inter-computer P2P sync is excluded.
- Packaged as `.exe`, `.zip`, `.msix` (Windows) and `.deb`, `.tar.gz` (Linux).

#### 4. Linux UI Redesign: Centered Tab Bar & Clean Spacing
- Moved the `Adw.ViewSwitcher` tab navigation out of the congested header bar into a dedicated, centered horizontal container one level lower.
- Full tab labels and icons are cleanly spaced, completely visible, and never crowded by window buttons or header controls.

#### 5. Linux Live Logs: Copy Logs, Compact Font & Dynamic Scaling
- Added a dedicated **"Copy Logs"** button in the Live Logs header bar with clipboard copy and instant visual feedback ("Copied!").
- Reduced log display font size by one size (compact 8.5pt monospace) for clean, readable, high-density diagnostic output.
- Added an integrated "Logging Level" dropdown selector directly in the Live Logs controls bar, bidirectionally synchronized with the Advanced tab.
- Replaced the constrained preferences group layout with a dynamic `Gtk.Box` container, allowing the log viewer (`Gtk.ScrolledWindow` + `Gtk.TextView`) to dynamically expand and fill all remaining window space.

---

### Package Checksums (SHA-256)

#### Standard Edition (Full Features including Bluetooth Inter-Host Link)
| Asset | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.2.0.exe` | 6.01 MB | `FD5F75E0F0DDD3470F547F133B5E2EAB7FF7B980F58275D5A4139DD057F9A62E` |
| `Lunifier-Windows-2.2.0.zip` | 6.43 MB | `A7FFBC302F760545FC6F50C956404116D50061695B6467222F6150B56466C48F` |
| `Lunifier-2.2.0.0.msix` | 6.47 MB | `C7EC59CF1722500F01C73021D4A4795B99FB13669663BEA866F005EF88A182FC` |
| `lunifier_2.2.0_all.deb` | 170.7 KB | `5E6F58D8DC7ED8A998D41B04A4AA9B869A3804B4F03AF8AEEA39BF8E7E0C29EA` |
| `Lunifier-Linux-2.2.0.tar.gz` | 239.1 KB | `3A8AFC1CD6433768E5FCDE5EDFBFE02D85386C383AEA40772CA1C25B2DA5018B` |

#### Standalone No-BtSync Edition (No RFCOMM Inter-Host Sync)
| Asset | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.2.0-nobtsync.exe` | 6.00 MB | `619D3DA0211C61048BB3DF686A9F4F8879D0EC8B52E14EEC854DDBEA6A87AE05` |
| `Lunifier-Windows-2.2.0-nobtsync.zip` | 6.42 MB | `781F79788953B1CCFA9DA2C887660988534C5E81EC4BA414970303573248681A` |
| `Lunifier-2.2.0.0-nobtsync.msix` | 6.47 MB | `B44780749AFDD4379E34CF953D8E8623C6C70B515BD35382BBCA74C42DDBCD57` |
| `lunifier_2.2.0-nobtsync_all.deb` | 170.7 KB | `83D23E55BCD470DAFEE3D88F8981A26C2B049CDC8A1D6825781E492352D9009A` |
| `Lunifier-Linux-2.2.0-nobtsync.tar.gz` | 239.1 KB | `6B4FAE8CD568A312F0084D607B5B47BE1B9B2C13A76ACD9E0B03A45E6DC9D5CA` |
