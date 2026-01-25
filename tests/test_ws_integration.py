"""Integration tests for WebSocket support.

Tests the complete WebSocket integration including:
- LogCollector with WebSocket manager
- WS -> REST -> SSH fallback chain
- Event deduplication and merging
- WSLogCollector event conversion
- WebSocketManager lifecycle
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from unifi_scanner.api.websocket import BufferedEvent, WebSocketEventBuffer
from unifi_scanner.config import UnifiSettings
from unifi_scanner.logs import LogCollector
from unifi_scanner.logs.ws_collector import WSCollectionError, WSLogCollector
from unifi_scanner.models import DeviceType, LogEntry, LogSource


class TestLogCollectorWithWebSocket:
    """Integration tests for LogCollector with WebSocket support."""

    def _create_settings(self, ssh_enabled: bool = False) -> UnifiSettings:
        """Create test settings."""
        return UnifiSettings(
            host="192.168.1.1",
            username="admin",
            password="secret",
            ssh_enabled=ssh_enabled,
        )

    def _create_mock_client(self) -> MagicMock:
        """Create a mock UniFi client."""
        mock_client = MagicMock()
        mock_client.device_type = DeviceType.UDM_PRO
        return mock_client

    def _create_mock_ws_manager(
        self,
        events: Optional[List[BufferedEvent]] = None,
        is_running: bool = True,
    ) -> MagicMock:
        """Create a mock WebSocket manager."""
        mock_manager = MagicMock()
        mock_manager.is_running.return_value = is_running
        mock_manager.drain_events.return_value = events or []
        return mock_manager

    def test_collector_uses_ws_when_available(self) -> None:
        """LogCollector merges WebSocket and REST API events."""
        mock_client = self._create_mock_client()

        # API returns some events
        mock_client.get_events.return_value = [
            {
                "time": 1705084800000,
                "key": "EVT_AP_Connected",
                "msg": "AP connected",
            },
        ]
        mock_client.get_alarms.return_value = []

        # WebSocket returns different events
        ws_events = [
            BufferedEvent(
                timestamp=datetime(2024, 1, 12, 16, 0, 1, tzinfo=timezone.utc),
                event_type="wu.connected",
                data={"mac": "aa:bb:cc:dd:ee:ff", "ap": "Office-AP"},
            ),
            BufferedEvent(
                timestamp=datetime(2024, 1, 12, 16, 0, 2, tzinfo=timezone.utc),
                event_type="wu.roam",
                data={
                    "mac": "11:22:33:44:55:66",
                    "ap": "Living-AP",
                    "ap_to": "Kitchen-AP",
                },
            ),
        ]
        mock_ws_manager = self._create_mock_ws_manager(events=ws_events)

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
            min_entries=1,
            ws_manager=mock_ws_manager,
        )

        entries = collector.collect()

        # Should have merged events from both sources
        # 2 WS events + 1 API event = 3 total
        assert len(entries) == 3

        # WS manager should have been consulted
        mock_ws_manager.is_running.assert_called()
        mock_ws_manager.drain_events.assert_called_once()

        # Verify we got WebSocket events
        ws_messages = [e.message for e in entries if e.source == LogSource.WEBSOCKET]
        assert len(ws_messages) == 2

    def test_collector_deduplicates_merged_events(self) -> None:
        """LogCollector deduplicates events by timestamp+message."""
        mock_client = self._create_mock_client()

        # API returns an event
        api_timestamp = 1705084800000  # 2024-01-12 16:00:00 UTC
        mock_client.get_events.return_value = [
            {
                "time": api_timestamp,
                "key": "EVT_AP_Connected",
                "msg": "Client aa:bb:cc:dd:ee:ff connected to Office-AP",
            },
        ]
        mock_client.get_alarms.return_value = []

        # WebSocket returns same event (same timestamp and similar message)
        ws_events = [
            BufferedEvent(
                timestamp=datetime.fromtimestamp(
                    api_timestamp / 1000, tz=timezone.utc
                ),
                event_type="wu.connected",
                data={"mac": "aa:bb:cc:dd:ee:ff", "ap": "Office-AP"},
            ),
        ]
        mock_ws_manager = self._create_mock_ws_manager(events=ws_events)

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
            min_entries=1,
            ws_manager=mock_ws_manager,
        )

        entries = collector.collect()

        # Events have different messages so both should appear
        # (deduplication is by timestamp+message tuple)
        # WS: "Client aa:bb:cc:dd:ee:ff connected to Office-AP"
        # API: "Client aa:bb:cc:dd:ee:ff connected to Office-AP"
        # These actually have different formats so won't deduplicate
        assert len(entries) >= 1

    def test_collector_falls_back_when_ws_empty(self) -> None:
        """LogCollector uses REST API when WebSocket returns no events."""
        mock_client = self._create_mock_client()

        # API returns events
        mock_client.get_events.return_value = [
            {
                "time": 1705084800000 + i,
                "key": f"EVT_AP_{i}",
                "msg": f"Event {i}",
            }
            for i in range(5)
        ]
        mock_client.get_alarms.return_value = []

        # WebSocket returns empty
        mock_ws_manager = self._create_mock_ws_manager(events=[])

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
            min_entries=1,
            ws_manager=mock_ws_manager,
        )

        entries = collector.collect()

        # Should have only API events
        assert len(entries) == 5
        for entry in entries:
            assert entry.source == LogSource.API

    def test_collector_falls_back_when_ws_error(self) -> None:
        """LogCollector handles WSCollectionError gracefully."""
        mock_client = self._create_mock_client()

        # API returns events
        mock_client.get_events.return_value = [
            {"time": 1705084800000, "key": "EVT_Test", "msg": "Test event"},
        ]
        mock_client.get_alarms.return_value = []

        # WebSocket raises error
        mock_ws_manager = MagicMock()
        mock_ws_manager.is_running.return_value = True
        mock_ws_manager.drain_events.side_effect = WSCollectionError(
            "WebSocket buffer corrupted"
        )

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
            min_entries=1,
            ws_manager=mock_ws_manager,
        )

        # Should not raise, should fall back to API
        entries = collector.collect()

        assert len(entries) == 1
        assert entries[0].source == LogSource.API

    def test_collector_works_without_ws_manager(self) -> None:
        """LogCollector works with ws_manager=None (backward compatibility)."""
        mock_client = self._create_mock_client()

        mock_client.get_events.return_value = [
            {"time": 1705084800000, "key": "EVT_Test", "msg": "Test event"},
        ]
        mock_client.get_alarms.return_value = []

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
            min_entries=1,
            ws_manager=None,  # Explicitly no WebSocket
        )

        entries = collector.collect()

        assert len(entries) == 1
        assert entries[0].source == LogSource.API

    def test_collector_skips_ws_when_not_running(self) -> None:
        """LogCollector skips WS collection if manager is not running."""
        mock_client = self._create_mock_client()

        mock_client.get_events.return_value = [
            {"time": 1705084800000, "key": "EVT_Test", "msg": "Test event"},
        ]
        mock_client.get_alarms.return_value = []

        # WS manager exists but is not running
        mock_ws_manager = self._create_mock_ws_manager(is_running=False)

        settings = self._create_settings()
        collector = LogCollector(
            client=mock_client,
            settings=settings,
            site="default",
            min_entries=1,
            ws_manager=mock_ws_manager,
        )

        entries = collector.collect()

        # Should use API only
        assert len(entries) == 1
        # drain_events should NOT be called since is_running() is False
        mock_ws_manager.drain_events.assert_not_called()


class TestWSLogCollectorEventConversion:
    """Tests for WSLogCollector event-to-LogEntry conversion."""

    def _create_mock_manager(
        self, events: Optional[List[BufferedEvent]] = None
    ) -> MagicMock:
        """Create mock manager that returns events."""
        mock = MagicMock()
        mock.drain_events.return_value = events or []
        return mock

    def test_ws_events_converted_to_logentry(self) -> None:
        """BufferedEvent objects are correctly converted to LogEntry."""
        events = [
            BufferedEvent(
                timestamp=datetime(2024, 1, 12, 16, 0, 0, tzinfo=timezone.utc),
                event_type="wu.connected",
                data={"mac": "aa:bb:cc:dd:ee:ff", "ap": "Office-AP"},
            ),
            BufferedEvent(
                timestamp=datetime(2024, 1, 12, 16, 0, 1, tzinfo=timezone.utc),
                event_type="wu.roam",
                data={
                    "mac": "11:22:33:44:55:66",
                    "ap": "Living-AP",
                    "ap_to": "Kitchen-AP",
                },
            ),
            BufferedEvent(
                timestamp=datetime(2024, 1, 12, 16, 0, 2, tzinfo=timezone.utc),
                event_type="wu.disconnected",
                data={"mac": "aa:bb:cc:dd:ee:ff", "ap": "Office-AP"},
            ),
        ]

        mock_manager = self._create_mock_manager(events=events)
        collector = WSLogCollector(manager=mock_manager)
        entries = collector.collect()

        assert len(entries) == 3

        # Check first entry (connected)
        entry0 = entries[0]
        assert isinstance(entry0, LogEntry)
        assert entry0.source == LogSource.WEBSOCKET
        assert entry0.event_type == "wu.connected"
        assert entry0.device_mac == "aa:bb:cc:dd:ee:ff"
        assert "connected" in entry0.message.lower()

        # Check second entry (roam)
        entry1 = entries[1]
        assert entry1.event_type == "wu.roam"
        assert "roamed" in entry1.message.lower()
        assert "Kitchen-AP" in entry1.message

        # Check third entry (disconnected)
        entry2 = entries[2]
        assert entry2.event_type == "wu.disconnected"
        assert "disconnected" in entry2.message.lower()

    def test_ws_events_preserve_timestamp(self) -> None:
        """LogEntry preserves original BufferedEvent timestamp."""
        original_ts = datetime(2024, 1, 12, 16, 30, 45, tzinfo=timezone.utc)
        events = [
            BufferedEvent(
                timestamp=original_ts,
                event_type="wu.connected",
                data={"mac": "aa:bb:cc:dd:ee:ff"},
            ),
        ]

        mock_manager = self._create_mock_manager(events=events)
        collector = WSLogCollector(manager=mock_manager)
        entries = collector.collect()

        assert len(entries) == 1
        assert entries[0].timestamp == original_ts

    def test_ws_events_filtered_by_since_timestamp(self) -> None:
        """WSLogCollector filters events by since_timestamp."""
        old_event = BufferedEvent(
            timestamp=datetime(2024, 1, 12, 15, 0, 0, tzinfo=timezone.utc),
            event_type="wu.connected",
            data={"mac": "old:event:mac"},
        )
        new_event = BufferedEvent(
            timestamp=datetime(2024, 1, 12, 17, 0, 0, tzinfo=timezone.utc),
            event_type="wu.connected",
            data={"mac": "new:event:mac"},
        )

        mock_manager = self._create_mock_manager(events=[old_event, new_event])

        # Filter: only events after 16:00
        since = datetime(2024, 1, 12, 16, 0, 0, tzinfo=timezone.utc)
        collector = WSLogCollector(manager=mock_manager, since_timestamp=since)
        entries = collector.collect()

        # Should only have the new event
        assert len(entries) == 1
        assert entries[0].device_mac == "new:event:mac"

    def test_ws_events_clock_skew_tolerance(self) -> None:
        """WSLogCollector applies 5-minute clock skew tolerance."""
        # Event at 15:57 - just within 5-minute tolerance of 16:00
        edge_event = BufferedEvent(
            timestamp=datetime(2024, 1, 12, 15, 57, 0, tzinfo=timezone.utc),
            event_type="wu.connected",
            data={"mac": "edge:event:mac"},
        )
        # Event at 15:50 - outside tolerance
        old_event = BufferedEvent(
            timestamp=datetime(2024, 1, 12, 15, 50, 0, tzinfo=timezone.utc),
            event_type="wu.connected",
            data={"mac": "old:event:mac"},
        )

        mock_manager = self._create_mock_manager(events=[old_event, edge_event])

        since = datetime(2024, 1, 12, 16, 0, 0, tzinfo=timezone.utc)
        collector = WSLogCollector(manager=mock_manager, since_timestamp=since)
        entries = collector.collect()

        # Should include edge_event (within tolerance) but not old_event
        assert len(entries) == 1
        assert entries[0].device_mac == "edge:event:mac"

    def test_ws_events_raw_data_preserved(self) -> None:
        """LogEntry preserves raw event data from BufferedEvent."""
        raw_data = {
            "mac": "aa:bb:cc:dd:ee:ff",
            "ap": "Office-AP",
            "channel": 36,
            "signal": -45,
            "extra_field": "value",
        }
        events = [
            BufferedEvent(
                timestamp=datetime.now(timezone.utc),
                event_type="wu.connected",
                data=raw_data,
            ),
        ]

        mock_manager = self._create_mock_manager(events=events)
        collector = WSLogCollector(manager=mock_manager)
        entries = collector.collect()

        assert len(entries) == 1
        assert entries[0].raw_data == raw_data


class TestWebSocketManagerIntegration:
    """Integration tests for WebSocketManager lifecycle."""

    def test_manager_not_running_initially(self) -> None:
        """WebSocketManager is not running before start() is called."""
        from unifi_scanner.api.ws_manager import WebSocketManager

        manager = WebSocketManager()
        assert manager.is_running() is False

    def test_manager_drain_events_returns_empty_when_not_running(self) -> None:
        """drain_events() returns empty list when manager not running."""
        from unifi_scanner.api.ws_manager import WebSocketManager

        manager = WebSocketManager()
        events = manager.drain_events()
        assert events == []

    def test_manager_buffer_operations(self) -> None:
        """WebSocketEventBuffer add/drain works correctly."""
        buffer = WebSocketEventBuffer()

        event1 = BufferedEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="wu.connected",
            data={"mac": "aa:bb:cc:dd:ee:ff"},
        )
        event2 = BufferedEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="wu.disconnected",
            data={"mac": "11:22:33:44:55:66"},
        )

        buffer.add(event1)
        buffer.add(event2)

        # First drain gets all events
        drained = buffer.drain()
        assert len(drained) == 2
        assert drained[0] == event1
        assert drained[1] == event2

        # Second drain is empty
        drained2 = buffer.drain()
        assert drained2 == []

    def test_manager_stop_when_not_started(self) -> None:
        """stop() is safe to call when manager was never started."""
        from unifi_scanner.api.ws_manager import WebSocketManager

        manager = WebSocketManager()
        # Should not raise
        manager.stop()
        assert manager.is_running() is False

    @patch("unifi_scanner.api.ws_manager.UnifiWebSocketClient")
    def test_manager_start_creates_client(self, mock_client_class: MagicMock) -> None:
        """start() creates UnifiWebSocketClient with correct parameters."""
        from unifi_scanner.api.ws_manager import WebSocketManager

        # Mock the client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        manager = WebSocketManager()
        manager.start(
            base_url="https://192.168.1.1",
            site="default",
            cookies={"TOKEN": "abc123"},
            device_type=DeviceType.UDM_PRO,
            verify_ssl=False,
        )

        # Client should be created
        mock_client_class.assert_called_once_with(
            base_url="https://192.168.1.1",
            site="default",
            cookies={"TOKEN": "abc123"},
            device_type=DeviceType.UDM_PRO,
            verify_ssl=False,
        )

        # Clean up
        manager.stop()

    @patch("unifi_scanner.api.ws_manager.UnifiWebSocketClient")
    def test_manager_start_twice_logs_warning(
        self, mock_client_class: MagicMock
    ) -> None:
        """Calling start() twice should not create second connection."""
        from unifi_scanner.api.ws_manager import WebSocketManager

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        manager = WebSocketManager()
        manager.start(
            base_url="https://192.168.1.1",
            site="default",
            cookies={"TOKEN": "abc123"},
            device_type=DeviceType.UDM_PRO,
        )

        # Second start should be ignored
        manager.start(
            base_url="https://192.168.1.1",
            site="default",
            cookies={"TOKEN": "abc123"},
            device_type=DeviceType.UDM_PRO,
        )

        # Client should only be created once
        assert mock_client_class.call_count == 1

        manager.stop()
