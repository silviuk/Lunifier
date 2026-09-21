### Lunifier v1.0.8 Release Notes

#### What's New in v1.0.8
- **Linux Python Typing Compatibility**:
  - Fixed a `NameError: name 'Dict' is not defined` crash that prevented `lunifier --gui` and daemon mode from starting on standard Linux distributions (Ubuntu, Debian, Fedora running Python 3.10–3.12).
  - Added `from __future__ import annotations` and explicit imports for `Dict, Any, List` in `lunifier.app`.
  - Added an automated typing verification unit test (`tests/test_annotations.py`) to prevent any future typing regressions across all Python runtimes.
- **Source Cleanliness**:
  - Removed UTF-8 Byte Order Mark (BOM) from `lunifier/logger.py`.
- **All v1.0.7 Features Included**:
  - Scalable vector graphics icon pipeline with multi-resolution mipmap caching (16px–512px).
  - Bluetooth-only timed peer discovery with ephemeral discovery tokens, mutual pairing handshake, cursor boundary alignment, and encrypted clipboard sync (zero network/Wi-Fi communication).

#### Package Checksums (SHA-256)
- `Lunifier-Setup-1.0.8.exe`: `688018CA3DD58998FA8B3B93EF40A464CB85BA4EDAE5A38697352C4B9DC3900C`
- `Lunifier-Windows-1.0.8.zip`: `2FC3778E736D7746FFBF6F7A575575935FBD540D25FC12AE6FEA749E3DFF00F0`
- `Lunifier-1.0.8.0.msix`: `4C0E9BA0D351E574EC43FF8EF29DD492DDBE4E74571E8DCAD02D7CB500A3C706`
- `lunifier_1.0.8_all.deb`: `CE56CD36F5A1B99C8C21B9C812DCD78716DE9FC4E46BC89BE3851186B8B4D6D8`
- `Lunifier-Linux-1.0.8.tar.gz`: `DE0AB0ABB24AD93D2C4592019BD8A026B15FF60FA861B3CF6369D3115738591B`
