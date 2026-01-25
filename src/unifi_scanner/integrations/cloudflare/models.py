"""Pydantic models for Cloudflare API responses.

Models for:
- WAF events (firewall blocks, challenges, rate limits)
- DNS analytics (query counts, response types)
- Tunnel status (cloudflared tunnel health)
- Combined CloudflareData container with helper methods
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class WAFEvent(BaseModel):
    """A single WAF event from Cloudflare firewall analytics.

    Represents blocked requests, challenges, or rate-limited traffic.
    """

    timestamp: datetime = Field(description="When the event occurred")
    action: Literal["block", "challenge", "managed_challenge", "js_challenge", "log"] = Field(
        description="Action taken by WAF rule"
    )
    source_ip: str = Field(description="Client IP that triggered the rule")
    rule_id: Optional[str] = Field(default=None, description="ID of the rule that matched")
    rule_source: str = Field(
        description="Source of the rule: waf, firewall_rules, rate_limit, bot_management"
    )
    host: Optional[str] = Field(default=None, description="Target hostname")
    path: Optional[str] = Field(default=None, description="Request path")
    country: Optional[str] = Field(default=None, description="Client country code (2-letter ISO)")
    user_agent: Optional[str] = Field(default=None, description="Client user agent string")
    ray_id: Optional[str] = Field(default=None, description="Cloudflare ray ID for debugging")


class DNSAnalytics(BaseModel):
    """DNS query analytics for a zone.

    Aggregated statistics about DNS resolution.
    """

    zone_name: str = Field(description="Zone domain name")
    total_queries: int = Field(ge=0, description="Total DNS queries in period")
    noerror_count: int = Field(ge=0, default=0, description="Successful responses (NOERROR)")
    nxdomain_count: int = Field(ge=0, default=0, description="Non-existent domain responses")
    servfail_count: int = Field(ge=0, default=0, description="Server failure responses")
    query_types: dict[str, int] = Field(
        default_factory=dict,
        description="Query counts by type (A, AAAA, CNAME, MX, etc.)",
    )
    period_start: datetime = Field(description="Start of analytics period")
    period_end: datetime = Field(description="End of analytics period")


class TunnelStatus(BaseModel):
    """Status of a Cloudflare Tunnel (cloudflared).

    Represents tunnel health and connection state.
    """

    tunnel_id: str = Field(description="Unique tunnel identifier")
    tunnel_name: str = Field(description="Human-readable tunnel name")
    status: Literal["healthy", "degraded", "down", "inactive"] = Field(
        description="Current tunnel health status"
    )
    connections_count: int = Field(ge=0, default=0, description="Active connector count")
    created_at: Optional[datetime] = Field(default=None, description="Tunnel creation time")
    connections: List[TunnelConnection] = Field(
        default_factory=list,
        description="Individual connector details",
    )


class TunnelConnection(BaseModel):
    """A single cloudflared connector connection.

    Each tunnel can have multiple connectors for redundancy.
    """

    colo_name: str = Field(description="Cloudflare datacenter location (e.g., 'SJC', 'LAX')")
    is_pending_reconnect: bool = Field(default=False, description="Connection is reconnecting")
    client_id: Optional[str] = Field(default=None, description="Connector client UUID")
    opened_at: Optional[datetime] = Field(default=None, description="Connection establish time")


# Update TunnelStatus to use forward reference
TunnelStatus.model_rebuild()


class CloudflareData(BaseModel):
    """Combined container for all Cloudflare data.

    Provides helper methods for analysis and reporting.
    """

    waf_events: List[WAFEvent] = Field(default_factory=list, description="WAF events in period")
    dns_analytics: List[DNSAnalytics] = Field(
        default_factory=list, description="DNS stats per zone"
    )
    tunnel_statuses: List[TunnelStatus] = Field(
        default_factory=list, description="Tunnel health data"
    )
    collected_at: datetime = Field(
        default_factory=datetime.utcnow, description="When data was fetched"
    )
    errors: List[str] = Field(
        default_factory=list, description="Non-fatal errors during collection"
    )

    @property
    def has_waf_events(self) -> bool:
        """Check if any WAF events were collected."""
        return len(self.waf_events) > 0

    @property
    def has_dns_analytics(self) -> bool:
        """Check if any DNS analytics were collected."""
        return len(self.dns_analytics) > 0

    @property
    def has_tunnel_statuses(self) -> bool:
        """Check if any tunnel statuses were collected."""
        return len(self.tunnel_statuses) > 0

    @property
    def blocked_event_count(self) -> int:
        """Count of WAF events with blocking action (not just logged)."""
        return sum(1 for e in self.waf_events if e.action in ("block", "managed_challenge"))

    def get_top_blocked_ips(self, limit: int = 10) -> List[tuple[str, int]]:
        """Get IPs with most blocked requests.

        Args:
            limit: Maximum number of IPs to return.

        Returns:
            List of (ip, count) tuples sorted by count descending.
        """
        blocked = [e.source_ip for e in self.waf_events if e.action == "block"]
        return Counter(blocked).most_common(limit)

    def get_top_blocked_countries(self, limit: int = 10) -> List[tuple[str, int]]:
        """Get countries with most blocked requests.

        Args:
            limit: Maximum number of countries to return.

        Returns:
            List of (country_code, count) tuples sorted by count descending.
        """
        blocked = [
            e.country for e in self.waf_events if e.action == "block" and e.country is not None
        ]
        return Counter(blocked).most_common(limit)

    def get_unhealthy_tunnels(self) -> List[TunnelStatus]:
        """Get tunnels that are not in healthy state."""
        return [t for t in self.tunnel_statuses if t.status != "healthy"]

    def total_dns_queries(self) -> int:
        """Sum of all DNS queries across zones."""
        return sum(d.total_queries for d in self.dns_analytics)
