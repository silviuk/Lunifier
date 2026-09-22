# Lunifier 2.1.1 Release Notes

**Lunifier v2.1.1** is a maintenance and feature update for the native 2.0 architecture (.NET 9 WPF on Windows 11 and GTK4 + Libadwaita on Linux).

## What's New in v2.1.1
- **Local Bluetooth Address Field & 1-Click Copy**:
  - Displays the local machine's primary Bluetooth adapter MAC address directly in the "Host A: Advertise This Computer" card.
  - Implemented in Windows C# .NET 9 (`BluetoothPeer.GetLocalBluetoothMac()`) via native Winsock socket bind and in Linux GTK4/Adwaita via sysfs and `bluetoothctl list`.
  - Added a `Copy` button with 1-click clipboard integration and visual feedback (`✓ Copied`).
- **Fixed Windows Bluetooth RFCOMM Server Socket Bind**:
  - Universally bound the RFCOMM server socket to `"00:00:00:00:00:00"` (`BDADDR_ANY`), completely eliminating the `bad bluetooth address` Winsock error and periodic retry loop log spam.
- **Window Sizing & Responsive Content Fitting**:
  - Increased default window height to `980` on Windows and `920` on Linux, ensuring full visibility of the bottom action buttons ("Test Switch Channel Now", "Save Configuration") without vertical squeezing across various display scaling factors.
- **Enhanced Bluetooth Pairing Clarity**:
  - Reorganized UI cards into "Host A: Advertise This Computer (Quick Pair)", "Host B: Find & Link Advertising Computer (Quick Pair)", and "Peer Link Status & Settings (Zero Network Bluetooth)".
  - Added explicit instructions distinguishing the automated 1-click Quick Pairing wizard from the persistent underlying RFCOMM link configuration and manual fallback handshake.

## Release Checksums (SHA256)
| File | Description | SHA256 Hash |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.1.1.exe` | Windows Inno Setup Installer | `AF1B0726A4860BC0FCC9541A5F95F4115889B302894DACC83FE9B9F4636B1D84` |
| `Lunifier-Windows-2.1.1.zip` | Windows Portable x64 | `0898BE6C6671C39D9226C144AECFD23C94F739DAB0B05138DD44C7A3A5D07AFB` |
| `Lunifier-2.1.1.0.msix` | Windows Store / Enterprise MSIX | `50CA6B24CA42C3BF07A6DE883F94C6369D12513A002D9C57BA95CCE86339B3E9` |
| `lunifier_2.1.1_all.deb` | Debian / Ubuntu Package | `E03D145E77AC9A4B58EFBF21A4B9D6AFC84F944B5D8A9D9A0769EEDB2BFBC802` |
| `Lunifier-Linux-2.1.1.tar.gz` | Linux Portable Tarball | `665CCD54BDFCFA8E9C1A11C7A0C2F0CE3157D37915EFA4458F1B80EC2D38FFD6` |
