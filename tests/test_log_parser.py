"""Tests for multi-format log parser."""

import json
from datetime import datetime, timezone

import pytest

from unifi_scanner.logs import LogParser
from unifi_scanner.models import LogEntry
from unifi_scanner.models.enums import LogSource


class TestLogParserApiEvents:
    """Tests for LogParser.parse_api_events method."""

    def setup_method(self) -> None:
        """Create parser instance for each test."""
        self.parser = LogParser()

    def test_parse_valid_events(self) -> None:
        """Valid events are parsed into LogEntry objects."""
        events = [
            {"time": 1705084800000, "key": "EVT_AP_Connected", "msg": "AP connected"},
            {"time": 1705084801000, "key": "EVT_WU_Connected", "msg": "Client connected"},
        ]
        entries = self.parser.parse_api_events(events)
        assert len(entries) == 2
        assert entries[0].event_type == "EVT_AP_Connected"
        assert entries[1].event_type == "EVT_WU_Connected"

    def test_parse_events_with_mac(self) -> None:
        """MAC addresses are extracted and normalized."""
        events = [
            {"time": 1705084800000, "key": "EVT_TEST", "msg": "Test", "mac": "AA-BB-CC-DD-EE-FF"},
        ]
        entries = self.parser.parse_api_events(events)
        assert len(entries) == 1
        assert entries[0].device_mac == "aa:bb:cc:dd:ee:ff"

    def test_parse_events_with_ap_mac(self) -> None:
        """AP MAC addresses are extracted."""
        events = [
            {"time": 1705084800000, "key": "EVT_TEST", "msg": "Test", "ap_mac": "11:22:33:44:55:66"},
        ]
        entries = self.parser.parse_api_events(events)
        assert entries[0].device_mac == "11:22:33:44:55:66"

    def test_skip_unparseable_events(self) -> None:
        """Unparseable events are skipped, not raising exceptions."""
        events = [
            {"time": 1705084800000, "key": "EVT_OK", "msg": "Good"},
            # This should still work - missing timestamp gets default
            {"key": "EVT_NO_TIME", "msg": "No timestamp"},
            {"time": 1705084802000, "key": "EVT_OK2", "msg": "Also good"},
        ]
        entries = self.parser.parse_api_events(events)
        assert len(entries) == 3

    def test_empty_list_returns_empty(self) -> None:
        """Empty event list returns empty result."""
        entries = self.parser.parse_api_events([])
        assert entries == []

    def test_source_is_api(self) -> None:
        """All parsed events have API source."""
        events = [{"time": 1705084800000, "key": "EVT_TEST", "msg": "Test"}]
        entries = self.parser.parse_api_events(events)
        assert entries[0].source == LogSource.API


class TestLogParserSyslogLines:
    """Tests for LogParser.parse_syslog_lines method."""

    def setup_method(self) -> None:
        """Create parser instance for each test."""
        self.parser = LogParser()

    def test_parse_standard_syslog(self) -> None:
        """Standard syslog format is parsed correctly."""
        lines = "Jan 24 10:30:15 unifi-ap kernel[1234]: WiFi event occurred"
        entries = self.parser.parse_syslog_lines(lines)
        assert len(entries) == 1
        assert entries[0].message == "WiFi event occurred"
        assert entries[0].source == LogSource.SYSLOG
        assert "kernel" in entries[0].event_type.lower()

    def test_parse_multiple_lines(self) -> None:
        """Multiple syslog lines are parsed."""
        lines = """Jan 24 10:30:15 host1 program1[123]: Message 1
Jan 24 10:30:16 host2 program2[456]: Message 2
Jan 24 10:30:17 host3 program3[789]: Message 3"""
        entries = self.parser.parse_syslog_lines(lines)
        assert len(entries) == 3
        assert entries[0].message == "Message 1"
        assert entries[1].message == "Message 2"
        assert entries[2].message == "Message 3"

    def test_skip_unparseable_lines(self) -> None:
        """Unparseable lines are skipped with warning."""
        lines = """Jan 24 10:30:15 host program[123]: Valid line
This is not valid syslog format
Jan 24 10:30:17 host program[456]: Another valid line"""
        entries = self.parser.parse_syslog_lines(lines)
        assert len(entries) == 2

    def test_skip_empty_lines(self) -> None:
        """Empty lines are skipped."""
        lines = """Jan 24 10:30:15 host program[123]: Line 1

Jan 24 10:30:16 host program[456]: Line 2"""
        entries = self.parser.parse_syslog_lines(lines)
        assert len(entries) == 2

    def test_hostname_in_metadata(self) -> None:
        """Hostname is stored in metadata."""
        lines = "Jan 24 10:30:15 my-hostname program[123]: Test"
        entries = self.parser.parse_syslog_lines(lines)
        assert entries[0].metadata.get("hostname") == "my-hostname"

    def test_pid_in_metadata(self) -> None:
        """PID is stored in metadata."""
        lines = "Jan 24 10:30:15 host program[12345]: Test"
        entries = self.parser.parse_syslog_lines(lines)
        assert entries[0].metadata.get("pid") == 12345

    def test_program_without_pid(self) -> None:
        """Syslog without PID is parsed."""
        lines = "Jan 24 10:30:15 host program: No PID here"
        entries = self.parser.parse_syslog_lines(lines)
        assert len(entries) == 1
        assert entries[0].message == "No PID here"

    def test_source_is_syslog(self) -> None:
        """All parsed entries have SYSLOG source."""
        lines = "Jan 24 10:30:15 host program[123]: Test"
        entries = self.parser.parse_syslog_lines(lines)
        assert entries[0].source == LogSource.SYSLOG


