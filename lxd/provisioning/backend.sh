#!/bin/bash
#
# Infinibay Backend Provisioning Script
# Sets up the backend environment with all dependencies
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the universal package manager library
source "${SCRIPT_DIR}/../lib/package-manager.sh"

echo "=========================================="
echo "Infinibay Backend Provisioning"
echo "=========================================="

# Install system dependencies
echo
echo "Installing system dependencies..."
pkg_update

# Install required packages
echo "Installing build tools and libraries..."
pkg_install \
    build-essential \
    curl \
    git \
    qemu-kvm \
    pkg-config \
    libssl-dev \
    python3 \
    python3-pip \
    ca-certificates \
    gnupg

echo "System dependencies installed successfully"

# Configuration variables
BACKEND_USER="${BACKEND_USER:-infinibay}"
BACKEND_DIR="${BACKEND_DIR:-/opt/infinibay/backend}"
BACKEND_REPO="${BACKEND_REPO:-https://github.com/infinibay/backend.git}"
BACKEND_BRANCH="${BACKEND_BRANCH:-main}"

# Create backend user if it doesn't exist
if ! id "$BACKEND_USER" >/dev/null 2>&1; then
    echo
    echo "Creating backend user: $BACKEND_USER"
    useradd -r -s /bin/bash -d "$BACKEND_DIR" -m "$BACKEND_USER"
    echo "User $BACKEND_USER created"
else
    echo "User $BACKEND_USER already exists"
fi

# Add backend user to kvm group for /dev/kvm access
if getent group kvm >/dev/null 2>&1; then
    usermod -aG kvm "$BACKEND_USER"
    echo "Added $BACKEND_USER to kvm group"
else
    echo "WARNING: kvm group not found - user may not have KVM access"
fi

# Install Node.js 20.x
echo
echo "Installing Node.js 20.x..."
install_nodejs

# Verify Node.js installation
if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: Node.js installation failed"
    exit 1
fi

NODE_VERSION=$(node -v)
echo "Node.js installed: $NODE_VERSION"

if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm not found after Node.js installation"
    exit 1
fi

NPM_VERSION=$(npm -v)
echo "npm installed: $NPM_VERSION"

# Clone or update backend repository
echo
if [ ! -d "$BACKEND_DIR/.git" ]; then
    echo "Cloning backend repository..."

    # Remove directory if it exists but is not a git repo
    if [ -d "$BACKEND_DIR" ]; then
        echo "Removing existing non-git directory..."
        rm -rf "$BACKEND_DIR"
    fi

    # Clone as backend user
    sudo -u "$BACKEND_USER" git clone -b "$BACKEND_BRANCH" "$BACKEND_REPO" "$BACKEND_DIR"
    echo "Backend repository cloned to $BACKEND_DIR"
else
    echo "Backend repository already exists, pulling latest changes..."
    sudo -u "$BACKEND_USER" git -C "$BACKEND_DIR" pull
fi

# Clone infinization (required for backend VM management)
echo
if [ ! -d /opt/infinibay/infinization/.git ]; then
    echo "Cloning infinization repository..."

    # Remove directory if it exists but is not a git repo
    if [ -d /opt/infinibay/infinization ]; then
        echo "Removing existing non-git directory..."
        rm -rf /opt/infinibay/infinization
    fi

    # Clone as backend user
    sudo -u "$BACKEND_USER" git clone https://github.com/Infinibay/infinization.git /opt/infinibay/infinization
    echo "infinization repository cloned"
else
    echo "infinization repository already exists, pulling latest changes..."
    sudo -u "$BACKEND_USER" git -C /opt/infinibay/infinization pull
fi

# Configure git safe directory for infinization
git config --global --add safe.directory /opt/infinibay/infinization

# Install backend npm dependencies
echo
echo "Installing backend npm dependencies..."
cd "$BACKEND_DIR"

sudo -u "$BACKEND_USER" npm install

if [ $? -eq 0 ]; then
    echo "Backend npm dependencies installed successfully"
else
    echo "ERROR: Failed to install backend npm dependencies"
    exit 1
fi

# Build infinization BEFORE generating Prisma client
echo
echo "Building infinization (this may take a few minutes)..."

# Change ownership to backend user
chown -R "$BACKEND_USER":"$BACKEND_USER" /opt/infinibay/infinization

# Install dependencies as backend user
echo "Installing infinization dependencies..."
sudo -u "$BACKEND_USER" npm --prefix /opt/infinibay/infinization install

# Build TypeScript
echo "Compiling infinization TypeScript..."
sudo -u "$BACKEND_USER" npm --prefix /opt/infinibay/infinization run build

# Verify build succeeded
if [ -f /opt/infinibay/infinization/dist/index.js ]; then
    echo "✓ infinization built successfully"
    ls -lh /opt/infinibay/infinization/dist/index.js
else
    echo "ERROR: infinization build failed - dist/index.js not found"
    exit 1
fi

# Install nftables systemd service
echo "Installing infinization nftables service..."
cd /opt/infinibay/infinization/systemd
./install-service.sh

if systemctl is-enabled infinization-nftables.service > /dev/null 2>&1; then
    echo "✓ infinization-nftables service installed and enabled"
else
    echo "WARNING: Failed to install infinization-nftables service"
    echo "   Firewall management may not work correctly"
fi

echo "✓ infinization installation complete"

# Generate Prisma client
echo
echo "Generating Prisma client..."
sudo -u "$BACKEND_USER" npm run prisma:generate 2>/dev/null || sudo -u "$BACKEND_USER" npx prisma generate

# Run database migrations (if DATABASE_URL is configured)
if [ -f "$BACKEND_DIR/.env" ]; then
    echo
    echo "Running database migrations..."
    sudo -u "$BACKEND_USER" npm run db:migrate 2>/dev/null || sudo -u "$BACKEND_USER" npx prisma migrate deploy

    if [ $? -eq 0 ]; then
        echo "Database migrations completed"
    else
        echo "WARNING: Database migrations failed - ensure DATABASE_URL is configured in .env"
    fi
else
    echo "Skipping database migrations - .env file not found"
    echo "Configure .env and run: npm run db:migrate"
fi

# Set up systemd service
echo
echo "Setting up systemd service..."

cat > /etc/systemd/system/infinibay-backend.service <<EOF
[Unit]
Description=Infinibay Backend Service
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=$BACKEND_USER
WorkingDirectory=$BACKEND_DIR
Environment="NODE_ENV=production"
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/npm start
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=infinibay-backend

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo "Systemd service created: infinibay-backend.service"
echo "To start the service: systemctl start infinibay-backend"
echo "To enable on boot: systemctl enable infinibay-backend"

echo
echo "=========================================="
echo "Backend Provisioning Complete!"
echo "=========================================="
echo
echo "Backend directory: $BACKEND_DIR"
echo "Backend user: $BACKEND_USER"
echo "Service name: infinibay-backend"
echo
echo "Infinization status:"
echo "  - nftables service: $(systemctl is-enabled infinization-nftables.service 2>/dev/null || echo 'not installed')"
echo "  - Build output: /opt/infinibay/infinization/dist/index.js"
echo
echo "Next steps:"
echo "1. Configure $BACKEND_DIR/.env with your settings"
echo "2. Run database migrations: cd $BACKEND_DIR && npm run db:migrate"
echo "3. Start the service: systemctl start infinibay-backend"
echo "4. Enable on boot: systemctl enable infinibay-backend"
echo
