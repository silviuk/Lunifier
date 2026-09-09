# Lunifier

Seamless cross-platform (Windows & Linux) software that transfers your **Logitech Easy-Switch keyboards and mice** (MX Keys, MX Master series, M720 Triathlon, POP, etc.) between computers when the mouse cursor hits the edge of your screen—just like **Logitech Flow**, but operating **autonomously over direct Bluetooth, Unifying, and Logi Bolt receivers** without requiring any local network!

---

## Why Lunifier?

Official Logitech Flow has significant limitations:
1. **No Linux Support**: Logitech Options+ is not available on Linux.
2. **Network Dependency**: Official Flow mandates that all computers share the same Wi-Fi/LAN subnet with open ports, which fails on VPNs, guest networks, corporate firewalls, or isolated PCs.
3. **Multi-Channel Border Routing**: Lunifier lets you route each screen edge (**Left**, **Right**, **Top**, **Bottom**) to distinct Easy-Switch channels (**Channel 1**, **Channel 2**, **Channel 3**), effortlessly coordinating 2-PC or 3-PC setups.

**Lunifier** solves all of these:
- **Autonomous Multi-Protocol Support**: Automatically detects and switches your Logitech devices whether connected via **Direct Bluetooth**, **Unifying Receivers**, **Logi Bolt Receivers**, or mixed transports (e.g. keyboard on Unifying receiver and mouse on Bluetooth).
- **Logitech HID++ 2.0 Feature `0x1814` (`CHANGE_HOST`)**: Issues hardware channel switch commands directly to all connected Easy-Switch peripherals simultaneously.
- **Multi-Border Screen Routing**: Configure what happens at each border independently: e.g. Left Border switches to Channel 1, Right Border switches to Channel 3.
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

### 1. Windows Installation

#### Option A: Windows Installer (`.exe` / Winget ready)
Download and run **`Lunifier-Setup-1.0.0.exe`** from [Releases](https://github.com/silviuk/Lunifier/releases).
- Includes clean installation to `Program Files\Lunifier`, Start Menu shortcuts, Desktop icons, uninstaller, and optional Windows startup integration.
- Fully compatible with silent installs:
  ```powershell
  Lunifier-Setup-1.0.0.exe /VERYSILENT /NORESTART
  ```

#### Option B: Windows Package Manager (Winget)
Once submitted to the official winget-pkgs repository, or using the local manifest:
```powershell
winget install silviuk.Lunifier
```

#### Option C: Portable / Development Setup
1. Clone or extract the repository.
2. Run `setup_windows.bat` (installs dependencies and tests device detection).
3. Run `run_gui.bat` to configure settings, or `run_daemon.bat` to start the background service.

---

### 2. Linux Installation

#### Option A: Debian / Ubuntu Package (`.deb`)
Download the `.deb` package from [Releases](https://github.com/silviuk/Lunifier/releases):
```bash
sudo apt install ./lunifier_1.0.0_all.deb
```
This automatically configures udev rules, installs desktop launcher shortcuts, and sets up a systemd user service.

#### Option B: Setup Script (Any Linux distribution)
1. Open a terminal in the cloned repository:
   ```bash
   chmod +x setup_linux.sh
   ./setup_linux.sh
   ```
2. Launch the settings GUI:
   ```bash
   python3 -m lunifier.app --gui
   # or simply
   lunifier --gui
   ```
3. Enable autostart on login:
   ```bash
   systemctl --user enable --now lunifier.service
   ```

---

## Configuration (`config.json`)

Settings can be modified via the GUI (`lunifier --gui`) or by editing `config.json`:
- **Windows location**: `%APPDATA%\Lunifier\config.json`
- **Linux location**: `~/.config/lunifier/config.json`

*(Note: Lunifier automatically migrates existing legacy settings if found).*

```json
{
    "host_name": "Host",
    "my_channel": 2,
    "target_channel": 3,
    "trigger_edge": "right",
    "entry_edge": "left",
    "hold_delay_ms": 250,
    "cooldown_ms": 2500,
    "edge_channels": {
        "left": 1,
        "right": 3,
        "top": null,
        "bottom": null
    },
    "devices": [
        "MX Keys",
        "Keys",
        "M370",
        "POP",
        "Triathlon",
        "M720",
        "MX Master",
        "MX Anywhere",
        "Mouse"
    ],
    "bt_p2p_enabled": false,
    "bt_peer_address": "",
    "sync_clipboard": false
}
```

### Key Parameters:
- `my_channel`: Easy-Switch channel (1, 2, or 3) on the current computer.
- `edge_channels`: Maps each screen edge (`left`, `right`, `top`, `bottom`) to a target Easy-Switch channel (or `null` to disable).
- `hold_delay_ms`: Dwell time (in milliseconds) before triggering to prevent accidental switches when targeting scrollbars or window edges (default: `250`).
- `cooldown_ms`: Delay after a switch before a new trigger is accepted to avoid immediate bounce-back.
- `bt_peer_address`: Bluetooth MAC address of partner host (optional, leave empty for Autonomous mode).

---

## CLI Usage

```text
usage: lunifier [-h] [--scan] [--switch {1,2,3}] [--daemon] [--gui] [--setup] [--config CONFIG]

Lunifier - Seamless cross-platform Logitech Easy-Switch Flow

options:
  -h, --help            show this help message and exit
  --scan                Scan and list connected Logitech devices across Bluetooth & Unifying
  --switch {1,2,3}      Immediately switch devices to Channel 1, 2, or 3
  --daemon              Run in background daemon mode
  --gui                 Launch the GUI settings and status window
  --setup, --configure  Interactive terminal configuration wizard
  --config CONFIG       Path to custom config.json file
```

---

## License

MIT License. Copyright (c) 2026 Silviu Vlasceanu.
