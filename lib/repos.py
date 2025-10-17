"""
Phase 4: Repository cloning and dependency building.

This module handles:
- Cloning repositories from GitHub
- Building dependencies in correct order
- Verifying successful builds
"""

import os
import subprocess
import time
import glob
import shutil

from .config import InstallerContext
from .logger import log_step, log_info, log_success, log_warning, log_error, log_debug, log_section, GREEN, RESET
from .utils import run_command, CommandResult
from .virtio_setup import setup_virtio_drivers

# Repository URLs
REPO_URLS = {
    'backend': 'https://github.com/infinibay/backend.git',
    'frontend': 'https://github.com/infinibay/frontend.git',
    'infiniservice': 'https://github.com/infinibay/infiniservice.git',
    'libvirt-node': 'https://github.com/Infinibay/libvirt-node.git',
}

# Build order (must build libvirt-node first as backend depends on it)
BUILD_ORDER = [
    'libvirt-node',
    'backend',
    'frontend',
    'infiniservice',
]

# Configuration constants
MAX_CLONE_RETRIES = 3
CLONE_RETRY_DELAY_SECONDS = 5


def verify_file_exists(filepath: str, description: str) -> bool:
    """
    Verify that a file exists at the given path.

    Args:
        filepath: Path to the file to check
        description: Human-readable description for error messages

    Returns:
        True if file exists

    Raises:
        RuntimeError: If file does not exist
    """
    if os.path.exists(filepath):
        log_debug(f"{description} found: {filepath}")
        return True
    else:
        raise RuntimeError(f"{description} not found at {filepath}. Build may have failed.")


def verify_directory_exists(dirpath: str, description: str) -> bool:
    """
    Verify that a directory exists and is not empty.

    Args:
        dirpath: Path to the directory to check
        description: Human-readable description for error messages

    Returns:
        True if directory exists and has files

    Raises:
        RuntimeError: If directory does not exist or is empty
    """
    if os.path.exists(dirpath) and os.path.isdir(dirpath):
        # Check if directory has files
        if os.listdir(dirpath):
            log_debug(f"{description} found: {dirpath}")
            return True
        else:
            raise RuntimeError(f"{description} is empty at {dirpath}. Build may have failed.")
    else:
        raise RuntimeError(f"{description} not found at {dirpath}. Build may have failed.")


def clone_repository(url: str, destination: str, context: InstallerContext):
    """
    Clone Git repository from URL to destination.

    IMPORTANT: For private repositories, authentication is required:
        - Use HTTPS with GitHub Personal Access Token (classic or fine-grained)
        - Configure git credential helper: git config --global credential.helper store
        - Or use SSH URLs instead of HTTPS

    Args:
        url: Git repository URL
        destination: Target directory path
        context: Installation configuration context

    Raises:
        RuntimeError: If clone fails after all retries
    """
    log_info(f"Cloning repository from {url}...")

    # Dry-run mode
    if context.dry_run:
        log_info(f"[DRY RUN] Would clone: {url} → {destination}")
        return

    # Check if already exists
    if os.path.exists(destination):
        git_dir = os.path.join(destination, '.git')
        if os.path.exists(git_dir):
            log_info("Repository already cloned, skipping")
            return
        else:
            # Directory exists but is not a git repo - assume it's local code
            log_info("Directory exists (not a git repo), assuming local development code")
            log_info("Skipping clone, will use existing code")
            return

    # Ensure parent directory exists
    parent_dir = os.path.dirname(destination)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    # Build git clone command
    command = f"git clone {url} {destination}"

    # Retry logic
    for attempt in range(1, MAX_CLONE_RETRIES + 1):
        try:
            log_info(f"Clone attempt {attempt}/{MAX_CLONE_RETRIES}...")
            result = run_command(command, timeout=600)

            # Verify .git directory exists
            git_dir = os.path.join(destination, '.git')
            if not os.path.exists(git_dir):
                raise RuntimeError(f".git directory not found after clone: {git_dir}")

            log_success(f"Repository cloned successfully to {destination}")
            return

        except subprocess.CalledProcessError as e:
            log_error(f"Clone attempt {attempt} failed: {e}")

            if attempt < MAX_CLONE_RETRIES:
                log_info(f"Retrying in {CLONE_RETRY_DELAY_SECONDS} seconds...")
                time.sleep(CLONE_RETRY_DELAY_SECONDS)
            else:
                # All retries failed
                log_error("All clone attempts failed. Possible issues:")
                log_error("  - Check internet connection")
                log_error(f"  - Verify GitHub URL is accessible: {url}")
                log_error("  - Check available disk space")
                log_error(f"  - Check write permissions to {parent_dir}")

                # Check for authentication errors
                error_str = str(e.stderr) if hasattr(e, 'stderr') and e.stderr else str(e)
                if "Authentication failed" in error_str or "fatal: could not read Username" in error_str:
                    log_error("")
                    log_error("Authentication required for private repository!")
                    log_error("Solutions:")
                    log_error("  1. Make repository public (if appropriate)")
                    log_error("  2. Use GitHub Personal Access Token:")
                    log_error("     - Generate token at: https://github.com/settings/tokens")
                    log_error("     - Use as password when Git prompts for credentials")
                    log_error("     - Token needs 'repo' scope for private repositories")
                    log_error("  3. Configure git credential helper:")
                    log_error("     git config --global credential.helper store")
                    log_error("  4. Use SSH URL instead of HTTPS (requires SSH key setup)")

                if "Permission denied" in error_str:
                    log_error("\nPermission denied - try running with sudo")

                raise RuntimeError(f"Failed to clone repository after {MAX_CLONE_RETRIES} attempts")

        except subprocess.TimeoutExpired:
            log_error(f"Clone attempt {attempt} timed out after 10 minutes")

            if attempt < MAX_CLONE_RETRIES:
                log_info(f"Retrying in {CLONE_RETRY_DELAY_SECONDS} seconds...")
                time.sleep(CLONE_RETRY_DELAY_SECONDS)
            else:
                log_error("Clone timed out. Check network connection.")
                raise RuntimeError("Clone operation timed out")


