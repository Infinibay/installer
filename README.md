# Infinibay Automated Installer

Automated installation framework for the Infinibay virtualization management platform.

## Overview

This installer automates the complete setup of Infinibay on supported Linux distributions. It handles system package installation, database configuration, repository cloning, dependency building, and service deployment.

**Key Features:**
- ✓ Fully automated installation with smart defaults
- ✓ Interactive troubleshooting for database setup
- ✓ Development mode for local code installation
- ✓ Automatic dependency building in correct order
- ✓ URL-encoded database passwords for special characters
- ✓ Systemd service creation and management
- ✓ Comprehensive dry-run mode
- ✓ Granular uninstallation options
- ✓ Animated ocean waves banner (because why not?)

**Supported Operating Systems:**
- Ubuntu 23.10 or later
- Fedora 37 or later

## Requirements

- **Python**: 3.8 or later
- **Privileges**: Must run as root/sudo
- **Internet**: Required for downloading packages and repositories
- **Disk Space**: Minimum 10GB free in `/opt/infinibay/`

### Optional Dependencies

For enhanced animated banner (ocean waves effect):

```bash
pip3 install asciimatics
```

> **Note**: The installer works perfectly fine without `asciimatics`. If not installed, it will automatically fall back to a beautiful animated wave effect using only ANSI codes, or a static banner in verbose mode.

## Usage

### Basic Installation

```bash
sudo python3 install.py
```

### Uninstallation

```bash
# Remove services only (keep files and database)
sudo python3 uninstall.py

# Remove services and files (keep database)
sudo python3 uninstall.py --remove-files

# Full uninstall (remove everything)
sudo python3 uninstall.py --remove-files --remove-database

# Preview what would be removed
sudo python3 uninstall.py --remove-files --remove-database --dry-run

# Skip confirmation prompts
sudo python3 uninstall.py --remove-files --yes
```

This will:
- Auto-detect your host IP address
- Generate a secure database password
- Use default libvirt network (default)
- Install to `/opt/infinibay/`

### Custom Installation Options

```bash
# With custom database password
sudo python3 install.py --db-password=mySecurePass123

# With custom host IP (for VM connectivity)
sudo python3 install.py --host-ip=192.168.1.100

# With custom libvirt network
sudo python3 install.py --libvirt-network-name=default

# Custom installation directory
sudo python3 install.py --install-dir=/opt/custom/path

# Custom ports
sudo python3 install.py --backend-port=8080 --frontend-port=8081
```

### Development Mode: Install from Local Code

If you already have the code cloned in a directory (e.g., `/home/user/infinibay`), you can install directly from it:

```bash
# Install using your existing code directory
# This will:
#   - Use your existing code (no git clone)
#   - Build dependencies
#   - Generate .env files
#   - Create systemd services
sudo python3 install.py --install-dir=/home/user/infinibay

# Example for your case:
cd /home/andres/infinibay
sudo python3 installer/install.py --install-dir=/home/andres/infinibay
```

**How it works**:
- If the directory exists with `.git`: Skips cloning
- If the directory exists without `.git`: Uses as local development code
- Then proceeds with build, .env generation, and service creation
- **Preserves file ownership**: Restores original ownership after npm/cargo builds

**Quick development install script**:
```bash
# Even simpler - use the provided script
cd /home/andres/infinibay
sudo ./installer/install-dev.sh
```

This script automatically:
- Detects your repository location
- Verifies all required directories exist
- Asks for confirmation
- Runs the installer with correct parameters

### Skip ISO Downloads

```bash
# Skip ISO downloads
sudo python3 install.py --skip-isos
sudo python3 install.py --skip-windows-isos

# Dry run (show what would be done)
sudo python3 install.py --dry-run

# Verbose logging
sudo python3 install.py --verbose
```

### For Private Repositories

If you're installing from private GitHub repositories, you'll need authentication:

**Option 1: GitHub Personal Access Token** (Recommended)
```bash
# 1. Generate token at: https://github.com/settings/tokens
#    - Token type: Classic or Fine-grained
#    - Scopes needed: 'repo' (full control of private repositories)
#    - Expiration: Set as needed

# 2. When Git prompts for credentials:
#    Username: your-github-username
#    Password: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # Use your token, NOT your GitHub password

# 3. Save credentials (optional, for convenience)
git config --global credential.helper store
```

**Option 2: Use Local Repositories** (For Development)
```bash
# Clone repos manually to your home directory first
cd ~
git clone https://github.com/infinibay/backend.git
git clone https://github.com/infinibay/frontend.git
git clone https://github.com/infinibay/infiniservice.git

# Then run installer with local repos
sudo python3 install.py --use-local-repos --local-repos-dir=$HOME
```

