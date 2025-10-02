"""
Infinibay Installer Library

This package contains all modules for the Infinibay automated installer.
"""

# Import submodules to make them accessible via "from lib import args"
from . import args as args
from . import logger as logger
from . import os_detect as os_detect
from . import privileges as privileges
from . import config as config
from . import utils as utils
from . import system_check as system_check
from . import database as database
from . import repos as repos
from . import services as services

# Also export commonly used classes and functions for convenience
# Configuration
from .config import InstallerContext

# Logging
from .logger import (
    setup_logger,
    log_info,
    log_success,
    log_warning,
    log_error,
    log_step,
    log_debug,
    log_command,
    print_banner,
)

# OS Detection
from .os_detect import OSType, OSInfo, detect_os

# Privileges
from .privileges import require_root, is_root

# Utilities
from .utils import run_command, CommandResult

__all__ = [
    # Submodules
    'args',
    'logger',
    'os_detect',
    'privileges',
    'config',
    'utils',
    'system_check',
    'database',
    'repos',
    'services',
    # Configuration
    'InstallerContext',
    # Logging
    'setup_logger',
    'log_info',
    'log_success',
    'log_warning',
    'log_error',
    'log_step',
    'log_debug',
    'log_command',
    'print_banner',
    # OS Detection
    'OSType',
    'OSInfo',
    'detect_os',
    # Privileges
    'require_root',
    'is_root',
    # Utilities
    'run_command',
    'CommandResult',
]
