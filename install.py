#!/usr/bin/env python3
"""
Infinibay Automated Installer

Main entry point for the Infinibay installation framework.
Orchestrates all installation phases with proper error handling.
"""

import json
import sys
import traceback

# Import all lib modules
from lib import args
from lib import logger
from lib import os_detect
from lib import privileges
from lib import config
from lib import system_check
from lib import database
from lib import repos
from lib import services


def display_configuration_summary(context: config.InstallerContext):
    """Display configuration summary before installation."""
    logger.log_info("Installation Configuration:")
    print()

    config_dict = context.to_dict()

    # OS Information
    logger.log_info(f"Operating System: {config_dict['os_info']['name']}")
    logger.log_info(f"Version: {config_dict['os_info']['version']}")
    print()

    # Installation Paths
    logger.log_info(f"Code Directory: {context.install_dir}")
    if context.data_dir != context.install_dir:
        logger.log_info(f"Data Directory: {context.data_dir}")
    print()

    # Database Configuration
    logger.log_info("Database Configuration:")
    logger.log_info(f"  Host: {context.db_host}:{context.db_port}")
    logger.log_info(f"  User: {context.db_user}")
    logger.log_info(f"  Database: {context.db_name}")
    logger.log_info(f"  Password: {'****' if context.db_password else 'Not set'}")
    print()

    # Network Configuration
    logger.log_info("Network Configuration:")
    logger.log_info(f"  Host IP: {context.host_ip}")
    logger.log_info(f"  Network: {context.network_name}")
    logger.log_info(f"  Backend Port: {context.backend_port}")
    logger.log_info(f"  Frontend Port: {context.frontend_port}")
    print()

    # Service URLs
    logger.log_info("Service URLs:")
    logger.log_info(f"  Frontend: {context.frontend_url}")
    logger.log_info(f"  GraphQL API: {context.graphql_url}")
    print()

    # Installation Options
    if context.skip_isos or context.skip_windows_isos:
        logger.log_info("Installation Options:")
        if context.skip_isos:
            logger.log_info("  - Skipping Ubuntu/Fedora ISOs")
        if context.skip_windows_isos:
            logger.log_info("  - Skipping Windows ISOs")
        print()


def display_dry_run_summary(context: config.InstallerContext):
    """Display what would be done in dry-run mode."""
    logger.log_warning("DRY RUN MODE - No changes will be made")
    print()

    logger.log_step(1, 5, "Framework initialization (completed)")
    logger.log_step(2, 5, "Would install system dependencies")
    logger.log_info("  - Package manager updates")
    logger.log_info("  - Node.js, npm, PostgreSQL, Redis, QEMU/KVM, libvirt, Rust, Cargo")
    logger.log_info("  - Build tools and development libraries")
    print()

    logger.log_step(3, 5, "Would set up PostgreSQL database")
    logger.log_info(f"  - Create user: {context.db_user}")
    logger.log_info(f"  - Create database: {context.db_name}")
    logger.log_info("  - Grant privileges")
    print()

    logger.log_step(4, 5, "Would clone and build repositories")
    logger.log_info(f"  - Clone to: {context.install_dir}")
    logger.log_info("  - Build order: libvirt-node → backend → frontend → infiniservice")
    print()

    logger.log_step(5, 5, "Would create services and configuration")
    logger.log_info(f"  - Generate .env files")
    logger.log_info("  - Run database migrations")
    logger.log_info("  - Create systemd services")
    logger.log_info("  - Enable and start services")
    print()

    logger.log_success("Dry run complete - review configuration above")


def display_installation_summary(context: config.InstallerContext):
    """Display installation summary with URLs and next steps."""
    logger.log_success("Installation Complete!")
    print()

    logger.log_info("Access your Infinibay installation:")
    logger.log_info(f"  Web Interface: {context.frontend_url}")
    logger.log_info(f"  GraphQL API: {context.graphql_url}")
    print()

    logger.log_info("Database Credentials:")
    logger.log_info(f"  Host: {context.db_host}:{context.db_port}")
    logger.log_info(f"  User: {context.db_user}")
    logger.log_info(f"  Password: {context.db_password}")
    logger.log_info(f"  Database: {context.db_name}")
    print()

    logger.log_info("Next Steps:")
    logger.log_info("  1. Access the web interface and create your admin account")
    logger.log_info("  2. Configure departments and security policies")
    logger.log_info("  3. Create your first virtual machine")
    print()

    logger.log_info("Service Management:")
    logger.log_info("  Start:   systemctl start infinibay-backend infinibay-frontend")
    logger.log_info("  Stop:    systemctl stop infinibay-backend infinibay-frontend")
    logger.log_info("  Restart: systemctl restart infinibay-backend infinibay-frontend")
    logger.log_info("  Status:  systemctl status infinibay-backend infinibay-frontend")
    print()


def main():
    """Main installer orchestrator."""
    exit_code = 0

    try:
        # Parse command-line arguments
        parsed_args = args.parse_arguments()

        # Initialize logger with verbosity
        logger.setup_logger(verbose=parsed_args.verbose)

        # Display animated welcome banner (or fallback to static)
        if not parsed_args.verbose:  # Only animate in non-verbose mode
            try:
                logger.print_animated_waves()
            except Exception:
                logger.print_banner()
        else:
            logger.print_banner()

        # Check for root privileges
        privileges.require_root()

        # Detect operating system
        logger.log_step(1, 5, "Detecting operating system")
        detected_os = os_detect.detect_os()
        logger.log_success(f"Detected: {detected_os.pretty_name}")

        # Validate OS compatibility
        if not os_detect.validate_os_version(detected_os):
            min_version = os_detect.get_minimum_version_string(detected_os.os_type)
            logger.log_error(
                f"{detected_os.pretty_name} is not supported. "
                f"Minimum version required: {min_version}"
            )
            sys.exit(1)

        logger.log_success(f"OS version {detected_os.version} is supported")
        print()

        # Create installer context
        installer_context = config.create_context_from_args(parsed_args, detected_os)

        # Display configuration summary
        display_configuration_summary(installer_context)

        # If dry-run mode, display what would be done and exit
        if installer_context.dry_run:
            display_dry_run_summary(installer_context)
            return 0

        # Execute installation phases
        try:
            # Phase 2: System dependencies (stub - will raise NotImplementedError)
            system_check.run_system_checks(installer_context)

            # Phase 3: Database setup (stub - will raise NotImplementedError)
            database.setup_database(installer_context)

            # Phase 4: Repository cloning and building (stub - will raise NotImplementedError)
            repos.clone_and_build(installer_context)

            # Phase 5: Service creation and configuration (stub - will raise NotImplementedError)
            services.create_services(installer_context)

            # Display installation summary (only reached if all phases complete)
            display_installation_summary(installer_context)

        except NotImplementedError as e:
            # This should not happen - all phases are implemented
            logger.log_error("Unexpected NotImplementedError:")
            logger.log_info(str(e))
            print()
            logger.log_error("This is a bug - all phases should be implemented")
            logger.log_info("Please report this issue on GitHub")
            return 1

    except KeyboardInterrupt:
        print()
        logger.log_warning("Installation interrupted by user")
        exit_code = 130

    except Exception as e:
        logger.log_error(f"Installation failed with error: {str(e)}")

        if parsed_args.verbose if 'parsed_args' in locals() else False:
            logger.log_debug("Full traceback:")
            traceback.print_exc()

        logger.log_error("Installation did not complete successfully")
        logger.log_info("Please review the error above and try again")
        logger.log_info("Run with --verbose for more detailed error information")
        exit_code = 1

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
