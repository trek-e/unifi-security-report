"""Tests for Cloudflare integration.

Tests models, client mocking, integration Protocol compliance, and template rendering.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from unifi_scanner.integrations.base import IntegrationResult
from unifi_scanner.integrations.cloudflare.models import (
    CloudflareData,
    DNSAnalytics,
    TunnelConnection,
    TunnelStatus,
    WAFEvent,
)

if TYPE_CHECKING:
    pass


# ============================================================================
# Model Tests
# ============================================================================


class TestWAFEvent:
    """Tests for WAFEvent model."""

    def test_minimal_waf_event(self):
        """WAFEvent with only required fields."""
        event = WAFEvent(
            timestamp=datetime.now(timezone.utc),
            action="block",
            source_ip="1.2.3.4",
            rule_source="waf",
        )
        assert event.source_ip == "1.2.3.4"
        assert event.action == "block"
        assert event.country is None  # optional, defaults to None

    def test_full_waf_event(self):
        """WAFEvent with all fields populated."""
        event = WAFEvent(
            timestamp=datetime.now(timezone.utc),
            action="block",
            source_ip="1.2.3.4",
            country="CN",
            path="/admin",
            host="example.com",
            rule_source="firewallrules",
            rule_id="abc123",
            user_agent="bad-bot/1.0",
            ray_id="abc123def456",
        )
        assert event.country == "CN"
        assert event.host == "example.com"
        assert event.path == "/admin"
        assert event.ray_id == "abc123def456"

    def test_waf_event_actions(self):
        """WAFEvent accepts all valid action types."""
        for action in ["block", "challenge", "managed_challenge", "js_challenge", "log"]:
            event = WAFEvent(
                timestamp=datetime.now(timezone.utc),
                action=action,
                source_ip="1.2.3.4",
                rule_source="waf",
            )
            assert event.action == action


class TestDNSAnalytics:
    """Tests for DNSAnalytics model."""

    def test_dns_analytics_required_fields(self):
        """DNSAnalytics with required fields."""
        now = datetime.now(timezone.utc)
        analytics = DNSAnalytics(
            zone_name="example.com",
            total_queries=1000,
            period_start=now,
            period_end=now,
        )
        assert analytics.zone_name == "example.com"
        assert analytics.total_queries == 1000
        assert analytics.noerror_count == 0  # default
        assert analytics.nxdomain_count == 0  # default
        assert analytics.servfail_count == 0  # default
        assert analytics.query_types == {}  # default

    def test_dns_analytics_full(self):
        """DNSAnalytics with all fields populated."""
        now = datetime.now(timezone.utc)
        analytics = DNSAnalytics(
            zone_name="example.com",
            total_queries=1000,
            noerror_count=950,
            nxdomain_count=30,
            servfail_count=20,
            query_types={"A": 500, "AAAA": 300, "MX": 100, "TXT": 100},
            period_start=now,
            period_end=now,
        )
        assert analytics.total_queries == 1000
        assert analytics.noerror_count == 950
        assert analytics.nxdomain_count == 30
        assert analytics.servfail_count == 20
        assert analytics.query_types["A"] == 500


class TestTunnelStatus:
    """Tests for TunnelStatus model."""

    def test_tunnel_status_required_fields(self):
        """TunnelStatus with required fields."""
        tunnel = TunnelStatus(
            tunnel_id="abc123",
            tunnel_name="prod-tunnel",
            status="healthy",
        )
        assert tunnel.tunnel_name == "prod-tunnel"
        assert tunnel.status == "healthy"
        assert tunnel.connections_count == 0  # default
        assert tunnel.connections == []  # default

    def test_tunnel_status_with_connections(self):
        """TunnelStatus with connections."""
        tunnel = TunnelStatus(
            tunnel_id="abc123",
            tunnel_name="prod-tunnel",
            status="healthy",
            connections_count=2,
            connections=[
                TunnelConnection(colo_name="SJC", is_pending_reconnect=False),
                TunnelConnection(colo_name="LAX", is_pending_reconnect=False),
            ],
        )
        assert tunnel.connections_count == 2
        assert len(tunnel.connections) == 2
        assert tunnel.connections[0].colo_name == "SJC"

    def test_tunnel_status_values(self):
        """TunnelStatus accepts valid status values."""
        for status in ["healthy", "degraded", "down", "inactive"]:
            tunnel = TunnelStatus(
                tunnel_id="abc123",
                tunnel_name="test",
                status=status,
            )
            assert tunnel.status == status


class TestTunnelConnection:
    """Tests for TunnelConnection model."""

    def test_tunnel_connection(self):
        """TunnelConnection model."""
        conn = TunnelConnection(
            colo_name="SJC",
            is_pending_reconnect=False,
            client_id="client-123",
            opened_at=datetime.now(timezone.utc),
        )
        assert conn.colo_name == "SJC"
        assert conn.is_pending_reconnect is False
        assert conn.client_id == "client-123"


class TestCloudflareData:
    """Tests for CloudflareData aggregation model."""

    def test_empty_cloudflare_data(self):
        """CloudflareData with no data."""
        data = CloudflareData()
        assert not data.has_waf_events
        assert not data.has_dns_analytics
        assert not data.has_tunnel_statuses
        assert data.blocked_event_count == 0

    def test_cloudflare_data_with_waf_events(self):
        """CloudflareData with WAF events."""
        events = [
            WAFEvent(
                timestamp=datetime.now(timezone.utc),
                action="block",
                source_ip="1.2.3.4",
                rule_source="waf",
                country="CN",
            ),
            WAFEvent(
                timestamp=datetime.now(timezone.utc),
                action="block",
                source_ip="1.2.3.4",
                rule_source="waf",
                country="CN",
            ),
            WAFEvent(
                timestamp=datetime.now(timezone.utc),
                action="block",
                source_ip="5.6.7.8",
                rule_source="firewallrules",
                country="RU",
            ),
            WAFEvent(
                timestamp=datetime.now(timezone.utc),
                action="log",  # Not a block
                source_ip="9.9.9.9",
                rule_source="waf",
            ),
        ]
        data = CloudflareData(waf_events=events)

        assert data.has_waf_events
        assert len(data.waf_events) == 4

        # Test blocked_event_count (only block and managed_challenge)
        assert data.blocked_event_count == 3

        # Test top IPs (only blocked, not logged)
        top_ips = data.get_top_blocked_ips()
        assert top_ips[0] == ("1.2.3.4", 2)
        assert top_ips[1] == ("5.6.7.8", 1)

        # Test top countries
        top_countries = data.get_top_blocked_countries()
        assert top_countries[0] == ("CN", 2)
        assert top_countries[1] == ("RU", 1)

    def test_cloudflare_data_unhealthy_tunnels(self):
        """CloudflareData filters unhealthy tunnels."""
        tunnels = [
            TunnelStatus(tunnel_id="1", tunnel_name="prod", status="healthy"),
            TunnelStatus(tunnel_id="2", tunnel_name="dev", status="down"),
            TunnelStatus(tunnel_id="3", tunnel_name="staging", status="degraded"),
            TunnelStatus(tunnel_id="4", tunnel_name="old", status="inactive"),
        ]
        data = CloudflareData(tunnel_statuses=tunnels)

        assert data.has_tunnel_statuses
        unhealthy = data.get_unhealthy_tunnels()
        assert len(unhealthy) == 3
        names = [t.tunnel_name for t in unhealthy]
        assert "dev" in names
        assert "staging" in names
        assert "old" in names
        assert "prod" not in names

    def test_cloudflare_data_dns_total(self):
        """CloudflareData sums DNS queries across zones."""
        now = datetime.now(timezone.utc)
        dns = [
            DNSAnalytics(
                zone_name="example.com",
                total_queries=1000,
                period_start=now,
                period_end=now,
            ),
            DNSAnalytics(
                zone_name="other.com",
                total_queries=500,
                period_start=now,
                period_end=now,
            ),
        ]
        data = CloudflareData(dns_analytics=dns)

        assert data.has_dns_analytics
        assert data.total_dns_queries() == 1500

    def test_cloudflare_data_errors_field(self):
        """CloudflareData tracks collection errors."""
        data = CloudflareData(
            errors=["Failed to fetch WAF events", "Zone xyz unavailable"]
        )
        assert len(data.errors) == 2


# ============================================================================
# Integration Protocol Tests
# ============================================================================


class TestCloudflareIntegration:
    """Tests for CloudflareIntegration Protocol compliance."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.cloudflare_api_token = None
        settings.cloudflare_account_id = None
        settings.initial_lookback_hours = 24
        return settings

    def test_not_configured_without_token(self, mock_settings):
        """is_configured() returns False without token."""
        from unifi_scanner.integrations.cloudflare.integration import CloudflareIntegration

        integration = CloudflareIntegration(mock_settings)
        assert integration.name == "cloudflare"
        assert not integration.is_configured()

    def test_configured_with_token(self, mock_settings):
        """is_configured() returns True with token."""
        from unifi_scanner.integrations.cloudflare.integration import CloudflareIntegration

        mock_settings.cloudflare_api_token = "test_token"
        integration = CloudflareIntegration(mock_settings)
        assert integration.is_configured()

    def test_validate_config_warns_missing_account_id(self, mock_settings):
        """validate_config() warns when account_id missing."""
        from unifi_scanner.integrations.cloudflare.integration import CloudflareIntegration

        mock_settings.cloudflare_api_token = "test_token"
        integration = CloudflareIntegration(mock_settings)

        warning = integration.validate_config()
        assert warning is not None
        assert "CLOUDFLARE_ACCOUNT_ID" in warning

    def test_validate_config_no_warning_when_complete(self, mock_settings):
        """validate_config() returns None when fully configured."""
        from unifi_scanner.integrations.cloudflare.integration import CloudflareIntegration

        mock_settings.cloudflare_api_token = "test_token"
        mock_settings.cloudflare_account_id = "test_account"
        integration = CloudflareIntegration(mock_settings)

        warning = integration.validate_config()
        assert warning is None

    @pytest.mark.asyncio
    async def test_fetch_returns_error_when_not_configured(self, mock_settings):
        """fetch() returns error when not configured."""
        from unifi_scanner.integrations.cloudflare.integration import CloudflareIntegration

        integration = CloudflareIntegration(mock_settings)
        result = await integration.fetch()

        assert not result.success
        assert result.error == "Not configured"

    @pytest.mark.asyncio
    async def test_fetch_calls_client(self, mock_settings):
        """fetch() calls CloudflareClient.fetch_all()."""
        from unifi_scanner.integrations.cloudflare.integration import CloudflareIntegration

        mock_settings.cloudflare_api_token = "test_token"
        mock_settings.cloudflare_account_id = "test_account"

        integration = CloudflareIntegration(mock_settings)

        # Mock the client
        mock_data = CloudflareData(
            waf_events=[
                WAFEvent(
                    timestamp=datetime.now(timezone.utc),
                    action="block",
                    source_ip="1.2.3.4",
                    rule_source="waf",
                )
            ],
        )

        with patch(
            "unifi_scanner.integrations.cloudflare.integration.CloudflareClient"
        ) as MockClient:
            mock_instance = MagicMock()
            mock_instance.fetch_all = AsyncMock(return_value=mock_data)
            mock_instance.close = MagicMock()
            MockClient.return_value = mock_instance

            result = await integration.fetch()

            assert result.success
            assert result.data is not None
            assert result.data["waf_count"] == 1
            assert result.data["has_waf_events"] is True

    @pytest.mark.asyncio
    async def test_fetch_closes_client(self, mock_settings):
        """fetch() always closes client, even on success."""
        from unifi_scanner.integrations.cloudflare.integration import CloudflareIntegration

        mock_settings.cloudflare_api_token = "test_token"
        mock_settings.cloudflare_account_id = "test_account"

        integration = CloudflareIntegration(mock_settings)

        mock_data = CloudflareData()

        with patch(
            "unifi_scanner.integrations.cloudflare.integration.CloudflareClient"
        ) as MockClient:
            mock_instance = MagicMock()
            mock_instance.fetch_all = AsyncMock(return_value=mock_data)
            mock_instance.close = MagicMock()
            MockClient.return_value = mock_instance

            await integration.fetch()

            mock_instance.close.assert_called_once()


