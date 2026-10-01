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

# 3. Generate Packages and Packages.gz index
echo "Generating Packages index..."
cd "$PUBLIC_DIR"
dpkg-scanpackages --arch all pool/main > dists/stable/main/binary-all/Packages
gzip -9c dists/stable/main/binary-all/Packages > dists/stable/main/binary-all/Packages.gz

# Sync to architecture folders (all packages are Architecture: all)
cp dists/stable/main/binary-all/Packages dists/stable/main/binary-amd64/Packages
cp dists/stable/main/binary-all/Packages.gz dists/stable/main/binary-amd64/Packages.gz
cp dists/stable/main/binary-all/Packages dists/stable/main/binary-arm64/Packages
cp dists/stable/main/binary-all/Packages.gz dists/stable/main/binary-arm64/Packages.gz

# 4. Generate Release manifest
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

# 5. Sign Release with GPG
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

# 6. Add a simple web landing page at index.html for users browsing the repo
cat << 'EOF' > "$PUBLIC_DIR/index.html"
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Lunifier APT Repository</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; max-width: 780px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #24292f; background: #f6f8fa; }
    .card { background: #fff; border: 1px solid #d0d7de; border-radius: 8px; padding: 24px 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    h1 { color: #0969da; margin-top: 0; }
    pre { background: #24292e; color: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto; font-size: 14px; }
    code { font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace; }
    p code { background: #eff1f3; padding: 2px 6px; border-radius: 4px; color: #cf222e; }
    a { color: #0969da; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Lunifier APT Repository</h1>
    <p>Official Debian / Ubuntu repository for <strong>Lunifier</strong> (Logitech Easy-Switch cross-platform coordinate utility).</p>
    
    <h2>Installation</h2>
    <p>Run the following commands to add the repository and install Lunifier with automatic updates:</p>
    <pre><code># 1. Add repository GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://silviuk.github.io/Lunifier/key.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/lunifier.gpg

# 2. Add repository to sources list
echo "deb [signed-by=/etc/apt/keyrings/lunifier.gpg] https://silviuk.github.io/Lunifier stable main" | sudo tee /etc/apt/sources.list.d/lunifier.list

# 3. Update & install
sudo apt update
sudo apt install lunifier</code></pre>

    <h2>Project Links</h2>
    <ul>
      <li><a href="https://github.com/silviuk/Lunifier">GitHub Repository</a></li>
      <li><a href="https://github.com/silviuk/Lunifier/releases">GitHub Releases</a></li>
      <li><a href="key.gpg">Repository GPG Public Key</a></li>
    </ul>
  </div>
</body>
</html>
EOF

echo "=== APT Repository Generation Complete! ==="