class TestLogParserDetectAndParse:
    """Tests for LogParser.detect_and_parse method."""

    def setup_method(self) -> None:
        """Create parser instance for each test."""
        self.parser = LogParser()

    def test_detect_json_array(self) -> None:
        """JSON array is detected and parsed."""
        data = json.dumps([
            {"time": 1705084800000, "key": "EVT_TEST", "msg": "Test"},
        ])
        entries = self.parser.detect_and_parse(data)
        assert len(entries) == 1
        assert entries[0].source == LogSource.API

    def test_detect_json_wrapped(self) -> None:
        """JSON with data wrapper is detected and parsed."""
        data = json.dumps({
            "data": [
                {"time": 1705084800000, "key": "EVT_TEST", "msg": "Test"},
            ]
        })
        entries = self.parser.detect_and_parse(data)
        assert len(entries) == 1
        assert entries[0].source == LogSource.API

    def test_detect_json_single_event(self) -> None:
        """Single JSON object is detected and parsed."""
        data = json.dumps({"time": 1705084800000, "key": "EVT_TEST", "msg": "Test"})
        entries = self.parser.detect_and_parse(data)
        assert len(entries) == 1
        assert entries[0].source == LogSource.API

    def test_detect_syslog_fallback(self) -> None:
        """Non-JSON data falls back to syslog parsing."""
        data = "Jan 24 10:30:15 host program[123]: Syslog message"
        entries = self.parser.detect_and_parse(data)
        assert len(entries) == 1
        assert entries[0].source == LogSource.SYSLOG

    def test_invalid_json_falls_back_to_syslog(self) -> None:
        """Invalid JSON falls back to syslog parsing."""
        data = "{ this is not valid json"
        # Will try syslog parsing, which will also fail for this line
        entries = self.parser.detect_and_parse(data)
        # Should return empty since it's not valid syslog either
        assert len(entries) == 0


class TestLogParserEdgeCases:
    """Edge case tests for LogParser."""

    def setup_method(self) -> None:
        """Create parser instance for each test."""
        self.parser = LogParser()

    def test_empty_string_returns_empty(self) -> None:
        """Empty string returns empty result."""
        entries = self.parser.detect_and_parse("")
        assert entries == []

    def test_whitespace_only_returns_empty(self) -> None:
        """Whitespace-only string returns empty result."""
        entries = self.parser.detect_and_parse("   \n\n  \t  ")
        assert entries == []

    def test_timestamp_is_utc(self) -> None:
        """Parsed timestamps are UTC-aware."""
        events = [{"time": 1705084800000, "key": "EVT_TEST", "msg": "Test"}]
        entries = self.parser.parse_api_events(events)
        assert entries[0].timestamp.tzinfo == timezone.utc

    def test_raw_data_preserved(self) -> None:
        """Raw event data is preserved in raw_data field."""
        original = {"time": 1705084800000, "key": "EVT_TEST", "msg": "Test", "custom_field": "value"}
        entries = self.parser.parse_api_events([original])
        assert entries[0].raw_data == original
        assert entries[0].raw_data["custom_field"] == "value"
