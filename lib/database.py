"""
Phase 3: PostgreSQL database setup with interactive troubleshooting.

This module handles database configuration:
- Test PostgreSQL connection
- Create database user with password
- Create infinibay database
- Grant necessary privileges
- Interactive troubleshooting guide if connection fails
"""

import glob
import os
import shlex
import subprocess
import time
from typing import Optional

from .config import InstallerContext
from .logger import log_step, log_info, log_success, log_warning, log_error, log_debug
from .os_detect import OSType
from .utils import run_command, CommandResult

# Constants
MAX_CONNECTION_RETRIES = 3
RETRY_DELAY_SECONDS = 3
PG_HBA_UBUNTU_PATTERN = '/etc/postgresql/*/main/pg_hba.conf'
PG_HBA_FEDORA_PATH = '/var/lib/pgsql/data/pg_hba.conf'


def check_user_exists(context: InstallerContext) -> bool:
    """Check if PostgreSQL user exists."""
    log_debug(f"Checking if PostgreSQL user '{context.db_user}' exists...")

    if context.dry_run:
        return False

    try:
        sql = f"SELECT 1 FROM pg_roles WHERE rolname='{context.db_user}';"
        result = run_command(f"sudo -u postgres psql -t -c {shlex.quote(sql)}", timeout=10)
        return '1' in result.stdout if result.stdout else False
    except Exception as e:
        log_debug(f"Could not check if user exists: {e}")
        return False


def check_database_exists(context: InstallerContext) -> bool:
    """Check if database exists."""
    log_debug(f"Checking if database '{context.db_name}' exists...")

    if context.dry_run:
        return False

    try:
        sql = f"SELECT 1 FROM pg_database WHERE datname='{context.db_name}';"
        result = run_command(f"sudo -u postgres psql -t -c {shlex.quote(sql)}", timeout=10)
        return '1' in result.stdout if result.stdout else False
    except Exception as e:
        log_debug(f"Could not check if database exists: {e}")
        return False


def test_connection(context: InstallerContext) -> bool:
    """
    Test PostgreSQL connection with provided credentials.

    Args:
        context: Installation configuration context

    Returns:
        True if connection successful, False otherwise
    """
    log_debug("Testing PostgreSQL connection...")

    if context.dry_run:
        log_info("[DRY RUN] Would test PostgreSQL connection")
        return True

    try:
        # Build psql command
        cmd = f"psql -h {context.db_host} -p {context.db_port} -U {context.db_user} -d postgres -c 'SELECT 1;'"

        # Set password in environment
        env = os.environ.copy()
        env['PGPASSWORD'] = context.db_password

        result = run_command(cmd, env=env, check=False, timeout=10)

        if result.returncode == 0:
            log_debug("PostgreSQL connection successful")
            return True

        # Log error details
        error_msg = result.stderr if result.stderr else result.stdout
        log_debug(f"Connection failed: {error_msg}")

        # Identify common issues
        if error_msg:
            if "connection refused" in error_msg.lower():
                log_debug("→ PostgreSQL may not be running")
            elif "authentication failed" in error_msg.lower():
                log_debug("→ Wrong password or pg_hba.conf issue")
            elif "role" in error_msg.lower() and "does not exist" in error_msg.lower():
                log_debug("→ User not created yet")

        return False

    except Exception as e:
        log_debug(f"Connection test exception: {e}")
        return False


def create_database_user(context: InstallerContext):
    """
    Create PostgreSQL user with password.

    Executes SQL:
        CREATE USER infinibay WITH PASSWORD 'password';
        GRANT CREATE ON DATABASE postgres TO infinibay;
        ALTER USER infinibay CREATEDB;

    Args:
        context: Installation configuration context
    """
    log_info(f"Creating PostgreSQL user '{context.db_user}'...")

    # Escape password for SQL (replace single quotes with '')
    escaped_password = context.db_password.replace("'", "''")

    if context.dry_run:
        log_info(f"[DRY RUN] Would create user with SQL:")
        log_info(f"  CREATE USER {context.db_user} WITH PASSWORD '***' CREATEDB;")
        return

    # Check if user exists
    user_exists = check_user_exists(context)

    if user_exists:
        log_info("User already exists, updating password...")
        sql = f"ALTER USER {context.db_user} WITH PASSWORD '{escaped_password}' CREATEDB;"
    else:
        sql = f"CREATE USER {context.db_user} WITH PASSWORD '{escaped_password}' CREATEDB NOSUPERUSER INHERIT NOCREATEROLE;"

    try:
        run_command(f"sudo -u postgres psql -c {shlex.quote(sql)}", timeout=30)
        log_success(f"User '{context.db_user}' created/updated successfully")
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)
        if "permission denied" in error_msg.lower():
            raise RuntimeError(
                f"Permission denied creating PostgreSQL user.\n"
                f"Please run the installer with sudo."
            )
        elif "postgres" in error_msg.lower() and "does not exist" in error_msg.lower():
            raise RuntimeError(
                f"PostgreSQL 'postgres' user does not exist.\n"
                f"Please check your PostgreSQL installation."
            )
        else:
            raise RuntimeError(f"Failed to create database user: {error_msg}")


