"""Signature parser for ET (Emerging Threats) Suricata signatures.

Parses IPS/IDS signature strings to extract category, friendly name,
and description. Handles both ET rulesets and non-ET signatures.
"""

import re
from typing import Tuple

# ET signature format: "ET <CATEGORY> <description>"
ET_SIGNATURE_PATTERN = re.compile(r"^ET\s+(\w+)\s+(.+)$", re.IGNORECASE)

# Category mapping to user-friendly names (per CONTEXT.md decisions)
ET_CATEGORY_FRIENDLY_NAMES: dict[str, str] = {
    "SCAN": "Reconnaissance",
    "MALWARE": "Malware Activity",
    "POLICY": "Policy Violation",
    "TROJAN": "Trojan Activity",  # Legacy, maps to Malware in Suricata 5+
    "EXPLOIT": "Exploit Attempt",
    "DOS": "Denial of Service",
    "ATTACK_RESPONSE": "Attack Response",
    "COINMINING": "Cryptocurrency Mining",
    "USER_AGENTS": "Suspicious User Agent",
    "DNS": "DNS Anomaly",
    "WEB_CLIENT": "Web Client Attack",
    "WEB_SERVER": "Web Server Attack",
    "BOTCC": "Botnet Command & Control",
    "COMPROMISED": "Compromised Host",
    "DROP": "Blocked by Reputation",
    "DSHIELD": "Known Attacker",
    "HUNTING": "Threat Hunting Match",
    "CURRENT_EVENTS": "Active Campaign",
    "PHISHING": "Phishing Attempt",
    "MOBILE_MALWARE": "Mobile Malware",
    "TOR": "TOR Network Traffic",
    "INFO": "Informational",
    "P2P": "Peer-to-Peer Traffic",
    "GAMES": "Gaming Traffic",
    "CHAT": "Chat Application",
}

# Actions that indicate the threat was blocked (not just detected)
IPS_ACTION_BLOCKED = {"blocked", "drop", "reject"}

# Actions that indicate detection only (IDS mode or allowed traffic)
IPS_ACTION_DETECTED = {"allowed", "alert", "pass"}


def parse_signature_category(signature: str) -> Tuple[str, str, str]:
    """Extract category from ET signature.

    Parses Emerging Threats signature strings to extract the raw category,
    user-friendly category name, and description.

    Args:
        signature: Full signature string, e.g., "ET SCAN Nmap Scripting Engine"

    Returns:
        Tuple of (raw_category, friendly_name, description)
        e.g., ("SCAN", "Reconnaissance", "Nmap Scripting Engine")

        For non-ET signatures, returns:
        ("UNKNOWN", "Security Event", original_signature)
    """
    match = ET_SIGNATURE_PATTERN.match(signature)
    if match:
        category = match.group(1).upper()
        description = match.group(2)
        friendly = ET_CATEGORY_FRIENDLY_NAMES.get(category, "Security Event")
        return (category, friendly, description)

    # Non-ET signature (Suricata built-in, GPL, etc.)
    return ("UNKNOWN", "Security Event", signature)


def is_action_blocked(action: str) -> bool:
    """Determine if threat was blocked or just detected.

    UniFi IPS action field values:
    - "blocked"/"drop"/"reject" = IPS blocked the traffic
    - "allowed"/"alert"/"pass" = IDS detected only (detection mode)

    Args:
        action: Action string from IPS event

    Returns:
        True if the action indicates the threat was blocked,
        False if it was only detected (or unknown action).
    """
    return action.lower() in IPS_ACTION_BLOCKED
