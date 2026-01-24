"""Explanation templates for analysis findings.

Templates include category prefix, event type for Googling, and plain
English explanations of what happened and why it matters.
"""

from typing import Any, Dict


class SafeDict(dict):
    """Dict subclass that returns 'Unknown' for missing keys.

    Used with str.format_map() to handle missing template variables
    gracefully instead of raising KeyError.
    """

    def __missing__(self, key: str) -> str:
        return "Unknown"


# Template structure:
# - title: Category-prefixed title, e.g., "[Security] Failed Login Attempt"
# - description: Plain English explanation with {event_type} for Googling
#
# Available placeholders:
# - {event_type}: Original UniFi event type for Googling
# - {device_name}: Device name or MAC address fallback
# - {device_mac}: MAC address
# - {timestamp}: Human-readable timestamp
# - {ip_address}: IP address if applicable
# - {message}: Original log message
# - {user}: Username if applicable
# - {count}: Occurrence count

EXPLANATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    # Security events
    "admin_login_failed": {
        "title": "[Security] Failed Admin Login Attempt",
        "description": (
            "Someone attempted to log into your UniFi controller but failed "
            "({event_type}). This could be a mistyped password, but multiple "
            "failures may indicate a brute-force attack. The attempt came from "
            "IP address {ip_address}."
        ),
    },
    "admin_login_success": {
        "title": "[Security] Admin Login",
        "description": (
            "An administrator successfully logged into your UniFi controller "
            "({event_type}). This is normal if you or a trusted admin signed in. "
            "Verify this was expected activity."
        ),
    },
    "rogue_ap_detected": {
        "title": "[Security] Rogue Access Point Detected",
        "description": (
            "An unauthorized wireless access point was detected on your network "
            "({event_type}). This could be a neighbor's WiFi, an employee's "
            "personal hotspot, or potentially a malicious device. Device: {device_name}."
        ),
    },
    "ips_alert": {
        "title": "[Security] Intrusion Prevention Alert",
        "description": (
            "The intrusion prevention system detected suspicious activity "
            "({event_type}). This may indicate an attempted attack or malicious "
            "traffic on your network. Review the alert details and affected devices."
        ),
    },

    # Connectivity events
    "ap_lost_contact": {
        "title": "[Connectivity] Access Point Disconnected",
        "description": (
            "Access point {device_name} lost connection to your controller "
            "({event_type}). Devices in that area have lost WiFi coverage. "
            "This could be due to power loss, network cable issues, or device failure."
        ),
    },
    "switch_lost_contact": {
        "title": "[Connectivity] Switch Disconnected",
        "description": (
            "Switch {device_name} lost connection to your controller "
            "({event_type}). Devices connected to this switch may have lost "
            "network access. Check power and uplink connections."
        ),
    },
    "gateway_wan_down": {
        "title": "[Connectivity] Internet Connection Lost",
        "description": (
            "Your gateway lost its internet connection ({event_type}). "
            "All devices on your network are unable to reach the internet. "
            "This could be an ISP outage or a problem with your modem/ONT."
        ),
    },
    "ap_isolated": {
        "title": "[Connectivity] Access Point Isolated",
        "description": (
            "Access point {device_name} is isolated from the network "
            "({event_type}). This means it can't communicate with other "
            "devices or the controller. Check cabling and switch port status."
        ),
    },
    "device_connected": {
        "title": "[Connectivity] Device Connected",
        "description": (
            "Device {device_name} connected to your network ({event_type}). "
            "This is normal activity when devices join your WiFi or wired network."
        ),
    },
    "client_activity": {
        "title": "[Connectivity] Client Network Activity",
        "description": (
            "Network activity detected for client {device_name} ({event_type}). "
            "This is informational and represents normal network usage."
        ),
    },

    # Performance events
    "interference_detected": {
        "title": "[Performance] WiFi Interference Detected",
        "description": (
            "Access point {device_name} detected wireless interference "
            "({event_type}). This can cause slower speeds and connection drops "
            "for nearby devices. Neighboring networks or electronic devices may "
            "be the source."
        ),
    },
    "high_cpu": {
        "title": "[Performance] High CPU Usage",
        "description": (
            "Device {device_name} is experiencing high CPU usage ({event_type}). "
            "This may cause slow performance and delayed responses. The device "
            "may be overloaded or experiencing a software issue."
        ),
    },
    "high_memory": {
        "title": "[Performance] High Memory Usage",
        "description": (
            "Device {device_name} is running low on memory ({event_type}). "
            "This can lead to instability and unexpected behavior. A restart "
            "may be needed if the issue persists."
        ),
    },
    "slow_speed": {
        "title": "[Performance] Slow Network Speed Detected",
        "description": (
            "Slow network speeds detected on {device_name} ({event_type}). "
            "Users may experience buffering, slow downloads, or laggy connections. "
            "Check for interference, congestion, or hardware issues."
        ),
    },
    "channel_congestion": {
        "title": "[Performance] WiFi Channel Congestion",
        "description": (
            "Access point {device_name} detected channel congestion ({event_type}). "
            "Too many networks are using the same channel, causing slower speeds. "
            "Consider enabling auto-channel or manually selecting a less busy channel."
        ),
    },

    # System events
    "firmware_upgraded": {
        "title": "[System] Firmware Updated",
        "description": (
            "Device {device_name} completed a firmware upgrade ({event_type}). "
            "This is normal maintenance activity. The device should now have "
            "the latest features and security patches."
        ),
    },
    "device_restarted": {
        "title": "[System] Device Restarted",
        "description": (
            "Device {device_name} was restarted ({event_type}). "
            "This was a planned restart, likely due to a firmware update "
            "or manual reboot."
        ),
    },
    "device_restarted_unexpected": {
        "title": "[System] Unexpected Device Restart",
        "description": (
            "Device {device_name} restarted unexpectedly ({event_type}). "
            "This could indicate a power issue, hardware problem, or software crash. "
            "Monitor for repeated occurrences."
        ),
    },
    "device_adopted": {
        "title": "[System] New Device Adopted",
        "description": (
            "Device {device_name} was adopted to your controller ({event_type}). "
            "This is normal when adding new UniFi equipment to your network."
        ),
    },
    "config_changed": {
        "title": "[System] Configuration Changed",
        "description": (
            "A configuration change was made to your UniFi controller ({event_type}). "
            "Review recent changes if this was unexpected. Changes may affect "
            "network behavior."
        ),
    },
    "backup_created": {
        "title": "[System] Backup Created",
        "description": (
            "A backup of your UniFi controller settings was created ({event_type}). "
            "This is good practice and ensures you can restore your configuration "
            "if needed."
        ),
    },
    "update_available": {
        "title": "[System] Firmware Update Available",
        "description": (
            "A firmware update is available for {device_name} ({event_type}). "
            "Updates often include security patches and bug fixes. Consider "
            "updating during a maintenance window."
        ),
    },

    # Fallback for unknown event types
    "unknown": {
        "title": "[Uncategorized] Network Event",
        "description": (
            "A network event occurred ({event_type}). "
            "Review the details below for more information. "
            "Message: {message}"
        ),
    },
}


def render_explanation(
    template_key: str,
    context: Dict[str, Any],
) -> Dict[str, str]:
    """Render an explanation template with context values.

    Args:
        template_key: Key from EXPLANATION_TEMPLATES (e.g., 'admin_login_failed')
        context: Dictionary with placeholder values (event_type, device_name, etc.)

    Returns:
        Dictionary with 'title' and 'description' rendered with context.
        Falls back to 'unknown' template if template_key not found.
    """
    template = EXPLANATION_TEMPLATES.get(template_key)
    if template is None:
        template = EXPLANATION_TEMPLATES["unknown"]

    safe_context = SafeDict(context)

    return {
        "title": template["title"].format_map(safe_context),
        "description": template["description"].format_map(safe_context),
    }