def build_libvirt_node(context: InstallerContext):
    """
    Build libvirt-node native addon.

    Commands:
        cd backend/lib/libvirt-node
        npm install
        npm run build
        npm pack

    Verifies:
        - *.node file exists (compiled Rust addon)
        - infinibay-libvirt-node-0.0.1.tgz exists

    Args:
        context: Installation configuration context

    Raises:
        RuntimeError: If build fails
    """
    log_info("Building libvirt-node native addon...")

    # Dry-run mode
    if context.dry_run:
        log_info(f"[DRY RUN] Would run in {context.libvirt_node_dir}:")
        log_info("[DRY RUN]   npm install")
        log_info("[DRY RUN]   npm run build")
        log_info("[DRY RUN]   npm pack")
        return

    # Check if directory exists
    if not os.path.exists(context.libvirt_node_dir):
        raise RuntimeError(f"libvirt-node directory not found: {context.libvirt_node_dir}")

    # Ensure Rust toolchain is available in PATH
    # This is critical because libvirt-node uses napi-rs which requires cargo
    sudo_user = os.environ.get('SUDO_USER')
    cargo_bin = f"/home/{sudo_user}/.cargo/bin" if sudo_user and sudo_user != 'root' else "/root/.cargo/bin"
    rustup_home = f"/home/{sudo_user}/.rustup" if sudo_user and sudo_user != 'root' else "/root/.rustup"
    cargo_home = f"/home/{sudo_user}/.cargo" if sudo_user and sudo_user != 'root' else "/root/.cargo"

    # Prepare environment with Rust toolchain in PATH
    # We need to create a fresh environment with the user's Rust installation
    build_env = os.environ.copy()

    # Add cargo bin to PATH
    current_path = build_env.get('PATH', '')
    if cargo_bin not in current_path:
        log_debug(f"Adding {cargo_bin} to PATH for libvirt-node build")
        build_env['PATH'] = f"{cargo_bin}:{current_path}"

    # Set Rust environment variables
    build_env['CARGO_HOME'] = cargo_home
    build_env['RUSTUP_HOME'] = rustup_home

    # Verify cargo is available in the build environment
    # We check by trying to run cargo --version with the new environment
    try:
        result = run_command(
            "cargo --version",
            env=build_env,
            timeout=10,
            check=False
        )
        if not result.success:
            raise RuntimeError(
                f"cargo not accessible with PATH={cargo_bin}\n"
                f"CARGO_HOME={cargo_home}\n"
                f"RUSTUP_HOME={rustup_home}\n"
                "Rust toolchain must be installed before building libvirt-node.\n"
                "Please ensure rustup was installed successfully in Phase 2."
            )
        log_debug(f"Verified cargo available: {result.stdout.strip()}")
    except Exception as e:
        raise RuntimeError(
            f"Failed to verify cargo availability: {e}\n"
            "libvirt-node uses napi-rs which requires cargo for compilation.\n"
            "Please ensure rustup was installed successfully in Phase 2."
        )

    try:
        # Step 1: npm install
        log_info("Step 1/3: Installing libvirt-node dependencies...")
        try:
            run_command("npm install", cwd=context.libvirt_node_dir, timeout=600, env=build_env)
        except subprocess.CalledProcessError as e:
            log_error("npm install failed for libvirt-node")
            log_error("Possible issues:")
            log_error("  - Node.js version must be >= 16")
            log_error("  - Check npm cache: npm cache clean --force")
            log_error("  - Check network connection")
            if e.stderr:
                log_error(f"Error output: {e.stderr}")
            raise RuntimeError("Failed to install libvirt-node dependencies")

        # Step 2: npm run build (runs napi build --release)
        log_info("Step 2/3: Building Rust native addon...")
        log_debug(f"Using cargo from: {cargo_bin}")
        try:
            run_command("npm run build", cwd=context.libvirt_node_dir, timeout=900, env=build_env)
        except subprocess.CalledProcessError as e:
            log_error("Rust build failed for libvirt-node")
            log_error("Possible issues:")
            log_error("  - Check if rust/cargo are installed: rustc --version")
            log_error("  - Check if libvirt-dev is installed: pkg-config --exists libvirt")
            log_error("  - Check build dependencies are installed")
            log_error(f"  - Cargo binary path: {cargo_bin}")
            if e.stderr:
                log_error(f"Error output: {e.stderr}")
            raise RuntimeError("Failed to build libvirt-node native addon")

        # Verify .node file exists
        node_files = glob.glob(os.path.join(context.libvirt_node_dir, "*.node"))
        if not node_files:
            raise RuntimeError("No .node file found after build")
        log_debug(f"Found compiled addon: {node_files[0]}")

        # Step 3: npm pack (creates .tgz package)
        log_info("Step 3/3: Packaging libvirt-node...")
        try:
            run_command("npm pack", cwd=context.libvirt_node_dir, timeout=300)
        except subprocess.CalledProcessError as e:
            log_error("npm pack failed for libvirt-node")
            if e.stderr:
                log_error(f"Error output: {e.stderr}")
            raise RuntimeError("Failed to package libvirt-node")

        # Verify .tgz file exists
        tgz_path = os.path.join(context.libvirt_node_dir, "infinibay-libvirt-node-0.0.1.tgz")
        verify_file_exists(tgz_path, "libvirt-node package")

        log_success("libvirt-node built and packaged successfully")
        log_debug(f"Created package: {tgz_path}")

    except subprocess.TimeoutExpired as e:
        log_error(f"Build timed out: {e}")
        raise RuntimeError("libvirt-node build timed out")
    except Exception as e:
        log_error(f"Unexpected error during libvirt-node build: {e}")
        raise


