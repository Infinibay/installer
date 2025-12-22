#!/bin/bash
#
# Infinibay Redis Provisioning Script
# Installs and configures Redis cache
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the universal package manager library
source "${SCRIPT_DIR}/../lib/package-manager.sh"

echo "=========================================="
echo "Infinibay Redis Provisioning"
echo "=========================================="

# Install Redis
echo
echo "Installing Redis..."
pkg_update

pkg_install redis

echo "Redis package installed successfully"

# Get the correct service name and config path
REDIS_SERVICE=$(get_service_name redis)
REDIS_CONF=$(get_config_path redis)

echo "Redis service name: $REDIS_SERVICE"
echo "Redis config file: $REDIS_CONF"

# Configuration variables
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_BIND="${REDIS_BIND:-127.0.0.1}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

# Configure Redis
echo
echo "Configuring Redis..."

# Check if config file exists
if [ ! -f "$REDIS_CONF" ]; then
    # Try to find the config file
    if [ -f "/etc/redis.conf" ]; then
        REDIS_CONF="/etc/redis.conf"
    elif [ -f "/etc/redis/redis.conf" ]; then
        REDIS_CONF="/etc/redis/redis.conf"
    elif [ -f "/etc/redis/default.conf.example" ]; then
        # openSUSE case - copy example to active config
        REDIS_CONF="/etc/redis/default.conf"
        cp /etc/redis/default.conf.example "$REDIS_CONF"
    else
        echo "ERROR: Could not find Redis configuration file"
        echo "Searched locations:"
        echo "  - /etc/redis/redis.conf"
        echo "  - /etc/redis.conf"
        echo "  - /etc/redis/default.conf.example"
        exit 1
    fi
fi

echo "Using Redis configuration file: $REDIS_CONF"

# Backup original config
if [ ! -f "$REDIS_CONF.backup" ]; then
    cp "$REDIS_CONF" "$REDIS_CONF.backup"
    echo "Backed up original config to $REDIS_CONF.backup"
fi

# Update Redis configuration
echo "Updating Redis configuration..."

# Set supervised to systemd
if grep -q "^supervised" "$REDIS_CONF"; then
    sed -i "s/^supervised .*/supervised systemd/" "$REDIS_CONF"
else
    echo "supervised systemd" >> "$REDIS_CONF"
fi

# Set bind address
if grep -q "^bind" "$REDIS_CONF"; then
    sed -i "s/^bind .*/bind $REDIS_BIND/" "$REDIS_CONF"
else
    echo "bind $REDIS_BIND" >> "$REDIS_CONF"
fi

# Set port
if grep -q "^port" "$REDIS_CONF"; then
    sed -i "s/^port .*/port $REDIS_PORT/" "$REDIS_CONF"
else
    echo "port $REDIS_PORT" >> "$REDIS_CONF"
fi

# Set password if provided
if [ -n "$REDIS_PASSWORD" ]; then
    if grep -q "^requirepass" "$REDIS_CONF"; then
        sed -i "s/^requirepass .*/requirepass $REDIS_PASSWORD/" "$REDIS_CONF"
    else
        echo "requirepass $REDIS_PASSWORD" >> "$REDIS_CONF"
    fi
    echo "Redis password configured"
fi

# Ensure proper permissions on config file
chmod 640 "$REDIS_CONF"

# Handle ownership based on distribution
case "$OS_FAMILY" in
    debian)
        chown redis:redis "$REDIS_CONF" 2>/dev/null || true
        ;;
    rhel|suse)
        chown redis:redis "$REDIS_CONF" 2>/dev/null || true
        ;;
    arch)
        chown redis:redis "$REDIS_CONF" 2>/dev/null || true
        ;;
esac

echo "Redis configuration updated"

# Start and enable Redis service
echo
echo "Starting Redis service..."

if systemctl is-active --quiet "$REDIS_SERVICE"; then
    echo "$REDIS_SERVICE is already running, restarting to apply config..."
    systemctl restart "$REDIS_SERVICE"
else
    systemctl start "$REDIS_SERVICE"
    echo "$REDIS_SERVICE started"
fi

if systemctl is-enabled --quiet "$REDIS_SERVICE"; then
    echo "$REDIS_SERVICE is already enabled"
else
    systemctl enable "$REDIS_SERVICE"
    echo "$REDIS_SERVICE enabled"
fi

# Wait for Redis to be ready
echo
echo "Waiting for Redis to be ready..."
sleep 2

# Test Redis connection
if command -v redis-cli >/dev/null 2>&1; then
    if [ -n "$REDIS_PASSWORD" ]; then
        REDIS_PING=$(redis-cli -h "$REDIS_BIND" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" ping 2>/dev/null || echo "FAILED")
    else
        REDIS_PING=$(redis-cli -h "$REDIS_BIND" -p "$REDIS_PORT" ping 2>/dev/null || echo "FAILED")
    fi

    if [ "$REDIS_PING" = "PONG" ]; then
        echo "Redis is responding to ping"
    else
        echo "WARNING: Redis is not responding to ping"
        echo "Check service status: systemctl status $REDIS_SERVICE"
    fi
else
    echo "redis-cli not found, skipping connection test"
fi

echo
echo "=========================================="
echo "Redis Provisioning Complete!"
echo "=========================================="
echo
echo "Service name: $REDIS_SERVICE"
echo "Config file: $REDIS_CONF"
echo "Bind address: $REDIS_BIND"
echo "Port: $REDIS_PORT"
if [ -n "$REDIS_PASSWORD" ]; then
    echo "Password: $REDIS_PASSWORD"
    echo "Connection string: redis://:$REDIS_PASSWORD@$REDIS_BIND:$REDIS_PORT"
else
    echo "Password: (none)"
    echo "Connection string: redis://$REDIS_BIND:$REDIS_PORT"
fi
echo
echo "Service status: systemctl status $REDIS_SERVICE"
echo
