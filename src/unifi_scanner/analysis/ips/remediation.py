"""IPS-specific remediation templates for threat analysis findings.

Provides category-specific remediation guidance with severity-adjusted detail:
- SEVERE: Step-by-step numbered instructions
- MEDIUM: Brief actionable advice
- LOW: Explanation only (returned as note, no action required)

Includes false positive notes for common categories.
"""

from typing import Any, Dict, Optional

from unifi_scanner.models.enums import Severity


class SafeDict(dict):
    """Dict subclass that returns placeholder for missing keys.

    Used with str.format_map() to handle missing template variables
    gracefully instead of raising KeyError.
    """

    def __missing__(self, key: str) -> str:
        return f"[{key}]"


# IPS remediation templates keyed by ET category (uppercase).
# Each category has severity-specific templates and optional false_positive_note.
IPS_REMEDIATION_TEMPLATES: Dict[str, Dict[str, Optional[str]]] = {
    "SCAN": {
        "severe": (
            "1. Identify the source IP {src_ip} - check if it's internal or external\n"
            "2. If external, this may be routine internet scanning - monitor for follow-up attacks\n"
            "3. If internal, check the device for malware or unauthorized scanning tools\n"
            "4. Review firewall logs for other probes from this source\n"
            "5. Consider blocking persistent scanners at the firewall level"
        ),
        "medium": (
            "Port scans from {src_ip} were detected. This is often routine internet "
            "background noise, but verify the source isn't an internal compromised device."
        ),
        "low": (
            "Low-level scanning activity detected. Usually background noise from "
            "internet-wide scans. No action typically required."
        ),
        "false_positive_note": None,
    },
    "MALWARE": {
        "severe": (
            "1. IMMEDIATELY isolate the affected device ({src_ip}) from the network\n"
            "2. Run a full malware scan on the device using updated antivirus\n"
            "3. Check for data exfiltration - review outbound traffic logs\n"
            "4. Change passwords for any accounts accessed from this device\n"
            "5. If confirmed infected, consider reimaging the device\n"
            "6. Monitor other devices for similar signatures"
        ),
        "medium": (
            "Potential malware communication from {src_ip}. Run a malware scan on "
            "the device and verify it's not a false positive from legitimate software."
        ),
        "low": (
            "Minor malware signature match detected. May be a false positive from "
            "legitimate software with similar traffic patterns."
        ),
        "false_positive_note": None,
    },
    "POLICY": {
        "severe": (
            "1. Review what triggered the policy violation - signature: {signature}\n"
            "2. Determine if this is legitimate traffic that needs a policy exception\n"
            "3. If unauthorized, investigate the user/device for policy compliance\n"
            "4. Update network policies if the traffic should be permitted"
        ),
        "medium": (
            "Policy violation detected from {src_ip}. This often indicates traffic that "
            "violates organizational policy (streaming, P2P, etc.). Verify if expected."
        ),
        "low": (
            "Policy violation logged for audit purposes. Review if unexpected traffic "
            "patterns are observed."
        ),
        "false_positive_note": (
            "Note: POLICY violations from streaming services (Netflix, YouTube, etc.) "
            "are common false positives and typically don't require action."
        ),
    },
    "EXPLOIT": {
        "severe": (
            "1. Identify the target device at {dest_ip} - it may be vulnerable\n"
            "2. Check if the exploit attempt was successful (review device logs)\n"
            "3. Patch or update the target device immediately\n"
            "4. Block the source IP {src_ip} if external and malicious\n"
            "5. Scan your network for similar vulnerabilities"
        ),
        "medium": (
            "Exploit attempt detected targeting {dest_ip}. Verify the target device "
            "is patched and up to date. Monitor for successful exploitation."
        ),
        "low": (
            "Exploit attempt detected but likely unsuccessful. Keep systems patched "
            "to prevent future attempts."
        ),
        "false_positive_note": None,
    },
    "DOS": {
        "severe": (
            "1. Identify if this is an ongoing attack by checking traffic volume\n"
            "2. Enable rate limiting on the firewall for the source IP {src_ip}\n"
            "3. If external, consider contacting your ISP for upstream filtering\n"
            "4. Document the attack for potential legal action\n"
            "5. Review and harden firewall rules against flood attacks"
        ),
        "medium": (
            "Denial of service pattern detected from {src_ip}. Monitor traffic levels "
            "and enable rate limiting if needed."
        ),
        "low": (
            "Minor DoS-like traffic pattern detected. May be legitimate high-volume "
            "traffic. Monitor for escalation."
        ),
        "false_positive_note": None,
    },
    "COINMINING": {
        "severe": (
            "1. Identify the device at {src_ip} - it may be compromised\n"
            "2. Check for unauthorized crypto mining software\n"
            "3. Scan the device for malware that may have installed miners\n"
            "4. Review CPU and power usage on the device\n"
            "5. Block cryptocurrency mining pools at the firewall level"
        ),
        "medium": (
            "Cryptocurrency mining traffic detected from {src_ip}. Verify if this "
            "is authorized. Unauthorized mining may indicate compromise."
        ),
        "low": (
            "Low-level crypto mining signature detected. May be false positive from "
            "legitimate blockchain-related services."
        ),
        "false_positive_note": None,
    },
    "P2P": {
        "severe": (
            "1. Identify the device at {src_ip} using P2P traffic\n"
            "2. Verify if P2P usage is authorized on your network\n"
            "3. Check for potential copyright infringement risks\n"
            "4. Consider bandwidth impact on other users\n"
            "5. Block P2P protocols if against network policy"
        ),
        "medium": (
            "Peer-to-peer traffic detected from {src_ip}. Verify if authorized. "
            "P2P can consume significant bandwidth."
        ),
        "low": (
            "P2P protocol signature detected. This is often legitimate software "
            "like game launchers or software updates."
        ),
        "false_positive_note": (
            "Note: P2P alerts from game launchers (Steam, Epic, Battle.net) and "
            "software updaters are common false positives."
        ),
    },
    "TOR": {
        "severe": (
            "1. Identify the device at {src_ip} using TOR\n"
            "2. Investigate why TOR access is being attempted\n"
            "3. Check if the device is compromised (malware often uses TOR)\n"
            "4. Review organizational policy on anonymization tools\n"
            "5. Block TOR exit nodes if against policy"
        ),
        "medium": (
            "TOR network traffic detected from {src_ip}. TOR can be legitimate but "
            "is also used by malware. Verify the usage is authorized."
        ),
        "low": (
            "TOR-related traffic pattern detected. May be a privacy tool or "
            "indicates investigation into TOR network."
        ),
        "false_positive_note": None,
    },
    "PHISHING": {
        "severe": (
            "1. Warn users who may have accessed the phishing site\n"
            "2. Check if any credentials were entered on the phishing page\n"
            "3. Force password resets for potentially compromised accounts\n"
            "4. Block the phishing domain at the firewall/DNS level\n"
            "5. Report the phishing site to appropriate authorities"
        ),
        "medium": (
            "Phishing attempt detected. Check if any users interacted with the "
            "suspicious content. Consider blocking the domain."
        ),
        "low": (
            "Potential phishing indicator detected. Monitor for user interaction "
            "with suspicious content."
        ),
        "false_positive_note": None,
    },
    # Additional categories from ET rulesets
    "TROJAN": {
        "severe": (
            "1. IMMEDIATELY isolate the device at {src_ip}\n"
            "2. This is trojan activity - the device is likely compromised\n"
            "3. Run full antivirus/antimalware scans\n"
            "4. Check for data exfiltration and unauthorized access\n"
            "5. Consider reimaging the affected system\n"
            "6. Change all passwords accessed from this device"
        ),
        "medium": (
            "Trojan communication pattern detected from {src_ip}. Run a full "
            "malware scan immediately."
        ),
        "low": (
            "Trojan signature match detected. Verify with malware scan - may be "
            "false positive from similar traffic patterns."
        ),
        "false_positive_note": None,
    },
    "BOTCC": {
        "severe": (
            "1. IMMEDIATELY isolate the device at {src_ip}\n"
            "2. Botnet C&C traffic indicates active compromise\n"
            "3. Run comprehensive malware removal tools\n"
            "4. Check for lateral movement to other devices\n"
            "5. Block the C&C server address at firewall\n"
            "6. Consider reimaging the affected system"
        ),
        "medium": (
            "Potential botnet command & control traffic from {src_ip}. "
            "Run malware scan and monitor for additional indicators."
        ),
        "low": (
            "Possible C&C traffic pattern detected. May be false positive but "
            "warrants monitoring."
        ),
        "false_positive_note": None,
    },
    "ATTACK_RESPONSE": {
        "severe": (
            "1. Investigate the target at {dest_ip} - it may be compromised\n"
            "2. Attack response indicates a successful attack\n"
            "3. Check for data exfiltration or unauthorized access\n"
            "4. Review logs for the initial attack vector\n"
            "5. Isolate and scan the affected system"
        ),
        "medium": (
            "Attack response traffic detected. The target may have been "
            "successfully compromised. Investigate immediately."
        ),
        "low": (
            "Attack response pattern detected. May be legitimate error messages "
            "or diagnostic traffic."
        ),
        "false_positive_note": None,
    },
    "DNS": {
        "severe": (
            "1. Investigate DNS anomaly from {src_ip}\n"
            "2. Check for DNS tunneling or data exfiltration\n"
            "3. Verify DNS server configurations are correct\n"
            "4. Look for malware using DNS for C&C communication\n"
            "5. Consider using DNS filtering/security services"
        ),
        "medium": (
            "DNS anomaly detected from {src_ip}. Verify DNS configuration and "
            "check for potential DNS-based attacks."
        ),
        "low": (
            "Minor DNS anomaly detected. May be misconfiguration or legitimate "
            "unusual DNS traffic."
        ),
        "false_positive_note": None,
    },
    "WEB_CLIENT": {
        "severe": (
            "1. Identify the browser/client at {src_ip} making suspicious requests\n"
            "2. Check if the user visited a malicious website\n"
            "3. Scan the client device for drive-by downloads\n"
            "4. Clear browser cache and check for malicious extensions\n"
            "5. Update browser and enable security features"
        ),
        "medium": (
            "Web client attack pattern detected from {src_ip}. The user may have "
            "visited a malicious site. Scan for malware."
        ),
        "low": (
            "Suspicious web client activity detected. May be triggered by "
            "legitimate but unusual web traffic."
        ),
        "false_positive_note": None,
    },
    "WEB_SERVER": {
        "severe": (
            "1. Check your web server at {dest_ip} for compromise\n"
            "2. Review web server logs for successful exploitation\n"
            "3. Patch web application vulnerabilities immediately\n"
            "4. Consider using a Web Application Firewall (WAF)\n"
            "5. Block the attacking IP {src_ip} if appropriate"
        ),
        "medium": (
            "Web server attack detected targeting {dest_ip}. Review logs and "
            "ensure web applications are patched."
        ),
        "low": (
            "Web server probe detected. Common internet scanning - ensure "
            "server is properly secured."
        ),
        "false_positive_note": None,
    },
    "COMPROMISED": {
        "severe": (
            "1. The device at {src_ip} is communicating with a known-compromised host\n"
            "2. Isolate the device immediately for investigation\n"
            "3. Run full malware and rootkit scans\n"
            "4. Check for data exfiltration\n"
            "5. Review how the compromise occurred"
        ),
        "medium": (
            "Traffic to/from known compromised host detected. Investigate {src_ip} "
            "for potential infection."
        ),
        "low": (
            "Traffic to potentially compromised host detected. May be historical "
            "or misclassified."
        ),
        "false_positive_note": None,
    },
    "DROP": {
        "severe": (
            "1. Traffic from {src_ip} matches reputation blocklist\n"
            "2. This IP is known for malicious activity\n"
            "3. Ensure traffic is being blocked\n"
            "4. Investigate why your device communicated with this IP\n"
            "5. Scan for malware that may have initiated the connection"
        ),
        "medium": (
            "Traffic to/from reputation-blocked IP detected. Verify the traffic "
            "is being blocked and investigate the cause."
        ),
        "low": (
            "Reputation-flagged IP communication detected. Often historical or "
            "misclassified IPs."
        ),
        "false_positive_note": None,
    },
    "DSHIELD": {
        "severe": (
            "1. Traffic from known attacker IP {src_ip} detected\n"
            "2. This IP is on the DShield blocklist\n"
            "3. Ensure firewall is blocking this traffic\n"
            "4. Review what triggered the communication\n"
            "5. Scan internal devices for compromise"
        ),
        "medium": (
            "DShield-listed attacker IP detected. Verify traffic is blocked and "
            "investigate any internal connections."
        ),
        "low": (
            "DShield-flagged IP activity detected. Often routine internet scanning "
            "from known bad actors."
        ),
        "false_positive_note": None,
    },
    "CURRENT_EVENTS": {
        "severe": (
            "1. Traffic matches an active threat campaign\n"
            "2. Investigate {src_ip} immediately for compromise\n"
            "3. Check threat intelligence feeds for campaign details\n"
            "4. Apply any available patches or mitigations\n"
            "5. Monitor for additional indicators of compromise"
        ),
        "medium": (
            "Active campaign indicator detected. Research the specific campaign "
            "and verify your systems are protected."
        ),
        "low": (
            "Current events signature match. May be related to ongoing campaigns "
            "but not necessarily a direct threat."
        ),
        "false_positive_note": None,
    },
    "INFO": {
        "severe": None,  # INFO rarely has severe findings
        "medium": (
            "Informational security event logged from {src_ip}. Review if "
            "unexpected but typically no action required."
        ),
        "low": (
            "Informational event captured for logging purposes. No action required."
        ),
        "false_positive_note": None,
    },
    "USER_AGENTS": {
        "severe": (
            "1. Suspicious user agent detected from {src_ip}\n"
            "2. Check if this is malware masquerading as legitimate software\n"
            "3. Verify the software installed on the device\n"
            "4. Run malware scans if user agent is unexpected\n"
            "5. Block suspicious user agents at the proxy/firewall"
        ),
        "medium": (
            "Suspicious user agent string detected from {src_ip}. Verify the "
            "software is legitimate and expected."
        ),
        "low": (
            "Unusual user agent detected. May be legitimate software with "
            "non-standard identification."
        ),
        "false_positive_note": (
            "Note: Non-standard user agents from IoT devices, mobile apps, and "
            "development tools are common false positives."
        ),
    },
    "HUNTING": {
        "severe": (
            "1. Threat hunting rule triggered - investigate {src_ip}\n"
            "2. Review the specific hunting rule for context\n"
            "3. Correlate with other indicators in your environment\n"
            "4. May indicate advanced persistent threat (APT) activity\n"
            "5. Consider engaging security professionals if confirmed"
        ),
        "medium": (
            "Threat hunting match detected. Review the signature context and "
            "investigate for potential advanced threats."
        ),
        "low": (
            "Threat hunting indicator logged. These are broad patterns that "
            "warrant awareness but may not indicate active threats."
        ),
        "false_positive_note": None,
    },
    "MOBILE_MALWARE": {
        "severe": (
            "1. Mobile device at {src_ip} may be infected\n"
            "2. Run mobile antivirus/security scan\n"
            "3. Review recently installed apps\n"
            "4. Factory reset if infection is confirmed\n"
            "5. Change passwords for accounts accessed from the device"
        ),
        "medium": (
            "Mobile malware signature detected from {src_ip}. Scan the mobile "
            "device and review installed applications."
        ),
        "low": (
            "Mobile malware indicator detected. May be false positive from "
            "legitimate apps with unusual traffic patterns."
        ),
        "false_positive_note": None,
    },
    "GAMES": {
        "severe": None,  # Gaming traffic rarely severe
        "medium": (
            "Gaming protocol traffic detected from {src_ip}. Verify if gaming "
            "traffic is permitted on your network."
        ),
        "low": (
            "Gaming traffic detected. This is typically harmless recreational "
            "activity."
        ),
        "false_positive_note": (
            "Note: GAMES alerts are usually legitimate gaming activity and "
            "rarely indicate security issues."
        ),
    },
    "CHAT": {
        "severe": None,  # Chat traffic rarely severe
        "medium": (
            "Chat application traffic detected from {src_ip}. Verify if this "
            "aligns with your acceptable use policy."
        ),
        "low": (
            "Chat application protocol detected. Typically legitimate "
            "communication software."
        ),
        "false_positive_note": (
            "Note: CHAT alerts from popular messaging apps (Discord, Slack, etc.) "
            "are normal and expected."
        ),
    },
}


