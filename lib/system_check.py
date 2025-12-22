"""
Phase 2: System dependencies installation.

This module handles installation of required system packages:
- Node.js and npm
- PostgreSQL
- Redis (for caching and performance optimization)
- QEMU/KVM (virtualization)
- Rust and Cargo
- Build tools and development libraries
"""

import os
import subprocess
import time
from pathlib import Path

from .config import InstallerContext
from .logger import log_step, log_info, log_success, log_warning, log_error, log_debug, log_section
from .os_detect import OSType, get_package_manager
from .utils import run_command, command_exists, get_command_version

# Package names by OS type
UBUNTU_PACKAGES = [
    'nodejs',
    'npm',
    'postgresql',
    'postgresql-contrib',
    'redis-server',  # Cache for firewall performance optimization
    'qemu-kvm',
    'bridge-utils',
    'cpu-checker',
    'build-essential',
    'pkg-config',
    'libssl-dev',
    'btrfs-progs',
    'p7zip-full',
    'mingw-w64',  # Windows cross-compilation toolchain for infiniservice.exe
    'curl',  # Required for rustup installation
]

FEDORA_PACKAGES = [
    'nodejs',
    'npm',
    'postgresql',
    'postgresql-server',
    'redis',  # Cache for firewall performance optimization
    'qemu-kvm',
    'bridge-utils',
    'gcc',
    'gcc-c++',
    'make',
    'pkg-config',
    'openssl-devel',
    'btrfs-progs',
    'p7zip',
    'mingw64-gcc',  # Windows cross-compilation toolchain for infiniservice.exe
    'curl',  # Required for rustup installation
]

