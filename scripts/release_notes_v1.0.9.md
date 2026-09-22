### Lunifier v1.0.9 Release Notes

#### What's New in v1.0.9
- **Local Bluetooth Address Field & 1-Click Copy**:
  - Displays the local machine's primary Bluetooth adapter MAC address directly in the "Host A: Advertise This Computer" card.
  - Added a `📋 Copy Address` button with clipboard integration and visual feedback (`✓ Copied`).
  - Added a `🔄` adapter refresh button with universal local Bluetooth MAC resolution across Windows and Linux.
- **Fixed Windows Bluetooth RFCOMM Server Socket Bind**:
  - Universally bound the RFCOMM server socket to `"00:00:00:00:00:00"` (`BDADDR_ANY`) instead of an empty string, resolving the `bad bluetooth address` error on Windows Winsock.
  - Eliminated the periodic 5-second server retry loop log spam and enabled reliable discovery probe detection and pairing between peer hosts.
- **Responsive Window Sizing & Zero Button Squeezing**:
  - Dynamically scales default window geometry to `780x1020` on both Windows and Linux, adapting safely to screen height.
  - Wrapped the Bluetooth Inter-Host Link page in a `CTkScrollableFrame` so content scrolls smoothly on smaller screens and displays with DPI scaling, completely preventing the "Test Switch Channel Now" and "Save Configuration" buttons from being squeezed or clipped.
- **Enhanced Bluetooth Pairing Clarity**:
  - Reorganized UI cards into "Host A: Advertise This Computer (Quick Pair)", "Host B: Find & Link Advertising Computer (Quick Pair)", and "Peer Link Status & Settings (Zero Network Bluetooth)".

#### Release Checksums (SHA256)
- `Lunifier-Setup-1.0.9.exe`: `F634D2B10426B115A706B844C3045DA33B2CDE7A0E15F95AD4A57D9B0AB2744A`
- `Lunifier-Windows-1.0.9.zip`: `558A40A8FD910EDD1BFBEB434C96DA54862DB72D6B4F40A3723D65D4BF8D502E`
- `Lunifier-1.0.9.0.msix`: `81FE8BB7FBC9E4BA2BFC8CA741E05081918FE7DCDABC9ECEEE6EA612570FC297`
- `lunifier_1.0.9_all.deb`: `9BEBB15C26CE2243C971CEE37E9B864E036DBC7953E9F0308C6561E1AC56E5F4`
- `Lunifier-Linux-1.0.9.tar.gz`: `F582CAD88B2595AF7C2D1D86ED9000BA6D71C8655C3E5534500ED62601CE3BBC`
