"""Tests for WebSocket client components.

TDD tests for:
- Event parsing (parse_unifi_event)
- Event buffer (WebSocketEventBuffer)
- Client endpoint selection (UnifiWebSocketClient.endpoint)
"""

import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from unifi_scanner.api.websocket import (
    BufferedEvent,
    WebSocketEventBuffer,
    UnifiWebSocketClient,
    parse_unifi_event,
)
from unifi_scanner.models import DeviceType


class TestParseUnifiEvent:
    """Tests for parse_unifi_event function."""

    def test_parse_wifi_connected_event(self) -> None:
        """Valid wu.connected event JSON returns BufferedEvent with correct type."""
        raw_message = '{"meta":{"message":"wu.connected"},"data":[{"mac":"aa:bb:cc:dd:ee:ff","ssid":"MyNetwork"}]}'

        result = parse_unifi_event(raw_message)

        assert result is not None
        assert isinstance(result, BufferedEvent)
        assert result.event_type == "wu.connected"
        assert result.data.get("mac") == "aa:bb:cc:dd:ee:ff"

    def test_parse_wifi_roam_event(self) -> None:
        """Valid wu.roam event JSON returns BufferedEvent with correct type."""
        raw_message = '{"meta":{"message":"wu.roam"},"data":[{"mac":"aa:bb:cc:dd:ee:ff","ap":"AP-Living","ap_to":"AP-Office"}]}'

        result = parse_unifi_event(raw_message)

        assert result is not None
        assert result.event_type == "wu.roam"
        assert result.data.get("ap") == "AP-Living"
        assert result.data.get("ap_to") == "AP-Office"

    def test_parse_wifi_roam_radio_event(self) -> None:
        """Valid wu.roam_radio event JSON returns BufferedEvent with correct type."""
        raw_message = '{"meta":{"message":"wu.roam_radio"},"data":[{"mac":"aa:bb:cc:dd:ee:ff","channel":"36"}]}'

        result = parse_unifi_event(raw_message)

        assert result is not None
        assert result.event_type == "wu.roam_radio"

    def test_parse_wifi_disconnected_event(self) -> None:
        """Valid wu.disconnected event JSON returns BufferedEvent with correct type."""
        raw_message = '{"meta":{"message":"wu.disconnected"},"data":[{"mac":"aa:bb:cc:dd:ee:ff","reason":"user_initiated"}]}'

        result = parse_unifi_event(raw_message)

        assert result is not None
        assert result.event_type == "wu.disconnected"

    def test_parse_sta_sync_event(self) -> None:
        """Valid sta:sync event JSON returns BufferedEvent with correct type."""
        raw_message = '{"meta":{"message":"sta:sync"},"data":[{"mac":"aa:bb:cc:dd:ee:ff","state":"connected"}]}'

        result = parse_unifi_event(raw_message)

        assert result is not None
        assert result.event_type == "sta:sync"

    def test_parse_non_wifi_event_returns_none(self) -> None:
        """Non-WiFi event (device:sync) returns None."""
        raw_message = '{"meta":{"message":"device:sync"},"data":[{"type":"uap","state":"online"}]}'

        result = parse_unifi_event(raw_message)

        assert result is None

    def test_parse_invalid_json_returns_none(self) -> None:
        """Invalid JSON returns None without raising exception."""
        raw_message = "invalid json {{"

        result = parse_unifi_event(raw_message)

        assert result is None

    def test_parse_empty_message_returns_none(self) -> None:
        """Empty message returns None."""
        raw_message = ""

        result = parse_unifi_event(raw_message)

        assert result is None

    def test_parse_missing_meta_returns_none(self) -> None:
        """Message without meta field returns None."""
        raw_message = '{"data":[{"mac":"aa:bb:cc:dd:ee:ff"}]}'

        result = parse_unifi_event(raw_message)

        assert result is None

    def test_parse_missing_data_uses_empty_dict(self) -> None:
        """Message without data field uses empty dict for data."""
        raw_message = '{"meta":{"message":"wu.connected"}}'

        result = parse_unifi_event(raw_message)

        assert result is not None
        assert result.data == {}

    def test_parse_event_sets_timestamp(self) -> None:
        """Parsed event has a timestamp set."""
        raw_message = '{"meta":{"message":"wu.connected"},"data":[{"mac":"aa:bb:cc:dd:ee:ff"}]}'

        before = datetime.now(timezone.utc)
        result = parse_unifi_event(raw_message)
        after = datetime.now(timezone.utc)

        assert result is not None
        assert before <= result.timestamp <= after


