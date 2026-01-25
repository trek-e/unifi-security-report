"""IPS event models for security analysis."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from unifi_scanner.models.enums import Severity


@dataclass
class IPSEvent:
    """Represents an IPS/IDS event from UniFi threat management.

    This model captures Suricata-based threat detection events including
    port scans, malware activity, policy violations, and other security alerts.

    Attributes:
        timestamp: When the event occurred
        signature: The Suricata signature that triggered (e.g., "ET SCAN Nmap")
        category: Event category (scan, malware, policy, etc.)
        source_ip: Source IP address of the traffic
        dest_ip: Destination IP address
        is_blocked: True if IPS blocked the traffic, False if detection-only
        severity: Severity level of the event
        source_port: Optional source port
        dest_port: Optional destination port
        protocol: Optional protocol (TCP, UDP, etc.)
        raw_data: Optional raw event data for additional context
    """

    timestamp: datetime
    signature: str
    category: str
    source_ip: str
    dest_ip: str
    is_blocked: bool = False
    severity: Severity = Severity.MEDIUM
    source_port: Optional[int] = None
    dest_port: Optional[int] = None
    protocol: Optional[str] = None
    raw_data: Optional[dict] = field(default_factory=dict)
