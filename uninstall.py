#!/usr/bin/env python3
"""
Infinibay Uninstaller

Safely removes Infinibay installation:
- Stops and disables systemd services
- Removes service files
- Optionally removes installation directory
- Optionally removes database and user
"""

import argparse
import os
import subprocess
import sys

# Import logger from lib
from lib import logger
from lib import privileges


def parse_uninstall_args():
    """Parse command-line arguments for uninstaller."""
    parser = argparse.ArgumentParser(
        description='Infinibay Uninstaller - Remove Infinibay installation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Remove services only (keep data)
  sudo python3 uninstall.py

  # Remove services and installation files
  sudo python3 uninstall.py --remove-files

  # Full uninstall including database
  sudo python3 uninstall.py --remove-files --remove-database

  # Preview what would be removed
  sudo python3 uninstall.py --remove-files --remove-database --dry-run
        """
    )

    parser.add_argument(
        '--install-dir',
        type=str,
        default='/opt/infinibay',
        help='Installation directory to remove (default: /opt/infinibay)'
    )

    parser.add_argument(
        '--remove-files',
        action='store_true',
        help='Remove installation directory and all files'
    )

    parser.add_argument(
        '--remove-database',
        action='store_true',
        help='Remove PostgreSQL database and user'
    )

    parser.add_argument(
        '--db-user',
        type=str,
        default='infinibay',
        help='PostgreSQL username to remove (default: infinibay)'
    )

    parser.add_argument(
        '--db-name',
        type=str,
        default='infinibay',
        help='PostgreSQL database to remove (default: infinibay)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually doing it'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--yes',
        '-y',
        action='store_true',
        help='Skip confirmation prompts'
    )

    return parser.parse_args()


def run_command(command, dry_run=False, check=True):
    """Execute a command with optional dry-run mode."""
    if dry_run:
        logger.log_info(f"[DRY RUN] Would execute: {command}")
        return True

    logger.log_debug(f"$ {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )
        if check and result.returncode != 0:
            logger.log_error(f"Command failed: {command}")
            logger.log_error(f"Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        logger.log_error(f"Failed to execute command: {e}")
        return False


def stop_and_disable_service(service_name, dry_run=False):
    """Stop and disable a systemd service."""
    logger.log_info(f"Stopping service: {service_name}...")

    # Check if service exists
    check_cmd = f"systemctl list-unit-files | grep -q {service_name}"
    result = subprocess.run(check_cmd, shell=True, capture_output=True)

    if result.returncode != 0:
        logger.log_warning(f"Service {service_name} not found, skipping")
        return True

    # Stop service
    if not run_command(f"systemctl stop {service_name}", dry_run, check=False):
        logger.log_warning(f"Failed to stop {service_name} (may not be running)")

    # Disable service
    if not run_command(f"systemctl disable {service_name}", dry_run, check=False):
        logger.log_warning(f"Failed to disable {service_name} (may not be enabled)")

    logger.log_success(f"Service {service_name} stopped and disabled")
    return True


def remove_service_file(service_name, dry_run=False):
    """Remove systemd service file."""
    service_file = f"/etc/systemd/system/{service_name}.service"

    if not os.path.exists(service_file):
        logger.log_debug(f"Service file not found: {service_file}")
        return True

    logger.log_info(f"Removing service file: {service_file}...")

    if dry_run:
        logger.log_info(f"[DRY RUN] Would remove: {service_file}")
    else:
        try:
            os.remove(service_file)
            logger.log_success(f"Removed: {service_file}")
        except Exception as e:
            logger.log_error(f"Failed to remove {service_file}: {e}")
            return False

    return True


def reload_systemd(dry_run=False):
    """Reload systemd daemon."""
    logger.log_info("Reloading systemd daemon...")
    return run_command("systemctl daemon-reload", dry_run)


def remove_installation_directory(install_dir, dry_run=False):
    """Remove installation directory."""
    if not os.path.exists(install_dir):
        logger.log_warning(f"Installation directory not found: {install_dir}")
        return True

    logger.log_info(f"Removing installation directory: {install_dir}...")

    if dry_run:
        logger.log_info(f"[DRY RUN] Would remove: {install_dir}")
    else:
        try:
            import shutil
            shutil.rmtree(install_dir)
            logger.log_success(f"Removed: {install_dir}")
        except Exception as e:
            logger.log_error(f"Failed to remove {install_dir}: {e}")
            return False

    return True


def remove_database(db_name, db_user, dry_run=False):
    """Remove PostgreSQL database and user."""
    logger.log_info("Removing PostgreSQL database and user...")

    # Drop database
    logger.log_info(f"Dropping database: {db_name}...")
    drop_db_cmd = f"sudo -u postgres psql -c \"DROP DATABASE IF EXISTS {db_name};\""
    if not run_command(drop_db_cmd, dry_run, check=False):
        logger.log_warning(f"Failed to drop database {db_name} (may not exist)")
    else:
        logger.log_success(f"Database {db_name} dropped")

    # Drop user
    logger.log_info(f"Dropping user: {db_user}...")
    drop_user_cmd = f"sudo -u postgres psql -c \"DROP USER IF EXISTS {db_user};\""
    if not run_command(drop_user_cmd, dry_run, check=False):
        logger.log_warning(f"Failed to drop user {db_user} (may not exist)")
    else:
        logger.log_success(f"User {db_user} dropped")

    return True


def remove_rustup(dry_run=False):
    """
    Remove rustup Rust toolchain installation.

    Rustup is installed by Infinibay installer and should be cleaned up on uninstall.
    """
    logger.log_info("Removing Rust toolchain (rustup)...")

    # Get the user who originally ran the installer
    sudo_user = os.environ.get('SUDO_USER')
    user_home = f"/home/{sudo_user}" if sudo_user and sudo_user != 'root' else '/root'
    cargo_dir = f"{user_home}/.cargo"
    rustup_dir = f"{user_home}/.rustup"

    # Check if rustup is installed
    if not os.path.exists(cargo_dir) and not os.path.exists(rustup_dir):
        logger.log_info("Rustup not found, skipping")
        return True

    if dry_run:
        logger.log_info(f"[DRY RUN] Would remove: {cargo_dir}")
        logger.log_info(f"[DRY RUN] Would remove: {rustup_dir}")
        return True

    try:
        # Remove .cargo directory
        if os.path.exists(cargo_dir):
            import shutil
            shutil.rmtree(cargo_dir)
            logger.log_success(f"Removed: {cargo_dir}")

        # Remove .rustup directory
        if os.path.exists(rustup_dir):
            import shutil
            shutil.rmtree(rustup_dir)
            logger.log_success(f"Removed: {rustup_dir}")

        logger.log_success("Rust toolchain removed")
        return True

    except Exception as e:
        logger.log_error(f"Failed to remove rustup: {e}")
        return False


def confirm_uninstall(args):
    """Ask user to confirm uninstallation."""
    if args.yes:
        return True

    logger.log_warning("This will uninstall Infinibay:")
    print()
    logger.log_info("  ✓ Stop and disable systemd services")
    logger.log_info("  ✓ Remove service files")

    if args.remove_files:
        logger.log_info(f"  ✓ Remove installation directory: {args.install_dir}")

    if args.remove_database:
        logger.log_info(f"  ✓ Remove database: {args.db_name}")
        logger.log_info(f"  ✓ Remove database user: {args.db_user}")

    print()
    response = input("Are you sure you want to continue? [y/N]: ")
    return response.lower() in ['y', 'yes']


def main():
    """Main uninstaller orchestrator."""
    args = parse_uninstall_args()

    # Initialize logger
    logger.setup_logger(verbose=args.verbose)

    # Display banner
    print()
    print(f"{logger.CYAN}{logger.BOLD}╔═══════════════════════════════════════════════╗{logger.RESET}")
    print(f"{logger.CYAN}{logger.BOLD}║         INFINIBAY UNINSTALLER                 ║{logger.RESET}")
    print(f"{logger.CYAN}{logger.BOLD}╚═══════════════════════════════════════════════╝{logger.RESET}")
    print()

    # Check for root privileges
    privileges.require_root()

    # Show dry run mode if enabled
    if args.dry_run:
        logger.log_warning("DRY RUN MODE - No changes will be made")
        print()

    # Confirm uninstallation
    if not args.dry_run and not confirm_uninstall(args):
        logger.log_info("Uninstallation cancelled")
        return 0

    print()
    logger.log_section("Removing Infinibay Services")

    # Stop and disable services
    services = ['infinibay-backend', 'infinibay-frontend']
    for service in services:
        stop_and_disable_service(service, args.dry_run)

    # Remove service files
    for service in services:
        remove_service_file(service, args.dry_run)

    # Reload systemd
    reload_systemd(args.dry_run)

    # Remove installation directory if requested
    if args.remove_files:
        print()
        logger.log_section("Removing Installation Files")
        remove_installation_directory(args.install_dir, args.dry_run)

    # Remove database if requested
    if args.remove_database:
        print()
        logger.log_section("Removing Database")
        remove_database(args.db_name, args.db_user, args.dry_run)

    # Remove rustup (always remove when removing files)
    if args.remove_files:
        print()
        logger.log_section("Removing Rust Toolchain")
        remove_rustup(args.dry_run)

    # Final summary
    print()
    logger.log_section("Uninstallation Complete")

    if args.dry_run:
        logger.log_info("This was a dry run - no changes were made")
    else:
        logger.log_success("Infinibay has been uninstalled successfully!")

        if not args.remove_files:
            logger.log_info(f"Installation files remain at: {args.install_dir}")
            logger.log_info("To remove them, run with --remove-files")

        if not args.remove_database:
            logger.log_info(f"Database '{args.db_name}' and user '{args.db_user}' remain")
            logger.log_info("To remove them, run with --remove-database")

    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