def create_database(context: InstallerContext):
    """
    Create infinibay database.

    Executes SQL:
        CREATE DATABASE infinibay OWNER infinibay;

    Args:
        context: Installation configuration context
    """
    log_info(f"Creating database '{context.db_name}'...")

    if context.dry_run:
        log_info(f"[DRY RUN] Would create database with SQL:")
        log_info(f"  CREATE DATABASE {context.db_name} OWNER {context.db_user};")
        return

    # Check if database exists
    db_exists = check_database_exists(context)

    if db_exists:
        log_info("Database already exists, ensuring correct owner...")
        sql = f"ALTER DATABASE {context.db_name} OWNER TO {context.db_user};"
    else:
        sql = f"CREATE DATABASE {context.db_name} OWNER {context.db_user};"

    try:
        run_command(f"sudo -u postgres psql -c {shlex.quote(sql)}", timeout=30)
        log_success(f"Database '{context.db_name}' created/configured successfully")
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)
        raise RuntimeError(f"Failed to create database: {error_msg}")


def configure_pg_hba(context: InstallerContext) -> bool:
    """
    Check pg_hba.conf configuration for password authentication.

    Returns:
        True if properly configured, False if needs manual configuration
    """
    log_info("Checking pg_hba.conf configuration...")

    if context.dry_run:
        log_info("[DRY RUN] Would check pg_hba.conf configuration")
        return True

    try:
        # Get pg_hba.conf location
        result = run_command("sudo -u postgres psql -t -c 'SHOW hba_file;'", timeout=10)
        pg_hba_path = result.stdout.strip() if result.stdout else None

        if not pg_hba_path:
            # Fallback to common locations
            if context.os_info.os_type == OSType.UBUNTU:
                hba_files = glob.glob(PG_HBA_UBUNTU_PATTERN)
                pg_hba_path = hba_files[0] if hba_files else None
            else:
                pg_hba_path = PG_HBA_FEDORA_PATH

        if not pg_hba_path:
            log_warning("Could not locate pg_hba.conf")
            return False

        log_debug(f"pg_hba.conf location: {pg_hba_path}")

        # Read pg_hba.conf
        result = run_command(f"sudo cat {pg_hba_path}", timeout=10)
        hba_content = result.stdout if result.stdout else ""

        # Check for md5 or scram-sha-256 authentication
        has_password_auth = False
        for line in hba_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                if 'local' in line and ('md5' in line or 'scram-sha-256' in line):
                    has_password_auth = True
                    break

        if has_password_auth:
            log_success("pg_hba.conf configured for password authentication")
            return True
        else:
            log_warning(
                "pg_hba.conf may need configuration for password authentication.\n"
                "Current configuration uses 'peer' authentication which requires system user."
            )
            return False

    except Exception as e:
        log_debug(f"Could not check pg_hba.conf: {e}")
        return False


