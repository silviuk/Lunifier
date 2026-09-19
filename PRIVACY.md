# Privacy Policy for Lunifier

**Effective Date:** September 19, 2026

**Lunifier** ("we", "our", or "the application") is an open-source utility designed to coordinate Logitech Easy-Switch keyboard and mouse channel switching across multiple screens and systems.

## 1. Zero Data Collection
Lunifier is designed with complete privacy in mind:
- **No Personal Information Collected**: Lunifier does not collect, store, transmit, or sell any personal data, user identifiers, or usage telemetry.
- **No Analytics or Telemetry**: There are no tracking scripts, third-party SDKs, or background telemetry services embedded in Lunifier.
- **No Cloud Synchronization**: All operations and configurations are executed entirely on your local machine.

## 2. Local Hardware Interfacing
Lunifier communicates directly with connected input devices (such as Logitech keyboards and mice) over local USB and Bluetooth interfaces using standard HID/HID++ protocols:
- Cursor position coordinates are evaluated purely in memory to trigger edge dwell and double-tap knock actions.
- Cursor positions and mouse coordinates are never saved to disk or broadcast over the network.
- Hotkey triggers (such as `Ctrl+Alt+1`) are monitored strictly for switching channels and are never logged as keystroke data.

## 3. Local Configuration
Configuration preferences (e.g., border dwell sensitivity, double-click actions, hotkeys) are stored locally on your device in standard application data paths (such as `%APPDATA%\Lunifier` on Windows or `~/.config/lunifier` on Linux). This data never leaves your computer.

## 4. Open Source & Transparency
Lunifier is open-source software distributed under the MIT License. The complete source code is publicly accessible for review and auditing at:
[https://github.com/silviuk/Lunifier](https://github.com/silviuk/Lunifier)

## 5. Contact
If you have any questions or feedback regarding this Privacy Policy, please open an issue on GitHub:
[https://github.com/silviuk/Lunifier/issues](https://github.com/silviuk/Lunifier/issues)
