"""Security category rules for UniFi event analysis.

Rules for authentication, intrusion detection, and other security-related events.
"""

from typing import List

from unifi_scanner.analysis.rules.base import Rule
from unifi_scanner.models.enums import Category, Severity


SECURITY_RULES: List[Rule] = [
    # SEVERE: Failed admin login attempts
    Rule(
        name="admin_login_failed",
        event_types=["EVT_AD_LOGIN_FAILED", "EVT_AD_LoginFailed"],
        category=Category.SECURITY,
        severity=Severity.SEVERE,
        title_template="[Security] Failed admin login from {ip}",
        description_template=(
            "Someone attempted to log into your UniFi controller from {ip} "
            "but failed authentication (EVT_AD_LOGIN_FAILED). This could indicate "
            "someone trying to guess your password or a misconfigured automation tool."
        ),
        remediation_template=(
            "1. Check if you recognize the IP address {ip}\n"
            "2. If this is a repeated pattern, consider blocking this IP in your firewall\n"
            "3. Ensure your admin password is strong and unique\n"
            "4. Consider enabling two-factor authentication if available\n"
            "5. Review firewall rules to limit controller access to trusted networks"
        ),
    ),
    # SEVERE: Rogue AP detection
    Rule(
        name="rogue_ap_detected",
        event_types=["EVT_AP_RogueAPDetected", "EVT_ROGUE_AP"],
        category=Category.SECURITY,
        severity=Severity.SEVERE,
        title_template="[Security] Rogue access point detected near {device_name}",
        description_template=(
            "An unauthorized wireless access point was detected in your network's vicinity "
            "by {device_name} (EVT_AP_RogueAPDetected). This could be a malicious actor "
            "attempting to capture network traffic or an unauthorized device from a neighbor."
        ),
        remediation_template=(
            "1. Identify the rogue AP - check the SSID and BSSID in your controller logs\n"
            "2. Physically locate the device if possible\n"
            "3. If it's an internal device, ensure it's properly secured or remove it\n"
            "4. If it's external, consider adjusting channel settings to reduce interference\n"
            "5. Enable rogue AP containment if your license supports it"
        ),
    ),
    # SEVERE: IPS/IDS alert
    Rule(
        name="ips_alert",
        event_types=["EVT_IPS_Alert", "EVT_IDS_Alert", "EVT_THREAT_DETECTED"],
        category=Category.SECURITY,
        severity=Severity.SEVERE,
        title_template="[Security] Intrusion Prevention System alert on {device_name}",
        description_template=(
            "The Intrusion Prevention System on {device_name} detected potentially malicious "
            "network activity (EVT_IPS_Alert). This could indicate an attack attempt, malware "
            "communication, or suspicious traffic patterns that match known threat signatures."
        ),
        remediation_template=(
            "1. Review the IPS alert details in your UniFi controller\n"
            "2. Identify the source and destination of the suspicious traffic\n"
            "3. Check if the flagged device is compromised - run malware scans\n"
            "4. Consider isolating the affected device until investigated\n"
            "5. Update IPS signatures if available\n"
            "6. Review firewall rules to block the malicious source if external"
        ),
    ),
    # LOW: Successful admin login (informational awareness)
    Rule(
        name="admin_login_success",
        event_types=["EVT_AD_Login", "EVT_AD_LOGIN"],
        category=Category.SECURITY,
        severity=Severity.LOW,
        title_template="[Security] Admin login from {ip}",
        description_template=(
            "An administrator successfully logged into your UniFi controller from {ip} "
            "(EVT_AD_Login). This is normal activity but logged for security awareness "
            "and audit trails."
        ),
        remediation_template=None,  # LOW severity - no remediation needed
    ),
]
