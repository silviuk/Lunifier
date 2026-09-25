# Lunifier 2.2.1 Release Notes

**Lunifier 2.2.1** provides official **Windows Store / Partner Center-compliant MSIX packages** built with Microsoft's `MakeAppx` tool, including authentic Open Packaging Conventions (`AppxBlockMap.xml`, `[Content_Types].xml`), distinct package identities for the Standard and No-BtSync editions, High-DPI visual tile/logo scale variants (`scale-100`, `scale-200`, `targetsize-44`, `targetsize-24`), and updated packages across Windows and Linux.

---

### Highlights & Fixes in v2.2.1

#### 1. Official Windows Store / Partner Center MSIX Compliance
- **Genuine MakeAppx Packaging**: Replaced fallback archive packaging with official Microsoft `MakeAppx.exe`, generating required cryptographic block maps (`AppxBlockMap.xml`) and Open Packaging Conventions manifests (`[Content_Types].xml`).
- **Fixed Manifest Versioning**: Corrected manifest generation to strictly update `<Identity Version="..." />` while preserving standard XML declarations (`<?xml version="1.0"?>`) and OS dependencies (`TargetDeviceFamily MinVersion="10.0.17763.0"`), passing Microsoft Partner Center schema validation.
- **Distinct Identity for No-BtSync Edition**: Configured `SilviuVlasceanu.LunifierNoBtSync` and `DisplayName="Lunifier (No-BtSync Edition)"` to allow seamless separate Windows Store submission without identity or package conflicts.
- **High-DPI Visual Assets**: Added comprehensive scale and target-size variants (`Square44x44Logo`, `Square150x150Logo`, `Wide310x150Logo`, `StoreLogo` at 100% and 200% scale plus unplated 44px/24px taskbar icons) ensuring crisp visuals and passing Windows App Certification Kit (WACK) asset tests.

#### 2. Linux System Tray Icon & Desktop Integration Fix
- **GNOME AppIndicator & Ubuntu System Tray**: Fixed missing indicator icon fallback ("three dots") on Ubuntu 24.04/26.04 by exporting direct ARGB32 pixmaps over D-Bus (`IconPixmap`), setting Freedesktop-compliant `IconThemePath`, and installing multi-resolution status/panel icons across all standard theme contexts.

#### 3. Ubuntu App Center & GNOME Software AppStream Integration
- **AppStream Metainfo Specification**: Included Freedesktop AppStream metainfo manifests (`io.github.silviuk.lunifier.metainfo.xml` and `io.github.silviuk.lunifier-nobtsync.metainfo.xml`), furnishing Ubuntu App Center and GNOME Software with rich app titles, summaries, developer info, homepage/issue tracker URLs, and OARS 1.1 content ratings.
- **Store Screenshots & Visuals**: Embedded native Libadwaita interface screenshots and high-resolution icons into package metadata for graphical software center presentation.
- **Package Metadata & Control Enhancements**: Added `Homepage` upstream links, structured feature lists in `DEBIAN/control`, desktop window associations (`StartupWMClass=lunifier`, `lunifier-nobtsync.desktop`), and comprehensive icon aliases across `/usr/share/pixmaps/` and `/usr/share/icons/hicolor/`.

---

### Package Checksums (SHA-256)

#### Standard Edition (Full Features including Bluetooth Inter-Host Link)
| Asset | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.2.1.exe` | 6.00 MB | `EA83B768AFB4B517B377C7181B37B7BE68DDAB0F311D39562BEF028F60DF2701` |
| `Lunifier-Windows-2.2.1.zip` | 6.43 MB | `C6B99179AC2428F7F12EC33D66E8D2809A87266FA7F13A9B382B7B3A33AE96F6` |
| `Lunifier-2.2.1.0.msix` | 6.74 MB | `7BEDE1CAF82D967673657E75A01DC1A7A10C25157C456CFDFFC791C5D3575F39` |
| `Lunifier-2.2.1.msix` | 6.74 MB | `7BEDE1CAF82D967673657E75A01DC1A7A10C25157C456CFDFFC791C5D3575F39` |
| `lunifier_2.2.1_all.deb` | 178.0 KB | `BC0401CE652399DE633F123365DC97315ACBA79C117F4334823F3FA50D7F07F7` |
| `Lunifier-Linux-2.2.1.tar.gz` | 246.2 KB | `4D42E6AF304415287BC270F80E35E90D1423E5E71A7261CDADC47CCC55D8EF78` |

#### Standalone No-BtSync Edition (No RFCOMM Inter-Host Sync)
| Asset | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.2.1-nobtsync.exe` | 6.01 MB | `5C9663E10382A860E7FAF81DA721A0A0ED0F057626AD3F0573E7F71FEA47D0A7` |
| `Lunifier-Windows-2.2.1-nobtsync.zip` | 6.42 MB | `39ED1BA13F1D960CB86BF9DF6385258DA03B1F6A7DCA3F27828391E2197478FE` |
| `Lunifier-2.2.1.0-nobtsync.msix` | 6.74 MB | `B4F63F17905E3CAD3B8EBDEB6F616C53BCFE7BD775FDC8BC982742F7216C2B02` |
| `Lunifier-2.2.1-nobtsync.msix` | 6.74 MB | `B4F63F17905E3CAD3B8EBDEB6F616C53BCFE7BD775FDC8BC982742F7216C2B02` |
| `lunifier_2.2.1-nobtsync_all.deb` | 178.4 KB | `9E7C621BE63A7B1F322B2CF154BDCBC8368CDAB258FE60FF0914DF72A74FABA6` |
| `Lunifier-Linux-2.2.1-nobtsync.tar.gz` | 246.2 KB | `DB25BD2E13F4B76CA84503F2D4E7A011B93E87438861F244FC3515CA53F182AB` |

---

> [!NOTE]
> **MSIX Package Naming (`2.2.1` vs `2.2.1.0`)**:
> `Lunifier-2.2.1.0.msix` and `Lunifier-2.2.1.msix` (as well as their respective `-nobtsync` counterparts) are bit-for-bit identical binary packages with matching SHA-256 checksums. The 4-part quad version `2.2.1.0` is strictly mandated by the Windows AppX/MSIX packaging specification (`AppxManifest.xml`) and Microsoft Partner Center / Windows Store upload validation (`Major.Minor.Build.Revision`). The 3-part `2.2.1` filename is provided as an alias matching standard semantic versioning and GitHub release tag conventions. Either package can be installed interchangeably.
