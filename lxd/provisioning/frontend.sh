#!/bin/bash
#
# Infinibay Frontend Provisioning Script
# Sets up the frontend environment with all dependencies
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the universal package manager library
source "${SCRIPT_DIR}/../lib/package-manager.sh"

echo "=========================================="
echo "Infinibay Frontend Provisioning"
echo "=========================================="

# Install system dependencies
echo
echo "Installing system dependencies..."
pkg_update

echo "Installing build tools..."
pkg_install \
    curl \
    git \
    build-essential \
    ca-certificates \
    gnupg

echo "System dependencies installed successfully"

# Configuration variables
FRONTEND_USER="${FRONTEND_USER:-infinibay}"
FRONTEND_DIR="${FRONTEND_DIR:-/opt/infinibay/frontend}"
FRONTEND_REPO="${FRONTEND_REPO:-https://github.com/infinibay/frontend.git}"
FRONTEND_BRANCH="${FRONTEND_BRANCH:-main}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

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

# Create frontend user if it doesn't exist
if ! id "$FRONTEND_USER" >/dev/null 2>&1; then
    echo
    echo "Creating frontend user: $FRONTEND_USER"
    useradd -r -s /bin/bash -d "$FRONTEND_DIR" -m "$FRONTEND_USER"
    echo "User $FRONTEND_USER created"
else
    echo "User $FRONTEND_USER already exists"
fi

# Clone or update frontend repository
echo
if [ ! -d "$FRONTEND_DIR/.git" ]; then
    echo "Cloning frontend repository..."

    # Remove directory if it exists but is not a git repo
    if [ -d "$FRONTEND_DIR" ]; then
        echo "Removing existing non-git directory..."
        rm -rf "$FRONTEND_DIR"
    fi

    # Clone as frontend user
    sudo -u "$FRONTEND_USER" git clone -b "$FRONTEND_BRANCH" "$FRONTEND_REPO" "$FRONTEND_DIR"
    echo "Frontend repository cloned to $FRONTEND_DIR"
else
    echo "Frontend repository already exists, pulling latest changes..."
    sudo -u "$FRONTEND_USER" git -C "$FRONTEND_DIR" pull
fi

# Install frontend npm dependencies
echo
echo "Installing frontend npm dependencies..."
cd "$FRONTEND_DIR"

sudo -u "$FRONTEND_USER" npm install

if [ $? -eq 0 ]; then
    echo "Frontend npm dependencies installed successfully"
else
    echo "ERROR: Failed to install frontend npm dependencies"
    exit 1
fi

# Build frontend for production
echo
echo "Building frontend for production..."

if [ -f "$FRONTEND_DIR/.env" ]; then
    sudo -u "$FRONTEND_USER" npm run build

    if [ $? -eq 0 ]; then
        echo "Frontend build completed successfully"
    else
        echo "WARNING: Frontend build failed - ensure .env is properly configured"
    fi
else
    echo "Skipping frontend build - .env file not found"
    echo "Configure .env and run: npm run build"
fi

# Set up systemd service
echo
echo "Setting up systemd service..."

cat > /etc/systemd/system/infinibay-frontend.service <<EOF
[Unit]
Description=Infinibay Frontend Service
After=network.target infinibay-backend.service
Wants=infinibay-backend.service

[Service]
Type=simple
User=$FRONTEND_USER
WorkingDirectory=$FRONTEND_DIR
Environment="NODE_ENV=production"
Environment="PORT=$FRONTEND_PORT"
ExecStart=/usr/bin/npm start
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=infinibay-frontend

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo "Systemd service created: infinibay-frontend.service"
echo "To start the service: systemctl start infinibay-frontend"
echo "To enable on boot: systemctl enable infinibay-frontend"

echo
echo "=========================================="
echo "Frontend Provisioning Complete!"
echo "=========================================="
echo
echo "Frontend directory: $FRONTEND_DIR"
echo "Frontend user: $FRONTEND_USER"
echo "Service name: infinibay-frontend"
echo "Port: $FRONTEND_PORT"
echo
echo "Next steps:"
echo "1. Configure $FRONTEND_DIR/.env with your settings"
echo "2. Build the frontend: cd $FRONTEND_DIR && npm run build"
echo "3. Start the service: systemctl start infinibay-frontend"
echo "4. Enable on boot: systemctl enable infinibay-frontend"
echo "5. Access the frontend at: http://localhost:$FRONTEND_PORT"
echo
