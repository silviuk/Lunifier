#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
LINUX_SRC_DIR="$ROOT_DIR/src/linux/lunifier-adwaita"

mkdir -p "$DIST_DIR"

VERSION="${1:-2.0.1}"
DEB_BUILD_DIR="/tmp/lunifier-deb"
rm -rf "$DEB_BUILD_DIR"
mkdir -p "$DEB_BUILD_DIR"
chmod 755 "$DEB_BUILD_DIR"

echo "=== Building Lunifier 2.0 Native Debian Package (v$VERSION) ==="

# 1. Create directory structure
mkdir -p "$DEB_BUILD_DIR/DEBIAN"
chmod 755 "$DEB_BUILD_DIR/DEBIAN"
mkdir -p "$DEB_BUILD_DIR/usr/bin"
mkdir -p "$DEB_BUILD_DIR/usr/lib/python3/dist-packages/lunifier"
mkdir -p "$DEB_BUILD_DIR/etc/udev/rules.d"
mkdir -p "$DEB_BUILD_DIR/usr/share/applications"
mkdir -p "$DEB_BUILD_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$DEB_BUILD_DIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$DEB_BUILD_DIR/usr/share/pixmaps"
mkdir -p "$DEB_BUILD_DIR/usr/lib/systemd/user"

# 2. Control file
cat << EOF > "$DEB_BUILD_DIR/DEBIAN/control"
Package: lunifier
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, libadwaita-1-0
Recommends: solaar, xdotool, wl-clipboard, xclip
Maintainer: Silviu Vlasceanu <silviuk@users.noreply.github.com>
Description: Seamless Logitech Easy-Switch flow across Windows and Linux
 Lunifier coordinates Logitech Easy-Switch keyboards and mice
 (MX Keys, MX Master series, M720 Triathlon, POP, etc.) across
 screens natively with GTK4 + Libadwaita without requiring Wi-Fi/LAN.
EOF

# 3. Post-install script
cat << 'EOF' > "$DEB_BUILD_DIR/DEBIAN/postinst"
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules || true
        udevadm trigger || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
    fi
fi
exit 0
EOF
chmod 755 "$DEB_BUILD_DIR/DEBIAN/postinst"

# 4. Binary launcher (/usr/bin/lunifier)
cat << 'EOF' > "$DEB_BUILD_DIR/usr/bin/lunifier"
#!/bin/sh
exec /usr/bin/python3 -c "import sys; from lunifier.run_lunifier import main; sys.exit(main())" "$@"
EOF
chmod 755 "$DEB_BUILD_DIR/usr/bin/lunifier"

# 5. Copy python package files and launcher
cp -r "$LINUX_SRC_DIR/lunifier/"* "$DEB_BUILD_DIR/usr/lib/python3/dist-packages/lunifier/"
cp "$LINUX_SRC_DIR/run_lunifier.py" "$DEB_BUILD_DIR/usr/lib/python3/dist-packages/lunifier/run_lunifier.py"
rm -rf "$DEB_BUILD_DIR/usr/lib/python3/dist-packages/lunifier/__pycache__"

cp "$LINUX_SRC_DIR/resources/icon.png" "$DEB_BUILD_DIR/usr/share/icons/hicolor/256x256/apps/lunifier.png"
cp "$LINUX_SRC_DIR/resources/icon.png" "$DEB_BUILD_DIR/usr/share/pixmaps/lunifier.png"
cp "$LINUX_SRC_DIR/resources/icon.svg" "$DEB_BUILD_DIR/usr/share/icons/hicolor/scalable/apps/lunifier.svg"

# 6. Udev rule
cat << 'EOF' > "$DEB_BUILD_DIR/etc/udev/rules.d/99-logitech-hidpp.rules"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", MODE="0666"
EOF

# 7. Desktop entry
cat << 'EOF' > "$DEB_BUILD_DIR/usr/share/applications/lunifier.desktop"
[Desktop Entry]
Name=Lunifier
Comment=Seamless Logitech Easy-Switch Flow across Systems
Exec=lunifier --gui
Icon=lunifier
Terminal=false
Type=Application
Categories=Utility;HardwareSettings;
Keywords=Logitech;Easy-Switch;Flow;Unifying;Bolt;Bluetooth;Mouse;Keyboard;
StartupNotify=true
EOF

# 8. Systemd user service
cat << 'EOF' > "$DEB_BUILD_DIR/usr/lib/systemd/user/lunifier.service"
[Unit]
Description=Lunifier 2.0 Native Daemon - Logitech Easy-Switch Flow
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/lunifier --daemon
Restart=always
RestartSec=3

[Install]
WantedBy=graphical-session.target
EOF

# 9. Build .deb
DEB_PACKAGE="$DIST_DIR/lunifier_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$DEB_BUILD_DIR" "$DEB_PACKAGE"
rm -rf "$DEB_BUILD_DIR"

echo " [OK] Created Debian Package: $DEB_PACKAGE"

# 10. Create Lunifier-Linux-2.0.0.tar.gz
TAR_BUILD_DIR="$DIST_DIR/Lunifier-Linux-$VERSION"
rm -rf "$TAR_BUILD_DIR"
mkdir -p "$TAR_BUILD_DIR"

cp -r "$LINUX_SRC_DIR/"* "$TAR_BUILD_DIR/"
cp "$ROOT_DIR/setup_linux.sh" "$TAR_BUILD_DIR/"
cp "$ROOT_DIR/README.md" "$TAR_BUILD_DIR/"
rm -rf "$TAR_BUILD_DIR/lunifier/__pycache__"

TAR_PACKAGE="$DIST_DIR/Lunifier-Linux-$VERSION.tar.gz"
tar -czf "$TAR_PACKAGE" -C "$DIST_DIR" "Lunifier-Linux-$VERSION"
rm -rf "$TAR_BUILD_DIR"

echo " [OK] Created Portable Tarball: $TAR_PACKAGE"

# 11. Print Hashes
echo ""
echo "=== Linux Package Hashes ==="
sha256sum "$DEB_PACKAGE"
sha256sum "$TAR_PACKAGE"
echo "=== Linux Packaging Complete! ==="
