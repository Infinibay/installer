#!/bin/bash
#
# Infinibay PostgreSQL Provisioning Script
# Installs and configures PostgreSQL database
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the universal package manager library
source "${SCRIPT_DIR}/../lib/package-manager.sh"

echo "=========================================="
echo "Infinibay PostgreSQL Provisioning"
echo "=========================================="

# Install PostgreSQL
echo
echo "Installing PostgreSQL..."
pkg_update

pkg_install postgresql postgresql-contrib

echo "PostgreSQL packages installed successfully"

# Configuration variables
DB_NAME="${DB_NAME:-infinibay}"
DB_USER="${DB_USER:-infinibay}"
DB_PASSWORD="${DB_PASSWORD:-infinibay}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# Initialize PostgreSQL (distribution-specific)
echo
echo "Initializing PostgreSQL database..."
init_postgresql

# Get the correct service name
PG_SERVICE=$(get_service_name postgresql)

# Start and enable PostgreSQL service
echo
echo "Starting PostgreSQL service..."

if systemctl is-active --quiet "$PG_SERVICE"; then
    echo "$PG_SERVICE is already running"
else
    systemctl start "$PG_SERVICE"
    echo "$PG_SERVICE started"
fi

if systemctl is-enabled --quiet "$PG_SERVICE"; then
    echo "$PG_SERVICE is already enabled"
else
    systemctl enable "$PG_SERVICE"
    echo "$PG_SERVICE enabled"
fi

# Wait for PostgreSQL to be ready
echo
echo "Waiting for PostgreSQL to be ready..."
sleep 3

# Check if PostgreSQL is accepting connections
for i in {1..30}; do
    if sudo -u postgres psql -c '\q' >/dev/null 2>&1; then
        echo "PostgreSQL is ready"
        break
    fi

    if [ $i -eq 30 ]; then
        echo "ERROR: PostgreSQL failed to start within 30 seconds"
        systemctl status "$PG_SERVICE"
        exit 1
    fi

    sleep 1
done

# Configure PostgreSQL for network access
echo
echo "Configuring PostgreSQL for network access..."

# Find PostgreSQL data directory
PG_DATA_DIR=""
if [ -d "/var/lib/postgresql/data" ]; then
    PG_DATA_DIR="/var/lib/postgresql/data"
elif [ -d "/var/lib/pgsql/data" ]; then
    PG_DATA_DIR="/var/lib/pgsql/data"
elif [ -d "/var/lib/postgres/data" ]; then
    PG_DATA_DIR="/var/lib/postgres/data"
else
    # Try to find it via PostgreSQL
    PG_DATA_DIR=$(sudo -u postgres psql -t -c "SHOW data_directory;" 2>/dev/null | xargs)
fi

if [ -n "$PG_DATA_DIR" ] && [ -d "$PG_DATA_DIR" ]; then
    echo "PostgreSQL data directory: $PG_DATA_DIR"

    # Update postgresql.conf to listen on all addresses (if not already configured)
    PG_CONF="$PG_DATA_DIR/postgresql.conf"
    if [ -f "$PG_CONF" ]; then
        if ! grep -q "^listen_addresses = '\*'" "$PG_CONF"; then
            echo "Configuring PostgreSQL to listen on all addresses..."
            sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" "$PG_CONF"
            sed -i "s/listen_addresses = 'localhost'/listen_addresses = '*'/" "$PG_CONF"
        fi
    fi

    # Update pg_hba.conf to allow connections (if not already configured)
    PG_HBA="$PG_DATA_DIR/pg_hba.conf"
    if [ -f "$PG_HBA" ]; then
        if ! grep -q "host.*all.*all.*0.0.0.0/0.*md5" "$PG_HBA"; then
            echo "Configuring PostgreSQL authentication..."
            echo "host    all             all             0.0.0.0/0               md5" >> "$PG_HBA"
            echo "host    all             all             ::0/0                   md5" >> "$PG_HBA"
        fi
    fi

    # Restart PostgreSQL to apply configuration changes
    echo "Restarting PostgreSQL to apply configuration..."
    systemctl restart "$PG_SERVICE"
    sleep 2
else
    echo "WARNING: Could not locate PostgreSQL data directory"
fi

# Create database user
echo
echo "Creating database user..."

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
    echo "User $DB_USER already exists"
else
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
    echo "User $DB_USER created"
fi

# Create database
echo
echo "Creating database..."

if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo "Database $DB_NAME already exists"
else
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
    echo "Database $DB_NAME created"
fi

# Grant privileges
echo
echo "Granting privileges..."
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;"

echo "Privileges granted to $DB_USER on database $DB_NAME"

echo
echo "=========================================="
echo "PostgreSQL Provisioning Complete!"
echo "=========================================="
echo
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo "Password: $DB_PASSWORD"
echo "Host: $DB_HOST"
echo "Port: $DB_PORT"
echo
echo "Connection string:"
echo "postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
echo
echo "Service name: $PG_SERVICE"
echo "Service status: systemctl status $PG_SERVICE"
echo