def get_directory_owner(directory: str) -> tuple:
    """
    Get the owner (uid, gid) of a directory.

    Args:
        directory: Path to directory

    Returns:
        Tuple of (uid, gid) or None if not determinable, or None if owner is root
    """
    try:
        stat_info = os.stat(directory)
        uid, gid = stat_info.st_uid, stat_info.st_gid

        # Don't bother restoring if already owned by root
        if uid == 0:
            return None

        return (uid, gid)
    except Exception:
        return None


def restore_ownership(directory: str, owner_info: tuple):
    """
    Restore ownership of directory and contents.

    Args:
        directory: Path to directory
        owner_info: Tuple of (uid, gid) from get_directory_owner
    """
    if not owner_info:
        return

    uid, gid = owner_info

    try:
        # Restore ownership recursively
        for root, dirs, files in os.walk(directory):
            os.chown(root, uid, gid)
            for d in dirs:
                try:
                    os.chown(os.path.join(root, d), uid, gid)
                except Exception:
                    pass
            for f in files:
                try:
                    os.chown(os.path.join(root, f), uid, gid)
                except Exception:
                    pass
        log_debug(f"Restored ownership of {directory} to {uid}:{gid}")
    except Exception as e:
        log_warning(f"Could not restore ownership of {directory}: {e}")


def build_backend(context: InstallerContext):
    """
    Build backend dependencies.

    Commands:
        cd backend
        npm cache clean --force  # Important: clears cached .tgz integrity hashes
        rm package-lock.json     # Regenerate with current libvirt-node .tgz hash
        npm install
        npx prisma generate

    Note on libvirt-node integrity errors:
        When libvirt-node is rebuilt, the .tgz file changes but package-lock.json
        keeps the old integrity hash. This causes EINTEGRITY errors.
        Solution: Clean cache and regenerate package-lock.json on each install.

    Note on ownership:
        When using existing code directory, preserves original file ownership.
        Files created by npm/prisma will be set back to original owner.

    Verifies:
        - node_modules exists
        - Prisma client generated

    Args:
        context: Installation configuration context

    Raises:
        RuntimeError: If build fails
    """
    log_info("Building backend dependencies...")

    # Dry-run mode
    if context.dry_run:
        log_info(f"[DRY RUN] Would run in {context.backend_dir}:")
        log_info("[DRY RUN]   npm install")
        log_info("[DRY RUN]   npx prisma generate")
        return

    # Check if directory exists
    if not os.path.exists(context.backend_dir):
        raise RuntimeError(f"Backend directory not found: {context.backend_dir}")

    # Remember original ownership
    original_owner = get_directory_owner(context.backend_dir)

    try:
        # Clean npm cache to avoid integrity checksum errors with local .tgz packages
        log_info("Cleaning npm cache to ensure fresh installation...")
        try:
            run_command("npm cache clean --force", cwd=context.backend_dir, timeout=60)
        except subprocess.CalledProcessError as e:
            log_warning("Failed to clean npm cache, continuing anyway...")

        # Remove package-lock.json to regenerate with correct integrity hashes
        package_lock_path = os.path.join(context.backend_dir, "package-lock.json")
        if os.path.exists(package_lock_path):
            log_info("Removing package-lock.json to regenerate with current .tgz hash...")
            os.remove(package_lock_path)

        # Step 1: npm install
        log_info("Step 1/2: Installing backend dependencies...")
        log_info("This will install @infinibay/libvirt-node from the .tgz package...")
        try:
            run_command("npm install", cwd=context.backend_dir, timeout=900)
        except subprocess.CalledProcessError as e:
            log_error("npm install failed for backend")

            # Check if libvirt-node package exists
            tgz_path = os.path.join(context.libvirt_node_dir, "infinibay-libvirt-node-0.0.1.tgz")
            if not os.path.exists(tgz_path):
                log_error(f"libvirt-node package not found: {tgz_path}")
                log_error("Make sure libvirt-node was built successfully first")

            log_error("Possible issues:")
            log_error("  - Check if libvirt-node was built successfully")
            log_error("  - Check Node.js version (>= 16)")
            log_error("  - Check npm cache: npm cache clean --force")
            log_error("  - Check network connection")
            if e.stderr:
                log_error(f"Error output: {e.stderr}")
            raise RuntimeError("Failed to install backend dependencies")

        # Verify node_modules exists
        node_modules_path = os.path.join(context.backend_dir, "node_modules")
        verify_directory_exists(node_modules_path, "Backend node_modules")

        # Step 2: Generate Prisma client
        log_info("Step 2/2: Generating Prisma client...")
        try:
            run_command("npx prisma generate", cwd=context.backend_dir, timeout=300)
        except subprocess.CalledProcessError as e:
            log_error("Prisma generate failed")
            log_error("Possible issues:")
            log_error("  - Check if prisma schema exists")
            log_error("  - Check if @prisma/client is installed")
            if e.stderr:
                log_error(f"Error output: {e.stderr}")
            raise RuntimeError("Failed to generate Prisma client")

        # Verify Prisma client generated
        prisma_client_path = os.path.join(context.backend_dir, "node_modules", ".prisma", "client")
        verify_directory_exists(prisma_client_path, "Prisma client")

        log_success("Backend dependencies installed and Prisma client generated")
        log_info("Note: Database migrations will be run in Phase 5 (after .env configuration)")

        # Restore original ownership if we're using an existing directory
        if original_owner:
            log_info("Restoring original file ownership...")
            restore_ownership(context.backend_dir, original_owner)

    except subprocess.TimeoutExpired as e:
        log_error(f"Build timed out: {e}")
        raise RuntimeError("Backend build timed out")
    except Exception as e:
        log_error(f"Unexpected error during backend build: {e}")
        raise


