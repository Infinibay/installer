"""
Utility functions for command execution, password generation, and network detection.
"""

import ipaddress
import os
import secrets
import shlex
import socket
import string
import subprocess
from dataclasses import dataclass
from typing import Optional, Union

from .logger import log_command, log_error, log_debug, log_warning


@dataclass
class CommandResult:
    """Result of a command execution."""
    success: bool
    returncode: int
    stdout: str
    stderr: str
    command: str


def run_command(
    command: Union[str, list[str]],
    check: bool = True,
    capture_output: bool = True,
    env: Optional[dict] = None,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None
) -> CommandResult:
    """
    Execute a shell command with consistent error handling.

    Args:
        command: Command to execute (string or list)
        check: Raise exception if command fails (default: True)
        capture_output: Capture stdout/stderr (default: True)
        env: Custom environment variables
        cwd: Working directory
        timeout: Command timeout in seconds

    Returns:
        CommandResult object with execution details

    Raises:
        subprocess.CalledProcessError: If check=True and command fails
        subprocess.TimeoutExpired: If command exceeds timeout
    """
    # Convert string command to list
    if isinstance(command, str):
        command_list = shlex.split(command)
        command_str = command
    else:
        command_list = command
        command_str = ' '.join(command)

    # Log the command
    log_command(command_str)

    try:
        # Execute command
        result = subprocess.run(
            command_list,
            capture_output=capture_output,
            text=True,
            env=env,
            cwd=cwd,
            timeout=timeout
        )

        # Create result object
        cmd_result = CommandResult(
            success=result.returncode == 0,
            returncode=result.returncode,
            stdout=result.stdout if capture_output else '',
            stderr=result.stderr if capture_output else '',
            command=command_str
        )

        # Handle failure
        if check and not cmd_result.success:
            log_error(f"Command failed with exit code {cmd_result.returncode}: {command_str}")
            if cmd_result.stderr:
                log_error(f"Error output: {cmd_result.stderr}")
            raise subprocess.CalledProcessError(
                returncode=cmd_result.returncode,
                cmd=command_str,
                output=cmd_result.stdout,
                stderr=cmd_result.stderr
            )

        return cmd_result

    except subprocess.TimeoutExpired as e:
        log_error(f"Command timed out after {timeout}s: {command_str}")
        raise


def command_exists(command: str) -> bool:
    """
    Check if a command is available in PATH.

    Args:
        command: Command name to check

    Returns:
        True if command exists, False otherwise
    """
    try:
        result = run_command(
            f"which {command}",
            check=False,
            capture_output=True
        )
        return result.success
    except Exception:
        return False


def get_command_version(command: str, version_flag: str = "--version") -> Optional[str]:
    """
    Get version string from a command.

    Args:
        command: Command to check
        version_flag: Flag to get version (default: --version)

    Returns:
        Version string if successful, None otherwise
    """
    try:
        result = run_command(
            f"{command} {version_flag}",
            check=False,
            capture_output=True
        )
        if result.success:
            # Return first line of output (usually contains version)
            return result.stdout.strip().split('\n')[0]
    except Exception:
        pass

    return None


