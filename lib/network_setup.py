"""
Network setup module for Infinibay installer.
Handles automatic libvirt virtual network detection and creation.
"""

import os
from typing import Optional, List, Dict
from .utils import run_command
from .logger import log_info, log_error, log_warning, log_debug, log_success
from .config import InstallerContext


def detect_libvirt_networks() -> List[Dict[str, str]]:
    """
    Detect all libvirt virtual networks using virsh.

    Returns:
        List of dictionaries with 'name' and 'active' status
    """
    log_debug("Detecting libvirt networks...")

    result = run_command('virsh net-list --all', check=False, capture_output=True)
    if not result or result.returncode != 0:
        log_debug("Failed to list libvirt networks")
        return []

    networks = []
    lines = result.stdout.strip().split('\n')

    # Skip header lines
    for line in lines[2:]:
        if not line.strip():
            continue

        # Parse network list output: Name State Autostart Persistent
        parts = line.split()
        if len(parts) >= 3:
            name = parts[0]
            state = parts[1]
            active = state == 'active'
            networks.append({'name': name, 'active': active})
            log_debug(f"Found network: {name} (active={active})")

    return networks


def get_default_network(networks: List[Dict[str, str]]) -> Optional[str]:
    """
    Get the default network from detected networks.

    Prefers:
    1. Network named 'default'
    2. Any active network
    3. Any inactive network

    Args:
        networks: List of network dictionaries

    Returns:
        Network name or None if no networks exist
    """
    if not networks:
        return None

    # Prefer network named 'default'
    for net in networks:
        if net['name'] == 'default':
            log_debug(f"Using 'default' network")
            return net['name']

    # Prefer any active network
    for net in networks:
        if net['active']:
            log_debug(f"Using active network: {net['name']}")
            return net['name']

    # Use first available network
    log_debug(f"Using first available network: {networks[0]['name']}")
    return networks[0]['name']


def create_default_libvirt_network(context: InstallerContext) -> bool:
    """
    Create a default NAT libvirt network named 'infinibay'.

    Args:
        context: Installer context

    Returns:
        True on success, False on failure
    """
    log_info("Creating default libvirt network 'infinibay'...")

    if context.dry_run:
        log_info("[DRY RUN] Would create libvirt network with:")
        log_info("  Name: infinibay")
        log_info("  Mode: NAT")
        log_info("  Bridge: virbr-infinibay (auto-generated)")
        log_info("  IP: 192.168.122.1/24")
        log_info("  DHCP: 192.168.122.2 - 192.168.122.254")
        return True

    # Define network XML
    network_xml = """<network>
  <name>infinibay</name>
  <forward mode='nat'/>
  <bridge name='virbr-infinibay' stp='on' delay='0'/>
  <ip address='192.168.122.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.122.2' end='192.168.122.254'/>
    </dhcp>
  </ip>
</network>"""

    # Write XML to temporary file
    xml_path = '/tmp/infinibay-network.xml'
    try:
        with open(xml_path, 'w') as f:
            f.write(network_xml)

        # Define the network
        log_debug("Defining network from XML...")
        result = run_command(f'virsh net-define {xml_path}', check=False, capture_output=True)
        if not result or result.returncode != 0:
            log_error("Failed to define network")
            if result and result.stderr:
                log_error(f"Error: {result.stderr}")
            return False

        # Start the network
        log_debug("Starting network...")
        result = run_command('virsh net-start infinibay', check=False, capture_output=True)
        if not result or result.returncode != 0:
            log_error("Failed to start network")
            if result and result.stderr:
                log_error(f"Error: {result.stderr}")
            return False

        # Set autostart
        log_debug("Setting network to autostart...")
        result = run_command('virsh net-autostart infinibay', check=False, capture_output=True)
        if not result or result.returncode != 0:
            log_warning("Failed to set network autostart (non-critical)")

        # Cleanup temp file
        try:
            os.remove(xml_path)
        except:
            pass

        log_success("Network 'infinibay' created successfully")
        return True

    except Exception as e:
        log_error(f"Failed to create network: {e}")
        return False


def prompt_create_network(context: InstallerContext) -> Optional[str]:
    """
    Prompt user to create a libvirt network if none exist.

    Args:
        context: Installer context

    Returns:
        Network name if created, None otherwise
    """
    log_warning("No libvirt virtual networks found")
    log_info("")
    log_info("Infinibay requires a libvirt virtual network for VM connectivity.")
    log_info("Would you like to create a default NAT network now?")
    log_info("")

    if context.dry_run:
        log_info("[DRY RUN] Would prompt user to create network")
        return None

    try:
        response = input("Create default network? [Y/n]: ").strip().lower()
        if response in ['', 'y', 'yes']:
            if create_default_libvirt_network(context):
                return 'infinibay'
            else:
                log_error("Network creation failed")
                return None
        else:
            log_info("")
            log_info("Network creation skipped. You can create one manually using:")
            log_info("")
            log_info("  sudo virsh net-define /path/to/network.xml")
            log_info("  sudo virsh net-start <network-name>")
            log_info("  sudo virsh net-autostart <network-name>")
            log_info("")
            log_info("Or use an existing physical bridge. See documentation for details.")
            log_info("")
            return None
    except Exception as e:
        log_error(f"Error during prompt: {e}")
        return None


def setup_libvirt_network(context: InstallerContext) -> bool:
    """
    Main orchestration function for libvirt network setup.

    Detects existing libvirt networks or prompts to create one.

    Args:
        context: Installer context

    Returns:
        True on success, False on failure
    """
    try:
        log_info(f"Setting up libvirt network configuration...")

        # Detect existing networks
        networks = detect_libvirt_networks()

        if networks:
            # Select default network
            selected_network = get_default_network(networks)
            if selected_network:
                # Update context with selected network
                context.network_name = selected_network
                log_info(f"Using libvirt network: {selected_network}")

                # Verify network is active
                result = run_command(f'virsh net-info {selected_network}', check=False, capture_output=True)
                if result and result.returncode == 0:
                    if 'Active:' in result.stdout:
                        if 'yes' in result.stdout.lower():
                            log_success(f"Network '{selected_network}' is active and ready")
                        else:
                            log_warning(f"Network '{selected_network}' exists but is not active")
                            log_info("You may need to start it manually with:")
                            log_info(f"  sudo virsh net-start {selected_network}")
                    return True
                else:
                    log_warning(f"Could not verify network status")
                    return True
        else:
            # No networks found - prompt to create one
            if not context.dry_run:
                created_network = prompt_create_network(context)
                if created_network:
                    context.network_name = created_network
                    return True
                else:
                    log_error("No libvirt network configured")
                    log_error("VMs will not be able to start without a network")
                    return False
            else:
                log_info("[DRY RUN] Would prompt to create network")
                return True

        return True

    except Exception as e:
        log_error(f"Exception during libvirt network setup: {e}")
        return False
