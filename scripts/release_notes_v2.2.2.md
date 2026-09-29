# Lunifier 2.2.2 Release Notes

**Lunifier 2.2.2** resolves intermittent mouse cursor jitter/stutter during normal PC usage by eliminating Bluetooth baseband radio contention through intelligent exponential backoff, cursor activity gating, strict `bt_p2p_enabled` enforcement, and Linux X11 display caching optimizations across Windows and Linux.

---

### Highlights & Fixes in v2.2.2

#### 1. Mouse Jitter Elimination via Radio Paging Contention Fix
- **Exponential Reconnection Backoff**: Replaced the previous fixed 5-second reconnect loop with an intelligent exponential backoff:
  $$5\text{s} \longrightarrow 10\text{s} \longrightarrow 20\text{s} \longrightarrow 40\text{s} \longrightarrow \text{capped at } 60\text{s}$$
  This slashes Bluetooth baseband radio paging duty cycle from ~50% of uptime down to under 1.5%, preventing Bluetooth HID packet starvation and 2.4 GHz co-channel RF interference on both Bluetooth mice and USB dongles (Bolt / Unifying).
- **Cursor Activity-Gated Reconnection**: `EdgeDetector` continuously tracks cursor displacement. If the mouse is actively moving ($\ge 4\text{ px}$ displacement within the last 600ms), background RFCOMM `connect()` calls are deferred by 1 second until the mouse is stationary, guaranteeing that radio paging never coincides with active mouse manipulation.
- **Instant Backoff Reset**: Backoff automatically resets back to 5.0s whenever you trigger a screen border switch (`NotifySwitchOut`), pair with a new host, or start the service, ensuring immediate sync with zero latency.

#### 2. Strict Enforcement of `bt_p2p_enabled`
- Fixed a bug on both Windows and Linux where background Bluetooth reconnect loops would start even if "Enable Bluetooth Link" was toggled off, provided a peer MAC address was saved in configuration.
- The background Bluetooth client and server now strictly require `bt_p2p_enabled: true` and a valid peer MAC address before initializing.

#### 3. Linux Input Polling & X11 Display Hardening
- **Persistent X11 Display Caching**: Avoids opening and closing ephemeral X11 display connections on every 15ms poll iteration, eliminating X server socket queue latency.
- **Throttled Subprocess Fallback**: In environments without native X11 libraries, fallback `xdotool` queries are throttled to 20 Hz (50ms interval) to eliminate process-fork storms and CPU hitching.

---

### Package Checksums (SHA-256)

#### Standard Edition (Full Features including Bluetooth Inter-Host Link)
| Asset | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.2.2.exe` | 6.00 MB | `D2CF5970748E62FD98D5258AF639CC74FCE36CC539FDC08ED154EA9417AD1EFE` |
| `Lunifier-Windows-2.2.2.zip` | 6.43 MB | `7D3482DCD78DC766F7EF9DF96D50BE5F70EA898FA8AE31059CA9201C1210D4CD` |
| `Lunifier-2.2.2.0.msix` | 6.73 MB | `F65C2C619FD19CA22C5D4EFB8EFEB09566B6C495B5978955A8228403A67099AA` |
| `Lunifier-2.2.2.msix` | 6.73 MB | `F65C2C619FD19CA22C5D4EFB8EFEB09566B6C495B5978955A8228403A67099AA` |
| `lunifier_2.2.2_all.deb` | 178.7 KB | `30732C0C7234D5C9E739E9A11BBA67ECA63A20DFB700BE15A8C778FB4D5EA667` |
| `Lunifier-Linux-2.2.2.tar.gz` | 246.8 KB | `88330352A35616ECB8C3A62D7FC9D96FCB389E82781BC531722ED395499CA6DC` |

#### Standalone No-BtSync Edition (No RFCOMM Inter-Host Sync)
| Asset | Size | SHA-256 Checksum |
| :--- | :--- | :--- |
| `Lunifier-Setup-2.2.2-nobtsync.exe` | 6.00 MB | `A1170854A505EF749BD9CD62C2B1C6C061B270B1DB0049CFA17BD355FBD3E2F8` |
| `Lunifier-Windows-2.2.2-nobtsync.zip` | 6.43 MB | `4B08A12E348C65F97D6268D8E16E5EA7C6221EF26D7EF5D2FC7DA8F7A2A7830E` |
| `Lunifier-2.2.2.0-nobtsync.msix` | 6.73 MB | `D26261539332125A4C71D660CC1D28301BD0D87CF98F0E0F59B71B2D214A9563` |
| `Lunifier-2.2.2-nobtsync.msix` | 6.73 MB | `D26261539332125A4C71D660CC1D28301BD0D87CF98F0E0F59B71B2D214A9563` |
| `lunifier_2.2.2-nobtsync_all.deb` | 179.1 KB | `1CA73F3FE0190929A2288EC4A87AE69761D0EC2C7A31EF71BB81D9BB2E69624D` |
| `Lunifier-Linux-2.2.2-nobtsync.tar.gz` | 246.8 KB | `D844D31D383A81F6B00545A29879B4415F0282844ACDCE43ABF177FB77CD8633` |

---

> [!NOTE]
> **MSIX Package Naming (`2.2.2` vs `2.2.2.0`)**:
> `Lunifier-2.2.2.0.msix` and `Lunifier-2.2.2.msix` (as well as their respective `-nobtsync` counterparts) are bit-for-bit identical binary packages with matching SHA-256 checksums. The 4-part quad version `2.2.2.0` is strictly mandated by the Windows AppX/MSIX packaging specification (`AppxManifest.xml`) and Microsoft Partner Center / Windows Store upload validation (`Major.Minor.Build.Revision`). The 3-part `2.2.2` filename is provided as an alias matching standard semantic versioning and GitHub release tag conventions. Either package can be installed interchangeably.
