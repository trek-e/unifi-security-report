"""Tests for UniFi API client event and alarm retrieval."""

from unittest.mock import MagicMock

import httpx
import pytest

from unifi_scanner.api.client import UnifiClient
from unifi_scanner.config import UnifiSettings
from unifi_scanner.models import DeviceType


@pytest.fixture
def mock_settings():
    """Create mock UnifiSettings for testing."""
    return UnifiSettings(
        host="192.168.1.1",
        username="admin",
        password="secret",
        verify_ssl=False,
    )


@pytest.fixture
def connected_client(mock_settings):
    """Create a UnifiClient in connected state for testing."""
    client = UnifiClient(mock_settings)
    # Manually set connected state without actual connection
    client._client = MagicMock(spec=httpx.Client)
    client._authenticated = True
    client.device_type = DeviceType.UDM_PRO
    client.base_url = "https://192.168.1.1:443"
    client.api_prefix = "/proxy/network"
    return client


class TestGetEvents:
    """Tests for UnifiClient.get_events() method."""

    def test_get_events_returns_data(self, connected_client):
        """Test get_events returns event data from API response."""
        # Setup mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meta": {"rc": "ok"},
            "data": [
                {"key": "EVT_AP_Connected", "time": 1705084800000, "msg": "AP connected"}
            ],
        }
        connected_client._client.request.return_value = mock_response

        # Call method
        events = connected_client.get_events("default")

        # Verify
        assert len(events) == 1
        assert events[0]["key"] == "EVT_AP_Connected"
        assert events[0]["time"] == 1705084800000

    def test_get_events_sends_correct_request(self, connected_client):
        """Test get_events sends POST with correct body."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        connected_client._client.request.return_value = mock_response

        # Call with specific parameters
        connected_client.get_events("mysite", history_hours=24, start=100, limit=500)

        # Verify request was made with correct parameters
        call_args = connected_client._client.request.call_args
        assert call_args[0][0] == "POST"  # Method
        assert "/proxy/network/api/s/mysite/stat/event" in call_args[0][1]  # URL

        # Check JSON body
        json_body = call_args[1].get("json")
        assert json_body["_sort"] == "-time"
        assert json_body["within"] == 24
        assert json_body["_start"] == 100
        assert json_body["_limit"] == 500

    def test_get_events_limits_to_3000(self, connected_client):
        """Test get_events enforces 3000 limit maximum."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        connected_client._client.request.return_value = mock_response

        # Request more than 3000
        connected_client.get_events("default", limit=10000)

        # Verify limit was capped at 3000
        call_args = connected_client._client.request.call_args
        json_body = call_args[1].get("json")
        assert json_body["_limit"] == 3000

    def test_get_events_detects_truncation(self, connected_client, capsys):
        """Test get_events logs warning when API returns truncated results."""
        # Create response with truncation (count > data length)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meta": {"rc": "ok", "count": 5000},
            "data": [{"key": f"EVT_{i}"} for i in range(3000)],
        }
        connected_client._client.request.return_value = mock_response

        # Call method
        events = connected_client.get_events("default")

        # Verify truncation was logged (structlog writes to stdout)
        assert len(events) == 3000
        captured = capsys.readouterr()
        assert "events_truncated" in captured.out
        assert "5000" in captured.out  # total_available
        assert "3000" in captured.out  # retrieved

    def test_get_events_handles_empty_response(self, connected_client):
        """Test get_events handles empty data array."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"meta": {"rc": "ok"}, "data": []}
        connected_client._client.request.return_value = mock_response

        events = connected_client.get_events("default")

        assert events == []

    def test_get_events_handles_list_response(self, connected_client):
        """Test get_events handles response without wrapper."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"key": "EVT_Test"}]
        connected_client._client.request.return_value = mock_response

        events = connected_client.get_events("default")

        assert len(events) == 1
        assert events[0]["key"] == "EVT_Test"