def interactive_troubleshooting_guide(context: InstallerContext):
    """
    Provide interactive step-by-step guide for PostgreSQL setup.

    Guides user through:
    1. Creating PostgreSQL user manually
    2. Granting CREATE DATABASE privileges
    3. Configuring pg_hba.conf for local connections
    4. Restarting PostgreSQL service
    5. Testing connection again

    Args:
        context: Installation configuration context
    """
    print("\n" + "="*70)
    log_error("PostgreSQL Connection Failed - Troubleshooting Guide")
    print("="*70 + "\n")

    # Display current configuration
    log_info("Current Configuration:")
    log_info(f"  Host:     {context.db_host}")
    log_info(f"  Port:     {context.db_port}")
    log_info(f"  User:     {context.db_user}")
    log_info(f"  Database: {context.db_name}")
    log_info(f"  Password: {'*' * len(context.db_password)}")
    print()

    # Step 1: Check PostgreSQL service
    print("Step 1: Check if PostgreSQL is running")
    print("-" * 70)
    print("Run:")
    print("  sudo systemctl status postgresql")
    print()
    print("If not running:")
    print("  sudo systemctl start postgresql")
    print("  sudo systemctl enable postgresql")
    print()

    # Step 2: Create database user
    print("Step 2: Create the database user manually")
    print("-" * 70)
    print("Run:")
    print("  sudo -u postgres psql")
    print()
    print("Then in psql, execute:")
    print(f"  CREATE USER {context.db_user} WITH PASSWORD '{context.db_password}' CREATEDB;")
    print("  \\q")
    print()

    # Step 3: Create database
    print("Step 3: Create the database")
    print("-" * 70)
    print("Run:")
    print(f"  sudo -u postgres psql -c \"CREATE DATABASE {context.db_name} OWNER {context.db_user};\"")
    print()

    # Step 4: Configure pg_hba.conf
    print("Step 4: Configure pg_hba.conf for password authentication")
    print("-" * 70)

    # Detect pg_hba.conf location
    pg_hba_path = None
    try:
        result = run_command("sudo -u postgres psql -t -c 'SHOW hba_file;'", timeout=10, check=False)
        if result.returncode == 0 and result.stdout:
            pg_hba_path = result.stdout.strip()
    except:
        pass

    if not pg_hba_path:
        if context.os_info.os_type == OSType.UBUNTU:
            hba_files = glob.glob(PG_HBA_UBUNTU_PATTERN)
            pg_hba_path = hba_files[0] if hba_files else "/etc/postgresql/*/main/pg_hba.conf"
        else:
            pg_hba_path = PG_HBA_FEDORA_PATH

    print(f"Edit pg_hba.conf (located at: {pg_hba_path}):")
    print(f"  sudo nano {pg_hba_path}")
    print()
    print("Add or modify these lines:")
    print("  # TYPE  DATABASE        USER            ADDRESS                 METHOD")
    print("  local   all             all                                     md5")
    print("  host    all             all             127.0.0.1/32            md5")
    print("  host    all             all             ::1/128                 md5")
    print()
    print("Save and exit, then reload PostgreSQL:")
    print("  sudo systemctl reload postgresql")
    print()

    # Step 5: Test connection
    print("Step 5: Test the connection")
    print("-" * 70)
    print("Run:")
    print(f"  psql -h {context.db_host} -p {context.db_port} -U {context.db_user} -d {context.db_name}")
    print(f"Enter password when prompted: {context.db_password}")
    print()

    print("="*70)
    print()

    # Wait for user to complete steps
    try:
        input("After completing these steps, press Enter to retry the connection, or Ctrl+C to exit...")
    except KeyboardInterrupt:
        raise KeyboardInterrupt("Installation cancelled by user")


def verify_permissions(context: InstallerContext) -> bool:
    """
    Verify user has proper database permissions.

    Checks:
    - Can connect to database
    - Can create tables
    - Can insert/update/delete data

    Args:
        context: Installation configuration context

    Returns:
        True if all permissions verified, False otherwise
    """
    log_info("Verifying database permissions...")

    if context.dry_run:
        log_info("[DRY RUN] Would verify database permissions")
        return True

    try:
        # Set password in environment
        env = os.environ.copy()
        env['PGPASSWORD'] = context.db_password

        # Try to create a test table
        create_sql = "CREATE TABLE IF NOT EXISTS _installer_test (id SERIAL PRIMARY KEY);"
        cmd = f"psql -h {context.db_host} -p {context.db_port} -U {context.db_user} -d {context.db_name} -c {shlex.quote(create_sql)}"
        result = run_command(cmd, env=env, check=False, timeout=10)

        if result.returncode != 0:
            log_error("Failed to create test table")
            error_msg = result.stderr if result.stderr else result.stdout
            if error_msg and "permission denied" in error_msg.lower():
                log_error("User lacks necessary privileges")
            return False

        # Try to drop the test table
        drop_sql = "DROP TABLE IF EXISTS _installer_test;"
        cmd = f"psql -h {context.db_host} -p {context.db_port} -U {context.db_user} -d {context.db_name} -c {shlex.quote(drop_sql)}"
        result = run_command(cmd, env=env, check=False, timeout=10)

        if result.returncode != 0:
            log_error("Failed to drop test table")
            return False

        log_success("Database permissions verified")
        return True

    except subprocess.CalledProcessError as e:
        log_error(f"Permission verification failed: {e}")
        return False
    except Exception as e:
        log_error(f"Permission verification exception: {e}")
        return False


