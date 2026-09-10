# Lunifier 2.0 Native

Seamless cross-platform software that transfers your **Logitech Easy-Switch keyboards and mice** (MX Keys, MX Master series, M720 Triathlon, POP, etc.) between computers when the mouse cursor hits the edge of your screen—just like **Logitech Flow**, but operating **autonomously over direct Bluetooth, Unifying, and Logi Bolt receivers** without requiring any local network!

Lunifier 2.0 is written from scratch in native code using modern APIs:
- **Windows 11**: Modern C# (.NET 9) with Windows 11 Fluent UI + direct Win32 APIs (`SetupAPI`, `hid.dll`, `user32.dll`, Winsock Bluetooth RFCOMM).
- **Ubuntu 24.04+**: Modern native GNOME application using **GTK4 + Libadwaita** (`Adw.Application`, `Adw.PreferencesWindow`, `Adw.ActionRow`, `Adw.SwitchRow`) with direct Linux `/dev/hidraw`, `libudev`, BlueZ RFCOMM sockets, and X11/Wayland coordinate monitoring.

---

## Why Lunifier?

Official Logitech Flow has significant limitations:
1. **No Linux Support**: Logitech Options+ is not available on Linux.
2. **Network Dependency**: Official Flow mandates that all computers share the same Wi-Fi/LAN subnet with open ports, which fails on VPNs, guest networks, corporate firewalls, or isolated PCs.
3. **Multi-Channel Border Routing**: Lunifier lets you route each screen edge (**Left**, **Right**, **Top**, **Bottom**) per monitor to distinct Easy-Switch channels (**Channel 1**, **Channel 2**, **Channel 3**), effortlessly coordinating 2-PC or 3-PC setups.

**Lunifier 2.0** solves all of these:
- **Autonomous Multi-Protocol Support**: Automatically detects and switches your Logitech devices whether connected via **Direct Bluetooth**, **Unifying Receivers**, **Logi Bolt Receivers**, or mixed transports.
- **Logitech HID++ 2.0 Feature `0x1814` (`CHANGE_HOST`)**: Issues hardware channel switch commands directly to all connected Easy-Switch peripherals simultaneously (<20ms execution).
- **Per-Monitor Border Routing**: Configure borders independently per physical monitor, correctly handling mixed resolutions and monitor alignments.
- **Configurable Active Border Zone**: Select the active middle percentage of each border (10% to 100%) with live visual feedback overlay.
- **Border Knock Activation**: Optional double-touch gesture to switch channels, preventing accidental triggers when working near boundaries.
- **Dual Operating Modes**: Operates completely autonomously on each host with **zero inter-PC connection**, or links peers over **Bluetooth RFCOMM** for cursor entry coordinate alignment and clipboard sync without any LAN/Wi-Fi connection.

---

## Multi-Border 3-Channel Architecture

Configure your desk layout visually:
```
+---------------------------+   +---------------------------+   +---------------------------+
|          Host 1           |   |          Host 2           |   |          Host 3           |
|        (Channel 1)        |   |        (Channel 2)        |   |        (Channel 3)        |
|                           |   |                           |   |                           |
|       Right Border ===>   |   |   <=== Left Border        |   |                           |
|      (Switch to Ch 2)     |   |   (Switch to Ch 1)        |   |                           |
|                           |   |                           |   |                           |
|                           |   |       Right Border ===>   |   |   <=== Left Border        |
|                           |   |      (Switch to Ch 3)     |   |   (Switch to Ch 2)        |
+---------------------------+   +---------------------------+   +---------------------------+
```

When cursor dwells against the border:
- **Host 2 Left Border** $\rightarrow$ Instantly switches keyboard & mouse to **Channel 1**.
- **Host 2 Right Border** $\rightarrow$ Instantly switches keyboard & mouse to **Channel 3**.

---

## Installation & Quick Start

### 1. Windows 11 Native Setup
1. Clone or extract the repository.
2. Run `setup_windows.bat` (builds the native .NET 9 solution and publishes single-file `Lunifier.Windows.exe` to `dist\windows\`).
3. Run `run_gui.bat` to open the Windows 11 Fluent settings UI, or `install_windows.ps1` to install shortcuts and startup integration.

### 2. Ubuntu 24.04+ Native Setup (GTK4 + Libadwaita)
1. Open a terminal in the repository:
   ```bash
   chmod +x setup_linux.sh
   ./setup_linux.sh
   ```
2. Launch the native Libadwaita GUI:
   ```bash
   python3 src/linux/lunifier-adwaita/run_lunifier.py --gui
   ```
3. Or run the daemon headless:
   ```bash
   python3 src/linux/lunifier-adwaita/run_lunifier.py --daemon
   ```
4. Enable autostart on login:
   ```bash
   systemctl --user enable --now lunifier.service
   ```

---

## Configuration (`config.json`)

Settings can be modified via the UI or by editing `config.json`:
- **Windows location**: `%APPDATA%\Lunifier\config.json`
- **Linux location**: `~/.config/lunifier/config.json`

Schema specification: `src/common/config.schema.json`.

```json
{
  "host_name": "Host",
  "my_channel": 1,
  "target_channel": 2,
  "hold_delay_ms": 250,
  "cooldown_ms": 2500,
  "border_active_zone_pct": 50,
  "knock_enabled": false,
  "knock_timeout_ms": 1000,
  "monitor_configs": {
    "0": {
      "enabled": true,
      "edges": {
        "left": null,
        "right": 2,
        "top": null,
        "bottom": null
      }
    }
  },
  "switch_backend": "auto",
  "connection_support": "both",
  "log_level": "normal",
  "bt_p2p_enabled": false,
  "sync_cursor_position": true,
  "sync_clipboard": false
}
```

---

## Author & License
- **Author**: Silviu Vlasceanu ([@silviuk](https://github.com/silviuk))
- **License**: MIT
