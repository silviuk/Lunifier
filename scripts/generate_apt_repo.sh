#!/bin/bash
set -e

# -----------------------------------------------------------------------------
# generate_apt_repo.sh
# Generates a standard Debian/Ubuntu APT repository with GPG signing
#
# Usage:
#   ./scripts/generate_apt_repo.sh <deb_pool_dir> <output_public_dir> [gpg_key_name]
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW_POOL="${1:-$SCRIPT_DIR/../dist}"
RAW_PUBLIC="${2:-$SCRIPT_DIR/../public}"
GPG_KEY_NAME="${3:-Lunifier Package Archive}"

mkdir -p "$RAW_POOL" "$RAW_PUBLIC"
POOL_DIR="$(cd "$RAW_POOL" && pwd)"
PUBLIC_DIR="$(cd "$RAW_PUBLIC" && pwd)"

echo "=== Generating APT Repository ==="
echo "Pool source: $POOL_DIR"
echo "Target dir:  $PUBLIC_DIR"
echo "GPG Key:     $GPG_KEY_NAME"

mkdir -p "$PUBLIC_DIR/pool/main"
mkdir -p "$PUBLIC_DIR/dists/stable/main/binary-all"
mkdir -p "$PUBLIC_DIR/dists/stable/main/binary-amd64"
mkdir -p "$PUBLIC_DIR/dists/stable/main/binary-arm64"

# 1. Copy deb packages to pool
if [ -d "$POOL_DIR" ]; then
    find "$POOL_DIR" -maxdepth 1 -name "*.deb" -exec cp {} "$PUBLIC_DIR/pool/main/" \;
fi

# Ensure at least one .deb package is present
DEB_COUNT=$(find "$PUBLIC_DIR/pool/main" -name "*.deb" | wc -l)
if [ "$DEB_COUNT" -eq 0 ]; then
    echo "Error: No .deb packages found in $PUBLIC_DIR/pool/main"
    exit 1
fi
echo "Found $DEB_COUNT package(s) in pool."

# 2. Export public GPG key if gpg is available
if command -v gpg >/dev/null 2>&1; then
    if gpg --list-keys "$GPG_KEY_NAME" >/dev/null 2>&1; then
        echo "Exporting public GPG key..."
        gpg --armor --export "$GPG_KEY_NAME" > "$PUBLIC_DIR/key.gpg"
        gpg --export "$GPG_KEY_NAME" > "$PUBLIC_DIR/lunifier.gpg"
    else
        echo "Warning: GPG key '$GPG_KEY_NAME' not found in keyring. Skipping key export."
    fi
fi

# 3. Copy architecture SVG diagram to public
if [ -f "$SCRIPT_DIR/../docs/architecture.svg" ]; then
    cp "$SCRIPT_DIR/../docs/architecture.svg" "$PUBLIC_DIR/architecture.svg"
elif [ -f "$SCRIPT_DIR/../lunifier/resources/architecture.svg" ]; then
    cp "$SCRIPT_DIR/../lunifier/resources/architecture.svg" "$PUBLIC_DIR/architecture.svg"
fi

# 4. Generate Packages and Packages.gz index
echo "Generating Packages index..."
cd "$PUBLIC_DIR"
dpkg-scanpackages --arch all pool/main > dists/stable/main/binary-all/Packages
gzip -9c dists/stable/main/binary-all/Packages > dists/stable/main/binary-all/Packages.gz

# Sync to architecture folders (all packages are Architecture: all)
cp dists/stable/main/binary-all/Packages dists/stable/main/binary-amd64/Packages
cp dists/stable/main/binary-all/Packages.gz dists/stable/main/binary-amd64/Packages.gz
cp dists/stable/main/binary-all/Packages dists/stable/main/binary-arm64/Packages
cp dists/stable/main/binary-all/Packages.gz dists/stable/main/binary-arm64/Packages.gz

# 5. Generate Release manifest
echo "Generating Release manifest..."
cd "$PUBLIC_DIR/dists/stable"

cat << 'EOF' > apt-ftparchive.conf
APT::FTPArchive::Release {
  Origin "Lunifier Archive";
  Label "Lunifier";
  Suite "stable";
  Codename "stable";
  Architectures "all amd64 arm64";
  Components "main";
  Description "Lunifier Logitech Easy-Switch Coordinate Utility Repository";
};
EOF

apt-ftparchive -c apt-ftparchive.conf release . > Release
rm apt-ftparchive.conf

