# Lunifier 2.x source builds

Use the [2.0 branch](https://github.com/silviuk/Lunifier/tree/2.0) for the native Windows and Linux applications.

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


See [configuration](CONFIGURATION.md) for the settings schema.
