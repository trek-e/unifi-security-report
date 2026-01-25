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
from unifi_scanner.analysis.ips.signature_parser import (
    ET_CATEGORY_FRIENDLY_NAMES,
    is_action_blocked,
    parse_signature_category,
)
from unifi_scanner.analysis.ips.remediation import (
    get_remediation,
    get_false_positive_note,
    IPS_REMEDIATION_TEMPLATES,
)

__all__ = [
    "IPSAnalyzer",
    "ThreatAnalysisResult",
    "ThreatSummary",
    "SourceIPSummary",
    "aggregate_source_ips",
    "IPSEvent",
    "parse_signature_category",
    "is_action_blocked",
    "ET_CATEGORY_FRIENDLY_NAMES",
    "get_remediation",
    "get_false_positive_note",
    "IPS_REMEDIATION_TEMPLATES",
]
