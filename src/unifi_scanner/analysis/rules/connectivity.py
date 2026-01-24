"""Connectivity category rules for UniFi event analysis.

Rules for device connectivity, network outages, and client connection events.
"""

from typing import List

from unifi_scanner.analysis.rules.base import Rule
from unifi_scanner.models.enums import Category, Severity


CONNECTIVITY_RULES: List[Rule] = [
    # SEVERE: Access point lost contact
    Rule(
        name="ap_lost_contact",
        event_types=["EVT_AP_Lost_Contact", "EVT_AP_DISCONNECTED"],
        category=Category.CONNECTIVITY,
        severity=Severity.SEVERE,
        title_template="[Connectivity] Access point {device_name} went offline",
        description_template=(
            "Access point {device_name} ({device_mac}) has lost contact with the controller "
            "(EVT_AP_Lost_Contact). This means the AP is no longer responding and clients "
            "connected to it will lose their wireless connection."
        ),
        remediation_template=(
            "1. Check if the access point has power - verify the PoE port or power adapter\n"
            "2. Check physical network connectivity - ensure the ethernet cable is connected\n"
            "3. Try power cycling the access point\n"
            "4. Check for upstream switch or network issues\n"
            "5. If persistent, the AP may have hardware failure - check for blinking LED patterns"
        ),
    ),
    # SEVERE: Switch lost contact
    Rule(
        name="switch_lost_contact",
        event_types=["EVT_SW_Lost_Contact", "EVT_SW_DISCONNECTED"],
        category=Category.CONNECTIVITY,
        severity=Severity.SEVERE,
        title_template="[Connectivity] Switch {device_name} went offline",
        description_template=(
            "Switch {device_name} ({device_mac}) has lost contact with the controller "
            "(EVT_SW_Lost_Contact). This affects all devices connected through this switch "
            "and may cause significant network outages."
        ),
        remediation_template=(
            "1. Check if the switch has power - verify power cable and outlet\n"
            "2. Check the uplink connection to the rest of your network\n"
            "3. Try power cycling the switch\n"
            "4. Check for overheating - ensure adequate ventilation\n"
            "5. If persistent, the switch may need replacement"
        ),
    ),
    # SEVERE: Gateway WAN down
    Rule(
        name="gateway_wan_down",
        event_types=["EVT_GW_WAN_DISCONNECTED", "EVT_GW_WAN_DOWN", "EVT_WAN_FAILOVER"],
        category=Category.CONNECTIVITY,
        severity=Severity.SEVERE,
        title_template="[Connectivity] Internet connection lost on {device_name}",
        description_template=(
            "Your gateway {device_name} has lost its WAN (internet) connection "
            "(EVT_GW_WAN_DISCONNECTED). All internet-dependent services will be affected "
            "until connectivity is restored."
        ),
        remediation_template=(
            "1. Check your modem or ONT - power cycle it if needed\n"
            "2. Verify the WAN cable connection between gateway and modem\n"
            "3. Contact your ISP to check for outages in your area\n"
            "4. Check if your ISP account is in good standing\n"
            "5. If using a static IP, verify the settings haven't changed"
        ),
    ),
    # SEVERE: AP isolated (can reach controller but not other devices)
    Rule(
        name="ap_isolated",
        event_types=["EVT_AP_Isolated", "EVT_AP_ISOLATED"],
        category=Category.CONNECTIVITY,
        severity=Severity.SEVERE,
        title_template="[Connectivity] Access point {device_name} is isolated",
        description_template=(
            "Access point {device_name} can communicate with the controller but is isolated "
            "from the rest of the network (EVT_AP_Isolated). Clients may have limited or no "
            "connectivity even though the AP appears online."
        ),
        remediation_template=(
            "1. Check the network cable and port where the AP is connected\n"
            "2. Verify VLAN configuration is correct\n"
            "3. Check for spanning tree issues that might be blocking the port\n"
            "4. Ensure the uplink switch port isn't in a separate VLAN or blocking traffic\n"
            "5. Try moving the AP to a different switch port"
        ),
    ),
    # LOW: AP connected (informational)
    Rule(
        name="ap_connected",
        event_types=["EVT_AP_Connected", "EVT_AP_CONNECTED"],
        category=Category.CONNECTIVITY,
        severity=Severity.LOW,
        title_template="[Connectivity] Access point {device_name} came online",
        description_template=(
            "Access point {device_name} ({device_mac}) has connected to the controller "
            "(EVT_AP_Connected). This typically indicates the device finished booting "
            "or recovered from a previous disconnection."
        ),
        remediation_template=None,  # LOW severity - no remediation needed
    ),
    # LOW: Client connected (informational)
    Rule(
        name="client_connected",
        event_types=["EVT_WU_Connected", "EVT_WG_Connected", "EVT_LU_Connected"],
        category=Category.CONNECTIVITY,
        severity=Severity.LOW,
        title_template="[Connectivity] Client connected to {device_name}",
        description_template=(
            "A client device connected to your network via {device_name} "
            "(EVT_WU_Connected/EVT_WG_Connected/EVT_LU_Connected). This is normal "
            "network activity logged for awareness."
        ),
        remediation_template=None,  # LOW severity - no remediation needed
    ),
    # LOW: Client disconnected (informational)
    Rule(
        name="client_disconnected",
        event_types=["EVT_WU_Disconnected", "EVT_WG_Disconnected", "EVT_LU_Disconnected"],
        category=Category.CONNECTIVITY,
        severity=Severity.LOW,
        title_template="[Connectivity] Client disconnected from {device_name}",
        description_template=(
            "A client device disconnected from your network via {device_name} "
            "(EVT_WU_Disconnected/EVT_WG_Disconnected/EVT_LU_Disconnected). This is normal "
            "network activity and could be the client leaving range or shutting down."
        ),
        remediation_template=None,  # LOW severity - no remediation needed
    ),
]