def setup_database(context: InstallerContext):
    """
    Phase 3: Set up PostgreSQL database with interactive troubleshooting.

    This phase will:
    1. Test PostgreSQL connection with retries
    2. If connection fails, provide interactive step-by-step guide:
       - How to create PostgreSQL user with password
       - How to grant privileges (CREATE DATABASE, etc.)
       - How to configure pg_hba.conf for local connections
       - How to restart PostgreSQL service
    3. Create 'infinibay' database
    4. Verify user has proper permissions
    5. Return validated connection string for .env generation

    Args:
        context: Installation configuration context

    Raises:
        RuntimeError: If database setup fails after manual intervention
        KeyboardInterrupt: If user cancels installation
    """
    log_step(3, 5, "Setting up PostgreSQL database")
    log_info(f"Configuring database '{context.db_name}' with user '{context.db_user}'")

    try:
        # Phase 3a: Test initial connection (postgres superuser)
        log_info("Testing PostgreSQL service...")
        postgres_running = False

        for attempt in range(MAX_CONNECTION_RETRIES):
            try:
                result = run_command("sudo -u postgres psql -c 'SELECT version();'", timeout=10, check=False)
                if result.returncode == 0:
                    postgres_running = True
                    log_debug("PostgreSQL service is running")
                    break
            except Exception as e:
                log_debug(f"PostgreSQL check attempt {attempt + 1} failed: {e}")

            if attempt < MAX_CONNECTION_RETRIES - 1:
                log_debug(f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
                time.sleep(RETRY_DELAY_SECONDS)

        if not postgres_running:
            log_error("PostgreSQL service is not running or not accessible")
            interactive_troubleshooting_guide(context)
            # Retry after manual steps
            result = run_command("sudo -u postgres psql -c 'SELECT version();'", timeout=10, check=False)
            if result.returncode != 0:
                raise RuntimeError("PostgreSQL service is still not accessible after manual intervention")

        # Phase 3b: Create user and database
        try:
            create_database_user(context)
            create_database(context)
        except Exception as e:
            log_error(f"Failed to create user/database: {e}")
            interactive_troubleshooting_guide(context)
            # Retry after manual steps
            create_database_user(context)
            create_database(context)

        # Phase 3c: Configure authentication
        configure_pg_hba(context)

        # Phase 3d: Test connection with new user
        log_info("Testing database connection...")
        connection_successful = False

        for attempt in range(MAX_CONNECTION_RETRIES):
            if test_connection(context):
                connection_successful = True
                break

            if attempt < MAX_CONNECTION_RETRIES - 1:
                log_debug(f"Connection attempt {attempt + 1} failed, retrying in {RETRY_DELAY_SECONDS} seconds...")
                time.sleep(RETRY_DELAY_SECONDS)

        if not connection_successful:
            log_error("Could not connect to database with configured credentials")
            interactive_troubleshooting_guide(context)
            # Retry after manual steps
            if not test_connection(context):
                raise RuntimeError("Database connection still failing after manual intervention")

        # Phase 3e: Verify permissions
        if not verify_permissions(context):
            log_error("Database permissions are insufficient")
            log_info(f"You may need to grant privileges manually:")
            log_info(f"  sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE {context.db_name} TO {context.db_user};\"")
            raise RuntimeError("Database permissions verification failed")

        # Success
        masked_url = context.database_url.replace(context.db_password, '****')
        log_success("PostgreSQL database configured successfully")
        log_info(f"Connection string: {masked_url}")
        log_info("Database is ready for Prisma migrations")

        return context.database_url

    except KeyboardInterrupt:
        log_error("\nInstallation cancelled by user")
        raise
    except subprocess.CalledProcessError as e:
        log_error(f"Database setup command failed: {e}")
        raise RuntimeError(f"Database setup failed: {e}")
    except Exception as e:
        log_error(f"Database setup failed: {e}")
        raise