def build_frontend(context: InstallerContext):
    """
    Build frontend dependencies and production build.

    Commands:
        cd frontend
        npm install
        npm run build

    Verifies:
        - node_modules exists
        - .next/BUILD_ID exists (production build artifact)

    Args:
        context: Installation configuration context

    Raises:
        RuntimeError: If build fails
    """
    log_info("Building frontend dependencies and production build...")

    # Dry-run mode
    if context.dry_run:
        log_info(f"[DRY RUN] Would run in {context.frontend_dir}:")
        log_info("[DRY RUN]   npm install")
        log_info("[DRY RUN]   npm run build")
        return

    # Check if directory exists
    if not os.path.exists(context.frontend_dir):
        raise RuntimeError(f"Frontend directory not found: {context.frontend_dir}")

    # Remember original ownership
    original_owner = get_directory_owner(context.frontend_dir)

    try:
        # Step 1: npm install
        log_info("Step 1/2: Installing frontend dependencies...")
        try:
            run_command("npm install", cwd=context.frontend_dir, timeout=900)
        except subprocess.CalledProcessError as e:
            log_error("npm install failed for frontend")
            log_error("Possible issues:")
            log_error("  - Check Node.js version (>= 16)")
            log_error("  - Check npm cache: npm cache clean --force")
            log_error("  - Check network connection")
            if e.stderr:
                log_error(f"Error output: {e.stderr}")
            raise RuntimeError("Failed to install frontend dependencies")

        # Verify node_modules exists
        node_modules_path = os.path.join(context.frontend_dir, "node_modules")
        verify_directory_exists(node_modules_path, "Frontend node_modules")

        log_success("Frontend dependencies installed successfully")

        # Step 2: npm run build
        log_info("Step 2/2: Building Next.js production bundle...")
        try:
            run_command("npm run build", cwd=context.frontend_dir, timeout=900)
        except subprocess.CalledProcessError as e:
            log_error("npm run build failed for frontend")
            log_error("Possible issues:")
            log_error("  - Check for TypeScript errors")
            log_error("  - Check for missing environment variables")
            log_error("  - Verify GraphQL codegen has been run")
            if e.stderr:
                log_error(f"Error output: {e.stderr}")
            raise RuntimeError("Failed to build frontend production bundle")

        # Verify .next/BUILD_ID exists (required for next start)
        build_id_path = os.path.join(context.frontend_dir, ".next", "BUILD_ID")
        if not os.path.exists(build_id_path):
            raise RuntimeError(f"Frontend build incomplete: {build_id_path} not found")

        log_success("Frontend production build completed successfully")
        log_info("Frontend is ready to be started in production mode (next start)")

        # Restore original ownership if we're using an existing directory
        if original_owner:
            log_info("Restoring original file ownership...")
            restore_ownership(context.frontend_dir, original_owner)

    except subprocess.TimeoutExpired as e:
        log_error(f"Build timed out: {e}")
        raise RuntimeError("Frontend build timed out")
    except Exception as e:
        log_error(f"Unexpected error during frontend build: {e}")
        raise


