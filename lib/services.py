"""
Phase 5: Configuration generation and systemd service creation.

This module handles:
- Generating .env configuration files
- Running backend setup scripts
- Creating systemd service files
- Enabling and starting services
"""

import os
import subprocess
import time
from .config import InstallerContext
from .logger import log_step, log_info, log_success, log_warning, log_error, log_debug
from .utils import run_command, generate_random_password


def generate_backend_env(context: InstallerContext):
    """
    Generate backend .env configuration file.

    Configuration includes:
    - DATABASE_URL: PostgreSQL connection string
    - APP_HOST: Host IP for VM connectivity
    - GRAPHIC_HOST: Host IP for graphics
    - BRIDGE_NAME: Network bridge name
    - INFINIBAY_BASE_DIR: Base installation directory
    - PORT: Backend server port
    - RPC_URL: InfiniService RPC endpoint
    - TOKENKEY: JWT token secret
    - BCRYPT_ROUNDS: Password hashing rounds
    - All path variables (iso, disks, uefi, sockets, wallpapers)

    Args:
        context: Installation configuration context
    """
    log_info("Generating backend .env configuration...")

    if context.dry_run:
        log_info(f"[DRY RUN] Would create {context.backend_dir}/.env with:")
        log_info(f"  DATABASE_URL={context.database_url}")
        log_info(f"  APP_HOST={context.host_ip}")
        log_info(f"  BRIDGE_NAME={context.bridge_name}")
        log_info(f"  PORT={context.backend_port}")
        return

    # Generate JWT secret
    tokenkey = generate_random_password(32)

    # Build .env content with all variables from backend/.env.example
    env_content = f"""# Database
DATABASE_URL="{context.database_url}"

# CORS
FRONTEND_URL="*"

# JWT
TOKENKEY="{tokenkey}"

# Server
PORT={context.backend_port}

# Security
BCRYPT_ROUNDS=10

# InfiniService RPC
RPC_URL="http://localhost:9090"

# Virtualization
VIRTIO_WIN_ISO_PATH="/var/lib/libvirt/driver/virtio-win-0.1.229.iso"

# Application Configuration
APP_HOST={context.host_ip}
INFINIBAY_BASE_DIR={context.install_dir}
INFINIBAY_ISO_DIR={context.iso_dir}
INFINIBAY_ISO_TEMP_DIR={context.iso_temp_dir}
INFINIBAY_ISO_PERMANENT_DIR={context.iso_permanent_dir}
INFINIBAY_STORAGE_POOL_NAME=infinibay
INFINIBAY_WALLPAPERS_DIR={context.wallpapers_dir}

# Graphics and Network
GRAPHIC_HOST={context.host_ip}
BRIDGE_NAME={context.bridge_name}

# Timeouts (uncomment to customize)
# LIBVIRT_CONNECT_TIMEOUT=30000
# LIBVIRT_OPERATION_TIMEOUT=60000
# VM_START_TIMEOUT=120000
# VM_SHUTDOWN_TIMEOUT=60000
"""

    try:
        env_path = os.path.join(context.backend_dir, ".env")
        with open(env_path, 'w') as f:
            f.write(env_content)

        # Set secure permissions (owner read/write only)
        os.chmod(env_path, 0o600)

        log_success(f"Backend .env created at {env_path}")
        log_debug("TOKENKEY generated and saved")

    except PermissionError:
        log_error(f"Permission denied writing to {context.backend_dir}")
        log_error("Please run the installer with sudo privileges")
        raise
    except FileNotFoundError:
        log_error(f"Directory not found: {context.backend_dir}")
        log_error("Please run Phase 4 (repository cloning) first")
        raise