**Option 3: SSH Keys**
```bash
# If you prefer SSH over HTTPS, modify REPO_URLS in lib/repos.py:
# Change: 'https://github.com/infinibay/backend.git'
# To:     'git@github.com:infinibay/backend.git'
```

### Combined Options

```bash
sudo python3 install.py \
  --host-ip=192.168.1.100 \
  --db-password=SecurePass123 \
  --libvirt-network-name=default \
  --verbose
```

## Command-Line Options Reference

| Option | Default | Description |
|--------|---------|-------------|
| `--db-password` | *auto-generated* | PostgreSQL password for infinibay user |
| `--db-user` | `infinibay` | PostgreSQL username |
| `--db-host` | `localhost` | PostgreSQL host |
| `--db-port` | `5432` | PostgreSQL port |
| `--db-name` | `infinibay` | PostgreSQL database name |
| `--host-ip` | *auto-detected* | Host IP address for VMs to connect |
| `--libvirt-network-name` | `default` | Libvirt virtual network name |
| `--backend-port` | `4000` | Backend GraphQL server port |
| `--frontend-port` | `3000` | Frontend web server port |
| `--install-dir` | `/opt/infinibay` | Installation directory |
| `--use-local-repos` | `false` | Use local repository code instead of cloning |
| `--local-repos-dir` | - | Path to local repositories directory |
| `--skip-isos` | `false` | Skip downloading Ubuntu/Fedora ISOs |
| `--skip-windows-isos` | `false` | Skip downloading Windows ISOs |
| `--dry-run` | `false` | Show what would be done without executing |
| `--verbose` | `false` | Enable verbose logging |

## What It Does

The installer executes the following phases:

### Phase 1: Framework Initialization ✓
- Parse command-line arguments
- Detect operating system and validate compatibility
- Check root privileges
- Generate secure defaults (IP detection, password generation)
- Create installation context

### Phase 2: System Dependencies ✓
- Update package cache (apt/dnf)
- Install required packages:
  - Node.js and npm
  - PostgreSQL
  - QEMU/KVM and libvirt
  - Rust and Cargo
  - Build tools and development libraries
  - bridge-utils
- Enable and start system services
- Configure libvirt virtual network automatically
- Verify KVM support

### Phase 3: Database Setup ✓
- Test PostgreSQL connectivity
- Interactive troubleshooting guide if connection fails
- Create `infinibay` database user
- Create `infinibay` database
- Grant necessary privileges
- Verify permissions

### Phase 4: Repository Setup ✓
- Clone repositories from GitHub:
  - backend
  - frontend
  - infiniservice
  - libvirt-node (native addon)
- Build dependencies in correct order:
  1. libvirt-node (Rust → Node.js addon)
  2. Backend (npm install + Prisma generate)
  3. Frontend (npm install)
  4. Infiniservice (cargo build --release)
- Automatic npm cache cleaning and package-lock.json regeneration for libvirt-node

### Phase 5: Configuration & Services ✓
- Generate backend `.env` configuration
- Generate frontend `.env` configuration
- Run database migrations
- Execute backend setup (folders, ISOs, network filters)
- Create systemd service files
- Enable and start services
- Display installation summary

## Installation Flow Summary

The installer follows this logical sequence:

1. **Pre-flight checks**: Root privileges, OS compatibility
2. **System packages**: Install Node.js, PostgreSQL, QEMU/KVM, Rust, build tools
3. **Database setup**: Create PostgreSQL user and database with interactive troubleshooting
4. **Repository setup**: Clone or use local repos, build in dependency order
5. **Configuration**: Generate .env files with proper password encoding
6. **Service deployment**: Create and start systemd services
7. **Post-install**: Run migrations, setup backend (ISOs, network filters)

## Network Configuration

The installer automatically detects and configures libvirt virtual networks for VM connectivity. This allows VMs to communicate with the host and external networks.

### Automatic Network Setup

By default, the installer will:
1. Detect existing libvirt virtual networks using `virsh net-list --all`
2. Select an appropriate network (prefers 'default', then any active network)
3. If no networks exist, prompt to create a default NAT network named 'infinibay'
4. Verify the selected network is active and ready

**Network modes supported:**
- NAT (default) - VMs access external network through host NAT
- Bridged - VMs connect directly to physical network
- Isolated - VMs only communicate with host

### Custom Network Selection

To use a specific libvirt network:

```bash
sudo python3 install.py --libvirt-network-name=your-network
```

List available networks:
```bash
virsh net-list --all
```

