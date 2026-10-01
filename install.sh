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
