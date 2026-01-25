"""Cloudflare API client for WAF events, DNS analytics, and tunnel status.

Uses:
- httpx for GraphQL queries (WAF events, DNS analytics)
- cloudflare SDK for REST API (tunnels)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
import structlog

from .models import (
    CloudflareData,
    DNSAnalytics,
    TunnelConnection,
    TunnelStatus,
    WAFEvent,
)

logger = structlog.get_logger(__name__)

GRAPHQL_ENDPOINT = "https://api.cloudflare.com/client/v4/graphql"


class CloudflareClient:
    """Client for fetching data from Cloudflare APIs.

    Combines GraphQL queries for analytics data and REST API for tunnel status.
    """

    def __init__(
        self,
        api_token: str,
        account_id: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize Cloudflare client.

        Args:
            api_token: Cloudflare API token with appropriate permissions.
            account_id: Cloudflare account ID. If not provided, will be
                discovered from zones. Required for tunnel status.
            timeout: Request timeout in seconds.
        """
        self.api_token = api_token
        self.account_id = account_id
        self.timeout = timeout
        self._zones: Optional[list[dict[str, Any]]] = None
        self._http_client: Optional[httpx.Client] = None

    @property
    def http_client(self) -> httpx.Client:
        """Lazy-initialize HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.Client(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
            )
        return self._http_client

    def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None

    def __enter__(self) -> "CloudflareClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    async def fetch_all(
        self,
        lookback_hours: int = 24,
    ) -> CloudflareData:
        """Fetch all Cloudflare data: WAF events, DNS analytics, and tunnel status.

        Args:
            lookback_hours: Hours of history to fetch for events/analytics.

        Returns:
            CloudflareData container with all fetched data.
        """
        errors: list[str] = []
        waf_events: list[WAFEvent] = []
        dns_analytics: list[DNSAnalytics] = []
        tunnel_statuses: list[TunnelStatus] = []

        # Discover account ID from zones if not provided
        if self.account_id is None:
            try:
                self._discover_account_id()
            except Exception as e:
                errors.append(f"Failed to discover account ID: {e}")
                logger.warning("cloudflare_account_discovery_failed", error=str(e))

        # Fetch WAF events
        try:
            waf_events = self._fetch_waf_events(lookback_hours=lookback_hours)
            logger.info("cloudflare_waf_events_fetched", count=len(waf_events))
        except Exception as e:
            errors.append(f"Failed to fetch WAF events: {e}")
            logger.warning("cloudflare_waf_fetch_failed", error=str(e))

        # Fetch DNS analytics
        try:
            dns_analytics = self._fetch_dns_analytics(lookback_hours=lookback_hours)
            logger.info("cloudflare_dns_analytics_fetched", zones=len(dns_analytics))
        except Exception as e:
            errors.append(f"Failed to fetch DNS analytics: {e}")
            logger.warning("cloudflare_dns_fetch_failed", error=str(e))

        # Fetch tunnel status (requires account_id)
        if self.account_id:
            try:
                tunnel_statuses = self._fetch_tunnels()
                logger.info("cloudflare_tunnels_fetched", count=len(tunnel_statuses))
            except Exception as e:
                errors.append(f"Failed to fetch tunnel status: {e}")
                logger.warning("cloudflare_tunnels_fetch_failed", error=str(e))
        else:
            errors.append("Tunnel status skipped: account_id not available")

        return CloudflareData(
            waf_events=waf_events,
            dns_analytics=dns_analytics,
            tunnel_statuses=tunnel_statuses,
            collected_at=datetime.now(timezone.utc),
            errors=errors,
        )

    def _discover_account_id(self) -> None:
        """Discover account ID from zones list."""
        zones = self._get_zones()
        if zones and len(zones) > 0:
            # All zones should be in the same account
            account = zones[0].get("account", {})
            self.account_id = account.get("id")
            logger.debug(
                "cloudflare_account_discovered",
                account_id=self.account_id,
                zone_count=len(zones),
            )

    def _get_zones(self) -> list[dict[str, Any]]:
        """Get list of zones for the account (cached)."""
        if self._zones is not None:
            return self._zones

        response = self.http_client.get(
            "https://api.cloudflare.com/client/v4/zones",
            params={"per_page": 50},
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("success", False):
            errors = data.get("errors", [])
            raise RuntimeError(f"Cloudflare API error: {errors}")

        self._zones = data.get("result", [])
        return self._zones

    def _fetch_waf_events(self, lookback_hours: int = 24) -> list[WAFEvent]:
        """Fetch WAF events using GraphQL.

        Args:
            lookback_hours: Hours of history to fetch.

        Returns:
            List of WAFEvent objects.
        """
        zones = self._get_zones()
        if not zones:
            return []

        # Build time filter
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=lookback_hours)

        events: list[WAFEvent] = []

        for zone in zones:
            zone_id = zone.get("id")
            zone_name = zone.get("name")

            query = """
            query GetFirewallEvents($zoneTag: string!, $since: Time!, $until: Time!) {
                viewer {
                    zones(filter: {zoneTag: $zoneTag}) {
                        firewallEventsAdaptive(
                            filter: {
                                datetime_gt: $since,
                                datetime_lt: $until
                            },
                            limit: 1000,
                            orderBy: [datetime_DESC]
                        ) {
                            datetime
                            action
                            clientIP
                            ruleId
                            source
                            clientRequestHTTPHost
                            clientRequestPath
                            clientCountryName
                            userAgent
                            rayName
                        }
                    }
                }
            }
            """

            variables = {
                "zoneTag": zone_id,
                "since": start_time.isoformat(),
                "until": end_time.isoformat(),
            }

            try:
                response = self.http_client.post(
                    GRAPHQL_ENDPOINT,
                    json={"query": query, "variables": variables},
                )
                response.raise_for_status()
                data = response.json()

                # Navigate GraphQL response
                viewer = data.get("data", {}).get("viewer", {})
                zones_data = viewer.get("zones", [])
                if zones_data:
                    fw_events = zones_data[0].get("firewallEventsAdaptive", [])
                    for event in fw_events:
                        try:
                            # Map GraphQL action to our Literal type
                            action = self._map_waf_action(event.get("action", "log"))
                            events.append(
                                WAFEvent(
                                    timestamp=datetime.fromisoformat(
                                        event["datetime"].replace("Z", "+00:00")
                                    ),
                                    action=action,
                                    source_ip=event.get("clientIP", "unknown"),
                                    rule_id=event.get("ruleId"),
                                    rule_source=event.get("source", "unknown"),
                                    host=event.get("clientRequestHTTPHost"),
                                    path=event.get("clientRequestPath"),
                                    country=event.get("clientCountryName"),
                                    user_agent=event.get("userAgent"),
                                    ray_id=event.get("rayName"),
                                )
                            )
                        except Exception as e:
                            logger.debug(
                                "cloudflare_waf_event_parse_error",
                                zone=zone_name,
                                error=str(e),
                            )

            except httpx.HTTPError as e:
                logger.warning(
                    "cloudflare_waf_zone_fetch_failed",
                    zone=zone_name,
                    error=str(e),
                )

        return events

    def _map_waf_action(self, action: str) -> str:
        """Map Cloudflare WAF action to our Literal type.

        Args:
            action: Raw action string from API.

        Returns:
            One of: block, challenge, managed_challenge, js_challenge, log
        """
        action_lower = action.lower()
        if action_lower in ("block", "drop"):
            return "block"
        elif action_lower in ("challenge", "jschallenge"):
            return "js_challenge"
        elif action_lower == "managed_challenge":
            return "managed_challenge"
        elif action_lower == "allow":
            return "log"  # Allowed but logged
        return "log"

    def _fetch_dns_analytics(self, lookback_hours: int = 24) -> list[DNSAnalytics]:
        """Fetch DNS analytics using GraphQL.

        Args:
            lookback_hours: Hours of history to fetch.

        Returns:
            List of DNSAnalytics objects (one per zone).
        """
        zones = self._get_zones()
        if not zones:
            return []

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=lookback_hours)

        analytics: list[DNSAnalytics] = []

        for zone in zones:
            zone_id = zone.get("id")
            zone_name = zone.get("name", "unknown")

            query = """
            query GetDNSAnalytics($zoneTag: string!, $since: Time!, $until: Time!) {
                viewer {
                    zones(filter: {zoneTag: $zoneTag}) {
                        dnsAnalyticsAdaptiveGroups(
                            filter: {
                                datetime_gt: $since,
                                datetime_lt: $until
                            },
                            limit: 100
                        ) {
                            count
                            dimensions {
                                queryType
                                responseCode
                            }
                        }
                    }
                }
            }
            """

            variables = {
                "zoneTag": zone_id,
                "since": start_time.isoformat(),
                "until": end_time.isoformat(),
            }

            try:
                response = self.http_client.post(
                    GRAPHQL_ENDPOINT,
                    json={"query": query, "variables": variables},
                )
                response.raise_for_status()
                data = response.json()

                # Navigate GraphQL response
                viewer = data.get("data", {}).get("viewer", {})
                zones_data = viewer.get("zones", [])

                total_queries = 0
                noerror = 0
                nxdomain = 0
                servfail = 0
                query_types: dict[str, int] = {}

                if zones_data:
                    groups = zones_data[0].get("dnsAnalyticsAdaptiveGroups", [])
                    for group in groups:
                        count = group.get("count", 0)
                        dims = group.get("dimensions", {})
                        query_type = dims.get("queryType", "UNKNOWN")
                        response_code = dims.get("responseCode", 0)

                        total_queries += count
                        query_types[query_type] = query_types.get(query_type, 0) + count

                        # Aggregate by response code
                        if response_code == 0:  # NOERROR
                            noerror += count
                        elif response_code == 3:  # NXDOMAIN
                            nxdomain += count
                        elif response_code == 2:  # SERVFAIL
                            servfail += count

                if total_queries > 0:
                    analytics.append(
                        DNSAnalytics(
                            zone_name=zone_name,
                            total_queries=total_queries,
                            noerror_count=noerror,
                            nxdomain_count=nxdomain,
                            servfail_count=servfail,
                            query_types=query_types,
                            period_start=start_time,
                            period_end=end_time,
                        )
                    )

            except httpx.HTTPError as e:
                logger.warning(
                    "cloudflare_dns_zone_fetch_failed",
                    zone=zone_name,
                    error=str(e),
                )

        return analytics

    def _fetch_tunnels(self) -> list[TunnelStatus]:
        """Fetch tunnel status using REST API.

        Returns:
            List of TunnelStatus objects.
        """
        if not self.account_id:
            return []

        response = self.http_client.get(
            f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/cfd_tunnel",
            params={"per_page": 50},
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("success", False):
            errors = data.get("errors", [])
            raise RuntimeError(f"Cloudflare API error: {errors}")

        tunnels: list[TunnelStatus] = []

        for tunnel in data.get("result", []):
            tunnel_id = tunnel.get("id", "")
            tunnel_name = tunnel.get("name", "unknown")

            # Map status
            status_raw = tunnel.get("status", "inactive")
            status = self._map_tunnel_status(status_raw)

            # Parse connections
            connections: list[TunnelConnection] = []
            for conn in tunnel.get("connections", []):
                opened_at = None
                if conn.get("opened_at"):
                    try:
                        opened_at = datetime.fromisoformat(
                            conn["opened_at"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                connections.append(
                    TunnelConnection(
                        colo_name=conn.get("colo_name", "unknown"),
                        is_pending_reconnect=conn.get("is_pending_reconnect", False),
                        client_id=conn.get("client_id"),
                        opened_at=opened_at,
                    )
                )

            # Parse created_at
            created_at = None
            if tunnel.get("created_at"):
                try:
                    created_at = datetime.fromisoformat(
                        tunnel["created_at"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            tunnels.append(
                TunnelStatus(
                    tunnel_id=tunnel_id,
                    tunnel_name=tunnel_name,
                    status=status,
                    connections_count=len(connections),
                    created_at=created_at,
                    connections=connections,
                )
            )

        return tunnels

    def _map_tunnel_status(self, status: str) -> str:
        """Map Cloudflare tunnel status to our Literal type.

        Args:
            status: Raw status string from API.

        Returns:
            One of: healthy, degraded, down, inactive
        """
        status_lower = status.lower()
        if status_lower == "healthy":
            return "healthy"
        elif status_lower == "degraded":
            return "degraded"
        elif status_lower in ("down", "offline"):
            return "down"
        return "inactive"