def generate_frontend_env(context: InstallerContext):
    """
    Generate frontend .env configuration file.

    Configuration includes:
    - NEXT_PUBLIC_BACKEND_HOST: Backend server URL
    - NEXT_PUBLIC_GRAPHQL_API_URL: GraphQL endpoint URL

    Args:
        context: Installation configuration context
    """
    log_info("Generating frontend .env configuration...")

    if context.dry_run:
        log_info(f"[DRY RUN] Would create {context.frontend_dir}/.env with:")
        log_info(f"  NEXT_PUBLIC_BACKEND_HOST={context.backend_url}")
        log_info(f"  NEXT_PUBLIC_GRAPHQL_API_URL={context.graphql_url}")
        return

    # Build .env content with variables from frontend/.env.example
    env_content = f"""# Backend API URLs
NEXT_PUBLIC_BACKEND_HOST={context.backend_url}
NEXT_PUBLIC_GRAPHQL_API_URL={context.graphql_url}
"""

    try:
        env_path = os.path.join(context.frontend_dir, ".env")
        with open(env_path, 'w') as f:
            f.write(env_content)

        # Set readable permissions
        os.chmod(env_path, 0o644)

        log_success(f"Frontend .env created at {env_path}")

    except PermissionError:
        log_error(f"Permission denied writing to {context.frontend_dir}")
        log_error("Please run the installer with sudo privileges")
        raise
    except FileNotFoundError:
        log_error(f"Directory not found: {context.frontend_dir}")
        log_error("Please run Phase 4 (repository cloning) first")
        raise


def run_backend_setup(context: InstallerContext):
    """
    Run backend setup script.

    Executes:
    - npx prisma migrate deploy (run migrations)
    - npm run setup (creates folders, downloads ISOs, installs network filters)

    Args:
        context: Installation configuration context
    """
    log_info("Running backend setup (migrations and initialization)...")

    if context.dry_run:
        log_info(f"[DRY RUN] Would run in {context.backend_dir}:")
        log_info("  1. npx prisma migrate deploy")
        log_info("  2. npm run setup")
        return

    # Step 1: Run Prisma migrations
    log_info("Step 1/2: Running database migrations...")
    try:
        # Merge DATABASE_URL into os.environ to preserve PATH
        env = os.environ.copy()
        env["DATABASE_URL"] = context.database_url

        result = run_command(
            "npx prisma migrate deploy",
            cwd=context.backend_dir,
            timeout=600,  # 10 minutes
            env=env
        )
        if not result.success:
            log_error("Database migration failed")
            log_error("Please verify:")
            log_error(f"  - PostgreSQL is running: systemctl status postgresql")
            log_error(f"  - Database is accessible: psql -h {context.db_host} -U {context.db_user} -d {context.db_name}")
            log_error(f"  - DATABASE_URL is correct: {context.database_url}")
            if result.stderr:
                log_error(f"Error output: {result.stderr}")
            raise RuntimeError("Prisma migration failed")

        log_success("Database migrations completed")

    except subprocess.TimeoutExpired:
        log_error("Migration command timed out after 10 minutes")
        raise
    except Exception as e:
        log_error(f"Failed to run migrations: {e}")
        raise

    # Step 2: Run backend setup script
    log_info("Step 2/2: Creating directories and installing network filters...")
    try:
        result = run_command(
            "npm run setup",
            cwd=context.backend_dir,
            timeout=1800  # 30 minutes for potential ISO downloads
        )
        if not result.success:
            log_error("Backend setup script failed")
            log_error("Please verify:")
            log_error("  - Libvirt is running: systemctl status libvirtd")
            log_error("  - Database connection is working")
            log_error("  - Backend .env file is correct")
            if result.stderr:
                log_error(f"Error output: {result.stderr}")
            raise RuntimeError("Backend setup failed")

        log_success("Backend setup completed successfully")

    except subprocess.TimeoutExpired:
        log_error("Setup command timed out after 30 minutes")
        raise
    except Exception as e:
        log_error(f"Failed to run backend setup: {e}")
        raise

    # Verification: Check if critical directories were created
    log_debug("Verifying directory structure...")
    critical_dirs = [
        ("ISO directory", context.iso_dir),
        ("Disks directory", context.disks_dir),
        ("Sockets directory", context.sockets_dir)
    ]

    for name, path in critical_dirs:
        if os.path.exists(path):
            log_debug(f"✓ {name} created: {path}")
        else:
            log_warning(f"⚠ {name} not found: {path}")

    log_info("Backend is ready to start")


