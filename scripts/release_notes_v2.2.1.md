# Lunifier 2.2.1 Release Notes

**Lunifier 2.2.1** provides official **Windows Store / Partner Center-compliant MSIX packages** built with Microsoft's `MakeAppx` tool, including authentic Open Packaging Conventions (`AppxBlockMap.xml`, `[Content_Types].xml`), distinct package identities for the Standard and No-BtSync editions, High-DPI visual tile/logo scale variants (`scale-100`, `scale-200`, `targetsize-44`, `targetsize-24`), and updated packages across Windows and Linux.

---

### Highlights & Fixes in v2.2.1

#### 1. Official Windows Store / Partner Center MSIX Compliance
- **Genuine MakeAppx Packaging**: Replaced fallback archive packaging with official Microsoft `MakeAppx.exe`, generating required cryptographic block maps (`AppxBlockMap.xml`) and Open Packaging Conventions manifests (`[Content_Types].xml`).
- **Fixed Manifest Versioning**: Corrected manifest generation to strictly update `<Identity Version="..." />` while preserving standard XML declarations (`<?xml version="1.0"?>`) and OS dependencies (`TargetDeviceFamily MinVersion="10.0.17763.0"`), passing Microsoft Partner Center schema validation.
- **Distinct Identity for No-BtSync Edition**: Configured `SilviuVlasceanu.LunifierNoBtSync` and `DisplayName="Lunifier (No-BtSync Edition)"` to allow seamless separate Windows Store submission without identity or package conflicts.
- **High-DPI Visual Assets**: Added comprehensive scale and target-size variants (`Square44x44Logo`, `Square150x150Logo`, `Wide310x150Logo`, `StoreLogo` at 100% and 200% scale plus unplated 44px/24px taskbar icons) ensuring crisp visuals and passing Windows App Certification Kit (WACK) asset tests.

---

### Package Checksums (SHA-256)

#### Standard Edition (Full Features including Bluetooth Inter-Host Link)
| Asset | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.2.1.exe` | 6.00 MB | `EA83B768AFB4B517B377C7181B37B7BE68DDAB0F311D39562BEF028F60DF2701` |
| `Lunifier-Windows-2.2.1.zip` | 6.43 MB | `C6B99179AC2428F7F12EC33D66E8D2809A87266FA7F13A9B382B7B3A33AE96F6` |
| `Lunifier-2.2.1.0.msix` | 6.74 MB | `7BEDE1CAF82D967673657E75A01DC1A7A10C25157C456CFDFFC791C5D3575F39` |
| `Lunifier-2.2.1.msix` | 6.74 MB | `7BEDE1CAF82D967673657E75A01DC1A7A10C25157C456CFDFFC791C5D3575F39` |
| `lunifier_2.2.1_all.deb` | 170.7 KB | `F21D64A01341E0DB0F6A5ACC8C5D488F351A1C99EE83CC0AD56BF3F73B2C307E` |
| `Lunifier-Linux-2.2.1.tar.gz` | 239.0 KB | `3E6634A71DA139E44A26354F488FFE72C8EF4A18234D1B86E2533E905E2370B1` |

#### Standalone No-BtSync Edition (No RFCOMM Inter-Host Sync)
| Asset | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.2.1-nobtsync.exe` | 6.01 MB | `5C9663E10382A860E7FAF81DA721A0A0ED0F057626AD3F0573E7F71FEA47D0A7` |
| `Lunifier-Windows-2.2.1-nobtsync.zip` | 6.42 MB | `39ED1BA13F1D960CB86BF9DF6385258DA03B1F6A7DCA3F27828391E2197478FE` |
| `Lunifier-2.2.1.0-nobtsync.msix` | 6.74 MB | `B4F63F17905E3CAD3B8EBDEB6F616C53BCFE7BD775FDC8BC982742F7216C2B02` |
| `Lunifier-2.2.1-nobtsync.msix` | 6.74 MB | `B4F63F17905E3CAD3B8EBDEB6F616C53BCFE7BD775FDC8BC982742F7216C2B02` |
| `lunifier_2.2.1-nobtsync_all.deb` | 170.7 KB | `A7879069A1B694E3149576D8671713DEEA0392C5171E5BE0C8A745F30A057BC2` |
| `Lunifier-Linux-2.2.1-nobtsync.tar.gz` | 239.1 KB | `4FF06A54D79D1E378F1C712F30340E79597EADD691276AB6CDB8FC6C1450565E` |

---

> [!NOTE]
> **MSIX Package Naming (`2.2.1` vs `2.2.1.0`)**:
> `Lunifier-2.2.1.0.msix` and `Lunifier-2.2.1.msix` (as well as their respective `-nobtsync` counterparts) are bit-for-bit identical binary packages with matching SHA-256 checksums. The 4-part quad version `2.2.1.0` is strictly mandated by the Windows AppX/MSIX packaging specification (`AppxManifest.xml`) and Microsoft Partner Center / Windows Store upload validation (`Major.Minor.Build.Revision`). The 3-part `2.2.1` filename is provided as an alias matching standard semantic versioning and GitHub release tag conventions. Either package can be installed interchangeably.
