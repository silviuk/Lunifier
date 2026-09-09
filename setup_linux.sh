#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=== Lunifier Linux Setup ==="
echo "Project location: $PROJECT_DIR"

# 1. Install udev rule for raw HID++ Logitech device access without root
echo "[1/4] Configuring udev rules for Logitech devices..."
UDEV_RULE_FILE="/etc/udev/rules.d/99-logitech-hidpp.rules"
if [ ! -f "$UDEV_RULE_FILE" ]; then
    echo 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", MODE="0666"' | sudo tee "$UDEV_RULE_FILE" > /dev/null
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "  Installed $UDEV_RULE_FILE successfully."
else
    echo "  $UDEV_RULE_FILE already exists."
fi

# 2. Check recommendations
echo "[2/4] Checking optional utilities (xdotool, xclip, solaar)..."
for cmd in xdotool xclip solaar; do
    if command -v $cmd &> /dev/null; then
        echo "  [OK] $cmd is installed."
    else
        echo "  [INFO] $cmd not found. Optional, but recommended: sudo apt install -y $cmd"
    fi
done

# 3. Install Python dependencies (supports PEP 668 on modern Linux)
echo "[3/4] Installing Python requirements..."
if ! pip3 install --user hidapi customtkinter 2>/dev/null; then
    echo "  Standard pip install restricted by system (PEP 668); retrying with --break-system-packages..."
    pip3 install --user --break-system-packages hidapi customtkinter || {
        echo "  [NOTE] If pip fails, install via package manager: sudo apt install -y python3-hidapi python3-tk"
    }
fi

# 4. Install Desktop Entry and Application Icon for current user
echo "[4/5] Installing Application Icon & Desktop Launcher..."
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$ICON_DIR" "$APPS_DIR"

if [ -f "$PROJECT_DIR/lunifier/resources/icon.png" ]; then
    cp "$PROJECT_DIR/lunifier/resources/icon.png" "$ICON_DIR/lunifier.png"
fi

cat << EOF > "$APPS_DIR/lunifier.desktop"
[Desktop Entry]
Name=Lunifier
Comment=Seamless Logitech Easy-Switch Screen Flow
Exec=python3 -m lunifier.app --gui
Icon=lunifier
Terminal=false
Type=Application
Categories=Utility;HardwareSettings;
Keywords=logitech;flow;easy-switch;mx-keys;mouse;
StartupNotify=true
Path=$PROJECT_DIR
EOF

# Update desktop and icon databases if available
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_DIR" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true

# 5. Create systemd user service with dynamic project directory
echo "[5/5] Setting up systemd user service (optional autostart)..."
SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"
cat << EOF > "$SERVICE_DIR/lunifier.service"
[Unit]
Description=Lunifier - Seamless Logitech Easy-Switch Flow
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -m lunifier.app --daemon
WorkingDirectory=$PROJECT_DIR
Restart=always
RestartSec=3

[Install]
WantedBy=graphical-session.target
EOF

echo ""
echo "=== Setup Completed Successfully! ==="
echo "Application icon and desktop entry installed in your app menu."
echo "To test device scanning: python3 -m lunifier.app --scan"
echo "To launch settings GUI:  python3 -m lunifier.app --gui"
echo "To enable autostart:     systemctl --user enable --now lunifier.service"
