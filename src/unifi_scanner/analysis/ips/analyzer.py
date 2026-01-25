"""IPS analyzer for threat analysis and aggregation."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from unifi_scanner.models.enums import Severity
from unifi_scanner.analysis.ips.models import IPSEvent
from unifi_scanner.analysis.ips.aggregator import SourceIPSummary, aggregate_source_ips


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
    """

    category_friendly: str
    description: str
    count: int
    severity: Severity
    sample_signature: str
    source_ips: List[str] = field(default_factory=list)


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
        # Stub - will fail tests
        raise NotImplementedError("process_events not implemented")

    def _separate_blocked_detected(
        self, events: List[IPSEvent]
    ) -> Tuple[List[IPSEvent], List[IPSEvent]]:
        """Separate events into blocked and detected lists.

        Args:
            events: List of all events

        Returns:
            Tuple of (blocked_events, detected_events)
        """
        raise NotImplementedError()

    def _group_by_category(
        self, events: List[IPSEvent]
    ) -> Dict[str, List[IPSEvent]]:
        """Group events by category.

        Args:
            events: List of events

        Returns:
            Dict mapping category to events
        """
        raise NotImplementedError()

    def _detect_detection_mode(self, events: List[IPSEvent]) -> Optional[str]:
        """Check if all events are detection-only.

        Args:
            events: List of all events

        Returns:
            Note string if all detected-only, None otherwise
        """
        raise NotImplementedError()
