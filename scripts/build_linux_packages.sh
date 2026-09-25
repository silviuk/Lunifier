#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
LINUX_SRC_DIR="$ROOT_DIR/src/linux/lunifier-adwaita"

mkdir -p "$DIST_DIR"

VERSION="${1:-2.2.1}"
TARGET_EDITION="${2:-all}" # "standard", "nobtsync", or "all"

build_edition() {
    local EDITION="$1"
    local IS_NOBTSYNC=0
    local SUFFIX=""
    local PKG_NAME="lunifier"
    local DESC_EXTRA=""
    local RECOMMENDS="solaar, xdotool, wl-clipboard, xclip, python3-evdev, bluez"
    local CONFLICTS_BLOCK=""

    if [ "$EDITION" = "nobtsync" ]; then
        IS_NOBTSYNC=1
        SUFFIX="-nobtsync"
        PKG_NAME="lunifier-nobtsync"
        DESC_EXTRA=" (Standalone No-BtSync Edition without inter-host Bluetooth RFCOMM)"
        RECOMMENDS="solaar, xdotool, wl-clipboard, xclip, python3-evdev"
        CONFLICTS_BLOCK="Conflicts: lunifier
Provides: lunifier
Replaces: lunifier"
    fi

    echo "==================================================="
    echo "  Building Linux Package: v${VERSION} (${EDITION})"
    echo "==================================================="

    local DEB_BUILD_DIR="/tmp/lunifier-deb-${EDITION}"
    rm -rf "$DEB_BUILD_DIR"
    mkdir -p "$DEB_BUILD_DIR"
    chmod 755 "$DEB_BUILD_DIR"

    # 1. Create directory structure
    mkdir -p "$DEB_BUILD_DIR/DEBIAN"
    chmod 755 "$DEB_BUILD_DIR/DEBIAN"
    mkdir -p "$DEB_BUILD_DIR/usr/bin"
    mkdir -p "$DEB_BUILD_DIR/usr/lib/python3/dist-packages/lunifier"
    mkdir -p "$DEB_BUILD_DIR/etc/udev/rules.d"
    mkdir -p "$DEB_BUILD_DIR/usr/share/applications"
    mkdir -p "$DEB_BUILD_DIR/usr/share/icons/hicolor/scalable/apps"
    mkdir -p "$DEB_BUILD_DIR/usr/share/pixmaps"
    mkdir -p "$DEB_BUILD_DIR/usr/lib/systemd/user"

    # 2. Control file
    cat << EOF > "$DEB_BUILD_DIR/DEBIAN/control"
Package: $PKG_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, libadwaita-1-0
Recommends: $RECOMMENDS
EOF
    if [ -n "$CONFLICTS_BLOCK" ]; then
        echo "$CONFLICTS_BLOCK" >> "$DEB_BUILD_DIR/DEBIAN/control"
    fi
    cat << EOF >> "$DEB_BUILD_DIR/DEBIAN/control"
Maintainer: Silviu Vlasceanu <silviuk@users.noreply.github.com>
Description: Seamless Logitech Easy-Switch flow across Windows and Linux${DESC_EXTRA}
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

    if [ "$IS_NOBTSYNC" -eq 1 ]; then
        cat << 'FEAT_EOF' > "$DEB_BUILD_DIR/usr/lib/python3/dist-packages/lunifier/features.py"
"""
Feature configuration and edition detection for Lunifier Linux.
No-BtSync Edition: inter-host Bluetooth RFCOMM sync is disabled.
"""

NO_BTSYNC: bool = True
FEAT_EOF
    fi

    for sz in 16 24 32 48 64 128 256 512; do
        mkdir -p "$DEB_BUILD_DIR/usr/share/icons/hicolor/${sz}x${sz}/apps"
        if [ -f "$LINUX_SRC_DIR/resources/icons/${sz}x${sz}.png" ]; then
            cp "$LINUX_SRC_DIR/resources/icons/${sz}x${sz}.png" "$DEB_BUILD_DIR/usr/share/icons/hicolor/${sz}x${sz}/apps/lunifier.png"
        fi
    done
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
Description=Lunifier 2.2 Native Service - Logitech Easy-Switch Flow
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/lunifier --minimized
Restart=always
RestartSec=3

[Install]
WantedBy=graphical-session.target
EOF

    # 9. Build .deb
    local DEB_PACKAGE="$DIST_DIR/lunifier_${VERSION}${SUFFIX}_all.deb"
    dpkg-deb --build --root-owner-group "$DEB_BUILD_DIR" "$DEB_PACKAGE"
    rm -rf "$DEB_BUILD_DIR"
    echo " [OK] Created Debian Package: $DEB_PACKAGE"

    # 10. Create Portable Tarball
    local TAR_BASE="Lunifier-Linux-${VERSION}${SUFFIX}"
    local TAR_BUILD_DIR="$DIST_DIR/$TAR_BASE"
    rm -rf "$TAR_BUILD_DIR"
    mkdir -p "$TAR_BUILD_DIR"

    cp -r "$LINUX_SRC_DIR/"* "$TAR_BUILD_DIR/"
    cp "$ROOT_DIR/setup_linux.sh" "$TAR_BUILD_DIR/"
    cp "$ROOT_DIR/README.md" "$TAR_BUILD_DIR/"
    rm -rf "$TAR_BUILD_DIR/lunifier/__pycache__"

    if [ "$IS_NOBTSYNC" -eq 1 ]; then
        cat << 'FEAT_EOF' > "$TAR_BUILD_DIR/lunifier/features.py"
"""
Feature configuration and edition detection for Lunifier Linux.
No-BtSync Edition: inter-host Bluetooth RFCOMM sync is disabled.
"""

NO_BTSYNC: bool = True
FEAT_EOF
    fi

    local TAR_PACKAGE="$DIST_DIR/${TAR_BASE}.tar.gz"
    tar -czf "$TAR_PACKAGE" -C "$DIST_DIR" "$TAR_BASE"
    rm -rf "$TAR_BUILD_DIR"
    echo " [OK] Created Portable Tarball: $TAR_PACKAGE"
    echo ""
}

if [ "$TARGET_EDITION" = "standard" ] || [ "$TARGET_EDITION" = "all" ]; then
    build_edition "standard"
fi

if [ "$TARGET_EDITION" = "nobtsync" ] || [ "$TARGET_EDITION" = "all" ]; then
    build_edition "nobtsync"
fi

echo "=== Linux Package Hashes ==="
sha256sum "$DIST_DIR"/lunifier_*all.deb
sha256sum "$DIST_DIR"/Lunifier-Linux-*.tar.gz
echo "=== Linux Packaging Complete! ==="
