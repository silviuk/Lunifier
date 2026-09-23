# Lunifier 2.1.5 Release Notes

**Lunifier v2.1.5** delivers essential UI contrast and readability enhancements across Light and Dark themes, unified button and status badge dimensions, and an organized tab layout for Windows 11 native (.NET 9 WPF).

## What's New & Improved in v2.1.5

- **High-Contrast Readability across Light & Dark Modes**:
  - Fixed dark text appearing on blue buttons in Light mode by enforcing pure white text in the button control template resources.
  - Redesigned the service status badge (RUNNING / STOPPED) into a high-contrast solid pill (`#16A34A` vibrant green / `#DC2626` crimson red) with bold pure white centered typography.
  - Replaced low-contrast light green on green and light red on red status labels with dynamic theme-aware high-contrast colors (`#15803D` / `#DC2626` in light mode, `#4ADE80` / `#F87171` in dark mode).
- **Uniform Button & Status Badge Dimensions and Alignment**:
  - Centered all button text both horizontally and vertically across the entire application.
  - Aligned running status badge and start/stop service button with identical dimensions (130x32px), matching corner radius (4px), and centered typography.
- **Tab Layout Reorganization**:
  - Renamed "Connected Devices" tab to **"Advanced"** and wrapped contents in a smooth scroll viewer.
  - Relocated "Edge Trigger Sensitivity" and "Hardware & Logging Options" cards from "Screen & Switching" into the "Advanced" tab, keeping "Screen & Switching" focused exclusively on Host Identity and Display/Border configuration.
  - Relocated the "Save Configuration" button to the top header row alongside the service status badge and toggle button, removing the redundant footer button.

---

## Artifact Checksums (SHA256)

| Asset | Description | SHA256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.1.5.exe` | Windows Inno Setup Installer | `107833C206E922C74D5A581C47F4D3C0054FBBB06A6D63E57C15A199B8C680E1` |
| `Lunifier-Windows-2.1.5.zip` | Windows Portable x64 | `A1BD1C005AE700CE78F472BCEFD15DFD0997B7EED2F232AA1381834126FACDC7` |
| `Lunifier-2.1.5.0.msix` | Windows Store / Enterprise MSIX | `6215CD7F45915EEE735239C01EBF401F835ABB450DA1B9AF88A119FCB1B5538C` |
| `lunifier_2.1.5_all.deb` | Debian / Ubuntu Package | `BA1D7D6775A46E5C707408417B78EE21265BB1D2F2CA8F4AA6C80ED7E07E166C` |
| `Lunifier-Linux-2.1.5.tar.gz` | Linux Portable Tarball | `EDEB545AFFF6C60091D5B20CB571123489E98F663FA59B9FD7DC5F5598A861B7` |
