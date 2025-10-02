"""
Operating system detection and validation.
Parses /etc/os-release to identify Linux distribution.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OSType(Enum):
    """Supported operating system types."""
    UBUNTU = "ubuntu"
    FEDORA = "fedora"
    UNKNOWN = "unknown"


@dataclass
class OSInfo:
    """Operating system information."""
    os_type: OSType
    version: str
    version_major: int
    version_minor: int
    name: str
    id: str
    id_like: str
    pretty_name: str


def detect_os() -> OSInfo:
    """
    Detect operating system by parsing /etc/os-release.

    Returns:
        OSInfo object with detected OS information

    Raises:
        FileNotFoundError: If /etc/os-release doesn't exist
        ValueError: If unable to parse OS information
    """
    os_release_path = '/etc/os-release'

    try:
        with open(os_release_path, 'r') as f:
            os_release_data = {}
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes from value
                    value = value.strip('"').strip("'")
                    os_release_data[key] = value
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Cannot detect OS: {os_release_path} not found. "
            "This installer requires a modern Linux distribution."
        )

    # Extract required fields
    os_id = os_release_data.get('ID', '').lower()
    os_id_like = os_release_data.get('ID_LIKE', '').lower()
    version_id = os_release_data.get('VERSION_ID', '0.0')
    name = os_release_data.get('NAME', 'Unknown')
    pretty_name = os_release_data.get('PRETTY_NAME', 'Unknown Linux')

    # Determine OS type
    os_type = OSType.UNKNOWN

    if os_id == 'ubuntu':
        os_type = OSType.UBUNTU
    elif os_id == 'fedora':
        os_type = OSType.FEDORA
    elif 'debian' in os_id_like or 'ubuntu' in os_id_like:
        # Debian-based derivatives (treat as Ubuntu-like)
        os_type = OSType.UBUNTU
    elif 'rhel' in os_id_like or 'fedora' in os_id_like:
        # RHEL-based derivatives (treat as Fedora-like)
        os_type = OSType.FEDORA

    # Parse version
    version_parts = version_id.split('.')
    try:
        version_major = int(version_parts[0])
        version_minor = int(version_parts[1]) if len(version_parts) > 1 else 0
    except (ValueError, IndexError):
        version_major = 0
        version_minor = 0

    return OSInfo(
        os_type=os_type,
        version=version_id,
        version_major=version_major,
        version_minor=version_minor,
        name=name,
        id=os_id,
        id_like=os_id_like,
        pretty_name=pretty_name
    )


def validate_os_version(os_info: OSInfo) -> bool:
    """
    Validate that the OS version meets minimum requirements.

    Args:
        os_info: Detected OS information

    Returns:
        True if OS version is supported, False otherwise
    """
    if os_info.os_type == OSType.UBUNTU:
        # Ubuntu 23.10 or later
        if os_info.version_major > 23:
            return True
        elif os_info.version_major == 23 and os_info.version_minor >= 10:
            return True
        return False

    elif os_info.os_type == OSType.FEDORA:
        # Fedora 37 or later
        return os_info.version_major >= 37

    # Unknown OS type is not supported
    return False


def get_package_manager(os_type: OSType) -> str:
    """
    Get package manager command for the OS type.

    Args:
        os_type: Detected OS type

    Returns:
        Package manager command ('apt' or 'dnf')

    Raises:
        ValueError: If OS type is not supported
    """
    if os_type == OSType.UBUNTU:
        return 'apt'
    elif os_type == OSType.FEDORA:
        return 'dnf'
    else:
        raise ValueError(f"Unsupported OS type: {os_type}")


def get_minimum_version_string(os_type: OSType) -> str:
    """Get human-readable minimum version requirement for OS type."""
    if os_type == OSType.UBUNTU:
        return "23.10"
    elif os_type == OSType.FEDORA:
        return "37"
    else:
        return "Unknown"
