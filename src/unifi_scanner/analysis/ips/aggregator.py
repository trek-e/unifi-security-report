"""IP aggregation utilities for IPS analysis."""

import ipaddress
from collections import defaultdict
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


def _is_internal_ip(ip_str: str) -> bool:
    """Check if an IP address is internal (RFC1918 private).

    Args:
        ip_str: IP address string

    Returns:
        True if private/internal, False if public/external
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private
    except ValueError:
        # Invalid IP format - treat as external for safety
        return False


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
    if not events:
        return []

    # Aggregate events by source IP
    # Use src_ip to match the pydantic IPSEvent model
    ip_data: Dict[str, Dict] = defaultdict(lambda: {
        "count": 0,
        "categories": defaultdict(int),
        "signatures": set(),
    })

    for event in events:
        data = ip_data[event.src_ip]
        data["count"] += 1
        data["categories"][event.category_raw] += 1
        data["signatures"].add(event.signature)

    # Filter by threshold and create summaries
    summaries = []
    for ip, data in ip_data.items():
        if data["count"] >= threshold:
            summary = SourceIPSummary(
                ip=ip,
                total_events=data["count"],
                category_breakdown=dict(data["categories"]),
                is_internal=_is_internal_ip(ip),
                sample_signatures=data["signatures"],
            )
            summaries.append(summary)

    # Sort by total events descending
    summaries.sort(key=lambda s: s.total_events, reverse=True)

    return summaries