def create_systemd_service(
    name: str,
    exec_start: str,
    working_dir: str,
    description: str,
    context: InstallerContext
):
    """
    Create systemd service file.

    Creates service file at /etc/systemd/system/{name}.service

    Args:
        name: Service name (e.g., infinibay-backend)
        exec_start: Command to start service
        working_dir: Working directory for service
        description: Service description
        context: Installation configuration context
    """
    log_info(f"Creating systemd service: {name}...")

    if context.dry_run:
        log_info(f"[DRY RUN] Would create /etc/systemd/system/{name}.service")
        log_info(f"  Description: {description}")
        log_info(f"  ExecStart: {exec_start}")
        log_info(f"  WorkingDirectory: {working_dir}")
        return

    # Build systemd service file content
    service_content = f"""[Unit]
Description={description}
After=network.target postgresql.service libvirtd.service
Requires=postgresql.service libvirtd.service

[Service]
Type=simple
User=root
WorkingDirectory={working_dir}
ExecStart={exec_start}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment="NODE_ENV=production"
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

[Install]
WantedBy=multi-user.target
"""

    try:
        service_path = f"/etc/systemd/system/{name}.service"
        with open(service_path, 'w') as f:
            f.write(service_content)

        # Set standard service file permissions
        os.chmod(service_path, 0o644)

        log_success(f"Service file created: {service_path}")

    except PermissionError:
        log_error(f"Permission denied creating service file")
        log_error("This installer must be run with sudo/root privileges")
        raise
    except Exception as e:
        log_error(f"Failed to create service file: {e}")
        raise


def enable_and_start_service(name: str, context: InstallerContext):
    """
    Enable and start systemd service.

    Executes:
    - systemctl daemon-reload
    - systemctl enable {name}
    - systemctl start {name}
    - systemctl is-active {name}

    Args:
        name: Service name to enable and start
        context: Installation configuration context
    """
    log_info(f"Enabling and starting service: {name}...")

    if context.dry_run:
        log_info(f"[DRY RUN] Would execute:")
        log_info("  systemctl daemon-reload")
        log_info(f"  systemctl enable {name}")
        log_info(f"  systemctl start {name}")
        log_info(f"  systemctl is-active {name}")
        return

    try:
        # Reload systemd daemon to pick up new service files
        result = run_command("systemctl daemon-reload", timeout=30)
        if not result.success:
            log_warning("Failed to reload systemd daemon, continuing anyway...")

        # Enable service (start on boot)
        result = run_command(f"systemctl enable {name}", timeout=30)
        if result.success:
            log_debug(f"Service {name} enabled")
        else:
            log_warning(f"Failed to enable service (may already be enabled)")

        # Start service
        result = run_command(f"systemctl start {name}", timeout=30)
        if not result.success:
            log_error(f"Failed to start service {name}")
            log_error("Check service logs with:")
            log_error(f"  journalctl -u {name} -n 50")
            if result.stderr:
                log_error(f"Error: {result.stderr}")
            raise RuntimeError(f"Failed to start {name}")

        log_debug(f"Service {name} started")

        # Wait for service to initialize
        time.sleep(3)

        # Verify service is running
        result = run_command(f"systemctl is-active {name}", timeout=10)
        if result.success and result.stdout.strip() == "active":
            log_success(f"Service {name} is running")
        else:
            # Get detailed status
            status_result = run_command(f"systemctl status {name}", timeout=10)
            log_error(f"Service {name} is not active")
            log_error("Service status:")
            if status_result.stdout:
                for line in status_result.stdout.split('\n')[:10]:
                    log_error(f"  {line}")
            log_error("Check logs with:")
            log_error(f"  journalctl -u {name} -n 50")
            raise RuntimeError(f"Service {name} failed to start")

        log_info(f"Service {name} enabled and started successfully")

    except subprocess.TimeoutExpired:
        log_error(f"Systemctl command timed out for service {name}")
        raise
    except Exception as e:
        log_error(f"Failed to enable/start service {name}: {e}")
        raise


