"""
Command-line argument parsing for the Infinibay installer.
"""

import argparse
import re
import sys

# Installer version
INSTALLER_VERSION = "1.0.0"


def validate_ip_address(ip: str) -> str:
    """Validate IP address format (basic regex check)."""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        raise argparse.ArgumentTypeError(f"Invalid IP address format: {ip}")

    # Check each octet is 0-255
    octets = ip.split('.')
    for octet in octets:
        if int(octet) > 255:
            raise argparse.ArgumentTypeError(f"Invalid IP address: {ip} (octet > 255)")

    return ip


def validate_port(port: str) -> int:
    """Validate port number (1-65535)."""
    try:
        port_int = int(port)
        if port_int < 1 or port_int > 65535:
            raise argparse.ArgumentTypeError(f"Port must be between 1 and 65535: {port}")
        return port_int
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid port number: {port}")


def validate_absolute_path(path: str) -> str:
    """Validate that path is absolute."""
    if not path.startswith('/'):
        raise argparse.ArgumentTypeError(f"Path must be absolute (start with /): {path}")
    return path


def parse_arguments():
    """Parse command-line arguments for the installer."""
    parser = argparse.ArgumentParser(
        description='Infinibay Automated Installer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 install.py
  sudo python3 install.py --host-ip=192.168.1.100
  sudo python3 install.py --db-password=SecurePass123 --verbose
  sudo python3 install.py --dry-run
        """
    )

    # Version
    parser.add_argument(
        '--version',
        action='version',
        version=f'Infinibay Installer v{INSTALLER_VERSION}'
    )

    # Database configuration
    db_group = parser.add_argument_group('Database Configuration')
    db_group.add_argument(
        '--db-password',
        type=str,
        default=None,
        help='PostgreSQL password for infinibay user (default: auto-generated)'
    )
    db_group.add_argument(
        '--db-user',
        type=str,
        default='infinibay',
        help='PostgreSQL username (default: infinibay)'
    )
    db_group.add_argument(
        '--db-host',
        type=str,
        default='localhost',
        help='PostgreSQL host (default: localhost)'
    )
    db_group.add_argument(
        '--db-port',
        type=validate_port,
        default=5432,
        help='PostgreSQL port (default: 5432)'
    )
    db_group.add_argument(
        '--db-name',
        type=str,
        default='infinibay',
        help='PostgreSQL database name (default: infinibay)'
    )

    # Network configuration
    network_group = parser.add_argument_group('Network Configuration')
    network_group.add_argument(
        '--host-ip',
        type=validate_ip_address,
        default=None,
        help='Host IP address for VMs to connect (default: auto-detected)'
    )
    network_group.add_argument(
        '--libvirt-network-name',
        type=str,
        default='default',
        help='Libvirt network name (default: default)'
    )
    network_group.add_argument(
        '--backend-port',
        type=validate_port,
        default=4000,
        help='Backend GraphQL server port (default: 4000)'
    )
    network_group.add_argument(
        '--frontend-port',
        type=validate_port,
        default=3000,
        help='Frontend web server port (default: 3000)'
    )

    # Installation configuration
    install_group = parser.add_argument_group('Installation Configuration')
    install_group.add_argument(
        '--install-dir',
        type=validate_absolute_path,
        default='/opt/infinibay',
        help='Installation directory (default: /opt/infinibay)'
    )
    install_group.add_argument(
        '--data-dir',
        type=validate_absolute_path,
        default=None,
        help='Data directory for ISOs, disks, etc. (default: same as --install-dir)'
    )
    install_group.add_argument(
        '--use-local-repos',
        action='store_true',
        help='Use local repository code instead of cloning from GitHub (useful for development)'
    )
    install_group.add_argument(
        '--local-repos-dir',
        type=validate_absolute_path,
        default=None,
        help='Path to local repositories directory (e.g., /home/user/infinibay)'
    )
    install_group.add_argument(
        '--skip-isos',
        action='store_true',
        help='Skip downloading Ubuntu/Fedora ISOs'
    )
    install_group.add_argument(
        '--skip-windows-isos',
        action='store_true',
        help='Skip downloading Windows ISOs'
    )

    # Execution options
    exec_group = parser.add_argument_group('Execution Options')
    exec_group.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without executing'
    )
    exec_group.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    return args
