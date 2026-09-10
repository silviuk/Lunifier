#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=== Lunifier 2.0 Native Linux Setup (GTK4 + Libadwaita) ==="
echo "Project location: $PROJECT_DIR"

# 1. Install udev rule for raw HID++ Logitech device access without root
echo "[1/5] Configuring udev rules for Logitech devices..."
UDEV_RULE_FILE="/etc/udev/rules.d/99-logitech-hidpp.rules"
if [ ! -f "$UDEV_RULE_FILE" ]; then
    if command -v sudo &> /dev/null; then
        echo 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", MODE="0666"' | sudo tee "$UDEV_RULE_FILE" > /dev/null
        sudo udevadm control --reload-rules || true
        sudo udevadm trigger || true
        echo "  Installed $UDEV_RULE_FILE successfully."
    else
        echo "  [NOTE] Sudo not available. Run manually: echo 'SUBSYSTEM==\"hidraw\", ATTRS{idVendor}==\"046d\", MODE=\"0666\"' > /etc/udev/rules.d/99-logitech-hidpp.rules"
    fi
else
    echo "  $UDEV_RULE_FILE already exists."
fi

# 2. Check recommendations
echo "[2/5] Checking recommended native packages (libadwaita-1, solaar, xdotool, wl-clipboard)..."
for cmd in solaar xdotool wl-paste; do
    if command -v $cmd &> /dev/null; then
        echo "  [OK] $cmd is installed."
    else
        echo "  [INFO] $cmd not found. Optional, but recommended: sudo apt install -y $cmd"
    fi
done

# 3. Check / install Python PyGObject
echo "[3/5] Checking PyGObject and Libadwaita..."
python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1'); from gi.repository import Gtk, Adw" 2>/dev/null || {
    echo "  Installing GTK4 & Libadwaita packages..."
    if command -v sudo &> /dev/null; then
        sudo apt update && sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-0 || true
    fi
}

# 4. Install Desktop Entry and Scalable Vector Icon for current user
echo "[4/5] Installing Scalable Vector Icon & Desktop Entry..."
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
ICON_PNG_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$ICON_DIR" "$ICON_PNG_DIR" "$APPS_DIR"

if [ -f "$PROJECT_DIR/src/linux/lunifier-adwaita/resources/icon.svg" ]; then
    cp "$PROJECT_DIR/src/linux/lunifier-adwaita/resources/icon.svg" "$ICON_DIR/lunifier.svg"
fi
if [ -f "$PROJECT_DIR/src/linux/lunifier-adwaita/resources/icon.png" ]; then
    cp "$PROJECT_DIR/src/linux/lunifier-adwaita/resources/icon.png" "$ICON_PNG_DIR/lunifier.png"
fi

cat << EOF > "$APPS_DIR/lunifier.desktop"
[Desktop Entry]
Name=Lunifier
Comment=Seamless Logitech Easy-Switch Flow across Systems
Exec=python3 $PROJECT_DIR/src/linux/lunifier-adwaita/run_lunifier.py --gui
Icon=lunifier
Terminal=false
Type=Application
Categories=Utility;HardwareSettings;
Keywords=Logitech;Easy-Switch;Flow;Unifying;Bolt;Bluetooth;Mouse;Keyboard;
StartupNotify=true
Path=$PROJECT_DIR/src/linux/lunifier-adwaita
EOF

# Update desktop and icon databases if available
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_DIR" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true

# 5. Create systemd user service
echo "[5/5] Setting up systemd user service (optional autostart)..."
SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"
cat << EOF > "$SERVICE_DIR/lunifier.service"
[Unit]
Description=Lunifier 2.0 Native Daemon - Logitech Easy-Switch Flow
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $PROJECT_DIR/src/linux/lunifier-adwaita/run_lunifier.py --daemon
WorkingDirectory=$PROJECT_DIR/src/linux/lunifier-adwaita
Restart=always
RestartSec=3

[Install]
WantedBy=graphical-session.target
EOF

echo ""
echo "=== Setup Completed Successfully! ==="
echo "Application icon and desktop entry installed in your app menu."
echo "To launch settings GUI:  python3 src/linux/lunifier-adwaita/run_lunifier.py --gui"
echo "To run background daemon: python3 src/linux/lunifier-adwaita/run_lunifier.py --daemon"
echo "To enable autostart:     systemctl --user enable --now lunifier.service"