def generate_random_password(length: int = 32) -> str:
    """
    Generate a cryptographically secure random password.

    Args:
        length: Password length (default: 32)

    Returns:
        Random password string with mixed character types
    """
    # Character sets
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = '!@#$%^&*()-_=+[]{}|;:,.<>?'

    # All characters
    all_chars = lowercase + uppercase + digits + special

    # Ensure at least one of each type
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]

    # Fill remaining length with random characters
    password.extend(secrets.choice(all_chars) for _ in range(length - 4))

    # Shuffle to avoid predictable pattern
    password_list = list(password)
    for i in range(len(password_list) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        password_list[i], password_list[j] = password_list[j], password_list[i]

    return ''.join(password_list)


def detect_host_ip() -> str:
    """
    Auto-detect the primary network interface IP address.

    Returns:
        Detected IP address, or fallback "192.168.1.100" if detection fails
    """
    try:
        # Method 1: Connect to external IP (doesn't actually send data)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]

            # Exclude loopback
            if ip.startswith('127.'):
                raise ValueError("Got loopback address")

            # Exclude Docker interfaces
            if ip.startswith('172.17.'):
                raise ValueError("Got Docker interface address")

            log_debug(f"Detected host IP: {ip}")
            return ip

    except Exception as e:
        log_debug(f"Socket method failed: {e}, trying ip command")

    try:
        # Method 2: Parse 'ip addr' output
        result = run_command('ip addr show', check=False, capture_output=True)
        if result.success:
            for line in result.stdout.split('\n'):
                if 'inet ' in line and 'scope global' in line:
                    parts = line.strip().split()
                    for i, part in enumerate(parts):
                        if part == 'inet' and i + 1 < len(parts):
                            ip_with_mask = parts[i + 1]
                            ip = ip_with_mask.split('/')[0]

                            # Exclude loopback and docker
                            if not ip.startswith('127.') and not ip.startswith('172.17.'):
                                log_debug(f"Detected host IP from ip command: {ip}")
                                return ip
    except Exception as e:
        log_debug(f"ip command failed: {e}")

    # Fallback
    fallback_ip = "192.168.1.100"
    log_warning(f"Could not auto-detect host IP, using fallback: {fallback_ip}")
    log_warning("You may need to specify --host-ip manually")
    return fallback_ip


def detect_primary_interface() -> Optional[str]:
    """
    Detect the primary network interface with internet connectivity.

    Returns:
        Interface name (e.g., 'eth0', 'ens33') or None if detection fails
    """
    # Try using ip route to find default interface
    result = run_command('ip route show default', check=False, capture_output=True)
    if result and result.returncode == 0:
        output = result.stdout.strip()
        log_debug(f"Default route output: {output}")

        # Parse output: "default via 192.168.1.1 dev eth0 proto dhcp metric 100"
        for line in output.split('\n'):
            if 'default via' in line and 'dev' in line:
                parts = line.split()
                try:
                    dev_index = parts.index('dev')
                    if dev_index + 1 < len(parts):
                        interface = parts[dev_index + 1]
                        log_debug(f"Detected primary network interface: {interface}")
                        return interface
                except (ValueError, IndexError):
                    continue

    # Fallback: try parsing ip link show
    result = run_command('ip link show', check=False, capture_output=True)
    if result and result.returncode == 0:
        output = result.stdout.strip()

        # Look for interfaces that are 'state UP'
        for line in output.split('\n'):
            if 'state UP' in line:
                # Extract interface name from line like "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>"
                parts = line.split(':')
                if len(parts) >= 2:
                    interface = parts[1].strip()

                    # Exclude loopback, docker, and bridge interfaces
                    if not any(interface.startswith(prefix) for prefix in ['lo', 'docker', 'br', 'virbr', 'veth']):
                        log_debug(f"Detected primary network interface: {interface}")
                        return interface

    log_warning("Could not auto-detect primary network interface")
    return None


def validate_ip_address(ip: str) -> bool:
    """
    Validate IP address format using ipaddress module.

    Args:
        ip: IP address string to validate

    Returns:
        True if valid IPv4 address, False otherwise
    """
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ValueError:
        return False


def ensure_directory(path: str, owner: Optional[str] = None):
    """
    Create directory if it doesn't exist, optionally set ownership.

    Args:
        path: Directory path to create
        owner: Username to set as owner (optional)
    """
    os.makedirs(path, exist_ok=True)
    log_debug(f"Ensured directory exists: {path}")

    if owner:
        try:
            run_command(f"chown {owner}:{owner} {path}", check=False)
            log_debug(f"Set ownership of {path} to {owner}")
        except Exception as e:
            log_warning(f"Failed to set ownership of {path}: {e}")
