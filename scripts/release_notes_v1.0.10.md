# Lunifier v1.0.10 Release Notes

**Lunifier v1.0.10** delivers official **Windows Store / Partner Center-compliant MSIX packaging** for the v1.x Python runtime series, built with Microsoft's `MakeAppx` tool with Open Packaging Conventions (`AppxBlockMap.xml`, `[Content_Types].xml`), complete High-DPI visual tile/logo scale variants (`scale-100`, `scale-200`, `targetsize-44`, `targetsize-24`), cleaned application staging free of macOS `.DS_Store` metadata, and updated Linux Debian packages.

---

### Highlights in v1.0.10

- **Windows Store / Partner Center Compliance**: Built with Microsoft `MakeAppx.exe`, generating genuine block map files (`AppxBlockMap.xml`) and `[Content_Types].xml` required by Microsoft Partner Center.
- **Manifest Schema Fixes**: Properly maintained standard XML declarations and OS dependency version constraints (`TargetDeviceFamily MinVersion="10.0.17763.0"`).
- **High-DPI Visual Assets**: Generated complete scaling suites (100% and 200% scale for `Square44x44Logo`, `Square150x150Logo`, `Wide310x150Logo`, `StoreLogo`, and unplated 44px/24px taskbar icons).
- **Cleaned Packaging**: Stripped development and macOS metadata files (`.DS_Store`) from the packaged distribution.

---

### Package Checksums (SHA-256)

| Asset | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-1.0.10.exe` | 16.84 MB | `A4DD49757FB019C5EEDDB973F7B9907323600C6DC324521FF2FC70F6F2732791` |
| `Lunifier-Windows-1.0.10.zip` | 21.78 MB | `CCF5FBC2A0C31146B912BB46709A3C95706CE69D239AC86233A9652A302BAB1E` |
| `Lunifier-1.0.10.0.msix` | 23.27 MB | `AEC00DCD402C735D105726F87955C33104E8F1FF7790BDAB43CCB2EF1F15C4C3` |
| `Lunifier-1.0.10.msix` | 23.27 MB | `AEC00DCD402C735D105726F87955C33104E8F1FF7790BDAB43CCB2EF1F15C4C3` |
| `lunifier_1.0.10_all.deb` | 186.2 KB | `A6A793FC7B0AC9933DB1E31EA73EC488F423DE0F7CC1AB9B208CE9B351DB1749` |
| `Lunifier-Linux-1.0.10.tar.gz` | 327.3 KB | `7BEF29E34C127B491A72B5D1FB6DB2851D72E8349BD1FB5C776B2CA4E10A179B` |
