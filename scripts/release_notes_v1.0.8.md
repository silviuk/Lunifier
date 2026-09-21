### Lunifier v1.0.8 Release Notes

#### What's New in v1.0.8
- **Unified Scalable Vector Graphics Iconography Across Windows & Linux**:
  - Replaced the mismatched Linux icon with the official Lunifier icon from the Windows package.
  - Recreated the icon as a master Scalable Vector Graphics (SVG) vector asset (`lunifier/resources/icon.svg`) featuring the metallic dark circular badge, diagonal inter-host communication link with status indicator beads, 4-lobed orange propeller/star, and pure white center.
  - Deployed full multi-resolution mipmap suite (`16x16` up to `512x512`) and scalable SVG into Linux FreeDesktop hicolor theme paths (`/usr/share/icons/hicolor/scalable/apps/lunifier.svg`, `/usr/share/pixmaps/`) and `lunifier.desktop` (`StartupWMClass=Lunifier`).
  - Integrated `resvg_py` and `cairosvg` vector rendering directly into `lunifier.icons.render_scalable_icon()`, ensuring razor-sharp rendering on High-DPI, 4K, and fractional display scaling on both Windows and Linux.
- **Linux Python Typing Compatibility**:
  - Fixed a `NameError: name 'Dict' is not defined` crash that prevented `lunifier --gui` and daemon mode from starting on standard Linux distributions (Ubuntu, Debian, Fedora running Python 3.10–3.12).
  - Added `from __future__ import annotations` and explicit imports for `Dict, Any, List` in `lunifier.app`.
  - Added an automated typing verification unit test (`tests/test_annotations.py`) to prevent any future typing regressions across all Python runtimes.
- **Source Cleanliness**:
  - Removed UTF-8 Byte Order Mark (BOM) from `lunifier/logger.py`.
- **All v1.0.7 Features Included**:
  - Bluetooth-only timed peer discovery with ephemeral discovery tokens, mutual pairing handshake, cursor boundary alignment, and encrypted clipboard sync (zero network/Wi-Fi communication).

#### Package Checksums (SHA-256)
- `Lunifier-Setup-1.0.8.exe`: `D6A09C58A133E24FF66E8704AADCEF45529FC4FF83A67F81638994AAC17EB326`
- `Lunifier-Windows-1.0.8.zip`: `786393B3BB2B50AAB6B0E7E08BE6A0BE347E58B819A0D618F48EEB86E0D13807`
- `Lunifier-1.0.8.0.msix`: `6EA599682555365363381320ECD83B71C4FE111A87C7E65E0F8AD827CDA16072`
- `lunifier_1.0.8_all.deb`: `55D5B06B8363589EBD3E513273C013236E24F4C7278665D47C080932BCEEF0F9`
- `Lunifier-Linux-1.0.8.tar.gz`: `206E2A3475AAC1C4C7F3AD44B2398158B04973138504A4BFF859120D7878033D`
