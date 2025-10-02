#!/bin/bash
#
# Infinibay Development Installer
#
# Quick installer for development environments where code is already cloned.
# This script installs Infinibay using your existing local code.
#
# Usage:
#   cd /path/to/infinibay
#   sudo ./installer/install-dev.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Infinibay Development Installer                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}✗ This script must be run as root${NC}"
   echo -e "${YELLOW}  Run with: sudo ./installer/install-dev.sh${NC}"
   exit 1
fi

# Detect the repository root
echo -e "${BLUE}ℹ${NC} Repository location: ${REPO_ROOT}"
echo ""

# Verify required directories exist
REQUIRED_DIRS=("backend" "frontend" "infiniservice" "installer")
MISSING_DIRS=()

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "${REPO_ROOT}/${dir}" ]; then
        MISSING_DIRS+=("$dir")
    fi
done

if [ ${#MISSING_DIRS[@]} -ne 0 ]; then
    echo -e "${RED}✗ Missing required directories:${NC}"
    for dir in "${MISSING_DIRS[@]}"; do
        echo -e "${RED}  - ${dir}${NC}"
    done
    echo ""
    echo -e "${YELLOW}Make sure you're running this from the infinibay repository root${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} All required directories found"
echo ""

# Show what will be done
echo -e "${BLUE}This will:${NC}"
echo -e "  ${GREEN}✓${NC} Use existing code in: ${REPO_ROOT}"
echo -e "  ${GREEN}✓${NC} Build all dependencies (libvirt-node, backend, frontend, infiniservice)"
echo -e "  ${GREEN}✓${NC} Generate .env configuration files"
echo -e "  ${GREEN}✓${NC} Setup PostgreSQL database"
echo -e "  ${GREEN}✓${NC} Create systemd services"
echo -e "  ${GREEN}✓${NC} Start services"
echo ""

# Ask for confirmation
read -p "Continue with installation? [y/N]: " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Installation cancelled${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Starting installation...${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Run the installer with the repo root as install-dir
cd "$SCRIPT_DIR"
python3 install.py \
    --install-dir="$REPO_ROOT" \
    --verbose \
    "$@"

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ Development installation complete!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BLUE}Services installed at:${NC} ${REPO_ROOT}"
    echo -e "${BLUE}Check status:${NC} systemctl status infinibay-backend infinibay-frontend"
    echo ""
else
    echo ""
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}✗ Installation failed${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}Check the error messages above for details${NC}"
    exit 1
fi
