# Infinibay Automated Installer

Automated installation framework for the Infinibay virtualization management platform.

## Overview

This installer automates the complete setup of Infinibay on supported Linux distributions. It handles system package installation, database configuration, repository cloning, dependency building, and service deployment.

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

This will:
- Auto-detect your host IP address
- Generate a secure database password
- Use default bridge name (br0)
- Install to `/opt/infinibay/`

### Custom Installation Options

```bash
# With custom database password
sudo python3 install.py --db-password=mySecurePass123

# With custom host IP (for VM connectivity)
sudo python3 install.py --host-ip=192.168.1.100

# With custom network bridge
sudo python3 install.py --bridge-name=virbr0

# Custom installation directory
sudo python3 install.py --install-dir=/opt/custom/path

# Custom ports
sudo python3 install.py --backend-port=8080 --frontend-port=8081

# Skip ISO downloads
sudo python3 install.py --skip-isos
sudo python3 install.py --skip-windows-isos

# Dry run (show what would be done)
sudo python3 install.py --dry-run

# Verbose logging
sudo python3 install.py --verbose
```

### Combined Options

```bash
sudo python3 install.py \
  --host-ip=192.168.1.100 \
  --db-password=SecurePass123 \
  --bridge-name=br0 \
  --verbose
```

## What It Does

The installer executes the following phases:

### Phase 1: Framework Initialization ✓
- Parse command-line arguments
- Detect operating system and validate compatibility
- Check root privileges
- Generate secure defaults (IP detection, password generation)
- Create installation context

### Phase 2: System Dependencies (Coming Soon)
- Update package cache (apt/dnf)
- Install required packages:
  - Node.js and npm
  - PostgreSQL
  - QEMU/KVM and libvirt
  - Rust and Cargo
  - Build tools and development libraries
- Enable and start system services
- Verify KVM support

### Phase 3: Database Setup (Coming Soon)
- Test PostgreSQL connectivity
- Interactive troubleshooting guide if connection fails
- Create `infinibay` database user
- Create `infinibay` database
- Grant necessary privileges
- Verify permissions

### Phase 4: Repository Setup (Coming Soon)
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

### Phase 5: Configuration & Services (Coming Soon)
- Generate backend `.env` configuration
- Generate frontend `.env` configuration
- Run database migrations
- Execute backend setup (folders, ISOs, network filters)
- Create systemd service files
- Enable and start services
- Display installation summary

## Default Values

| Setting | Default Value | Description |
|---------|--------------|-------------|
| Installation Directory | `/opt/infinibay/` | Base installation path |
| Database Host | `localhost` | PostgreSQL server |
| Database Port | `5432` | PostgreSQL port |
| Database User | `infinibay` | Database username |
| Database Password | *auto-generated* | 32-character secure password |
| Database Name | `infinibay` | Database name |
| Host IP | *auto-detected* | Primary network interface IP |
| Bridge Name | `br0` | Libvirt network bridge |
| Backend Port | `4000` | GraphQL API server port |
| Frontend Port | `3000` | Next.js web interface port |

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

### Build Failures

If dependency builds fail, check:
- Internet connectivity
- Sufficient disk space
- Required system packages installed
- Build logs in verbose mode: `sudo python3 install.py --verbose`

### Port Already in Use

If default ports are occupied, specify custom ports:

```bash
sudo python3 install.py --backend-port=8080 --frontend-port=8081
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
- **Colored output**: ANSI escape codes for visual clarity
- **Dry-run mode**: Preview changes before execution
- **Verbose logging**: Optional detailed command output

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

## Version

Current version: **1.0.0** (Phase 1 - Framework Complete)

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

**Note**: This installer is currently in Phase 1 (framework complete). Phases 2-5 are stubs and will be implemented in subsequent releases.
