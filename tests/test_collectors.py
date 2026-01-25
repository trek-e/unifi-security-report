"""Tests for log collectors."""

from unittest.mock import MagicMock, patch

import pytest

from unifi_scanner.config import UnifiSettings
from unifi_scanner.logs import (
    APICollectionError,
    APILogCollector,
    LogCollectionError,
    LogCollector,
    SSHCollectionError,
)
from unifi_scanner.models import DeviceType


class TestAPILogCollector:
    """Tests for APILogCollector."""

    def test_collect_events_and_alarms(self) -> None:
        """Should collect both events and alarms and parse them."""
        # Mock client with events and alarms
        mock_client = MagicMock()
        mock_client.get_events.return_value = [
            {"time": 1705084800000, "key": "EVT_AP_Connected", "msg": "AP connected"},
            {"time": 1705084801000, "key": "EVT_SW_Connected", "msg": "Switch connected"},
        ]
        mock_client.get_alarms.return_value = [
            {"time": 1705084802000, "key": "ALM_Rogue_AP", "msg": "Rogue AP detected"},
        ]

        collector = APILogCollector(client=mock_client, site="default")
        entries = collector.collect()

        # Should have parsed all 3 entries
        assert len(entries) == 3
        mock_client.get_events.assert_called_once()
        mock_client.get_alarms.assert_called_once()

    def test_collect_events_only(self) -> None:
        """Should collect only events when alarms disabled."""
        mock_client = MagicMock()
        mock_client.get_events.return_value = [
            {"time": 1705084800000, "key": "EVT_TEST", "msg": "Test event"},
        ]

        collector = APILogCollector(client=mock_client, site="default")
        entries = collector.collect(include_events=True, include_alarms=False)

        assert len(entries) == 1
        mock_client.get_events.assert_called_once()
        mock_client.get_alarms.assert_not_called()

    def test_collect_alarms_only(self) -> None:
        """Should collect only alarms when events disabled."""
        mock_client = MagicMock()
        mock_client.get_alarms.return_value = [
            {"time": 1705084800000, "key": "ALM_TEST", "msg": "Test alarm"},
        ]

        collector = APILogCollector(client=mock_client, site="default")
        entries = collector.collect(include_events=False, include_alarms=True)

        assert len(entries) == 1
        mock_client.get_events.assert_not_called()
        mock_client.get_alarms.assert_called_once()

    def test_collect_api_error_raises_exception(self) -> None:
        """Should raise APICollectionError on API failure."""
        mock_client = MagicMock()
        mock_client.get_events.side_effect = Exception("API failed")

        collector = APILogCollector(client=mock_client, site="default")

        with pytest.raises(APICollectionError) as exc_info:
            collector.collect()

        assert "API collection failed" in str(exc_info.value)