### Manual Network Setup

If you prefer to configure the network manually before installation:

#### Create a NAT network:
```bash
# Create network XML file
cat > /tmp/infinibay-network.xml <<EOF
<network>
  <name>infinibay</name>
  <forward mode='nat'/>
  <bridge name='virbr-infinibay' stp='on' delay='0'/>
  <ip address='192.168.122.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.122.2' end='192.168.122.254'/>
    </dhcp>
  </ip>
</network>
EOF

# Define and start the network
sudo virsh net-define /tmp/infinibay-network.xml
sudo virsh net-start infinibay
sudo virsh net-autostart infinibay
```

#### Using netplan (Ubuntu Server):
Create `/etc/netplan/01-infinibay-bridge.yaml`:
```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: no
      dhcp6: no
  bridges:
    br0:
      interfaces: [eth0]
      dhcp4: yes
      dhcp6: yes
```
Then apply: `sudo netplan apply`

#### Using bridge-utils (manual):
```bash
sudo brctl addbr br0
sudo brctl addif br0 eth0
sudo ip link set br0 up
sudo dhclient br0
```

### Verifying Bridge Status

After installation, verify the bridge is active:
```bash
ip link show br0
```

Look for `state UP` in the output.

### Examples

```bash
# Install with custom bridge name
sudo python3 install.py --bridge-name=virbr1

# Install with manual bridge setup
sudo python3 install.py --skip-bridge-setup

# Install with specific interface
sudo python3 install.py --primary-interface=ens33

# Install with custom bridge and interface
sudo python3 install.py --bridge-name=br1 --primary-interface=enp0s3
```

## Troubleshooting

### Permission Denied

```
Error: This installer must be run as root
```

**Solution**: Run with sudo: `sudo python3 install.py`

### Unsupported OS

```
Error: Ubuntu 22.04 is not supported. Minimum version: 23.10
```

**Solution**: Upgrade to Ubuntu 23.10+ or Fedora 37+

### Database Connection Failed

The installer provides an interactive troubleshooting guide if PostgreSQL connection fails, including:
- How to create the database user
- How to configure authentication (pg_hba.conf)
- How to restart the PostgreSQL service

### Invalid Port Number in Database URL

If you see:
```
Error: P1013: The provided database string is invalid. invalid port number in database URL
```

**Cause**: The auto-generated database password contains special characters (like `:` or `@`) that weren't properly encoded in the connection string.

**Solution**: This is now automatically fixed! The installer URL-encodes passwords using `quote_plus()`. If you still encounter this:
- Use a simple password without special characters: `--db-password=SimplePass123`
- Or let the installer regenerate (it now encodes properly)

### GitHub Authentication Required

If you see:
```
fatal: could not read Username for 'https://github.com'
Authentication failed for 'https://github.com/...'
```

**Cause**: The repositories are private and require authentication.

**Solutions**:
1. **Use GitHub Personal Access Token**:
   - Generate at https://github.com/settings/tokens
   - When Git prompts, use token as password (NOT your GitHub password)
   - Token needs 'repo' scope for private repositories

2. **Use local repositories** (recommended for development):
   ```bash
   sudo python3 install.py --use-local-repos --local-repos-dir=/home/youruser/infinibay
   ```

3. **Configure credential helper** (saves token):
   ```bash
   git config --global credential.helper store
   ```

### Build Failures

If dependency builds fail, check:
- Internet connectivity
- Sufficient disk space
- Required system packages installed
- Build logs in verbose mode: `sudo python3 install.py --verbose`

### libvirt-node Integrity Checksum Error

If you see an error like:

```
npm ERR! sha512-XXX integrity checksum failed when using sha512:
wanted sha512-XXX but got sha512-YYY
```

**Cause**: The `@infinibay/libvirt-node` package was rebuilt, changing the `.tgz` file hash, but `package-lock.json` still has the old hash cached.

**Solution**: The installer automatically fixes this by:
1. Cleaning npm cache before backend installation
2. Removing `package-lock.json` to regenerate with current hash

**Manual fix** (if needed):
```bash
cd /opt/infinibay/backend
npm cache clean --force
rm package-lock.json
npm install
```

**Note for developers**: If you frequently modify libvirt-node, the installer will automatically handle hash mismatches on each run. The `.tgz` package is rebuilt during Phase 4b, and the hash is refreshed during Phase 4c.

### Port Already in Use

If default ports are occupied, specify custom ports:

```bash
sudo python3 install.py --backend-port=8080 --frontend-port=8081
```

### Network Bridge Issues

**Problem**: Bridge creation fails or network connectivity is lost

