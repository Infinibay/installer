"""
Phase 2: System dependencies installation.

This module handles installation of required system packages:
- Node.js and npm
- PostgreSQL
- QEMU/KVM and libvirt
- Rust and Cargo
- Build tools and development libraries
"""

import os
import subprocess
import time
from pathlib import Path

from .config import InstallerContext
from .logger import log_step, log_info, log_success, log_warning, log_error, log_debug
from .os_detect import OSType, get_package_manager
from .utils import run_command, command_exists, get_command_version

# Package names by OS type
UBUNTU_PACKAGES = [
    'nodejs',
    'npm',
    'postgresql',
    'postgresql-contrib',
    'qemu-kvm',
    'libvirt-daemon-system',
    'libvirt-clients',
    'bridge-utils',
    'virtinst',
    'virt-manager',
    'cpu-checker',
    'rustc',
    'cargo',
    'build-essential',
    'pkg-config',
    'libvirt-dev',
    'libssl-dev',
    'btrfs-progs',
]

FEDORA_PACKAGES = [
    'nodejs',
    'npm',
    'postgresql',
    'postgresql-server',
    'qemu-kvm',
    'libvirt',
    'libvirt-client',
    'bridge-utils',
    'virt-install',
    'virt-manager',
    'rust',
    'cargo',
    'gcc',
    'gcc-c++',
    'make',
    'pkg-config',
    'libvirt-devel',
    'openssl-devel',
    'btrfs-progs',
]

# Commands that must be available after installation
REQUIRED_COMMANDS = [
    'node',
    'npm',
    'psql',
    'virsh',
    'qemu-system-x86_64',
    'rustc',
    'cargo',
]


def update_package_cache(context: InstallerContext):
    """Update the package manager cache."""
    pkg_manager = get_package_manager(context.os_info.os_type)
    log_info("Updating package cache...")

    if context.dry_run:
        log_info(f"[DRY RUN] Would run: {pkg_manager} update/check-update")
        return

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if pkg_manager == "apt":
                env = os.environ.copy()
                env['DEBIAN_FRONTEND'] = 'noninteractive'
                run_command("apt update", env=env, timeout=300)
                break
            elif pkg_manager == "dnf":
                # dnf check-update returns 100 if updates are available, which is normal
                run_command("dnf check-update", check=False, timeout=300)
                break
        except subprocess.CalledProcessError as e:
            if attempt < max_retries - 1:
                log_warning(f"Package cache update failed (attempt {attempt + 1}/{max_retries}), retrying in 5 seconds...")
                time.sleep(5)
            else:
                raise RuntimeError(f"Failed to update package cache after {max_retries} attempts: {e}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Package cache update timed out. Please check your internet connection.")

    log_success("Package cache updated")


def install_packages(context: InstallerContext):
    """Install required system packages."""
    pkg_manager = get_package_manager(context.os_info.os_type)

    if context.os_info.os_type == OSType.UBUNTU:
        packages = UBUNTU_PACKAGES
    else:
        packages = FEDORA_PACKAGES

    log_info(f"Installing {len(packages)} system packages...")
    log_debug(f"Packages: {', '.join(packages)}")

    if context.dry_run:
        log_info(f"[DRY RUN] Would install: {', '.join(packages)}")
        return

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            if pkg_manager == "apt":
                env = os.environ.copy()
                env['DEBIAN_FRONTEND'] = 'noninteractive'
                cmd = f"apt install -y {' '.join(packages)}"
                run_command(cmd, env=env, timeout=1800)
                break
            elif pkg_manager == "dnf":
                cmd = f"dnf install -y {' '.join(packages)}"
                run_command(cmd, timeout=1800)
                break
        except subprocess.CalledProcessError as e:
            if attempt < max_retries:
                log_warning(f"Package installation failed (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                time.sleep(10)
            else:
                raise RuntimeError(
                    f"Failed to install packages after {max_retries + 1} attempts.\n"
                    f"Error: {e}\n"
                    f"Please install manually using:\n"
                    f"  sudo {cmd}"
                )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "Package installation timed out. This may be due to slow internet connection.\n"
                "Please try running the installer again or install packages manually."
            )

    log_success("All packages installed successfully")


def verify_installations(context: InstallerContext):
    """Verify that all required commands are available."""
    log_info("Verifying installations...")

    failed_commands = []

    for cmd in REQUIRED_COMMANDS:
        if not command_exists(cmd):
            log_error(f"Required command not found: {cmd}")
            failed_commands.append(cmd)
        else:
            version = get_command_version(cmd)
            log_debug(f"✓ {cmd}: {version}")

    # Special check for Node.js version
    if command_exists('node'):
        try:
            node_version_output = get_command_version('node')
            # Extract version number (e.g., "v16.20.0" -> 16)
            version_parts = node_version_output.strip().lstrip('v').split('.')
            major_version = int(version_parts[0])

            if major_version < 16:
                log_warning(
                    f"Node.js version {major_version} detected. "
                    f"Infinibay requires Node.js 16 or higher."
                )
        except Exception as e:
            log_warning(f"Could not parse Node.js version: {e}")

    if failed_commands:
        raise RuntimeError(
            f"Installation verification failed. Missing commands: {', '.join(failed_commands)}\n"
            f"Please install the missing packages manually and run the installer again."
        )

    log_success("All required commands verified")


