"""IP aggregation utilities for IPS analysis."""

from typing import Dict, List, NamedTuple, Set

from unifi_scanner.analysis.ips.models import IPSEvent


class SourceIPSummary(NamedTuple):
    """Summary of events from a single source IP.

    Attributes:
        ip: The source IP address
        total_events: Total number of events from this IP
        category_breakdown: Dict mapping category to event count
        is_internal: True if IP is RFC1918 private address
        sample_signatures: Set of sample signatures from this IP
    """

    ip: str
    total_events: int
    category_breakdown: Dict[str, int]
    is_internal: bool
    sample_signatures: Set[str]


def aggregate_source_ips(
    events: List[IPSEvent],
    threshold: int = 10,
) -> List[SourceIPSummary]:
    """Aggregate IPS events by source IP with threshold filtering.

    Only includes IPs that have at least threshold events.
    Results are sorted by total_events descending.

    Args:
        events: List of IPS events to aggregate
        threshold: Minimum events to include an IP (default: 10)

    Returns:
        List of SourceIPSummary for IPs meeting threshold
    """
    # Stub - will fail tests
    raise NotImplementedError("aggregate_source_ips not implemented")
