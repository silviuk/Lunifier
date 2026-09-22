# Lunifier 2.1.2 Release Notes

**Lunifier v2.1.2** is a release for the native 2.0 architecture (.NET 9 WPF on Windows 11 and GTK4 + Libadwaita on Linux), bringing dynamic Bluetooth RFCOMM port allocation, automatic binding recovery, and live over-the-air BLE broadcasting.

## What's New in v2.1.2
- **Over-the-Air Live BLE Advertisement Broadcaster & Watcher**:
  - Implemented live Bluetooth Low Energy (BLE) advertisement packets containing Lunifier beacon data (magic `LUNI`, protocol version, RFCOMM channel, Classic BT MAC, ephemeral token, host name).
  - Built-in on Windows via native WinRT `BluetoothLEAdvertisementPublisher` and `BluetoothLEAdvertisementWatcher` (.NET 9 Win10/11 projection).
  - Built-in on Linux via BlueZ `bluetoothctl` / D-Bus.
  - Enables advertising hosts to be discovered over the air instantly by scanning hosts without requiring prior pairing.
- **Dynamic RFCOMM Port Allocation & Port Auto-Binding Fallback**:
  - Automatically detects available RFCOMM channels and binds to candidate ports in range `[preferred, 5..30]`.
  - Gracefully recovers if port 4, 7, or any other port is reserved or in use by another application or the Windows Bluetooth stack (`[WinError 10048]` / `10013`).
  - Automatically migrates legacy config from port 4 to port 5.
  - Discovery beacon and RFCOMM probe replies report the actual bound listening port; pairing clients automatically connect to and save the target's reported port.
- **Bluetooth Server Bind Error Elimination**:
  - Completely eliminated continuous 5-second `Bluetooth link server bind error: [WinError 10048]` log spam by automatically selecting an available port on startup.
- **Window Sizing & Layout Optimization**:
  - Increased default window dimensions (Windows: 780x1020, Linux: 780x980) so that bottom action buttons and configuration cards are fully displayed without vertical squeezing.

## Release Checksums (SHA256)
| File | Description | SHA256 Hash |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.1.2.exe` | Windows Inno Setup Installer | `34B9A3660FAD1980C222664527EBA7C30CE0D7809E39E030B4145ACCA557EE21` |
| `Lunifier-Windows-2.1.2.zip` | Windows Portable x64 | `5DF69E05968C059AC2029FA804E87A721AD030F3DA6D7F4166042CD8BDEB7172` |
| `Lunifier-2.1.2.0.msix` | Windows Store / Enterprise MSIX | `5CD8196C2D62BFA9A224C09D8721BF15AE7C863DE0EA7C35574BCEEE1223D007` |
| `lunifier_2.1.2_all.deb` | Debian / Ubuntu Package | `F6F2FB9B4BE66D9617ABB8B2848F01679D9D98C941E681B04AD270B4286AF69E` |
| `Lunifier-Linux-2.1.2.tar.gz` | Linux Portable Tarball | `A17609E58ABFC336A20FBC2F161B6CC6429B201135BAC358AC813C809963F3D8` |
