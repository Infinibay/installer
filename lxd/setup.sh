#!/bin/bash
#
# Infinibay LXD Setup Script
# Installs and configures LXD for Infinibay VDI platform
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the universal package manager library
source "${SCRIPT_DIR}/lib/package-manager.sh"

# Color definitions for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root or with sudo"
        exit 1
    fi
}

# Check KVM support
check_kvm_support() {
    log_info "Checking KVM support..."

    # Check if /dev/kvm exists
    if [ ! -e /dev/kvm ]; then
        log_warning "/dev/kvm not found, checking if KVM is supported..."

        # Try to install cpu-checker if available on this distribution
        if [ "$OS_FAMILY" = "debian" ]; then
            log_info "Installing cpu-checker to verify KVM support..."
            pkg_update
            pkg_install cpu-checker

            if command -v kvm-ok >/dev/null 2>&1; then
                if ! kvm-ok; then
                    log_error "KVM is not supported or not enabled in BIOS"
                    log_error "Please enable Intel VT-x or AMD-V in your BIOS settings"
                    exit 1
                fi
            fi
        else
            # On non-Debian systems, check for CPU flags
            if grep -qE 'vmx|svm' /proc/cpuinfo; then
                log_warning "CPU supports virtualization but /dev/kvm is not available"
                log_warning "You may need to load the KVM kernel module:"
                log_warning "  modprobe kvm"
                log_warning "  modprobe kvm_intel  # for Intel CPUs"
                log_warning "  modprobe kvm_amd    # for AMD CPUs"
            else
                log_error "CPU does not support hardware virtualization"
                log_error "KVM requires Intel VT-x or AMD-V support"
                exit 1
            fi
        fi
    else
        log_success "KVM support detected"
    fi
}

# Install LXD
install_lxd() {
    log_info "Installing LXD..."

    # Check if snap is available
    if ! command -v snap >/dev/null 2>&1; then
        log_error "Snap is required for LXD installation but not found"
        log_info "Please install snapd for your distribution:"
        log_info "  Debian/Ubuntu: apt install snapd"
        log_info "  RHEL/Fedora: dnf install snapd && systemctl enable --now snapd.socket"
        log_info "  Arch: pacman -S snapd && systemctl enable --now snapd.socket"
        log_info "  openSUSE: zypper install snapd && systemctl enable --now snapd.socket"
        exit 1
    fi

    # Install LXD via snap
    if ! snap list lxd >/dev/null 2>&1; then
        log_info "Installing LXD via snap..."
        snap install lxd
        log_success "LXD installed"
    else
        log_info "LXD is already installed"
    fi

    # Add current user to lxd group if not root
    if [ -n "$SUDO_USER" ]; then
        usermod -aG lxd "$SUDO_USER"
        log_success "Added $SUDO_USER to lxd group"
    fi
}

# Install LXD Compose
install_lxd_compose() {
    log_info "Installing lxd-compose..."

    # Check if Go is available
    if ! command -v go >/dev/null 2>&1; then
        log_info "Go not found, installing..."

        # Try to install via snap first
        if command -v snap >/dev/null 2>&1; then
            snap install go --classic
            export PATH=$PATH:/snap/bin
        else
            # Fall back to package manager
            log_info "Installing Go via package manager..."
            pkg_install golang || pkg_install go

            if ! command -v go >/dev/null 2>&1; then
                log_error "Failed to install Go"
                log_error "Please install Go manually and re-run this script"
                exit 1
            fi
        fi

        log_success "Go installed: $(go version)"
    else
        log_info "Go already installed: $(go version)"
    fi

    # Install lxd-compose
    if ! command -v lxd-compose >/dev/null 2>&1; then
        log_info "Installing lxd-compose from source..."

        # Create temporary directory
        TMP_DIR=$(mktemp -d)
        cd "$TMP_DIR"

        # Clone and build lxd-compose
        git clone https://github.com/lxc/lxd-compose.git
        cd lxd-compose
        make build
        make install

        cd /
        rm -rf "$TMP_DIR"

        if command -v lxd-compose >/dev/null 2>&1; then
            log_success "lxd-compose installed"
        else
            log_error "Failed to install lxd-compose"
            exit 1
        fi
    else
        log_info "lxd-compose already installed"
    fi
}

# Install system dependencies
install_dependencies() {
    log_info "Installing system dependencies..."

    local dependencies=(
        "curl"
        "git"
        "build-essential"
        "libvirt-daemon-system"
        "libvirt-dev"
        "qemu-kvm"
        "bridge-utils"
        "virt-manager"
    )

    log_info "Updating package manager cache..."
    pkg_update

    log_info "Installing packages..."
    for package in "${dependencies[@]}"; do
        log_info "Checking $package..."

        if pkg_is_installed "$package"; then
            log_info "  $package is already installed"
        else
            log_info "  Installing $package..."
            pkg_install "$package"

            if pkg_is_installed "$package"; then
                log_success "  $package installed successfully"
            else
                log_warning "  Failed to install $package (may not be available on this distribution)"
            fi
        fi
    done

    # Start and enable libvirt service
    local libvirt_service=$(get_service_name libvirt)
    log_info "Starting and enabling $libvirt_service service..."

    if systemctl is-active --quiet "$libvirt_service"; then
        log_info "$libvirt_service is already running"
    else
        systemctl start "$libvirt_service"
        log_success "$libvirt_service started"
    fi

    if systemctl is-enabled --quiet "$libvirt_service"; then
        log_info "$libvirt_service is already enabled"
    else
        systemctl enable "$libvirt_service"
        log_success "$libvirt_service enabled"
    fi

    log_success "All dependencies installed"
}

# Main execution
main() {
    echo "=========================================="
    echo "Infinibay LXD Setup"
    echo "=========================================="
    echo

    check_root
    check_kvm_support
    install_dependencies
    install_lxd
    install_lxd_compose

    echo
    log_success "LXD setup completed successfully!"
    echo
    log_info "Next steps:"
    log_info "1. Initialize LXD: lxd init"
    log_info "2. If you were added to the lxd group, log out and back in for changes to take effect"
    echo
}

# Run main function
main "$@"
