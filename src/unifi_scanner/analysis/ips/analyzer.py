"""IPS analyzer for threat analysis and aggregation."""

import structlog
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from unifi_scanner.models.enums import Severity

logger = structlog.get_logger(__name__)
from unifi_scanner.analysis.ips.models import IPSEvent
from unifi_scanner.analysis.ips.aggregator import SourceIPSummary, aggregate_source_ips
from unifi_scanner.analysis.ips.remediation import get_remediation
from unifi_scanner.analysis.ips.signature_parser import (
    parse_signature_category,
    ET_CATEGORY_FRIENDLY_NAMES,
)


def _get_category_description(category: str) -> str:
    """Get description for a threat category.

    Args:
        category: Raw category string

    Returns:
        Description of the threat type
    """
    descriptions = {
        "scan": "Network reconnaissance activity detected, typically port scanning or service enumeration.",
        "malware": "Malware communication or download attempt detected.",
        "policy": "Traffic violating network security policy.",
        "exploit": "Attempted exploitation of known vulnerability.",
        "trojan": "Trojan horse communication detected.",
        "dos": "Denial of service attack pattern detected.",
        "shellcode": "Potentially malicious shellcode detected in traffic.",
        "web-application-attack": "Attack targeting web application vulnerabilities.",
        "inappropriate-content": "Content policy violation detected.",
        "misc-activity": "Suspicious but uncategorized network activity.",
        "blocked": "Threat traffic blocked by IPS. Signature details unavailable via MongoDB.",
    }
    return descriptions.get(category.lower(), f"Security event in category: {category}")


def _int_severity_to_enum(severity_int: int) -> Severity:
    """Convert integer severity (1=high, 2=medium, 3=low) to Severity enum.

    Args:
        severity_int: Integer severity from IPS event

    Returns:
        Severity enum value
    """
    if severity_int == 1:
        return Severity.SEVERE
    elif severity_int == 2:
        return Severity.MEDIUM
    else:
        return Severity.LOW


@dataclass
class ThreatSummary:
    """Summary of a threat type.

    Attributes:
        category_friendly: Human-readable category name
        description: Description of the threat
        count: Number of events of this type
        severity: Severity level
        sample_signature: Sample signature from this threat type
        source_ips: List of unique source IPs for this threat
        remediation: Category-specific remediation guidance
        is_cybersecure: True if ANY event in this summary is from Cybersecure (ET PRO)
        cybersecure_count: Count of events with Cybersecure (ET PRO) signatures
    """

    category_friendly: str
    description: str
    count: int
    severity: Severity
    sample_signature: str
    source_ips: List[str] = field(default_factory=list)
    remediation: Optional[str] = None
    is_cybersecure: bool = False
    cybersecure_count: int = 0


@dataclass
class ThreatAnalysisResult:
    """Result of IPS event analysis.

    Attributes:
        blocked_threats: List of blocked threat summaries
        detected_threats: List of detected (not blocked) threat summaries
        external_source_ips: Source IPs from external addresses (above threshold)
        internal_source_ips: Source IPs from internal addresses (above threshold)
        detection_mode_note: Note if all events are detection-only
    """

    blocked_threats: List[ThreatSummary] = field(default_factory=list)
    detected_threats: List[ThreatSummary] = field(default_factory=list)
    external_source_ips: List[SourceIPSummary] = field(default_factory=list)
    internal_source_ips: List[SourceIPSummary] = field(default_factory=list)
    detection_mode_note: Optional[str] = None