class TestGetAlarms:
    """Tests for UnifiClient.get_alarms() method."""

    def test_get_alarms_returns_data(self, connected_client):
        """Test get_alarms returns alarm data from API response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meta": {"rc": "ok"},
            "data": [
                {"key": "EVT_IPS_Alert", "time": 1705084800000, "msg": "IPS alert triggered"}
            ],
        }
        connected_client._client.request.return_value = mock_response

        alarms = connected_client.get_alarms("default")

        assert len(alarms) == 1
        assert alarms[0]["key"] == "EVT_IPS_Alert"

    def test_get_alarms_sends_get_request(self, connected_client):
        """Test get_alarms sends GET request to correct endpoint."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        connected_client._client.request.return_value = mock_response

        connected_client.get_alarms("mysite")

        call_args = connected_client._client.request.call_args
        assert call_args[0][0] == "GET"  # Method
        assert "/proxy/network/api/s/mysite/list/alarm" in call_args[0][1]  # URL

    def test_get_alarms_filters_archived_true(self, connected_client):
        """Test get_alarms passes archived=true query param when archived=True."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        connected_client._client.request.return_value = mock_response

        connected_client.get_alarms("default", archived=True)

        call_args = connected_client._client.request.call_args
        params = call_args[1].get("params")
        assert params is not None
        assert params.get("archived") == "true"

    def test_get_alarms_filters_archived_false(self, connected_client):
        """Test get_alarms passes archived=false query param when archived=False."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        connected_client._client.request.return_value = mock_response

        connected_client.get_alarms("default", archived=False)

        call_args = connected_client._client.request.call_args
        params = call_args[1].get("params")
        assert params is not None
        assert params.get("archived") == "false"

    def test_get_alarms_no_archived_filter_when_none(self, connected_client):
        """Test get_alarms does not include archived param when archived=None."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        connected_client._client.request.return_value = mock_response

        connected_client.get_alarms("default", archived=None)

        call_args = connected_client._client.request.call_args
        params = call_args[1].get("params")
        # params should be None or not contain "archived"
        assert params is None or "archived" not in params

    def test_get_alarms_handles_empty_response(self, connected_client):
        """Test get_alarms handles empty data array."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"meta": {"rc": "ok"}, "data": []}
        connected_client._client.request.return_value = mock_response

        alarms = connected_client.get_alarms("default")

        assert alarms == []


class TestEndpointRouting:
    """Tests for endpoint routing based on device type."""

    def test_events_endpoint_udm_pro(self, mock_settings):
        """Test events endpoint uses UDM Pro path."""
        client = UnifiClient(mock_settings)
        client._client = MagicMock(spec=httpx.Client)
        client._authenticated = True
        client.device_type = DeviceType.UDM_PRO
        client.base_url = "https://192.168.1.1:443"
        client.api_prefix = "/proxy/network"

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        client._client.request.return_value = mock_response

        client.get_events("default")

        call_args = client._client.request.call_args
        url = call_args[0][1]
        assert "/proxy/network/api/s/default/stat/event" in url

    def test_events_endpoint_self_hosted(self, mock_settings):
        """Test events endpoint uses self-hosted path."""
        client = UnifiClient(mock_settings)
        client._client = MagicMock(spec=httpx.Client)
        client._authenticated = True
        client.device_type = DeviceType.SELF_HOSTED
        client.base_url = "https://192.168.1.1:8443"
        client.api_prefix = ""

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        client._client.request.return_value = mock_response

        client.get_events("default")

        call_args = client._client.request.call_args
        url = call_args[0][1]
        assert "/api/s/default/stat/event" in url
        assert "/proxy/network" not in url

    def test_alarms_endpoint_udm_pro(self, mock_settings):
        """Test alarms endpoint uses UDM Pro path."""
        client = UnifiClient(mock_settings)
        client._client = MagicMock(spec=httpx.Client)
        client._authenticated = True
        client.device_type = DeviceType.UDM_PRO
        client.base_url = "https://192.168.1.1:443"
        client.api_prefix = "/proxy/network"

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        client._client.request.return_value = mock_response

        client.get_alarms("default")

        call_args = client._client.request.call_args
        url = call_args[0][1]
        assert "/proxy/network/api/s/default/list/alarm" in url

    def test_alarms_endpoint_self_hosted(self, mock_settings):
        """Test alarms endpoint uses self-hosted path."""
        client = UnifiClient(mock_settings)
        client._client = MagicMock(spec=httpx.Client)
        client._authenticated = True
        client.device_type = DeviceType.SELF_HOSTED
        client.base_url = "https://192.168.1.1:8443"
        client.api_prefix = ""

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        client._client.request.return_value = mock_response

        client.get_alarms("default")

        call_args = client._client.request.call_args
        url = call_args[0][1]
        assert "/api/s/default/list/alarm" in url
        assert "/proxy/network" not in url