def build_infiniservice(context: InstallerContext):
    """
    Build infiniservice Rust binary for Linux and Windows.

    Commands:
        cd infiniservice
        rustup target add x86_64-pc-windows-gnu  # Add Windows target
        cargo build --release                     # Linux binary
        cargo build --release --target x86_64-pc-windows-gnu  # Windows binary

    Verifies:
        - target/release/infiniservice exists (Linux)
        - target/x86_64-pc-windows-gnu/release/infiniservice.exe exists (Windows)

    Args:
        context: Installation configuration context

    Raises:
        RuntimeError: If build fails
    """
    log_info("Building infiniservice Rust binaries (Linux and Windows)...")

    # Dry-run mode
    if context.dry_run:
        log_info(f"[DRY RUN] Would run in {context.infiniservice_dir}:")
        log_info("[DRY RUN]   rustup target add x86_64-pc-windows-gnu")
        log_info("[DRY RUN]   cargo build --release")
        log_info("[DRY RUN]   cargo build --release --target x86_64-pc-windows-gnu")
        return

    # Check if directory exists
    if not os.path.exists(context.infiniservice_dir):
        raise RuntimeError(f"Infiniservice directory not found: {context.infiniservice_dir}")

    # Ensure Rust toolchain is available in PATH
    sudo_user = os.environ.get('SUDO_USER')
    cargo_bin = f"/home/{sudo_user}/.cargo/bin" if sudo_user and sudo_user != 'root' else "/root/.cargo/bin"
    rustup_home = f"/home/{sudo_user}/.rustup" if sudo_user and sudo_user != 'root' else "/root/.rustup"
    cargo_home = f"/home/{sudo_user}/.cargo" if sudo_user and sudo_user != 'root' else "/root/.cargo"

    # Prepare environment with Rust toolchain
    build_env = os.environ.copy()

    # Add cargo bin to PATH
    current_path = build_env.get('PATH', '')
    if cargo_bin not in current_path:
        log_debug(f"Adding {cargo_bin} to PATH for infiniservice build")
        build_env['PATH'] = f"{cargo_bin}:{current_path}"

    # Set Rust environment variables
    build_env['CARGO_HOME'] = cargo_home
    build_env['RUSTUP_HOME'] = rustup_home

    # Verify rustup and cargo are available in the build environment
    try:
        result = run_command("rustup --version", env=build_env, timeout=10, check=False)
        if not result.success:
            raise RuntimeError(
                f"rustup not accessible with PATH={cargo_bin}\n"
                f"CARGO_HOME={cargo_home}\n"
                f"RUSTUP_HOME={rustup_home}\n"
                "Please run the installer from the beginning or install Rust manually:\n"
                "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
            )
        log_debug(f"Verified rustup: {result.stdout.strip()}")

        result = run_command("cargo --version", env=build_env, timeout=10, check=False)
        if not result.success:
            raise RuntimeError("cargo not accessible in build environment")
        log_debug(f"Verified cargo: {result.stdout.strip()}")

    except Exception as e:
        raise RuntimeError(f"Failed to verify Rust toolchain: {e}")

    # Verify mingw-w64 is installed for Windows cross-compilation
    mingw_gcc = 'x86_64-w64-mingw32-gcc'
    from .utils import command_exists
    if not command_exists(mingw_gcc):
        log_warning(f"{mingw_gcc} not found - Windows build may fail")
        log_warning("Install mingw-w64 package for Windows cross-compilation")

    # Remember original ownership
    original_owner = get_directory_owner(context.infiniservice_dir)

    try:
        # Step 1: Add Windows cross-compilation target
        log_info("Step 1/3: Installing Windows cross-compilation target...")
        try:
            run_command(
                "rustup target add x86_64-pc-windows-gnu",
                cwd=context.infiniservice_dir,
                timeout=300,
                env=build_env
            )
            log_success("Windows target installed")
        except subprocess.CalledProcessError as e:
            log_warning("Failed to add Windows target (may already be installed)")
            log_debug(f"Error: {e}")

        # Step 2: Build Linux binary
        log_info("Step 2/3: Compiling Linux binary (this may take several minutes)...")
        try:
            run_command(
                "cargo build --release",
                cwd=context.infiniservice_dir,
                timeout=1800,
                env=build_env
            )
        except subprocess.CalledProcessError as e:
            log_error("Cargo build failed for infiniservice (Linux)")
            log_error("Possible issues:")
            log_error("  - Check if rust/cargo are installed: rustc --version")
            log_error("  - Check if all system dependencies are available")
            log_error("  - Check network connection (for crate downloads)")
            if e.stderr:
                log_error(f"Error output: {e.stderr}")
            raise RuntimeError("Failed to build infiniservice for Linux")

        # Verify Linux binary exists
        linux_binary_path = os.path.join(context.infiniservice_dir, "target", "release", "infiniservice")
        verify_file_exists(linux_binary_path, "Infiniservice Linux binary")

        # Make Linux binary executable
        if not os.access(linux_binary_path, os.X_OK):
            log_warning("Binary is not executable, making it executable...")
            try:
                run_command(f"chmod +x {linux_binary_path}", check=False)
            except Exception as e:
                log_warning(f"Failed to make binary executable: {e}")

        log_success("Linux binary compiled successfully")
        log_debug(f"Linux binary location: {linux_binary_path}")

        # Step 3: Build Windows binary
        log_info("Step 3/3: Compiling Windows binary (this may take several minutes)...")
        try:
            # Set RUSTFLAGS for static linking and smaller binary
            # Start with build_env (has Rust paths) and add RUSTFLAGS
            windows_env = build_env.copy()
            windows_env['RUSTFLAGS'] = '-C target-feature=+crt-static -C link-arg=-s'

            run_command(
                "cargo build --release --target x86_64-pc-windows-gnu",
                cwd=context.infiniservice_dir,
                timeout=1800,
                env=windows_env
            )
        except subprocess.CalledProcessError as e:
            log_error("Cargo build failed for infiniservice (Windows)")
            log_error("Possible issues:")
            log_error("  - Check if mingw-w64 is installed: x86_64-w64-mingw32-gcc --version")
            log_error("  - Check if Windows target is installed: rustup target list --installed")
            log_error("  - Check network connection (for crate downloads)")
            if e.stderr:
                log_error(f"Error output: {e.stderr}")
            raise RuntimeError("Failed to build infiniservice for Windows")

        # Verify Windows binary exists
        windows_binary_path = os.path.join(
            context.infiniservice_dir,
            "target",
            "x86_64-pc-windows-gnu",
            "release",
            "infiniservice.exe"
        )
        verify_file_exists(windows_binary_path, "Infiniservice Windows binary")

        # Strip Windows binary to reduce false positives in antivirus
        log_info("Stripping Windows binary to reduce antivirus false positives...")
        try:
            run_command(
                f"x86_64-w64-mingw32-strip {windows_binary_path}",
                timeout=60,
                check=False
            )
            log_success("Windows binary stripped successfully")
        except Exception as e:
            log_warning(f"Failed to strip Windows binary: {e}")
            log_warning("Binary may trigger antivirus false positives")

        log_success("Windows binary compiled successfully")
        log_debug(f"Windows binary location: {windows_binary_path}")

        # Restore original ownership if we're using an existing directory
        if original_owner:
            log_info("Restoring original file ownership...")
            restore_ownership(context.infiniservice_dir, original_owner)

        log_success("All infiniservice binaries compiled successfully")

    except subprocess.TimeoutExpired as e:
        log_error(f"Build timed out after 30 minutes: {e}")
        raise RuntimeError("Infiniservice build timed out")
    except Exception as e:
        log_error(f"Unexpected error during infiniservice build: {e}")
        raise