# Commands that must be available after installation
# Note: rustc and cargo are installed via rustup, not system packages
REQUIRED_COMMANDS = [
    'node',
    'npm',
    'psql',
    'redis-cli',  # Redis client for cache verification
    'qemu-system-x86_64',
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

    # Redis service name differs by OS
    redis_service = 'redis-server' if context.os_info.os_type == OSType.UBUNTU else 'redis'
    services = ['postgresql', redis_service]

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

    # Add current user to kvm group for /dev/kvm access
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user and not context.dry_run:
        groups_added = []
        for group in ['kvm']:
            try:
                run_command(f"usermod -aG {group} {sudo_user}", timeout=10)
                groups_added.append(group)
                log_debug(f"Added {sudo_user} to {group} group")
            except subprocess.CalledProcessError as e:
                log_warning(f"Could not add user to {group} group: {e}")

        if groups_added:
            log_info(f"Added {sudo_user} to groups: {', '.join(groups_added)}")
            log_info("Note: You may need to log out and back in for group changes to take effect")

    log_success("All services enabled and started")


def verify_mingw_installation(context: InstallerContext):
    """
    Verify mingw-w64 cross-compilation toolchain is installed.

    Required for building Windows binaries from Linux.
    """
    log_info("Verifying mingw-w64 installation...")

    mingw_gcc = 'x86_64-w64-mingw32-gcc'

    if command_exists(mingw_gcc):
        version = get_command_version(mingw_gcc)
        log_success(f"mingw-w64 verified: {version}")
    else:
        log_error(f"{mingw_gcc} not found")
        raise RuntimeError(
            "mingw-w64 toolchain not installed.\n"
            "This is required for building Windows binaries.\n"
            "Install with:\n"
            "  Ubuntu: sudo apt install mingw-w64\n"
            "  Fedora: sudo dnf install mingw64-gcc"
        )


def install_rustup(context: InstallerContext):
    """
    Install rustup (Rust toolchain manager) and Rust stable toolchain.

    Rustup is required for:
    - Installing Rust compiler and cargo
    - Adding cross-compilation targets (x86_64-pc-windows-gnu)
    - Managing Rust toolchain versions

    This is installed via the official rustup.sh script instead of system packages
    to ensure we have rustup available for target management.
    """
    log_info("Installing Rust toolchain via rustup...")

    # Check if rustup is already installed
    if command_exists('rustup'):
        log_info("rustup already installed, updating...")
        if not context.dry_run:
            try:
                # Update rustup itself
                run_command("rustup self update", timeout=300)
                log_success("rustup updated")

                # Update stable toolchain
                run_command("rustup update stable", timeout=300)
                log_success("Rust stable toolchain updated")

                # Ensure stable is default
                run_command("rustup default stable", timeout=60)
                log_success("Rust stable set as default")

                # Verify versions
                for cmd in ['rustc', 'cargo']:
                    if command_exists(cmd):
                        version = get_command_version(cmd)
                        log_debug(f"✓ {cmd}: {version}")

            except subprocess.CalledProcessError as e:
                log_warning(f"Failed to update Rust: {e}")
        return

    # Check if cargo/rustc exist (system packages)
    if command_exists('cargo') or command_exists('rustc'):
        log_warning("Found system-installed Rust/Cargo packages")
        log_warning("Removing system Rust packages to install via rustup...")
        pkg_manager = get_package_manager(context.os_info.os_type)
        if not context.dry_run:
            try:
                if pkg_manager == "apt":
                    run_command("apt remove -y rustc cargo", check=False, timeout=60)
                elif pkg_manager == "dnf":
                    run_command("dnf remove -y rust cargo", check=False, timeout=60)
            except Exception as e:
                log_debug(f"Error removing system Rust: {e}")

    if context.dry_run:
        log_info("[DRY RUN] Would install rustup via https://sh.rustup.rs")
        log_info("[DRY RUN] Would install Rust stable toolchain")
        log_info("[DRY RUN] Would set stable as default toolchain")
        return

    # Get the user who invoked sudo (for proper home directory)
    sudo_user = os.environ.get('SUDO_USER')
    install_user = sudo_user if sudo_user else os.environ.get('USER', 'root')

    try:
        # Download and run rustup installer
        log_info("Downloading rustup installer...")
        rustup_cmd = "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable"

        # Run as the actual user, not root
        if sudo_user:
            # Run as the sudo user to install in their home directory
            env = os.environ.copy()
            env['USER'] = sudo_user
            env['HOME'] = f"/home/{sudo_user}" if sudo_user != 'root' else '/root'

            run_command(
                f"su - {sudo_user} -c '{rustup_cmd}'",
                timeout=600,
                env=env
            )
        else:
            # Run as current user (already root or in script)
            run_command(rustup_cmd, timeout=600, shell=True)

        log_success("Rustup installed successfully")

        # Add cargo to PATH for current session
        cargo_bin = f"/home/{sudo_user}/.cargo/bin" if sudo_user and sudo_user != 'root' else "/root/.cargo/bin"
        os.environ['PATH'] = f"{cargo_bin}:{os.environ.get('PATH', '')}"

        # Verify rustup is available
        if not command_exists('rustup'):
            raise RuntimeError("rustup not found in PATH after installation")

        # Install stable toolchain explicitly
        log_info("Installing Rust stable toolchain...")
        try:
            if sudo_user:
                run_command(
                    f"su - {sudo_user} -c 'rustup toolchain install stable'",
                    timeout=600
                )
            else:
                run_command("rustup toolchain install stable", timeout=600)
            log_success("Rust stable toolchain installed")
        except subprocess.CalledProcessError as e:
            log_error(f"Failed to install Rust stable toolchain: {e}")
            raise RuntimeError("Failed to install Rust stable toolchain")

        # Set stable as default toolchain
        log_info("Setting stable as default Rust toolchain...")
        try:
            if sudo_user:
                run_command(
                    f"su - {sudo_user} -c 'rustup default stable'",
                    timeout=60
                )
            else:
                run_command("rustup default stable", timeout=60)
            log_success("Rust stable set as default toolchain")
        except subprocess.CalledProcessError as e:
            log_error(f"Failed to set default toolchain: {e}")
            raise RuntimeError("Failed to set default Rust toolchain")

        # Verify installation
        log_info("Verifying Rust installation...")
        for cmd in ['rustup', 'rustc', 'cargo']:
            if command_exists(cmd):
                version = get_command_version(cmd)
                log_success(f"✓ {cmd}: {version}")
            else:
                raise RuntimeError(f"{cmd} not found after rustup installation")

        log_success("Rust toolchain verified and configured")

    except subprocess.CalledProcessError as e:
        log_error(f"Failed to install rustup: {e}")
        raise RuntimeError(
            "Rustup installation failed.\n"
            "Please install manually:\n"
            "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Rustup installation timed out. Please check your internet connection.")


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


def setup_libvirt_network_phase(context: InstallerContext):
    """
    DEPRECATED: This function is no longer used.

    Network management has moved to infinization, which handles networking via nftables.
    Libvirt is no longer installed or managed by the installer.

    This function is retained temporarily for backwards compatibility and will be
    removed in a future cleanup once all dependent phases are verified complete.

    Args:
        context: Installation configuration context
    """
    log_warning(
        "setup_libvirt_network_phase() is deprecated. "
        "Network management is now handled by infinization via nftables."
    )
    log_info("No libvirt network configuration performed - this is expected behavior.")


def run_system_checks(context: InstallerContext):
    """
    Phase 2: Install system dependencies and verify installation.

    This phase will:
    1. Detect package manager (apt for Ubuntu, dnf for Fedora)
    2. Update package cache (apt update / dnf check-update)
    3. Install system packages with OS-specific names
    4. Verify installations with version checks
    5. Enable and start postgresql and redis services
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

        # Install Rust toolchain via rustup
        try:
            install_rustup(context)
        except RuntimeError as e:
            log_error(f"Rust installation failed: {e}")
            raise

        # Verify mingw-w64 installation (for Windows builds)
        try:
            verify_mingw_installation(context)
        except RuntimeError as e:
            log_error(f"mingw-w64 verification failed: {e}")
            raise

        # Network setup is handled by infinization via nftables
        # No libvirt network configuration needed
        log_info("Network management will be handled by infinization (nftables)")

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
                "\nNote: If you were added to the kvm group, you may need to "
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
