"""CloudflareIntegration implementing the Integration Protocol.

Provides WAF events, DNS analytics, and tunnel status for the security report.
Registered with IntegrationRegistry at module import time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import structlog

from unifi_scanner.integrations.base import Integration, IntegrationResult
from unifi_scanner.integrations.cloudflare.client import CloudflareClient
from unifi_scanner.integrations.cloudflare.models import CloudflareData
from unifi_scanner.integrations.registry import IntegrationRegistry

if TYPE_CHECKING:
    from unifi_scanner.config.settings import UnifiSettings

log = structlog.get_logger()


class CloudflareIntegration:
    """Cloudflare integration for WAF, DNS, and tunnel data.

    Implements the Integration Protocol from Phase 10 infrastructure.
    Automatically registered with IntegrationRegistry at module import.

    Configuration:
        - CLOUDFLARE_API_TOKEN (required): Scoped API token
        - CLOUDFLARE_ACCOUNT_ID (optional): Account ID for tunnels/DNS

    Per CONTEXT.md:
        - API Token only, not legacy global API key
        - Silent skip if not configured (is_configured()=False means
          IntegrationRegistry.get_configured() excludes this integration,
          so IntegrationRunner never calls it - no cleanup needed)
        - Warning if partial config (token without account_id for tunnels)
    """

    def __init__(self, settings: "UnifiSettings") -> None:
        """Initialize with settings.

        Args:
            settings: Application settings containing Cloudflare credentials.
        """
        self._settings = settings
        self._token = getattr(settings, "cloudflare_api_token", None)
        self._account_id = getattr(settings, "cloudflare_account_id", None)

    @property
    def name(self) -> str:
        """Unique integration identifier."""
        return "cloudflare"

    def is_configured(self) -> bool:
        """Check if integration has required credentials.

        Per CONTEXT.md: API token is the only required credential.
        Account ID is optional (can be auto-discovered from zones).

        When this returns False:
        - IntegrationRegistry.get_configured() excludes this integration
        - IntegrationRunner never instantiates or calls fetch()
        - No cleanup/disconnection needed - integration is simply not used
        - This is the expected behavior when credentials are removed

        Returns:
            True if API token is set, False otherwise (silent skip).
        """
        return bool(self._token)

    def validate_config(self) -> Optional[str]:
        """Validate configuration completeness.

        Per CONTEXT.md: Warn if partial config.
        Token without account_id means tunnels might not work if zone
        discovery fails to find account ID.

        Returns:
            Warning message if partial config, None otherwise.
        """
        if self._token and not self._account_id:
            return (
                "CLOUDFLARE_ACCOUNT_ID not set. "
                "Tunnel status may not be available if account ID cannot be auto-discovered."
            )
        return None

    async def fetch(self) -> IntegrationResult:
        """Fetch data from Cloudflare APIs.

        Creates CloudflareClient and fetches WAF events, DNS analytics,
        and tunnel status. Lookback uses initial_lookback_hours from settings.

        Returns:
            IntegrationResult with CloudflareData or error message.

        Raises:
            Exception: Any error from API calls (caught by IntegrationRunner).
        """
        if not self._token:
            return IntegrationResult(
                name=self.name,
                success=False,
                error="Not configured",
            )

        # Get lookback from settings (same as report window)
        lookback_hours = getattr(self._settings, "initial_lookback_hours", 24)

        log.info(
            "cloudflare_fetch_start",
            lookback_hours=lookback_hours,
            has_account_id=bool(self._account_id),
        )

        client = CloudflareClient(
            api_token=self._token,
            account_id=self._account_id,
        )

        try:
            data = await client.fetch_all(lookback_hours=lookback_hours)

            log.info(
                "cloudflare_fetch_complete",
                waf_events=len(data.waf_events),
                has_dns=data.has_dns_analytics,
                tunnels=len(data.tunnel_statuses),
            )

            # Convert CloudflareData to dict for IntegrationResult.data
            return IntegrationResult(
                name=self.name,
                success=True,
                data=self._data_to_dict(data),
            )
        finally:
            client.close()

    def _data_to_dict(self, data: CloudflareData) -> dict:
        """Convert CloudflareData to dict for template rendering.

        Formats data for Jinja2 template consumption with helper values.
        """
        return {
            # WAF events
            "waf_events": [e.model_dump() for e in data.waf_events],
            "top_blocked_ips": data.get_top_blocked_ips(10),
            "top_blocked_countries": data.get_top_blocked_countries(10),
            "has_waf_events": data.has_waf_events,
            "waf_count": len(data.waf_events),
            "blocked_count": data.blocked_event_count,
            # DNS analytics
            "dns_analytics": [d.model_dump() for d in data.dns_analytics],
            "has_dns_analytics": data.has_dns_analytics,
            "total_dns_queries": data.total_dns_queries(),
            # Tunnels
            "tunnels": [t.model_dump() for t in data.tunnel_statuses],
            "has_tunnels": data.has_tunnel_statuses,
            "unhealthy_tunnels": [t.model_dump() for t in data.get_unhealthy_tunnels()],
            "has_unhealthy_tunnels": len(data.get_unhealthy_tunnels()) > 0,
            # Errors during collection
            "collection_errors": data.errors,
            "has_collection_errors": len(data.errors) > 0,
        }


# Register at module import time (per Phase 10 pattern)
IntegrationRegistry.register(CloudflareIntegration)
