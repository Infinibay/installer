"""
Privilege checking and management for the installer.
Ensures installer runs with appropriate root/sudo permissions.
"""

import os
import sys
from typing import Optional

from .logger import log_error, log_debug


def is_root() -> bool:
    """
    Check if running with root privileges.

    Returns:
        True if effective UID is 0 (root), False otherwise
    """
    return os.geteuid() == 0


def require_root():
    """
    Ensure installer is running as root, exit if not.

    Exits:
        Exit code 1 if not running as root
    """
    if not is_root():
        log_error("This installer must be run as root. Please use: sudo python3 install.py")
        sys.exit(1)

    log_debug("Running with root privileges")


def get_sudo_user() -> Optional[str]:
    """
    Get the original user who invoked sudo.

    Returns:
        Username of the original sudo user, or None if not run via sudo
    """
    return os.environ.get('SUDO_USER')


def drop_privileges_for_command(command: list[str]) -> list[str]:
    """
    Prepend command with sudo -u to run as original user.

    Useful for running commands as the original user who invoked sudo,
    such as npm install in the user's home directory.

    Args:
        command: Command list to execute

    Returns:
        Modified command list with sudo -u prefix if SUDO_USER exists,
        otherwise returns original command unchanged
    """
    sudo_user = get_sudo_user()
    if sudo_user:
        return ['sudo', '-u', sudo_user] + command
    return command
