"""
Configuration context for the installer.
Manages all settings and provides computed properties for paths and URLs.
"""

from argparse import Namespace
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

from .os_detect import OSInfo
from .utils import generate_random_password, detect_host_ip, validate_ip_address


@dataclass
class InstallerContext:
    """
    Central configuration object passed between all installation phases.
    Contains all settings and provides computed properties for derived values.
    """
    # OS information
    os_info: OSInfo

    # Installation paths
    install_dir: str

    # Database configuration
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str

    # Admin user configuration
    admin_email: str
    admin_password: str

    # Network configuration
    host_ip: str
    network_name: str
    backend_port: int
    frontend_port: int

    # Installation options
    skip_isos: bool
    skip_windows_isos: bool

    # Execution options
    dry_run: bool
    verbose: bool

    # Optional fields with defaults
    data_dir: Optional[str] = None  # If None, uses install_dir

    def __post_init__(self):
        """Initialize computed properties after dataclass init."""
        # If data_dir is not specified, use install_dir
        if self.data_dir is None:
            self.data_dir = self.install_dir

    @property
    def database_url(self) -> str:
        """
        PostgreSQL connection string for Prisma.

        Note: Password is URL-encoded to handle special characters safely.
        Special chars like : @ / ? # [ ] need encoding in connection strings.
        """
        # URL-encode the password to handle special characters
        encoded_password = quote_plus(self.db_password)

        return (
            f"postgresql://{self.db_user}:{encoded_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?schema=public"
        )

    @property
    def backend_dir(self) -> str:
        """Backend installation directory."""
        return f"{self.install_dir}/backend"

    @property
    def frontend_dir(self) -> str:
        """Frontend installation directory."""
        return f"{self.install_dir}/frontend"

    @property
    def infiniservice_dir(self) -> str:
        """Infiniservice installation directory."""
        return f"{self.install_dir}/infiniservice"

    @property
    def libvirt_node_dir(self) -> str:
        """Libvirt-node native addon directory."""
        return f"{self.install_dir}/libvirt-node"

    @property
    def iso_dir(self) -> str:
        """ISO storage directory."""
        return f"{self.data_dir}/iso"

    @property
    def iso_permanent_dir(self) -> str:
        """Permanent ISO storage directory."""
        return f"{self.data_dir}/iso/permanent"

    @property
    def iso_temp_dir(self) -> str:
        """Temporary ISO storage directory."""
        return f"{self.data_dir}/iso/temp"

    @property
    def disks_dir(self) -> str:
        """VM disk storage directory."""
        return f"{self.data_dir}/disks"

    @property
    def uefi_dir(self) -> str:
        """UEFI firmware directory."""
        return f"{self.data_dir}/uefi"

    @property
    def sockets_dir(self) -> str:
        """Virtio socket directory."""
        return f"{self.data_dir}/sockets"

    @property
    def wallpapers_dir(self) -> str:
        """VM wallpapers directory."""
        return f"{self.data_dir}/wallpapers"

    @property
    def backend_url(self) -> str:
        """Backend server URL."""
        return f"http://{self.host_ip}:{self.backend_port}"

    @property
    def frontend_url(self) -> str:
        """Frontend web interface URL."""
        return f"http://{self.host_ip}:{self.frontend_port}"

    @property
    def graphql_url(self) -> str:
        """GraphQL API endpoint URL."""
        return f"{self.backend_url}/graphql"

    def to_dict(self) -> dict:
        """
        Convert context to dictionary for logging/debugging.
        Masks sensitive values like passwords.
        """
        return {
            'os_info': {
                'type': self.os_info.os_type.value,
                'version': self.os_info.version,
                'name': self.os_info.pretty_name,
            },
            'install_dir': self.install_dir,
            'data_dir': self.data_dir,
            'database': {
                'host': self.db_host,
                'port': self.db_port,
                'user': self.db_user,
                'password': '****' if self.db_password else None,
                'name': self.db_name,
                'url': self.database_url.replace(self.db_password, '****') if self.db_password else None,
            },
            'admin_user': {
                'email': self.admin_email,
                'password': '****' if self.admin_password else None,
            },
            'network': {
                'host_ip': self.host_ip,
                'network_name': self.network_name,
                'backend_port': self.backend_port,
                'frontend_port': self.frontend_port,
            },
            'urls': {
                'backend': self.backend_url,
                'frontend': self.frontend_url,
                'graphql': self.graphql_url,
            },
            'options': {
                'skip_isos': self.skip_isos,
                'skip_windows_isos': self.skip_windows_isos,
                'dry_run': self.dry_run,
                'verbose': self.verbose,
            },
        }

    def validate(self):
        """
        Validate all configuration values.

        Raises:
            ValueError: If any configuration value is invalid
        """
        # Validate IP address
        if not validate_ip_address(self.host_ip):
            raise ValueError(f"Invalid IP address: {self.host_ip}")

        # Validate ports
        if not (1 <= self.backend_port <= 65535):
            raise ValueError(f"Invalid backend port: {self.backend_port}")
        if not (1 <= self.frontend_port <= 65535):
            raise ValueError(f"Invalid frontend port: {self.frontend_port}")
        if not (1 <= self.db_port <= 65535):
            raise ValueError(f"Invalid database port: {self.db_port}")

        # Validate paths are absolute
        if not self.install_dir.startswith('/'):
            raise ValueError(f"Installation directory must be absolute: {self.install_dir}")

        # Validate required fields are not empty
        if not self.db_user:
            raise ValueError("Database user cannot be empty")
        if not self.db_password:
            raise ValueError("Database password cannot be empty")
        if not self.db_name:
            raise ValueError("Database name cannot be empty")


def create_context_from_args(args: Namespace, os_info: OSInfo) -> InstallerContext:
    """
    Create InstallerContext from parsed arguments and detected OS info.

    Args:
        args: Parsed command-line arguments
        os_info: Detected operating system information

    Returns:
        Validated InstallerContext object

    Raises:
        ValueError: If configuration validation fails
    """
    # Generate password if not provided
    db_password = args.db_password if args.db_password else generate_random_password()

    # Auto-detect host IP if not provided
    host_ip = args.host_ip if args.host_ip else detect_host_ip()

    # Create context
    context = InstallerContext(
        os_info=os_info,
        install_dir=args.install_dir,
        data_dir=args.data_dir,  # Will be set to install_dir in __post_init__ if None
        db_host=args.db_host,
        db_port=args.db_port,
        db_user=args.db_user,
        db_password=db_password,
        db_name=args.db_name,
        admin_email=args.admin_email,
        admin_password=args.admin_password,
        host_ip=host_ip,
        network_name=args.libvirt_network_name,
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        skip_isos=args.skip_isos,
        skip_windows_isos=args.skip_windows_isos,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    # Validate configuration
    context.validate()

    return context
