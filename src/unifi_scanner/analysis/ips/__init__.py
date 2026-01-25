"""IPS analysis module for threat detection and aggregation."""

from unifi_scanner.analysis.ips.analyzer import (
    IPSAnalyzer,
    ThreatAnalysisResult,
    ThreatSummary,
)
from unifi_scanner.analysis.ips.aggregator import (
    SourceIPSummary,
    aggregate_source_ips,
)
from unifi_scanner.analysis.ips.models import IPSEvent

__all__ = [
    "IPSAnalyzer",
    "ThreatAnalysisResult",
    "ThreatSummary",
    "SourceIPSummary",
    "aggregate_source_ips",
    "IPSEvent",
]