# ============================================================================
# Template Rendering Tests
# ============================================================================


class TestCloudflareTemplateRendering:
    """Tests for cloudflare_section.html template."""

    @pytest.fixture
    def jinja_env(self):
        """Create Jinja environment."""
        from jinja2 import Environment, FileSystemLoader

        return Environment(
            loader=FileSystemLoader("src/unifi_scanner/reports/templates")
        )

    def test_template_renders_with_waf_events(self, jinja_env):
        """Template renders WAF events section."""
        template = jinja_env.get_template("cloudflare_section.html")

        # Create actual CloudflareData object for template
        cloudflare = CloudflareData(
            waf_events=[
                WAFEvent(
                    timestamp=datetime.now(timezone.utc),
                    action="block",
                    source_ip="1.2.3.4",
                    country="CN",
                    host="example.com",
                    path="/admin",
                    rule_source="waf",
                ),
                WAFEvent(
                    timestamp=datetime.now(timezone.utc),
                    action="block",
                    source_ip="1.2.3.4",
                    country="CN",
                    host="example.com",
                    path="/wp-admin",
                    rule_source="waf",
                ),
            ],
        )

        html = template.render(cloudflare=cloudflare)

        assert "Cloudflare Security" in html
        assert "WAF Blocks" in html
        assert "1.2.3.4" in html
        assert "example.com" in html

    def test_template_renders_dns_analytics(self, jinja_env):
        """Template renders DNS analytics section."""
        template = jinja_env.get_template("cloudflare_section.html")

        now = datetime.now(timezone.utc)
        cloudflare = CloudflareData(
            dns_analytics=[
                DNSAnalytics(
                    zone_name="example.com",
                    total_queries=1000,
                    noerror_count=950,
                    nxdomain_count=30,
                    servfail_count=20,
                    period_start=now,
                    period_end=now,
                ),
            ],
        )

        html = template.render(cloudflare=cloudflare)

        assert "DNS Analytics" in html
        assert "1000" in html  # total
        assert "950" in html  # success
        assert "30" in html  # nxdomain

    def test_template_renders_tunnels(self, jinja_env):
        """Template renders tunnel status section."""
        template = jinja_env.get_template("cloudflare_section.html")

        cloudflare = CloudflareData(
            tunnel_statuses=[
                TunnelStatus(
                    tunnel_id="1",
                    tunnel_name="prod-tunnel",
                    status="healthy",
                    connections_count=2,
                ),
                TunnelStatus(
                    tunnel_id="2",
                    tunnel_name="dev-tunnel",
                    status="down",
                    connections_count=0,
                ),
            ],
        )

        html = template.render(cloudflare=cloudflare)

        assert "Tunnel Status" in html
        assert "prod-tunnel" in html
        assert "HEALTHY" in html
        assert "DOWN" in html
        assert "Tunnel Issues" in html  # Warning for down tunnel

    def test_template_skips_when_no_data(self, jinja_env):
        """Template renders nothing when no Cloudflare data."""
        template = jinja_env.get_template("cloudflare_section.html")

        # No data
        html = template.render(cloudflare=None)
        assert "Cloudflare" not in html

        # Empty data
        cloudflare = CloudflareData()
        html = template.render(cloudflare=cloudflare)
        assert "Cloudflare Security" not in html

    def test_template_renders_errors(self, jinja_env):
        """Template shows collection errors."""
        template = jinja_env.get_template("cloudflare_section.html")

        # Need at least some data to render the section
        cloudflare = CloudflareData(
            tunnel_statuses=[
                TunnelStatus(
                    tunnel_id="1",
                    tunnel_name="prod",
                    status="healthy",
                ),
            ],
            errors=["Failed to fetch WAF events from zone xyz"],
        )

        html = template.render(cloudflare=cloudflare)

        assert "Some Cloudflare data may be incomplete" in html
        assert "Failed to fetch WAF events" in html


