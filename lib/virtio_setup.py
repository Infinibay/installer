"""
VirtIO Windows Drivers ISO Setup.

This module handles downloading and verifying the VirtIO Windows drivers ISO
needed for Windows VM installations.
"""

import os
import urllib.request
import urllib.error
from typing import Optional, Tuple

from .config import InstallerContext
from .logger import log_info, log_success, log_warning, log_error, log_debug
from .utils import run_command

# VirtIO ISO download URL (latest stable)
VIRTIO_ISO_URL = "https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.iso"
VIRTIO_ISO_FILENAME = "virtio-win.iso"

# Minimum expected ISO size (in bytes) - virtio-win is typically ~700MB+
MIN_ISO_SIZE = 500 * 1024 * 1024  # 500 MB


def check_existing_virtio_iso(context: InstallerContext) -> Optional[str]:
    """
    Check if VirtIO ISO already exists in common locations.

    Args:
        context: Installation configuration context

    Returns:
        Path to existing ISO if found, None otherwise
    """
    search_paths = [
        os.path.join(context.iso_permanent_dir, VIRTIO_ISO_FILENAME),
        "/usr/share/virtio-win/virtio-win.iso",
        "/var/lib/libvirt/images/virtio-win.iso",
        "/var/lib/libvirt/driver/virtio-win-0.1.229.iso",
    ]

    for path in search_paths:
        if os.path.exists(path) and os.path.getsize(path) > MIN_ISO_SIZE:
            log_debug(f"Found existing VirtIO ISO at: {path}")
            return path

    return None


def download_with_progress(url: str, destination: str) -> bool:
    """
    Download file from URL to destination with progress reporting.

    Args:
        url: Source URL
        destination: Destination file path

    Returns:
        True if download successful, False otherwise
    """
    try:
        def report_progress(block_num, block_size, total_size):
            """Report download progress."""
            if total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, (downloaded * 100) // total_size)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)

                # Update progress on same line
                print(f"\r  Progress: {percent}% ({mb_downloaded:.1f} MB / {mb_total:.1f} MB)",
                      end='', flush=True)

        log_info(f"Downloading from: {url}")
        urllib.request.urlretrieve(url, destination, reporthook=report_progress)
        print()  # New line after progress

        return True

    except urllib.error.URLError as e:
        log_error(f"Download failed: {e}")
        return False
    except Exception as e:
        log_error(f"Unexpected error during download: {e}")
        return False


def verify_iso_integrity(iso_path: str) -> bool:
    """
    Verify ISO file integrity by checking size and basic structure.

    Args:
        iso_path: Path to ISO file

    Returns:
        True if ISO appears valid, False otherwise
    """
    try:
        # Check file exists
        if not os.path.exists(iso_path):
            log_error(f"ISO file not found: {iso_path}")
            return False

        # Check file size
        size = os.path.getsize(iso_path)
        if size < MIN_ISO_SIZE:
            log_error(f"ISO file is too small ({size} bytes). Expected at least {MIN_ISO_SIZE} bytes.")
            return False

        # Check file is readable
        with open(iso_path, 'rb') as f:
            # Read first 2 bytes to verify it's accessible
            header = f.read(2)
            if len(header) < 2:
                log_error("ISO file appears to be empty or corrupted")
                return False

        log_debug(f"ISO verification passed. Size: {size / (1024*1024):.1f} MB")
        return True

    except Exception as e:
        log_error(f"ISO verification failed: {e}")
        return False


def setup_virtio_drivers(context: InstallerContext) -> Tuple[bool, Optional[str]]:
    """
    Set up VirtIO Windows drivers ISO.

    This function:
    1. Checks if ISO already exists in common locations
    2. If not found, downloads it to the Infinibay ISO directory
    3. Verifies the downloaded ISO

    Args:
        context: Installation configuration context

    Returns:
        Tuple of (success: bool, iso_path: Optional[str])
    """
    log_info("Setting up VirtIO Windows drivers...")

    if context.dry_run:
        log_info("[DRY RUN] Would check for existing VirtIO ISO")
        log_info(f"[DRY RUN] Would download to: {context.iso_permanent_dir}/{VIRTIO_ISO_FILENAME}")
        return True, None

    # Check for existing ISO
    existing_iso = check_existing_virtio_iso(context)
    if existing_iso:
        log_success(f"Found existing VirtIO ISO: {existing_iso}")
        log_info("Skipping download")
        return True, existing_iso

    # Ensure target directory exists
    os.makedirs(context.iso_permanent_dir, exist_ok=True)

    # Download ISO
    target_path = os.path.join(context.iso_permanent_dir, VIRTIO_ISO_FILENAME)
    log_info("VirtIO ISO not found locally, downloading...")
    log_info("This may take several minutes (ISO is ~750 MB)")

    success = download_with_progress(VIRTIO_ISO_URL, target_path)

    if not success:
        log_error("Failed to download VirtIO ISO")
        log_warning("You can manually download it later from:")
        log_warning(f"  {VIRTIO_ISO_URL}")
        log_warning(f"And place it at: {target_path}")
        return False, None

    # Verify downloaded ISO
    log_info("Verifying downloaded ISO...")
    if not verify_iso_integrity(target_path):
        log_error("Downloaded ISO failed integrity check")
        # Clean up potentially corrupted file
        try:
            os.remove(target_path)
        except:
            pass
        return False, None

    log_success(f"VirtIO ISO downloaded successfully: {target_path}")
    return True, target_path


def update_env_with_virtio_path(context: InstallerContext, iso_path: str):
    """
    Update backend .env file with VirtIO ISO path if needed.

    Args:
        context: Installation configuration context
        iso_path: Path to VirtIO ISO file
    """
    if context.dry_run:
        log_info(f"[DRY RUN] Would update .env with VIRTIO_WIN_ISO_PATH={iso_path}")
        return

    env_path = os.path.join(context.backend_dir, ".env")

    if not os.path.exists(env_path):
        log_warning(".env file not found, skipping VirtIO path update")
        return

    try:
        # Read current .env
        with open(env_path, 'r') as f:
            env_content = f.read()

        # Check if VIRTIO_WIN_ISO_PATH is already set (not commented)
        if '\nVIRTIO_WIN_ISO_PATH=' in env_content:
            log_debug("VIRTIO_WIN_ISO_PATH already set in .env")
            return

        # Add or uncomment VIRTIO_WIN_ISO_PATH
        if '# VIRTIO_WIN_ISO_PATH=' in env_content:
            # Uncomment and set the path
            env_content = env_content.replace(
                '# VIRTIO_WIN_ISO_PATH=/path/to/virtio-win.iso',
                f'VIRTIO_WIN_ISO_PATH={iso_path}'
            )
        else:
            # Add new entry
            env_content += f'\n# VirtIO Windows Drivers ISO (auto-configured)\nVIRTIO_WIN_ISO_PATH={iso_path}\n'

        # Write updated .env
        with open(env_path, 'w') as f:
            f.write(env_content)

        log_debug(f"Updated .env with VIRTIO_WIN_ISO_PATH={iso_path}")

    except Exception as e:
        log_warning(f"Failed to update .env with VirtIO path: {e}")
        log_info("You can manually add this line to backend/.env:")
        log_info(f"  VIRTIO_WIN_ISO_PATH={iso_path}")