class TestWebSocketEventBuffer:
    """Tests for WebSocketEventBuffer class."""

    def test_add_and_drain_single_event(self) -> None:
        """Add one event, drain returns it."""
        buffer = WebSocketEventBuffer()
        event = BufferedEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="wu.connected",
            data={"mac": "aa:bb:cc:dd:ee:ff"},
        )

        buffer.add(event)
        result = buffer.drain()

        assert len(result) == 1
        assert result[0] == event

    def test_add_and_drain_multiple_events(self) -> None:
        """Add multiple events, drain returns all in order."""
        buffer = WebSocketEventBuffer()
        events = [
            BufferedEvent(
                timestamp=datetime.now(timezone.utc),
                event_type=f"event_{i}",
                data={"index": i},
            )
            for i in range(5)
        ]

        for event in events:
            buffer.add(event)

        result = buffer.drain()

        assert len(result) == 5
        for i, event in enumerate(result):
            assert event.event_type == f"event_{i}"

    def test_drain_clears_buffer(self) -> None:
        """Drain clears buffer, second drain returns empty list."""
        buffer = WebSocketEventBuffer()
        event = BufferedEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="wu.connected",
            data={},
        )

        buffer.add(event)
        first_drain = buffer.drain()
        second_drain = buffer.drain()

        assert len(first_drain) == 1
        assert len(second_drain) == 0

    def test_buffer_respects_maxsize(self) -> None:
        """Buffer drops oldest events when maxsize exceeded."""
        buffer = WebSocketEventBuffer(maxsize=3)
        events = [
            BufferedEvent(
                timestamp=datetime.now(timezone.utc),
                event_type=f"event_{i}",
                data={"index": i},
            )
            for i in range(5)
        ]

        for event in events:
            buffer.add(event)

        result = buffer.drain()

        # Should only have the 3 most recent events (2, 3, 4)
        assert len(result) == 3
        assert result[0].event_type == "event_2"
        assert result[1].event_type == "event_3"
        assert result[2].event_type == "event_4"

    def test_thread_safety(self) -> None:
        """Buffer handles concurrent add and drain from multiple threads."""
        buffer = WebSocketEventBuffer(maxsize=1000)
        events_added = []
        events_drained = []
        lock = threading.Lock()

        def producer(thread_id: int, count: int) -> None:
            for i in range(count):
                event = BufferedEvent(
                    timestamp=datetime.now(timezone.utc),
                    event_type=f"thread_{thread_id}_event_{i}",
                    data={"thread": thread_id, "index": i},
                )
                buffer.add(event)
                with lock:
                    events_added.append(event.event_type)
                time.sleep(0.001)  # Small delay to increase contention

        def consumer() -> None:
            for _ in range(10):
                drained = buffer.drain()
                with lock:
                    events_drained.extend([e.event_type for e in drained])
                time.sleep(0.005)  # Give producers time to add more

        # Start multiple producer threads
        producers = [
            threading.Thread(target=producer, args=(i, 10))
            for i in range(3)
        ]
        consumer_thread = threading.Thread(target=consumer)

        for p in producers:
            p.start()
        consumer_thread.start()

        for p in producers:
            p.join()
        consumer_thread.join()

        # Final drain to get remaining events
        final_drain = buffer.drain()
        events_drained.extend([e.event_type for e in final_drain])

        # All events should be drained (30 total)
        assert len(events_drained) == 30


class TestUnifiWebSocketClientEndpoint:
    """Tests for UnifiWebSocketClient.endpoint property."""

    def test_endpoint_udm_pro(self) -> None:
        """UDM_PRO device type uses /proxy/network/wss path."""
        client = UnifiWebSocketClient(
            base_url="https://192.168.1.1",
            site="default",
            cookies={},
            device_type=DeviceType.UDM_PRO,
        )

        endpoint = client.endpoint

        assert endpoint == "wss://192.168.1.1/proxy/network/wss/s/default/events"

    def test_endpoint_self_hosted(self) -> None:
        """SELF_HOSTED device type uses direct /wss path without proxy."""
        client = UnifiWebSocketClient(
            base_url="https://192.168.1.1:8443",
            site="default",
            cookies={},
            device_type=DeviceType.SELF_HOSTED,
        )

        endpoint = client.endpoint

        assert endpoint == "wss://192.168.1.1:8443/wss/s/default/events"

    def test_https_to_wss_conversion(self) -> None:
        """https:// in base_url is converted to wss://."""
        client = UnifiWebSocketClient(
            base_url="https://unifi.example.com",
            site="mysite",
            cookies={},
            device_type=DeviceType.UDM_PRO,
        )

        endpoint = client.endpoint

        assert endpoint.startswith("wss://")
        assert "https://" not in endpoint

    def test_endpoint_includes_site(self) -> None:
        """Endpoint includes the correct site name."""
        client = UnifiWebSocketClient(
            base_url="https://192.168.1.1",
            site="custom_site",
            cookies={},
            device_type=DeviceType.UDM_PRO,
        )

        endpoint = client.endpoint

        assert "/s/custom_site/events" in endpoint

    def test_endpoint_handles_trailing_slash(self) -> None:
        """Endpoint handles base_url with trailing slash."""
        client = UnifiWebSocketClient(
            base_url="https://192.168.1.1/",
            site="default",
            cookies={},
            device_type=DeviceType.UDM_PRO,
        )

        endpoint = client.endpoint

        # Should not have double slashes
        assert "//" not in endpoint.replace("wss://", "")


class TestBufferedEventDataclass:
    """Tests for BufferedEvent dataclass."""

    def test_buffered_event_creation(self) -> None:
        """BufferedEvent can be created with required fields."""
        timestamp = datetime.now(timezone.utc)
        event = BufferedEvent(
            timestamp=timestamp,
            event_type="wu.connected",
            data={"mac": "aa:bb:cc:dd:ee:ff"},
        )

        assert event.timestamp == timestamp
        assert event.event_type == "wu.connected"
        assert event.data == {"mac": "aa:bb:cc:dd:ee:ff"}

    def test_buffered_event_equality(self) -> None:
        """BufferedEvent instances with same values are equal."""
        timestamp = datetime(2026, 1, 24, 12, 0, 0, tzinfo=timezone.utc)
        event1 = BufferedEvent(timestamp=timestamp, event_type="test", data={})
        event2 = BufferedEvent(timestamp=timestamp, event_type="test", data={})

        assert event1 == event2