# ============================================================================
# Data Conversion Tests
# ============================================================================


class TestCloudflareDataToDict:
    """Tests for CloudflareIntegration._data_to_dict method."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.cloudflare_api_token = "test_token"
        settings.cloudflare_account_id = "test_account"
        settings.initial_lookback_hours = 24
        return settings

    def test_data_to_dict_waf_events(self, mock_settings):
        """_data_to_dict converts WAF events correctly."""
        from unifi_scanner.integrations.cloudflare.integration import CloudflareIntegration

        integration = CloudflareIntegration(mock_settings)

        data = CloudflareData(
            waf_events=[
                WAFEvent(
                    timestamp=datetime.now(timezone.utc),
                    action="block",
                    source_ip="1.2.3.4",
                    rule_source="waf",
                    country="CN",
                ),
            ],
        )

        result = integration._data_to_dict(data)

        assert result["has_waf_events"] is True
        assert result["waf_count"] == 1
        assert result["blocked_count"] == 1
        assert len(result["top_blocked_ips"]) == 1
        assert result["top_blocked_ips"][0] == ("1.2.3.4", 1)

    def test_data_to_dict_tunnels(self, mock_settings):
        """_data_to_dict converts tunnel status correctly."""
        from unifi_scanner.integrations.cloudflare.integration import CloudflareIntegration

        integration = CloudflareIntegration(mock_settings)

        data = CloudflareData(
            tunnel_statuses=[
                TunnelStatus(
                    tunnel_id="1",
                    tunnel_name="prod",
                    status="healthy",
                ),
                TunnelStatus(
                    tunnel_id="2",
                    tunnel_name="dev",
                    status="down",
                ),
            ],
        )

        result = integration._data_to_dict(data)

        assert result["has_tunnels"] is True
        assert len(result["tunnels"]) == 2
        assert result["has_unhealthy_tunnels"] is True
        assert len(result["unhealthy_tunnels"]) == 1
        assert result["unhealthy_tunnels"][0]["tunnel_name"] == "dev"

    def test_data_to_dict_empty(self, mock_settings):
        """_data_to_dict handles empty data."""
        from unifi_scanner.integrations.cloudflare.integration import CloudflareIntegration

        integration = CloudflareIntegration(mock_settings)

        data = CloudflareData()

        result = integration._data_to_dict(data)

        assert result["has_waf_events"] is False
        assert result["waf_count"] == 0
        assert result["has_dns_analytics"] is False
        assert result["has_tunnels"] is False
        assert result["has_unhealthy_tunnels"] is False