class TestLogCollector:
    """Tests for LogCollector with fallback logic."""

    def _create_settings(self, ssh_enabled: bool = True) -> UnifiSettings:
        """Create settings for testing."""
        return UnifiSettings(
            host="192.168.1.1",
            username="admin",
            password="secret",
            ssh_enabled=ssh_enabled,
        )

    def test_api_sufficient_no_fallback(self) -> None:
        """Should return API results when sufficient entries."""
        mock_client = MagicMock()
        mock_client.device_type = DeviceType.UDM_PRO
        mock_client.get_events.return_value = [
            {"time": 1705084800000 + i, "key": f"EVT_{i}", "msg": f"Event {i}"}
            for i in range(20)
        ]
        mock_client.get_alarms.return_value = []

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
            min_entries=10,
        )

        with patch.object(collector, "_collect_via_ssh") as mock_ssh:
            entries = collector.collect()

            # Should have 20 entries from API
            assert len(entries) == 20
            # SSH should NOT be called
            mock_ssh.assert_not_called()

    def test_api_insufficient_triggers_fallback(self) -> None:
        """Should fall back to SSH when API returns too few entries."""
        mock_client = MagicMock()
        mock_client.device_type = DeviceType.UDM_PRO
        mock_client.get_events.return_value = [
            {"time": 1705084800000, "key": "EVT_1", "msg": "Only one event"},
        ]
        mock_client.get_alarms.return_value = []

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
            min_entries=10,
        )

        # Mock SSH to return more entries
        with patch.object(collector, "_collect_via_ssh") as mock_ssh:
            mock_ssh.return_value = [MagicMock() for _ in range(15)]
            entries = collector.collect()

            # SSH should be called
            mock_ssh.assert_called_once()
            # Should have entries from both sources
            assert len(entries) > 0

    def test_api_failure_triggers_fallback(self) -> None:
        """Should fall back to SSH when API fails."""
        mock_client = MagicMock()
        mock_client.device_type = DeviceType.UDM_PRO
        mock_client.get_events.side_effect = Exception("API broken")

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
        )

        with patch.object(collector, "_collect_via_ssh") as mock_ssh:
            mock_ssh.return_value = [MagicMock() for _ in range(5)]
            entries = collector.collect()

            mock_ssh.assert_called_once()
            assert len(entries) == 5

    def test_ssh_disabled_no_fallback(self) -> None:
        """Should not fall back to SSH when disabled."""
        mock_client = MagicMock()
        mock_client.device_type = DeviceType.UDM_PRO
        mock_client.get_events.side_effect = Exception("API broken")

        settings = self._create_settings(ssh_enabled=False)
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
        )

        with pytest.raises(LogCollectionError) as exc_info:
            collector.collect()

        assert "All log collection sources failed" in str(exc_info.value)

    def test_both_sources_fail_raises_error(self) -> None:
        """Should raise LogCollectionError when both API and SSH fail."""
        mock_client = MagicMock()
        mock_client.device_type = DeviceType.UDM_PRO
        mock_client.get_events.side_effect = Exception("API broken")

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
        )

        with patch.object(collector, "_collect_via_ssh") as mock_ssh:
            mock_ssh.side_effect = SSHCollectionError("SSH broken")

            with pytest.raises(LogCollectionError) as exc_info:
                collector.collect()

            assert "All log collection sources failed" in str(exc_info.value)
            assert exc_info.value.api_error is not None
            assert exc_info.value.ssh_error is not None

    def test_force_ssh_skips_api(self) -> None:
        """Should skip API when force_ssh is True."""
        mock_client = MagicMock()
        mock_client.device_type = DeviceType.UDM_PRO

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
        )

        with patch.object(collector, "_collect_via_ssh") as mock_ssh:
            mock_ssh.return_value = [MagicMock() for _ in range(10)]
            entries = collector.collect(force_ssh=True)

            # API should NOT be called
            mock_client.get_events.assert_not_called()
            mock_client.get_alarms.assert_not_called()
            # SSH should be called
            mock_ssh.assert_called_once()
            assert len(entries) == 10

    def test_partial_api_results_returned_on_ssh_failure(self) -> None:
        """Should return partial API results even if SSH fallback fails."""
        mock_client = MagicMock()
        mock_client.device_type = DeviceType.UDM_PRO
        mock_client.get_events.return_value = [
            {"time": 1705084800000, "key": "EVT_1", "msg": "One event"},
        ]
        mock_client.get_alarms.return_value = []

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
            min_entries=10,  # API returns fewer than this
        )

        with patch.object(collector, "_collect_via_ssh") as mock_ssh:
            mock_ssh.side_effect = SSHCollectionError("SSH broken")
            entries = collector.collect()

            # Should return the 1 entry from API even though SSH failed
            assert len(entries) == 1

    def test_zero_api_entries_returned_when_ssh_unavailable(self) -> None:
        """Should return empty list when API returns 0 entries and SSH fails.

        This is a valid scenario: the controller may have no events in the
        time window (new controller, events cleared, quiet network).
        Should NOT raise LogCollectionError.
        """
        mock_client = MagicMock()
        mock_client.device_type = DeviceType.UDM_PRO
        mock_client.get_events.return_value = []  # No events
        mock_client.get_alarms.return_value = []  # No alarms

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
            min_entries=10,  # API returns 0, below threshold
        )

        with patch.object(collector, "_collect_via_ssh") as mock_ssh:
            mock_ssh.side_effect = SSHCollectionError("SSH port 22 not accessible")
            entries = collector.collect()

            # Should return empty list (not raise error)
            # 0 entries is valid - API succeeded, just no events
            assert entries == []

    def test_zero_api_entries_returned_when_ssh_disabled(self) -> None:
        """Should return empty list when API returns 0 entries and SSH disabled."""
        mock_client = MagicMock()
        mock_client.device_type = DeviceType.UDM_PRO
        mock_client.get_events.return_value = []  # No events
        mock_client.get_alarms.return_value = []  # No alarms

        settings = self._create_settings(ssh_enabled=False)
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
            min_entries=10,
        )

        entries = collector.collect()

        # Should return empty list (not raise error)
        assert entries == []