def initialize_postgresql(context: InstallerContext):
    """Initialize PostgreSQL database (Fedora only)."""
    if context.os_info.os_type != OSType.FEDORA:
        return

    log_info("Initializing PostgreSQL...")

    pg_data_dir = Path("/var/lib/pgsql/data/PG_VERSION")

    if pg_data_dir.exists():
        log_info("PostgreSQL already initialized, skipping")
        return

    if context.dry_run:
        log_info("[DRY RUN] Would run: postgresql-setup --initdb")
        return

    try:
        run_command("postgresql-setup --initdb", timeout=60)
        log_success("PostgreSQL initialized")
    except subprocess.CalledProcessError as e:
        # May already be initialized
        if "Data directory is not empty" in str(e.stderr) if e.stderr else False:
            log_info("PostgreSQL already initialized")
        else:
            log_warning(f"PostgreSQL initialization may have failed: {e}")


def enable_and_start_services(context: InstallerContext):
    """Enable and start required system services."""
    log_info("Enabling and starting services...")

    services = ['libvirtd', 'postgresql']

    for service in services:
        if context.dry_run:
            log_info(f"[DRY RUN] Would enable and start: {service}")
            continue

        try:
            # Enable service
            run_command(f"systemctl enable {service}", timeout=30)
            log_debug(f"Enabled {service}")

            # Start service
            run_command(f"systemctl start {service}", timeout=30)
            log_debug(f"Started {service}")

            # Verify service is running
            run_command(f"systemctl is-active {service}", timeout=10)
            log_success(f"✓ {service} is running")

        except subprocess.CalledProcessError as e:
            # Service may already be running
            try:
                run_command(f"systemctl is-active {service}", timeout=10)
                log_success(f"✓ {service} is already running")
            except:
                log_warning(f"Could not start {service}: {e}")

    # Add current user to libvirt group
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user and not context.dry_run:
        try:
            run_command(f"usermod -aG libvirt {sudo_user}", timeout=10)
            log_info(f"Added {sudo_user} to libvirt group")
            log_info("Note: You may need to log out and back in for group changes to take effect")
        except subprocess.CalledProcessError as e:
            log_warning(f"Could not add user to libvirt group: {e}")

    log_success("All services enabled and started")


def check_kvm_support(context: InstallerContext):
    """Check if KVM virtualization is available."""
    log_info("Checking KVM virtualization support...")

    kvm_available = False

    # Try kvm-ok command (Ubuntu)
    if command_exists('kvm-ok'):
        try:
            result = run_command("kvm-ok", timeout=10)
            if result.stdout and "KVM acceleration can be used" in result.stdout:
                kvm_available = True
        except subprocess.CalledProcessError:
            pass

    # Check /dev/kvm exists
    if not kvm_available:
        if Path("/dev/kvm").exists():
            kvm_available = True
            # Check if user has access
            try:
                run_command("test -r /dev/kvm -a -w /dev/kvm", timeout=5)
            except subprocess.CalledProcessError:
                log_warning(
                    "KVM device exists but may not be accessible. "
                    "You may need to add your user to the kvm group."
                )

    if kvm_available:
        log_success("KVM virtualization support detected")
    else:
        log_warning(
            "KVM virtualization is not available. VMs will run without hardware acceleration.\n"
            "To enable KVM:\n"
            "  1. Enable virtualization in your BIOS/UEFI settings\n"
            "  2. Verify CPU supports virtualization (Intel VT-x or AMD-V)\n"
            "  3. Reboot your system"
        )


def run_system_checks(context: InstallerContext):
    """
    Phase 2: Install system dependencies and verify installation.

    This phase will:
    1. Detect package manager (apt for Ubuntu, dnf for Fedora)
    2. Update package cache (apt update / dnf check-update)
    3. Install system packages with OS-specific names
    4. Verify installations with version checks
    5. Enable and start libvirt and postgresql services
    6. Check KVM support (kvm-ok or equivalent)

    Args:
        context: Installation configuration context

    Raises:
        RuntimeError: If critical steps fail (package installation, verification)
    """
    log_step(2, 5, "Installing system dependencies")
    log_info(f"Detected {context.os_info.pretty_name}")

    try:
        # Update package cache
        update_package_cache(context)

        # Install packages
        install_packages(context)

        # Verify installations
        verify_installations(context)

        # Initialize PostgreSQL (Fedora only)
        initialize_postgresql(context)

        # Enable and start services
        enable_and_start_services(context)

        # Check KVM support (non-critical)
        try:
            check_kvm_support(context)
        except Exception as e:
            log_warning(f"KVM check failed: {e}")

        log_success("System dependencies installed and configured successfully")

        # Helpful reminder
        sudo_user = os.environ.get('SUDO_USER')
        if sudo_user:
            log_info(
                "\nNote: If you were added to the libvirt group, you may need to "
                "log out and back in for changes to take effect."
            )

    except subprocess.CalledProcessError as e:
        log_error(f"Command failed: {e}")
        raise RuntimeError(f"System dependency installation failed: {e}")
    except subprocess.TimeoutExpired as e:
        log_error(f"Command timed out: {e}")
        raise RuntimeError(f"System dependency installation timed out: {e}")
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        raise