def deploy_infiniservice(context: InstallerContext):
    """
    Deploy infiniservice binaries and install scripts to backend access location.

    Deployment structure:
        {data_dir}/infiniservice/
        ├── binaries/
        │   ├── linux/
        │   │   ├── infiniservice
        │   │   └── install-linux.sh
        │   └── windows/
        │       ├── infiniservice.exe
        │       └── install-windows.ps1
        └── install/
            ├── install-linux.sh
            └── install-windows.ps1

    Args:
        context: Installation configuration context

    Raises:
        RuntimeError: If deployment fails
    """
    log_info("Deploying infiniservice binaries and install scripts...")

    # Dry-run mode
    if context.dry_run:
        log_info(f"[DRY RUN] Would deploy to {context.data_dir}/infiniservice/")
        log_info("[DRY RUN]   - Linux binary: binaries/linux/infiniservice")
        log_info("[DRY RUN]   - Windows binary: binaries/windows/infiniservice.exe")
        log_info("[DRY RUN]   - Install scripts: install/*.sh, install/*.ps1")
        return

    # Define deployment paths
    deploy_base = os.path.join(context.data_dir, "infiniservice")
    binaries_dir = os.path.join(deploy_base, "binaries")
    linux_binaries_dir = os.path.join(binaries_dir, "linux")
    windows_binaries_dir = os.path.join(binaries_dir, "windows")
    install_scripts_dir = os.path.join(deploy_base, "install")

    try:
        # Create deployment directories
        log_debug("Creating deployment directories...")
        os.makedirs(linux_binaries_dir, exist_ok=True)
        os.makedirs(windows_binaries_dir, exist_ok=True)
        os.makedirs(install_scripts_dir, exist_ok=True)

        # Source paths
        linux_binary_src = os.path.join(context.infiniservice_dir, "target", "release", "infiniservice")
        windows_binary_src = os.path.join(
            context.infiniservice_dir,
            "target",
            "x86_64-pc-windows-gnu",
            "release",
            "infiniservice.exe"
        )
        install_dir_src = os.path.join(context.infiniservice_dir, "install")

        # Deploy Linux binary
        log_info("Deploying Linux binary...")
        if not os.path.exists(linux_binary_src):
            raise RuntimeError(f"Linux binary not found at {linux_binary_src}. Build may have failed.")

        linux_binary_dest = os.path.join(linux_binaries_dir, "infiniservice")
        shutil.copy2(linux_binary_src, linux_binary_dest)
        os.chmod(linux_binary_dest, 0o755)
        log_success(f"Linux binary deployed: {linux_binary_dest}")

        # Deploy Windows binary
        log_info("Deploying Windows binary...")
        if not os.path.exists(windows_binary_src):
            log_warning(f"Windows binary not found at {windows_binary_src}")
            log_warning("Windows binary deployment skipped")
        else:
            windows_binary_dest = os.path.join(windows_binaries_dir, "infiniservice.exe")
            shutil.copy2(windows_binary_src, windows_binary_dest)
            # Windows executables don't need chmod
            log_success(f"Windows binary deployed: {windows_binary_dest}")

        # Deploy install scripts
        log_info("Deploying install scripts...")

        # Linux install script (to both locations)
        linux_install_src = os.path.join(install_dir_src, "install-linux.sh")
        if os.path.exists(linux_install_src):
            # Copy to binaries/linux/ directory
            linux_install_dest_binaries = os.path.join(linux_binaries_dir, "install-linux.sh")
            shutil.copy2(linux_install_src, linux_install_dest_binaries)
            os.chmod(linux_install_dest_binaries, 0o755)

            # Copy to install/ directory
            linux_install_dest_main = os.path.join(install_scripts_dir, "install-linux.sh")
            shutil.copy2(linux_install_src, linux_install_dest_main)
            os.chmod(linux_install_dest_main, 0o755)

            log_success("Linux install script deployed")
        else:
            log_warning(f"Linux install script not found: {linux_install_src}")

        # Windows install script (to both locations)
        windows_install_src = os.path.join(install_dir_src, "install-windows.ps1")
        if os.path.exists(windows_install_src):
            # Copy to binaries/windows/ directory
            windows_install_dest_binaries = os.path.join(windows_binaries_dir, "install-windows.ps1")
            shutil.copy2(windows_install_src, windows_install_dest_binaries)

            # Copy to install/ directory
            windows_install_dest_main = os.path.join(install_scripts_dir, "install-windows.ps1")
            shutil.copy2(windows_install_src, windows_install_dest_main)

            log_success("Windows install script deployed")
        else:
            log_warning(f"Windows install script not found: {windows_install_src}")

        # Set proper permissions on deployment directories
        os.chmod(deploy_base, 0o755)
        os.chmod(binaries_dir, 0o755)
        os.chmod(linux_binaries_dir, 0o755)
        os.chmod(windows_binaries_dir, 0o755)
        os.chmod(install_scripts_dir, 0o755)

        log_success("Infiniservice deployment completed")
        log_info(f"Deployment location: {deploy_base}")
        log_info("Backend can now serve binaries to VMs via /infiniservice routes")

    except PermissionError as e:
        log_error(f"Permission denied during deployment: {e}")
        log_error("Please ensure the installer is run with proper permissions")
        raise RuntimeError("Infiniservice deployment failed due to permissions")
    except Exception as e:
        log_error(f"Unexpected error during infiniservice deployment: {e}")
        raise RuntimeError(f"Infiniservice deployment failed: {e}")