def create_services(context: InstallerContext):
    """
    Phase 5: Generate configuration and create systemd services.

    This phase will:
    1. Generate backend .env file with all configuration
    2. Generate frontend .env file with backend URLs
    3. Run backend setup (migrations and initialization)
    4. Create systemd service files
    5. Enable and start services
    6. Display installation summary with URLs and credentials

    Args:
        context: Installation configuration context
    """
    log_step(5, 5, "Generating configuration and creating systemd services")
    log_info("This is the final phase of installation...")

    # Phase 5a: Generate configuration files
    log_info("\n=== Generating Configuration Files ===")
    try:
        generate_backend_env(context)
        generate_frontend_env(context)
        log_success("Configuration files generated")
    except Exception as e:
        log_error("Failed to generate configuration files")
        log_error(f"Error: {e}")
        raise RuntimeError("Configuration generation failed")

    # Phase 5b: Run backend setup
    log_info("\n=== Running Backend Setup ===")
    log_warning("This may take several minutes...")
    try:
        run_backend_setup(context)
        log_success("Backend setup completed")
    except Exception as e:
        log_error("Backend setup failed. This is critical for system operation.")
        log_error("Troubleshooting steps:")
        log_error(f"  1. Check PostgreSQL: systemctl status postgresql")
        log_error(f"  2. Check libvirt: systemctl status libvirtd")
        log_error(f"  3. Test database connection: psql -h {context.db_host} -U {context.db_user} -d {context.db_name}")
        log_error(f"  4. Review backend logs in the terminal output above")
        log_error(f"Error: {e}")
        raise RuntimeError("Backend setup failed")

    # Phase 5c: Create systemd services
    log_info("\n=== Creating Systemd Services ===")
    try:
        # Create backend service
        create_systemd_service(
            name="infinibay-backend",
            exec_start="/usr/bin/npm run start",
            working_dir=context.backend_dir,
            description="Infinibay Backend API Server",
            context=context
        )

        # Create frontend service
        create_systemd_service(
            name="infinibay-frontend",
            exec_start="/usr/bin/npm run start",
            working_dir=context.frontend_dir,
            description="Infinibay Frontend Web Interface",
            context=context
        )

        log_success("Systemd services created")
    except Exception as e:
        log_error("Failed to create systemd services")
        log_error(f"Error: {e}")
        raise RuntimeError("Service creation failed")

    # Phase 5d: Enable and start services
    log_info("\n=== Starting Services ===")
    try:
        # Start backend
        enable_and_start_service("infinibay-backend", context)

        # Start frontend
        enable_and_start_service("infinibay-frontend", context)

        log_success("All services started successfully")
    except Exception as e:
        log_error("Failed to start services")
        log_error("You can try starting them manually:")
        log_error("  systemctl start infinibay-backend")
        log_error("  systemctl start infinibay-frontend")
        log_error(f"Error: {e}")
        raise RuntimeError("Service startup failed")

    # Phase 5e: Display installation summary
    log_success("\n" + "="*70)
    log_success("🎉 INFINIBAY INSTALLATION COMPLETED SUCCESSFULLY! 🎉")
    log_success("="*70 + "\n")

    # Installation summary
    log_info("Installation Summary:")
    log_info(f"  Installation Directory: {context.install_dir}")
    log_info(f"  Host IP Address: {context.host_ip}")
    log_info(f"  Bridge Name: {context.bridge_name}")
    log_info("")

    # Access URLs
    log_info("Access URLs:")
    log_info(f"  Frontend (Web UI): {context.frontend_url}")
    log_info(f"  Backend API: {context.backend_url}")
    log_info(f"  GraphQL Playground: {context.graphql_url}")
    log_info("")

    # Database credentials
    log_info("Database Configuration:")
    log_info(f"  Host: {context.db_host}:{context.db_port}")
    log_info(f"  Database: {context.db_name}")
    log_info(f"  User: {context.db_user}")
    log_info(f"  Password: {context.db_password}")
    log_warning("  ⚠️  Save these credentials securely!")
    log_info("")

    # Service management
    log_info("Service Management:")
    log_info("  Check status: systemctl status infinibay-backend infinibay-frontend")
    log_info("  View logs: journalctl -u infinibay-backend -f")
    log_info("  Restart: systemctl restart infinibay-backend infinibay-frontend")
    log_info("  Stop: systemctl stop infinibay-backend infinibay-frontend")
    log_info("")

    # Next steps
    log_info("Next Steps:")
    log_info(f"  1. Open your browser and navigate to: {context.frontend_url}")
    log_info("  2. Create your first admin user account")
    log_info("  3. Configure your network bridge (if not already done)")
    log_info("  4. Start creating virtual machines!")
    log_info("")

    # Important notes
    log_warning("Important Notes:")
    log_warning("  • Services will start automatically on system boot")
    log_warning("  • Backend .env contains sensitive data (DATABASE_URL, TOKENKEY)")
    log_warning("  • Ensure your firewall allows access to ports:")
    log_warning(f"    - Frontend: {context.frontend_port}")
    log_warning(f"    - Backend: {context.backend_port}")
    if context.skip_isos:
        log_warning("  • ISO downloads were skipped. You may need to download them manually.")
    log_info("")

    # Final message
    log_success("="*70)
    log_success("Installation complete! Enjoy using Infinibay! 🚀")
    log_success("="*70)