**Symptoms**:
- `ip link show br0` shows bridge doesn't exist
- No internet connectivity after installation
- VM creation fails with network errors

**Solutions**:

1. **Check NetworkManager/netplan status**:
   ```bash
   # For NetworkManager
   systemctl status NetworkManager

   # For netplan
   netplan get
   ```

2. **Restore previous network configuration**:
   ```bash
   # If using NetworkManager
   nmcli connection delete br0
   nmcli connection up <original-connection>

   # If using netplan
   sudo rm /etc/netplan/01-infinibay-bridge.yaml
   sudo cp /etc/netplan/*.yaml.backup /etc/netplan/
   sudo netplan apply
   ```

3. **Skip automatic bridge setup and configure manually**:
   ```bash
   sudo python3 install.py --skip-bridge-setup
   # Then follow manual bridge setup instructions above
   ```

4. **Specify correct primary interface**:
   ```bash
   # First, list your interfaces
   ip link show

   # Then specify the correct one
   sudo python3 install.py --primary-interface=<your-interface>
   ```

## Architecture

The installer uses a modular architecture with clean separation of concerns:

```
installer/
├── install.py              # Main orchestrator
├── lib/
│   ├── __init__.py        # Package exports
│   ├── args.py            # CLI argument parsing
│   ├── logger.py          # Colored logging system
│   ├── os_detect.py       # OS detection and validation
│   ├── privileges.py      # Root/sudo privilege checks
│   ├── utils.py           # Command execution utilities
│   ├── config.py          # Configuration context
│   ├── network_setup.py   # Network bridge configuration
│   ├── system_check.py    # Phase 2: System packages
│   ├── database.py        # Phase 3: PostgreSQL setup
│   ├── repos.py           # Phase 4: Repo cloning & building
│   └── services.py        # Phase 5: Services & configuration
└── README.md
```

### Key Design Decisions

- **No external dependencies**: Uses only Python standard library for maximum portability
- **Dataclass-based config**: `InstallerContext` carries all settings between phases
- **Smart defaults with overrides**: Auto-detection with CLI flag overrides
- **Colored output**: ANSI escape codes for visual clarity with animated banner
- **Dry-run mode**: Preview changes before execution
- **Verbose logging**: Optional detailed command output
- **Robust error handling**: Interactive troubleshooting for common issues
- **Development-friendly**: Local code installation and automatic ownership restoration
- **Build optimization**: Automatic npm cache cleanup and hash mismatch resolution

## Development

### Running in Dry-Run Mode

Test the installer without making changes:

```bash
sudo python3 install.py --dry-run --verbose
```

### Adding New Phases

Each phase is implemented in a separate module under `lib/`. To add a new phase:

1. Create module: `lib/new_phase.py`
2. Import context: `from lib.config import InstallerContext`
3. Implement function: `def run_new_phase(context: InstallerContext)`
4. Call from `install.py` in the main sequence

### Module Dependencies

- `args.py`: No dependencies (uses argparse)
- `logger.py`: No dependencies (uses ANSI codes)
- `os_detect.py`: No dependencies (parses /etc/os-release)
- `privileges.py`: No dependencies (uses os.geteuid)
- `utils.py`: Uses `logger.py` (for command logging)
- `config.py`: Uses `os_detect.py` and `utils.py`
- Phase modules: Use `config.py` and `utils.py`

## Uninstallation Options

The uninstaller provides granular control over what gets removed:

| Option | What it removes | What it keeps |
|--------|----------------|---------------|
| Default | Services only | Files, Database |
| `--remove-files` | Services + Files | Database |
| `--remove-database` | Services + Database | Files |
| `--remove-files --remove-database` | Everything | Nothing |

**Additional flags:**
- `--dry-run` - Preview changes without executing
- `--yes` or `-y` - Skip confirmation prompts
- `--verbose` - Show detailed logging
- `--install-dir` - Specify custom installation directory
- `--db-name` / `--db-user` - Specify custom database/user names

## Version

Current version: **2.0.0** (All Phases Complete)

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or contributions:
- GitHub: https://github.com/infinibay/installer
- Documentation: https://docs.infinibay.com

## Next Steps After Installation

Once installation completes successfully:

1. **Access the web interface**: `http://<host-ip>:3000`
2. **GraphQL API**: `http://<host-ip>:4000/graphql`
3. **Default credentials**: Displayed in installation summary
4. **Create your first VM**: Follow the quick start guide
5. **Configure departments**: Set up organizational structure
6. **Review security policies**: Customize network filters

---

**Note**: The installer is fully complete and production-ready. All phases (1-5) have been implemented and tested.