def clone_and_build(context: InstallerContext):
    """
    Phase 4: Clone repositories and build dependencies.

    This phase will:
    1. Clone repos from GitHub to /opt/infinibay/:
       - backend (https://github.com/infinibay/backend.git)
       - frontend (https://github.com/infinibay/frontend.git)
       - infiniservice (https://github.com/infinibay/infiniservice.git)
       - libvirt-node is inside backend/lib/libvirt-node

    2. Build in correct order:
       a. libvirt-node: cd backend/lib/libvirt-node && npm install && npm run build && npm pack
       b. Backend: cd backend && npm install && npx prisma generate
       c. Frontend: cd frontend && npm install
       d. Infiniservice: cd infiniservice && cargo build --release

    3. Handle build errors with clear messages
    4. Verify builds succeeded (check for output files)

    Args:
        context: Installation configuration context

    Raises:
        RuntimeError: If any step fails
    """
    log_step(4, 5, "Cloning repositories and building dependencies")
    log_info(f"Installation directory: {context.install_dir}")
    log_info("This phase will take 15-30 minutes depending on your system...")

    # =================================================================
    # Phase 4a: Clone Repositories
    # =================================================================
    try:
        log_section("Phase 4a: Cloning Repositories")

        # Clone all repositories as top-level directories
        # Note: libvirt-node is now a top-level repo, not nested in backend

        clone_repository(REPO_URLS['backend'], context.backend_dir, context)
        clone_repository(REPO_URLS['frontend'], context.frontend_dir, context)
        clone_repository(REPO_URLS['infiniservice'], context.infiniservice_dir, context)
        clone_repository(REPO_URLS['libvirt-node'], context.libvirt_node_dir, context)

        log_success("All repositories cloned successfully")

    except RuntimeError as e:
        log_error(f"Repository cloning failed: {e}")
        raise
    except Exception as e:
        log_error(f"Unexpected error during repository cloning: {e}")
        raise

    # =================================================================
    # Phase 4b: Build libvirt-node (CRITICAL - must be first)
    # =================================================================
    try:
        log_section("Phase 4b: Building libvirt-node (Native Addon)")
        log_warning("This is a critical step - backend depends on this package")

        build_libvirt_node(context)

        # Setup libvirt-node as git submodule in backend/lib/libvirt-node
        # This allows backend's package.json to reference it at the expected path
        backend_lib_dir = os.path.join(context.backend_dir, "lib")
        backend_libvirt_submodule = os.path.join(backend_lib_dir, "libvirt-node")

        if not context.dry_run:
            # Ensure backend/lib directory exists
            os.makedirs(backend_lib_dir, exist_ok=True)

            # Remove existing symlink or directory if present (but not if it's already a proper submodule)
            if os.path.exists(backend_libvirt_submodule) or os.path.islink(backend_libvirt_submodule):
                # Check if it's a git submodule
                is_submodule = os.path.exists(os.path.join(backend_libvirt_submodule, ".git"))

                if os.path.islink(backend_libvirt_submodule):
                    log_warning(f"Removing existing symlink: {backend_libvirt_submodule}")
                    os.unlink(backend_libvirt_submodule)
                elif is_submodule:
                    log_info("libvirt-node submodule already exists, skipping")
                elif os.path.isdir(backend_libvirt_submodule):
                    log_warning(f"Found non-submodule directory at {backend_libvirt_submodule}, removing")
                    shutil.rmtree(backend_libvirt_submodule)

            # Add as git submodule if not already present
            if not os.path.exists(backend_libvirt_submodule):
                log_info(f"Adding libvirt-node as git submodule in backend/lib/")

                # Get the relative path from libvirt-node to backend for submodule
                # We'll use the top-level libvirt-node directory as the source
                try:
                    run_command(
                        f"git submodule add ../../libvirt-node lib/libvirt-node",
                        cwd=context.backend_dir,
                        timeout=30
                    )
                    log_success("Git submodule added successfully")
                except subprocess.CalledProcessError:
                    # Submodule might already be registered in .gitmodules
                    log_info("Submodule already registered, initializing...")
                    run_command(
                        "git submodule update --init lib/libvirt-node",
                        cwd=context.backend_dir,
                        timeout=30
                    )
                    log_success("Git submodule initialized successfully")
        else:
            log_info(f"[DRY RUN] Would add git submodule: lib/libvirt-node → ../../libvirt-node")

    except RuntimeError as e:
        log_error(f"libvirt-node build failed: {e}")
        log_error("\nCannot proceed with backend installation.")
        log_error("\nTroubleshooting:")
        log_error("  1. Verify rust and cargo are installed:")
        log_error("     $ rustc --version")
        log_error("  2. Verify libvirt-dev is installed:")
        log_error("     $ pkg-config --exists libvirt && echo 'OK' || echo 'MISSING'")
        log_error(f"  3. Check build logs in: {context.libvirt_node_dir}")
        raise
    except Exception as e:
        log_error(f"Unexpected error during libvirt-node build: {e}")
        raise

    # =================================================================
    # Phase 4c: Build Backend
    # =================================================================
    try:
        log_section("Phase 4c: Building Backend")

        build_backend(context)

    except RuntimeError as e:
        log_error(f"Backend build failed: {e}")
        raise
    except Exception as e:
        log_error(f"Unexpected error during backend build: {e}")
        raise

    # =================================================================
    # Phase 4d: Build Frontend
    # =================================================================
    try:
        log_section("Phase 4d: Building Frontend")

        build_frontend(context)

    except RuntimeError as e:
        log_error(f"Frontend build failed: {e}")
        raise
    except Exception as e:
        log_error(f"Unexpected error during frontend build: {e}")
        raise

    # =================================================================
    # Phase 4e: Build Infiniservice
    # =================================================================
    try:
        log_section("Phase 4e: Building Infiniservice")

        build_infiniservice(context)

    except RuntimeError as e:
        log_error(f"Infiniservice build failed: {e}")
        raise
    except Exception as e:
        log_error(f"Unexpected error during infiniservice build: {e}")
        raise

    # =================================================================
    # Phase 4e-1: Deploy Infiniservice
    # =================================================================
    try:
        log_section("Phase 4e-1: Deploying Infiniservice")

        deploy_infiniservice(context)

    except RuntimeError as e:
        log_error(f"Infiniservice deployment failed: {e}")
        raise
    except Exception as e:
        log_error(f"Unexpected error during infiniservice deployment: {e}")
        raise

    # =================================================================
    # Phase 4f: Setup VirtIO Windows Drivers
    # =================================================================
    try:
        log_section("Phase 4f: Setting up VirtIO Windows Drivers")

        success, iso_path = setup_virtio_drivers(context)

        if success and iso_path:
            log_success(f"VirtIO drivers ready at: {iso_path}")
        elif not success:
            log_warning("VirtIO drivers setup skipped or failed")
            log_warning("Windows VM creation will not work until VirtIO ISO is available")
            log_info("You can download it later from:")
            log_info("  https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/")

    except Exception as e:
        log_warning(f"VirtIO setup encountered an error: {e}")
        log_warning("This is not critical - installation will continue")
        log_info("You can download VirtIO drivers manually later if needed")

    # =================================================================
    # Final Verification
    # =================================================================
    log_section("Verifying All Builds")

    try:
        # Verify libvirt-node
        node_files = glob.glob(os.path.join(context.libvirt_node_dir, "*.node"))
        if node_files:
            log_success(f"libvirt-node: ✓ {os.path.basename(node_files[0])}")
        tgz_path = os.path.join(context.libvirt_node_dir, "infinibay-libvirt-node-0.0.1.tgz")
        if os.path.exists(tgz_path):
            log_success("libvirt-node: ✓ infinibay-libvirt-node-0.0.1.tgz")

        # Verify libvirt-node submodule in backend/lib/
        backend_libvirt_submodule = os.path.join(context.backend_dir, "lib", "libvirt-node")
        if os.path.exists(backend_libvirt_submodule):
            if os.path.exists(os.path.join(backend_libvirt_submodule, ".git")):
                log_success(f"Backend: ✓ lib/libvirt-node (git submodule)")
            else:
                log_success(f"Backend: ✓ lib/libvirt-node (directory)")

        # Verify backend
        backend_node_modules = os.path.join(context.backend_dir, "node_modules")
        if os.path.exists(backend_node_modules):
            log_success("Backend: ✓ node_modules")
        backend_prisma = os.path.join(context.backend_dir, "node_modules", ".prisma", "client")
        if os.path.exists(backend_prisma):
            log_success("Backend: ✓ Prisma client")

        # Verify frontend
        frontend_node_modules = os.path.join(context.frontend_dir, "node_modules")
        if os.path.exists(frontend_node_modules):
            log_success("Frontend: ✓ node_modules")

        # Verify infiniservice build
        infiniservice_linux_binary = os.path.join(context.infiniservice_dir, "target", "release", "infiniservice")
        if os.path.exists(infiniservice_linux_binary):
            log_success("Infiniservice: ✓ target/release/infiniservice (Linux)")

        infiniservice_windows_binary = os.path.join(
            context.infiniservice_dir,
            "target",
            "x86_64-pc-windows-gnu",
            "release",
            "infiniservice.exe"
        )
        if os.path.exists(infiniservice_windows_binary):
            log_success("Infiniservice: ✓ target/x86_64-pc-windows-gnu/release/infiniservice.exe (Windows)")

        # Verify infiniservice deployment
        deployed_linux_binary = os.path.join(context.data_dir, "infiniservice", "binaries", "linux", "infiniservice")
        if os.path.exists(deployed_linux_binary):
            log_success("Infiniservice: ✓ binaries/linux/infiniservice (deployed)")

        deployed_windows_binary = os.path.join(context.data_dir, "infiniservice", "binaries", "windows", "infiniservice.exe")
        if os.path.exists(deployed_windows_binary):
            log_success("Infiniservice: ✓ binaries/windows/infiniservice.exe (deployed)")

        deployed_install_script = os.path.join(context.data_dir, "infiniservice", "install", "install-linux.sh")
        if os.path.exists(deployed_install_script):
            log_success("Infiniservice: ✓ install/install-linux.sh (deployed)")

    except Exception as e:
        log_warning(f"Verification check failed (builds may still be OK): {e}")

    # =================================================================
    # Success Summary
    # =================================================================
    print()  # Empty line before summary
    print(f"{GREEN}{'='*60}{RESET}")
    log_success("All repositories cloned and built successfully!")
    print(f"{GREEN}{'='*60}{RESET}")
    print()  # Empty line after summary

    log_info("Build summary:")
    log_info(f"  ✓ Backend: {context.backend_dir}")
    log_info(f"  ✓ Frontend: {context.frontend_dir}")
    log_info(f"  ✓ Infiniservice: {context.infiniservice_dir}")
    log_info(f"  ✓ libvirt-node: {context.libvirt_node_dir}")

    log_info("\nNext: Phase 5 will configure .env files and create systemd services")
