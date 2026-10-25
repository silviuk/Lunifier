[**Website & downloads ↗**](https://silviuk.github.io/Lunifier/) · [Latest release](https://github.com/silviuk/Lunifier/releases/latest)

[![Support on Ko-fi](docs/assets/ko-fi.svg)](https://ko-fi.com/silviuvlasceanu)

# Lunifier

Move your Logitech keyboard and mouse between computers by touching a screen edge. Your Easy-Switch devices change hardware channels together, without needing a shared Wi-Fi or LAN.

**Windows + Linux · Logitech Easy-Switch**

## Why Lunifier?

- **Choose your edges.** Map the left, right, top, and bottom edges to Easy-Switch channels 1, 2, or 3.
- **Switch your way.** Use screen edges, global hotkeys, or the tray menu. Tune dwell and cooldown to suit your desk.
- **Keep the connection local.** Hardware switching works independently on each host. Optional Bluetooth peer features add cursor alignment and text clipboard sync.

## See it in action

<img src="docs/assets/screen-switching.png" alt="Configure screen edges, host channels, and switching shortcuts." width="350">

*Configure screen edges, host channels, and switching shortcuts.*

<img src="docs/assets/advanced.png" alt="Detect devices and adjust switching behavior." width="350">

*Detect devices and adjust switching behavior.*

## Get started

1. Pair your compatible keyboard and mouse with each computer on its own Easy-Switch channel.
2. Install Lunifier on each host and select that computer’s channel.
3. Assign screen edges to the other channels, then move to an edge to switch.

### Debian / Ubuntu

Download the latest `.deb` from Releases, or use the [APT installation instructions](https://silviuk.github.io/Lunifier/#installation).

## Requirements & limits

A Windows or Linux computer for each host, compatible Logitech Easy-Switch peripherals, and Bluetooth, Unifying, or Logi Bolt connections supported by your devices. Pair the devices with every host before configuring Lunifier.

Hardware support depends on the device’s HID++ Easy-Switch features. Bluetooth peer features are optional and off by default. Lunifier is an independent project, unaffiliated with Logitech.

## Documentation & contributing

[Configuration reference](docs/CONFIGURATION.md) and [source build instructions](docs/DEVELOPMENT.md). The current native Windows source is maintained on the [2.0 branch](https://github.com/silviuk/Lunifier/tree/2.0).

Found a problem or have an idea? [Open an issue](https://github.com/silviuk/Lunifier/issues). If the app helps you, [support its development on Ko-fi](https://ko-fi.com/silviuvlasceanu).

© 2026 Silviu Vlasceanu. [License](LICENSE).