# 6. Sign Release with GPG
if command -v gpg >/dev/null 2>&1 && gpg --list-secret-keys "$GPG_KEY_NAME" >/dev/null 2>&1; then
    echo "Signing Release with GPG ($GPG_KEY_NAME)..."
    PASSPHRASE_ARGS=""
    if [ -n "$APT_GPG_PASSPHRASE" ]; then
        PASSPHRASE_ARGS="--pinentry-mode loopback --passphrase $APT_GPG_PASSPHRASE"
    fi
    gpg --batch --yes $PASSPHRASE_ARGS --local-user "$GPG_KEY_NAME" --clearsign -o InRelease Release
    gpg --batch --yes $PASSPHRASE_ARGS --local-user "$GPG_KEY_NAME" -abs -o Release.gpg Release
    echo " [OK] Generated InRelease and Release.gpg"
else
    echo "Warning: Secret key for '$GPG_KEY_NAME' not found. InRelease and Release.gpg were not signed."
fi

# 7. Generate One-Line Installer script (install.sh)
cat << 'EOF' > "$PUBLIC_DIR/install.sh"
#!/bin/bash
set -e

# =============================================================================
# Lunifier One-Line APT Installer for Ubuntu & Debian
# https://silviuk.github.io/Lunifier/
# =============================================================================

BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}${BOLD}=== Lunifier APT Installer ===${NC}"

# Check for root / sudo
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        echo -e "${RED}Error: This installer must be run as root or with sudo.${NC}"
        exit 1
    fi
else
    SUDO=""
fi

if ! command -v apt-get >/dev/null 2>&1; then
    echo -e "${RED}Error: apt-get was not found. This installer requires Ubuntu or Debian.${NC}"
    exit 1
fi

echo -e "-> Installing required dependencies (curl, gpg)..."
$SUDO apt-get update -qq || true
$SUDO apt-get install -y -qq curl gnupg >/dev/null 2>&1 || true

echo -e "-> Configuring Lunifier repository keyring..."
$SUDO mkdir -p /etc/apt/keyrings

if curl -fsSL https://silviuk.github.io/Lunifier/key.gpg > /tmp/lunifier-key.gpg 2>/dev/null && [ -s /tmp/lunifier-key.gpg ]; then
    $SUDO gpg --dearmor --yes -o /etc/apt/keyrings/lunifier.gpg /tmp/lunifier-key.gpg 2>/dev/null || true
    rm -f /tmp/lunifier-key.gpg
fi

echo -e "-> Adding Lunifier repository to /etc/apt/sources.list.d/lunifier.list..."
if [ -f /etc/apt/keyrings/lunifier.gpg ] && [ -s /etc/apt/keyrings/lunifier.gpg ]; then
    echo "deb [signed-by=/etc/apt/keyrings/lunifier.gpg] https://silviuk.github.io/Lunifier stable main" | $SUDO tee /etc/apt/sources.list.d/lunifier.list >/dev/null
else
    echo "deb [trusted=yes] https://silviuk.github.io/Lunifier stable main" | $SUDO tee /etc/apt/sources.list.d/lunifier.list >/dev/null
fi

echo -e "-> Updating package indices..."
$SUDO apt-get update -o Dir::Etc::sourcelist="sources.list.d/lunifier.list" -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0" 2>/dev/null || $SUDO apt-get update

echo -e "-> Installing Lunifier..."
$SUDO apt-get install -y lunifier

echo -e ""
echo -e "${GREEN}${BOLD}✓ Lunifier installed successfully!${NC}"
echo -e "To configure & launch:      ${BOLD}lunifier --gui${NC}"
echo -e "To run background service:  ${BOLD}systemctl --user enable --now lunifier.service${NC}"
EOF
chmod +x "$PUBLIC_DIR/install.sh"

# 8. Publish the maintained project page alongside the generated APT metadata.
mkdir -p "$PUBLIC_DIR/assets"
cp -R "$SCRIPT_DIR/../docs/assets/." "$PUBLIC_DIR/assets/"
cp "$SCRIPT_DIR/../docs/index.html" "$SCRIPT_DIR/../docs/style.css" "$SCRIPT_DIR/../docs/theme-init.js" "$SCRIPT_DIR/../docs/theme.js" "$PUBLIC_DIR/"
touch "$PUBLIC_DIR/.nojekyll"

echo "=== APT Repository Generation Complete! ==="
