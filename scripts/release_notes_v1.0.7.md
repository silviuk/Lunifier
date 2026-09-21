### Lunifier v1.0.7 Release Notes

#### What's New in v1.0.7
- **Scalable Vector Graphics Icon Pipeline**:
  - Replaced raster-dependent icon sizing with mathematical vector rendering and supersampled anti-aliasing.
  - Multi-resolution mipmap suite (`16px`, `24px`, `32px`, `48px`, `64px`, `128px`, `256px`, `512px`) providing crisp, pixel-perfect visuals on 4K, retina, and fractional display scaling factors (100%, 125%, 150%, 200%).
  - Integrated high-DPI icons into window titles, application headers, system tray, and OS taskbars on Windows and Linux.
- **Bluetooth-Only Timed Peer Discovery & Linking**:
  - **Zero Network / LAN Traffic**: 100% of inter-host traffic is conducted over Bluetooth RFCOMM / BLE. No Wi-Fi or local network ports are opened.
  - **Timed Advertising Button**: User-activated **"Advertise Lunifier"** button with a real-time countdown timer (30s, 60s, 120s, 300s) that automatically disables upon timeout.
  - **Strict Peer Filtering**: Scanning sends Bluetooth discovery probes and detects **only** partner hosts actively advertising Lunifier, filtering out unrelated phones, headsets, and other Bluetooth devices.
  - **1-Click Secure Handshake & Pairing**: Automated mutual pairing handshake over Bluetooth verifying ephemeral discovery tokens and establishing an authenticated session.
  - **Encrypted Inter-Host Synchronization**: Seamlessly exchanges cursor alignment boundaries and synchronized clipboard text over the encrypted Bluetooth connection.

#### Package Checksums (SHA-256)
- `Lunifier-Setup-1.0.7.exe`: `A2FE68E7C645346B61449AA47A06939AE63BA8D6B95C714A7F78208C9E937D59`
- `Lunifier-Windows-1.0.7.zip`: `634FDDC0E0F38001D347A24846742F6D5D27F59693CEF14D4ECFC14C8E11FF2A`
- `Lunifier-1.0.7.0.msix`: `DCCFFDDA2FFCF7C781B17C380E08862366AFB5B23A62BAAC216DA695BF4D807B`
- `lunifier_1.0.7_all.deb`: `BB3693FBB1A1D23363BB414D96185570AC2D46F96E1F392D9D1E29CA7EA879D2`
- `Lunifier-Linux-1.0.7.tar.gz`: `F2FEF6EE7CC036E73E7B4246E21A3BDDAB26DD7E779A6EF56629FEC9AD967195`