class IPSAnalyzer:
    """Analyzer for IPS/IDS events.

    Separates blocked vs detected events, aggregates by source IP,
    and identifies top threat sources with threshold-based filtering.
    """

    def __init__(self, event_threshold: int = 10):
        """Initialize the analyzer.

        Args:
            event_threshold: Minimum events for IP to be highlighted (default: 10)
        """
        self._event_threshold = event_threshold

    def process_events(self, events: List[IPSEvent]) -> ThreatAnalysisResult:
        """Process IPS events and produce threat analysis.

        Args:
            events: List of IPS events to analyze

        Returns:
            ThreatAnalysisResult with separated threats and IP summaries
        """
        if not events:
            return ThreatAnalysisResult()

        # Debug: Log signature IDs and Cybersecure status
        cybersecure_events = [e for e in events if e.is_cybersecure]
        sig_ids = sorted(set(e.signature_id for e in events))
        logger.debug(
            "ips_events_processing",
            total_events=len(events),
            unique_signature_ids=len(sig_ids),
            cybersecure_count=len(cybersecure_events),
            sample_sig_ids=sig_ids[:10],  # First 10 unique SIDs
        )
        if cybersecure_events:
            logger.info(
                "cybersecure_events_found",
                count=len(cybersecure_events),
                signatures=[e.signature for e in cybersecure_events[:5]],
                signature_ids=[e.signature_id for e in cybersecure_events[:5]],
            )

        # Separate blocked and detected events
        blocked_events, detected_events = self._separate_blocked_detected(events)

        # Create threat summaries (deduplicated by signature)
        blocked_threats = self._create_threat_summaries(blocked_events)
        detected_threats = self._create_threat_summaries(detected_events)

        # Aggregate IPs by threshold
        all_ip_summaries = aggregate_source_ips(events, threshold=self._event_threshold)

        # Separate internal and external IPs
        internal_ips = [s for s in all_ip_summaries if s.is_internal]
        external_ips = [s for s in all_ip_summaries if not s.is_internal]

        # Detect if running in detection-only mode
        detection_mode_note = self._detect_detection_mode(events)

        return ThreatAnalysisResult(
            blocked_threats=blocked_threats,
            detected_threats=detected_threats,
            external_source_ips=external_ips,
            internal_source_ips=internal_ips,
            detection_mode_note=detection_mode_note,
        )

    def _separate_blocked_detected(
        self, events: List[IPSEvent]
    ) -> Tuple[List[IPSEvent], List[IPSEvent]]:
        """Separate events into blocked and detected lists.

        Args:
            events: List of all events

        Returns:
            Tuple of (blocked_events, detected_events)
        """
        blocked = []
        detected = []

        for event in events:
            if event.is_blocked:
                blocked.append(event)
            else:
                detected.append(event)

        return blocked, detected

    def _create_threat_summaries(
        self, events: List[IPSEvent]
    ) -> List[ThreatSummary]:
        """Create deduplicated threat summaries from events.

        Events are grouped by signature. Each unique signature
        becomes one ThreatSummary with count and unique source IPs.

        Args:
            events: List of events (all blocked or all detected)

        Returns:
            List of ThreatSummary objects
        """
        if not events:
            return []

        # Group by signature for deduplication
        signature_data: Dict[str, Dict] = defaultdict(lambda: {
            "events": [],
            "source_ips": set(),
        })

        for event in events:
            data = signature_data[event.signature]
            data["events"].append(event)
            data["source_ips"].add(event.src_ip)

        # Create summaries
        summaries = []
        for signature, data in signature_data.items():
            event_list = data["events"]
            first_event = event_list[0]

            # Parse signature for friendly category name
            _, friendly_name, _ = parse_signature_category(signature)

            # Use category_friendly from event if available, else from parser
            if first_event.category_friendly:
                friendly_name = first_event.category_friendly

            # If still no friendly name, use raw category
            if not friendly_name or friendly_name == "Security Event":
                friendly_name = ET_CATEGORY_FRIENDLY_NAMES.get(
                    first_event.category_raw.upper(),
                    first_event.category_raw.title() if first_event.category_raw else "Security Event"
                )

            # Use the highest severity among events with this signature
            # severity is int: 1=high, 2=medium, 3=low (lower is worse)
            min_severity_int = min(e.severity for e in event_list)
            max_severity = _int_severity_to_enum(min_severity_int)

            # Get remediation guidance for this threat
            remediation_context = {
                "src_ip": list(data["source_ips"])[0] if data["source_ips"] else "[unknown]",
                "dest_ip": first_event.dest_ip,
                "signature": signature,
            }
            remediation_text = get_remediation(
                first_event.category_raw,
                max_severity,
                remediation_context,
            )

            # Count Cybersecure (ET PRO) events in this signature group
            cybersecure_count = sum(1 for e in event_list if e.is_cybersecure)

            summary = ThreatSummary(
                category_friendly=friendly_name,
                description=_get_category_description(first_event.category_raw),
                count=len(event_list),
                severity=max_severity,
                sample_signature=signature,
                source_ips=list(data["source_ips"]),
                remediation=remediation_text,
                is_cybersecure=cybersecure_count > 0,
                cybersecure_count=cybersecure_count,
            )
            summaries.append(summary)

        # Sort by severity (severe first) then by count
        severity_order = {Severity.SEVERE: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
        summaries.sort(key=lambda s: (severity_order.get(s.severity, 99), -s.count))

        return summaries

    def _group_by_category(
        self, events: List[IPSEvent]
    ) -> Dict[str, List[IPSEvent]]:
        """Group events by category.

        Args:
            events: List of events

        Returns:
            Dict mapping category to events
        """
        grouped: Dict[str, List[IPSEvent]] = defaultdict(list)
        for event in events:
            grouped[event.category_raw].append(event)
        return dict(grouped)

    def _detect_detection_mode(self, events: List[IPSEvent]) -> Optional[str]:
        """Check if all events are detection-only.

        Args:
            events: List of all events

        Returns:
            Note string if all detected-only, None otherwise
        """
        if not events:
            return None

        # If any event is blocked, IPS is not in detection-only mode
        has_blocked = any(e.is_blocked for e in events)

        if has_blocked:
            return None

        return (
            "Note: IPS is in detection mode. "
            "Threats are logged but not blocked."
        )
