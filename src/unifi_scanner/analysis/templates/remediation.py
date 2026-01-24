"""Remediation templates for analysis findings.

SEVERE findings get step-by-step numbered instructions.
MEDIUM findings get high-level guidance without strict numbering.
LOW findings return None (informational only, no remediation needed).
"""

from typing import Any, Dict, Optional

from unifi_scanner.models.enums import Severity


class SafeDict(dict):
    """Dict subclass that returns 'Unknown' for missing keys.

    Used with str.format_map() to handle missing template variables
    gracefully instead of raising KeyError.
    """

    def __missing__(self, key: str) -> str:
        return "Unknown"


# Remediation templates are keyed by rule name.
# Each template has 'severe' and/or 'medium' content.
# 'severe' templates have numbered steps (1., 2., 3., etc.)
# 'medium' templates have high-level guidance

REMEDIATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    # Security remediations
    "admin_login_failed": {
        "severe": (
            "1. Check the source IP address {ip_address} - is it from your network or external?\n"
            "2. Review the UniFi controller access logs for patterns of failed attempts.\n"
            "3. If external, consider blocking the IP in your firewall settings.\n"
            "4. Verify your admin password is strong (12+ characters, mixed case, numbers, symbols).\n"
            "5. Enable two-factor authentication in UniFi Account Settings if not already enabled.\n"
            "6. Consider limiting admin access to specific IP ranges in Controller Settings."
        ),
        "medium": (
            "Check if the login attempts are from a known IP address. If you recognize the "
            "source, someone may have mistyped the password. If unfamiliar, monitor for "
            "additional attempts and consider enabling two-factor authentication."
        ),
    },
    "admin_login_success": {
        "medium": (
            "Verify this login was expected. If you didn't log in recently, check who has "
            "admin access to your controller and consider changing passwords as a precaution."
        ),
    },
    "rogue_ap_detected": {
        "severe": (
            "1. Identify the rogue access point - check the MAC address and signal strength.\n"
            "2. Walk through your space to physically locate the device if signal is strong.\n"
            "3. If it's an employee's personal hotspot, remind them of network policy.\n"
            "4. If it's a neighbor's WiFi, no action needed (just interference).\n"
            "5. If suspicious and unknown, investigate further - it could be a security threat.\n"
            "6. Consider enabling Rogue AP containment if available on your controller."
        ),
        "medium": (
            "Identify whether this is a neighbor's WiFi, a personal hotspot, or an unknown "
            "device. Personal hotspots should follow your network policy. Unknown devices "
            "warrant further investigation."
        ),
    },
    "ips_alert": {
        "severe": (
            "1. Review the IPS alert details in your UniFi controller under Threat Management.\n"
            "2. Identify the source and destination of the flagged traffic.\n"
            "3. Check if the affected device is compromised (run malware scans).\n"
            "4. Block the malicious IP if it's external traffic.\n"
            "5. Update firmware and software on affected devices.\n"
            "6. Review your firewall rules to prevent similar traffic."
        ),
        "medium": (
            "Review the IPS alert details to understand what triggered it. Many alerts are "
            "false positives from legitimate services. If the traffic looks suspicious, "
            "investigate the source device."
        ),
    },

    # Connectivity remediations
    "ap_lost_contact": {
        "severe": (
            "1. Check if the access point {device_name} has power - verify the LED status.\n"
            "2. Inspect the ethernet cable connection at both the AP and the switch/injector.\n"
            "3. Try a different ethernet cable if available.\n"
            "4. Check the switch port or PoE injector for issues.\n"
            "5. Try power cycling the AP by disconnecting and reconnecting power.\n"
            "6. If still offline, the AP may need replacement."
        ),
        "medium": (
            "Check if the access point has power and its ethernet cable is connected. "
            "Try power cycling the device. If it doesn't come back online, inspect "
            "the cable and switch port."
        ),
    },
    "switch_lost_contact": {
        "severe": (
            "1. Verify the switch {device_name} has power - check LED indicators.\n"
            "2. Inspect the uplink cable connecting the switch to your network.\n"
            "3. Try a different uplink port if available.\n"
            "4. Power cycle the switch by unplugging and replugging power.\n"
            "5. Check for overheating - ensure adequate ventilation.\n"
            "6. If still offline after power cycle, the switch may need replacement."
        ),
        "medium": (
            "Check that the switch has power and its uplink is connected. Try power "
            "cycling the device. Ensure it has adequate ventilation and isn't overheating."
        ),
    },
    "gateway_wan_down": {
        "severe": (
            "1. Check your modem/ONT - verify it has power and shows normal status lights.\n"
            "2. Try power cycling the modem/ONT (unplug for 30 seconds, then reconnect).\n"
            "3. Verify the ethernet cable from modem to gateway is secure.\n"
            "4. Check for ISP outages in your area (use mobile data to check provider status page).\n"
            "5. Try connecting a laptop directly to the modem to test ISP connection.\n"
            "6. If ISP connection works on laptop but not gateway, restart the gateway."
        ),
        "medium": (
            "Power cycle your modem and gateway. Check for ISP outages in your area. "
            "If the issue persists, contact your internet service provider."
        ),
    },
    "ap_isolated": {
        "severe": (
            "1. Check the ethernet cable from AP {device_name} to the switch.\n"
            "2. Try a different switch port.\n"
            "3. Verify the switch port configuration allows the AP VLAN.\n"
            "4. Check for spanning tree issues blocking the port.\n"
            "5. Test with a different ethernet cable.\n"
            "6. Restart the AP and monitor if isolation recurs."
        ),
        "medium": (
            "Check the ethernet cable and switch port for the access point. "
            "Try a different port or cable. Verify VLAN configuration is correct."
        ),
    },

    # Performance remediations
    "interference_detected": {
        "medium": (
            "Consider changing WiFi channels to reduce interference. Enable auto-channel "
            "optimization or manually select a less congested channel. Moving the access "
            "point away from electronic devices may also help."
        ),
    },
    "high_cpu": {
        "severe": (
            "1. Check what's causing high load - review connected clients on {device_name}.\n"
            "2. Look for unusual traffic patterns or DDoS indicators.\n"
            "3. Restart the device to clear any stuck processes.\n"
            "4. Check if firmware is up to date - updates often fix performance issues.\n"
            "5. Consider reducing the number of clients if device is overloaded.\n"
            "6. Monitor after restart - if CPU stays high, contact Ubiquiti support."
        ),
        "medium": (
            "Restart the device to clear any stuck processes. If high CPU persists, "
            "check for unusual traffic patterns and ensure firmware is up to date."
        ),
    },
    "high_memory": {
        "severe": (
            "1. Restart device {device_name} to clear memory.\n"
            "2. Check for firmware updates that may fix memory leaks.\n"
            "3. Review the number of connected clients - reduce if excessive.\n"
            "4. Check for features that consume memory (DPI, IPS) and disable if not needed.\n"
            "5. Monitor memory after restart - if it climbs quickly, there may be a leak.\n"
            "6. Contact Ubiquiti support if the issue persists across firmware versions."
        ),
        "medium": (
            "Restart the device to free up memory. Check for firmware updates that "
            "address memory issues. Disable unused features if memory remains high."
        ),
    },
    "slow_speed": {
        "medium": (
            "Check for WiFi interference and congestion. Verify the device isn't "
            "overloaded with clients. Test speed from a wired connection to isolate "
            "whether the issue is wireless or network-wide."
        ),
    },
    "channel_congestion": {
        "medium": (
            "Enable auto-channel optimization to let the AP select the best channel "
            "automatically. Alternatively, use a WiFi analyzer app to find the least "
            "congested channel in your area and set it manually."
        ),
    },

    # System remediations (mostly informational, few remediation steps)
    "device_restarted_unexpected": {
        "severe": (
            "1. Check device {device_name} power supply - ensure it's stable and adequate.\n"
            "2. Verify the device isn't overheating - check ventilation.\n"
            "3. Review the event logs for errors before the restart.\n"
            "4. Check if firmware is up to date.\n"
            "5. Monitor for additional unexpected restarts.\n"
            "6. If restarts continue, the device may have a hardware issue."
        ),
        "medium": (
            "Check the device's power supply and ventilation. Monitor for additional "
            "unexpected restarts. If the issue recurs, consider replacing the power adapter "
            "or investigating hardware issues."
        ),
    },
    "config_changed": {
        "medium": (
            "Review recent configuration changes in your controller. If you didn't make "
            "the change, verify who has admin access. Consider enabling change logging "
            "and notifications for future visibility."
        ),
    },
    "update_available": {
        "medium": (
            "Review the release notes for the available update. Plan to install the "
            "update during a maintenance window when brief network disruption is acceptable. "
            "Always back up your configuration before updating."
        ),
    },
}


def render_remediation(
    template_key: str,
    severity: Severity,
    context: Dict[str, Any],
) -> Optional[str]:
    """Render a remediation template based on rule key and severity.

    Args:
        template_key: Key from REMEDIATION_TEMPLATES (e.g., 'admin_login_failed')
        severity: Finding severity (Severity.SEVERE, MEDIUM, or LOW)
        context: Dictionary with placeholder values

    Returns:
        Rendered remediation string, or None if:
        - Severity is LOW (informational only)
        - No template exists for this rule/severity combination
    """
    # LOW severity gets no remediation (informational only)
    if severity == Severity.LOW:
        return None

    template_group = REMEDIATION_TEMPLATES.get(template_key)
    if template_group is None:
        return None

    # Get severity-specific template
    severity_key = severity.value  # 'severe' or 'medium'
    template = template_group.get(severity_key)
    if template is None:
        return None

    safe_context = SafeDict(context)
    return template.format_map(safe_context)
