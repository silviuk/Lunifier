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

# 8. Generate Web landing page (index.html)
cat << 'EOF' > "$PUBLIC_DIR/index.html"
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Lunifier — Seamless Logitech Flow for Windows & Linux</title>
  <link rel="icon" type="image/svg+xml" href="https://raw.githubusercontent.com/silviuk/Lunifier/master/lunifier/resources/icon.svg">
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --card-border: #30363d;
      --text: #c9d1d9;
      --text-bright: #f0f6fc;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --accent-hover: #79c0ff;
      --code-bg: #0b0e14;
      --btn-bg: #21262d;
      --btn-border: #363b42;
      --btn-hover: #30363d;
      --success: #3fb950;
      --orange: #ff5722;
      --purple: #a371f7;
    }
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      max-width: 880px;
      margin: 40px auto;
      padding: 0 20px;
      line-height: 1.6;
      color: var(--text);
      background: var(--bg);
    }
    .header {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 24px;
    }
    .header img {
      width: 56px;
      height: 56px;
    }
    h1 {
      color: var(--text-bright);
      margin: 0;
      font-size: 26px;
      font-weight: 700;
    }
    .subtitle {
      color: var(--text-muted);
      margin-top: 4px;
      font-size: 14.5px;
    }
    .pill-group {
      display: flex;
      gap: 8px;
      margin-top: 10px;
      flex-wrap: wrap;
    }
    .pill {
      font-size: 11.5px;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 20px;
      background: var(--btn-bg);
      border: 1px solid var(--card-border);
      color: var(--text-bright);
    }
    .pill.accent {
      background: rgba(88, 166, 255, 0.12);
      border-color: rgba(88, 166, 255, 0.35);
      color: var(--accent);
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 22px 26px;
      margin-bottom: 22px;
    }
    h2 {
      color: var(--text-bright);
      font-size: 18px;
      margin-top: 0;
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .section-title {
      font-size: 14.5px;
      font-weight: 600;
      color: var(--text-bright);
      margin-top: 16px;
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .badge {
      font-size: 11px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 20px;
      background: rgba(88, 166, 255, 0.15);
      color: var(--accent);
      border: 1px solid rgba(88, 166, 255, 0.3);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .code-block {
      position: relative;
      margin: 10px 0 14px 0;
    }
    pre {
      background: var(--code-bg);
      color: #e6edf3;
      padding: 14px 18px;
      border-radius: 8px;
      border: 1px solid var(--card-border);
      overflow-x: auto;
      font-size: 13px;
      margin: 0;
      line-height: 1.5;
    }
    code {
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    }
    .copy-btn {
      position: absolute;
      top: 8px;
      right: 8px;
      background: var(--btn-bg);
      border: 1px solid var(--btn-border);
      color: var(--text);
      font-size: 12px;
      font-weight: 500;
      padding: 5px 10px;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .copy-btn:hover {
      background: var(--btn-hover);
      color: var(--text-bright);
      border-color: var(--text-muted);
    }
    .copy-btn.copied {
      background: rgba(63, 185, 80, 0.15);
      color: var(--success);
      border-color: rgba(63, 185, 80, 0.4);
    }
    .copy-btn svg {
      width: 13px;
      height: 13px;
      fill: currentColor;
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-top: 14px;
    }
    @media (max-width: 680px) {
      .grid-2 { grid-template-columns: 1fr; }
    }
    .feature-item {
      background: var(--code-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 14px 16px;
      font-size: 13px;
    }
    .feature-item strong {
      color: var(--text-bright);
      display: block;
      margin-bottom: 4px;
    }
    .diagram-img {
      width: 100%;
      height: auto;
      border-radius: 8px;
      border: 1px solid var(--card-border);
      margin: 12px 0 16px 0;
      display: block;
    }
    .download-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 12px;
    }
    @media (max-width: 600px) {
      .download-grid { grid-template-columns: 1fr; }
    }
    .download-btn {
      display: flex;
      align-items: center;
      gap: 12px;
      background: var(--code-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 12px 14px;
      color: var(--text-bright);
      text-decoration: none;
      transition: all 0.2s ease;
    }
    .download-btn:hover {
      border-color: var(--accent);
      background: var(--btn-bg);
      text-decoration: none;
    }
    .download-btn .icon {
      font-size: 22px;
    }
    .download-btn .label {
      font-size: 13px;
      font-weight: 600;
    }
    .download-btn .desc {
      font-size: 11.5px;
      color: var(--text-muted);
    }
    a {
      color: var(--accent);
      text-decoration: none;
    }
    a:hover {
      color: var(--accent-hover);
      text-decoration: underline;
    }
    ul {
      margin: 8px 0 0 0;
      padding-left: 20px;
    }
    li {
      margin-bottom: 6px;
    }
    details {
      margin-top: 10px;
      background: var(--code-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 10px 14px;
    }
    details summary {
      cursor: pointer;
      color: var(--accent);
      font-weight: 500;
      font-size: 13.5px;
    }
    details summary:hover {
      color: var(--accent-hover);
    }
    details .code-block {
      margin-top: 10px;
      margin-bottom: 0;
    }
    .footer {
      text-align: center;
      margin-top: 32px;
      color: var(--text-muted);
      font-size: 12.5px;
    }
  </style>
</head>
<body>

  <div class="header">
    <img src="https://raw.githubusercontent.com/silviuk/Lunifier/master/lunifier/resources/icon.svg" alt="Lunifier Logo">
    <div>
      <h1>Lunifier</h1>
      <div class="subtitle">Seamless multi-border screen switching for Logitech Easy-Switch keyboards and mice across Windows &amp; Linux</div>
      <div class="pill-group">
        <span class="pill accent">🐧 Linux (Ubuntu / Debian)</span>
        <span class="pill accent">🪟 Windows 10 / 11</span>
        <span class="pill">⚡ Zero LAN/Wi-Fi Req.</span>
        <span class="pill">🖱️ Logitech Flow Alternative</span>
      </div>
    </div>
  </div>

  <!-- Linux Installation Card -->
  <div class="card">
    <h2>
      🐧 Linux Installation (Ubuntu, Debian &amp; Derivatives)
    </h2>

    <div class="section-title">
      Option 1: One-Line APT Install (Recommended — Automatic Updates)
      <span class="badge">Easiest</span>
    </div>
    <p style="margin: 0 0 6px 0; font-size: 13px; color: var(--text-muted);">Configures the repository keyring, adds the source list, and installs Lunifier with automated updates via standard <code>apt upgrade</code>:</p>
    <div class="code-block">
      <button class="copy-btn" onclick="copyCode(this)" title="Copy to clipboard">
        <svg viewBox="0 0 16 16"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg>
        <span>Copy</span>
      </button>
      <pre><code>curl -fsSL https://silviuk.github.io/Lunifier/install.sh | sudo bash</code></pre>
    </div>

    <div class="section-title">
      Option 2: Standalone Debian Package (.deb)
    </div>
    <p style="margin: 0 0 6px 0; font-size: 13px; color: var(--text-muted);">Download and install the standalone deb package directly:</p>
    <div class="code-block">
      <button class="copy-btn" onclick="copyCode(this)" title="Copy to clipboard">
        <svg viewBox="0 0 16 16"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg>
        <span>Copy</span>
      </button>
      <pre><code># Download the latest .deb from Releases and install
sudo apt install ./lunifier_all.deb</code></pre>
    </div>

    <details>
      <summary>Manual Step-by-Step APT Keyring &amp; Sources Setup</summary>
      <div class="code-block">
        <button class="copy-btn" onclick="copyCode(this)" title="Copy to clipboard">
          <svg viewBox="0 0 16 16"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg>
          <span>Copy</span>
        </button>
        <pre><code># 1. Add repository GPG signing key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://silviuk.github.io/Lunifier/key.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/lunifier.gpg

# 2. Add repository to sources list
echo "deb [signed-by=/etc/apt/keyrings/lunifier.gpg] https://silviuk.github.io/Lunifier stable main" | sudo tee /etc/apt/sources.list.d/lunifier.list

# 3. Update &amp; install Lunifier
sudo apt update
sudo apt install lunifier</code></pre>
      </div>
    </details>
  </div>

  <!-- Windows Installation Card -->
  <div class="card">
    <h2>
      🪟 Windows Installation (Windows 10 / 11)
    </h2>

    <div class="section-title">
      Option 1: Windows Package Manager (WinGet — Recommended)
      <span class="badge">Easiest</span>
    </div>
    <p style="margin: 0 0 6px 0; font-size: 13px; color: var(--text-muted);">Install directly via Windows Package Manager in PowerShell or Command Prompt:</p>
    <div class="code-block">
      <button class="copy-btn" onclick="copyCode(this)" title="Copy to clipboard">
        <svg viewBox="0 0 16 16"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg>
        <span>Copy</span>
      </button>
      <pre><code>winget install silviuk.Lunifier</code></pre>
    </div>

    <div class="section-title">
      Option 2: Windows Setup Installer (.exe) &amp; MSIX Packages
    </div>
    <p style="margin: 0 0 10px 0; font-size: 13px; color: var(--text-muted);">Download clean standalone installers including Start Menu shortcuts, tray integration, uninstaller, and silent install support:</p>
    
    <div class="download-grid">
      <a href="https://github.com/silviuk/Lunifier/releases/latest" class="download-btn">
        <div class="icon">📦</div>
        <div>
          <div class="label">Windows Installer (.exe)</div>
          <div class="desc">Standard Inno Setup executable installer</div>
        </div>
      </a>
      <a href="https://github.com/silviuk/Lunifier/releases/latest" class="download-btn">
        <div class="icon">🪟</div>
        <div>
          <div class="label">Store-Compliant MSIX (.msix)</div>
          <div class="desc">Modern packaged application package</div>
        </div>
      </a>
    </div>

    <details>
      <summary>Silent / Automated Windows Installation</summary>
      <div class="code-block">
        <button class="copy-btn" onclick="copyCode(this)" title="Copy to clipboard">
          <svg viewBox="0 0 16 16"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z"></path><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"></path></svg>
          <span>Copy</span>
        </button>
        <pre><code># Run Windows installer silently in background
Lunifier-Setup.exe /VERYSILENT /NORESTART</code></pre>
      </div>
    </details>
  </div>

  <!-- Architecture & Overview Card -->
  <div class="card">
    <h2>Multi-Border 3-Channel Architecture</h2>
    <p style="margin: 0 0 6px 0; font-size: 13.5px;">Lunifier transfers your Logitech peripherals simultaneously when the cursor dwells against any configured screen edge:</p>
    
    <img src="architecture.svg" alt="Lunifier Multi-Border Architecture" class="diagram-img">

    <div class="grid-2">
      <div class="feature-item">
        <strong>⚡ Zero LAN / Wi-Fi Dependency</strong>
        Operates autonomously on each host over direct Bluetooth, Logi Bolt, and Unifying receivers. Works seamlessly across VPNs, guest networks, and corporate firewalls.
      </div>
      <div class="feature-item">
        <strong>🎛️ Logitech HID++ 2.0 Feature 0x1814</strong>
        Transmits hardware <code>CHANGE_HOST</code> commands directly to all connected Easy-Switch keyboards and mice simultaneously for sub-second switching.
      </div>
      <div class="feature-item">
        <strong>🖥️ Multi-Border Screen Routing</strong>
        Independently route Left, Right, Top, or Bottom screen edges to distinct channels (Channel 1, 2, or 3) to coordinate 2-PC or 3-PC desk setups.
      </div>
      <div class="feature-item">
        <strong>🐧🪟 Cross-Platform Parity (Linux &amp; Windows)</strong>
        Full parity with system tray controls, configuration GUI, background services (systemd / Windows startup), and optional Bluetooth RFCOMM entry alignment.
      </div>
    </div>
  </div>

  <!-- Resources Card -->
  <div class="card">
    <h2>Project Links &amp; Downloads</h2>
    <ul>
      <li><a href="https://github.com/silviuk/Lunifier">GitHub Repository (Source Code &amp; Issues)</a></li>
      <li><a href="https://github.com/silviuk/Lunifier/releases">Releases &amp; Checksums (Windows .exe, .msix, Linux .deb)</a></li>
      <li><a href="install.sh">Linux One-Line Shell Installer (install.sh)</a></li>
      <li><a href="key.gpg">APT Repository GPG Public Key (key.gpg)</a></li>
    </ul>
  </div>

  <div class="footer">
    Lunifier is open source under the MIT License.
  </div>

  <script>
    function copyCode(btn) {
      const pre = btn.parentElement.querySelector('pre');
      const text = pre.innerText;
      navigator.clipboard.writeText(text).then(() => {
        btn.classList.add('copied');
        btn.querySelector('span').innerText = 'Copied!';
        setTimeout(() => {
          btn.classList.remove('copied');
          btn.querySelector('span').innerText = 'Copy';
        }, 2000);
      }).catch(err => {
        console.error('Failed to copy text: ', err);
      });
    }
  </script>
</body>
</html>
EOF

echo "=== APT Repository Generation Complete! ==="
