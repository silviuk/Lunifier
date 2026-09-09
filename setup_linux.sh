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

# 4. Create systemd user service with dynamic project directory
echo "[4/4] Setting up systemd user service (optional autostart)..."
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
echo "To test device scanning: python3 -m lunifier.app --scan"
echo "To launch settings GUI:  python3 -m lunifier.app --gui"
echo "To enable autostart:     systemctl --user enable --now lunifier.service"