def get_remediation(
    category: str,
    severity: Severity,
    context: Dict[str, Any],
) -> Optional[str]:
    """Get formatted remediation for a threat category and severity.

    Returns severity-adjusted remediation guidance:
    - SEVERE: Step-by-step instructions
    - MEDIUM: Brief actionable advice
    - LOW: Explanation of what happened

    Args:
        category: ET category (e.g., "SCAN", "MALWARE")
        severity: Finding severity level
        context: Dictionary with placeholder values (src_ip, dest_ip, signature, etc.)

    Returns:
        Formatted remediation string, or None if no template exists.
    """
    # Normalize category to uppercase
    category_upper = category.upper()

    # Get template group for this category
    template_group = IPS_REMEDIATION_TEMPLATES.get(category_upper)
    if template_group is None:
        # Fallback for unknown categories
        return _get_generic_remediation(severity, context)

    # Get severity-specific template
    severity_key = severity.value  # 'severe', 'medium', or 'low'
    template = template_group.get(severity_key)

    if template is None:
        return None

    # Format with safe context
    safe_context = SafeDict(context)
    return template.format_map(safe_context)


def get_false_positive_note(category: str) -> Optional[str]:
    """Get false positive note for a category if one exists.

    Args:
        category: ET category (e.g., "POLICY", "P2P")

    Returns:
        False positive note string, or None if none exists for this category.
    """
    category_upper = category.upper()
    template_group = IPS_REMEDIATION_TEMPLATES.get(category_upper)

    if template_group is None:
        return None

    return template_group.get("false_positive_note")


def _get_generic_remediation(severity: Severity, context: Dict[str, Any]) -> str:
    """Get generic remediation for unknown categories.

    Args:
        severity: Finding severity level
        context: Dictionary with placeholder values

    Returns:
        Generic remediation string based on severity.
    """
    safe_context = SafeDict(context)

    if severity == Severity.SEVERE:
        template = (
            "1. Investigate the source IP {src_ip} for suspicious activity\n"
            "2. Review the specific alert details for context\n"
            "3. Check affected devices for compromise\n"
            "4. Monitor for additional related events\n"
            "5. Block the source if confirmed malicious"
        )
    elif severity == Severity.MEDIUM:
        template = (
            "Security event detected from {src_ip}. Review the alert details "
            "and monitor for additional indicators."
        )
    else:
        template = (
            "Security event logged for awareness. No immediate action required."
        )

    return template.format_map(safe_context)
