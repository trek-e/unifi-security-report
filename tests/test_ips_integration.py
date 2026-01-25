"""Integration tests for IPS analysis in report generation.

Tests end-to-end flow from IPS events through analysis to report output.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from unifi_scanner.analysis.ips import (
    IPSAnalyzer,
    IPSEvent,
    ThreatAnalysisResult,
    ThreatSummary,
)
from unifi_scanner.models.enums import Category, DeviceType, Severity
from unifi_scanner.models.finding import Finding
from unifi_scanner.models.report import Report
from unifi_scanner.reports.generator import ReportGenerator


# Sample IPS event matching real UniFi API structure
# Using 8.8.8.8 as external IP (Google DNS - truly external)
# Note: 203.0.113.x (TEST-NET-3) is reserved for documentation and
# Python's ipaddress module correctly marks it as non-global
SAMPLE_IPS_EVENT = {
    "_id": "abc123",
    "timestamp": 1706234567890,
    "src_ip": "8.8.8.8",
    "dest_ip": "192.168.1.100",
    "proto": "TCP",
    "inner_alert": {
        "signature": "ET SCAN Nmap Scripting Engine User-Agent",
        "signature_id": 2009358,
        "category": "Attempted Information Leak",
        "severity": 2,
        "action": "blocked",
    }
}

SAMPLE_DETECTED_EVENT = {
    "_id": "def456",
    "timestamp": 1706234600000,
    "src_ip": "198.51.100.25",
    "dest_ip": "192.168.1.50",
    "proto": "TCP",
    "inner_alert": {
        "signature": "ET MALWARE Trojan CnC Communication",
        "signature_id": 2010000,
        "category": "malware",
        "severity": 1,
        "action": "allowed",
    }
}


@pytest.fixture
def sample_findings():
    """Sample findings for report."""
    now = datetime.now(ZoneInfo("UTC"))
    return [
        Finding(
            severity=Severity.MEDIUM,
            category=Category.SECURITY,
            title="[Security] Warning",
            description="Test warning",
            first_seen=now - timedelta(hours=1),
            last_seen=now,
            device_mac="aa:bb:cc:dd:ee:ff",
            occurrence_count=1,
        )
    ]


@pytest.fixture
def sample_report(sample_findings):
    """Sample report for testing."""
    now = datetime.now(ZoneInfo("UTC"))
    return Report(
        period_start=now - timedelta(days=1),
        period_end=now,
        site_name="Test Site",
        controller_type=DeviceType.UDM_PRO,
        findings=sample_findings,
        log_entry_count=50,
    )


class TestIPSAnalysisFlowsToReport:
    """Tests that IPS events are analyzed and appear in report output."""

    def test_ips_analysis_appears_in_html_report(self, sample_report):
        """IPS events are analyzed and appear in HTML report output."""
        # Create IPS events
        ips_event = IPSEvent.from_api_event(SAMPLE_IPS_EVENT)

        # Analyze
        analyzer = IPSAnalyzer()
        ips_analysis = analyzer.process_events([ips_event])

        # Generate report
        generator = ReportGenerator()
        html = generator.generate_html(sample_report, ips_analysis=ips_analysis)

        # Verify IPS section appears
        assert "Security Threat Summary" in html
        assert "Threats Blocked" in html

    def test_ips_analysis_appears_in_text_report(self, sample_report):
        """IPS events are analyzed and appear in text report output."""
        # Create IPS events
        ips_event = IPSEvent.from_api_event(SAMPLE_IPS_EVENT)

        # Analyze
        analyzer = IPSAnalyzer()
        ips_analysis = analyzer.process_events([ips_event])

        # Generate report
        generator = ReportGenerator()
        text = generator.generate_text(sample_report, ips_analysis=ips_analysis)

        # Verify IPS section appears
        assert "SECURITY THREAT SUMMARY" in text
        assert "THREATS BLOCKED" in text


class TestEmptyIPSEventsHandled:
    """Tests that reports generate correctly with no IPS events."""

    def test_empty_ips_events_html_report(self, sample_report):
        """Reports generate correctly with no IPS events (HTML)."""
        generator = ReportGenerator()
        html = generator.generate_html(sample_report, ips_analysis=None)

        # Should not have IPS section heading (look for the <h2> tag content)
        # HTML comment "Security Threat Summary (IPS Analysis)" is allowed
        assert '<h2 style=' not in html or 'Security Threat Summary</h2>' not in html
        # Should still have regular report content
        assert "UniFi Network Report" in html

    def test_empty_ips_events_text_report(self, sample_report):
        """Reports generate correctly with no IPS events (text)."""
        generator = ReportGenerator()
        text = generator.generate_text(sample_report, ips_analysis=None)

        # Should not have IPS section header
        assert "SECURITY THREAT SUMMARY" not in text
        # Should still have regular content
        assert "Site: Test Site" in text

    def test_empty_ips_analysis_result(self, sample_report):
        """Empty ThreatAnalysisResult renders correctly."""
        # Create empty result
        ips_analysis = ThreatAnalysisResult()

        generator = ReportGenerator()
        html = generator.generate_html(sample_report, ips_analysis=ips_analysis)

        # Section should appear but with "no threats" message
        assert "Security Threat Summary" in html
        assert "No security threats detected" in html


class TestBlockedAndDetectedBothShown:
    """Tests that both blocked and detected threats appear in report."""

    def test_blocked_and_detected_threats_in_html(self, sample_report):
        """Both blocked and detected threats appear in HTML report."""
        # Create mixed events
        blocked_event = IPSEvent.from_api_event(SAMPLE_IPS_EVENT)  # action=blocked
        detected_event = IPSEvent.from_api_event(SAMPLE_DETECTED_EVENT)  # action=allowed

        # Analyze
        analyzer = IPSAnalyzer()
        ips_analysis = analyzer.process_events([blocked_event, detected_event])

        # Generate report
        generator = ReportGenerator()
        html = generator.generate_html(sample_report, ips_analysis=ips_analysis)

        # Both sections should appear
        assert "Threats Blocked" in html
        assert "Threats Detected" in html

    def test_blocked_and_detected_threats_in_text(self, sample_report):
        """Both blocked and detected threats appear in text report."""
        # Create mixed events
        blocked_event = IPSEvent.from_api_event(SAMPLE_IPS_EVENT)
        detected_event = IPSEvent.from_api_event(SAMPLE_DETECTED_EVENT)

        # Analyze
        analyzer = IPSAnalyzer()
        ips_analysis = analyzer.process_events([blocked_event, detected_event])

        # Generate report
        generator = ReportGenerator()
        text = generator.generate_text(sample_report, ips_analysis=ips_analysis)

        # Both sections should appear
        assert "THREATS BLOCKED" in text
        assert "THREATS DETECTED" in text


class TestSourceIPThresholdApplied:
    """Tests that only IPs with 10+ events appear in top sources."""

    def test_above_threshold_appears(self, sample_report):
        """IPs with 10+ events appear in top sources."""
        # Create 15 events from same IP
        events = []
        for i in range(15):
            event_data = SAMPLE_IPS_EVENT.copy()
            event_data["_id"] = f"event_{i}"
            event_data["timestamp"] = 1706234567890 + (i * 1000)
            events.append(IPSEvent.from_api_event(event_data))

        analyzer = IPSAnalyzer(event_threshold=10)
        ips_analysis = analyzer.process_events(events)

        # IP should be in external sources (8.8.8.8 is truly external)
        assert len(ips_analysis.external_source_ips) == 1
        assert ips_analysis.external_source_ips[0].ip == "8.8.8.8"

    def test_below_threshold_excluded(self, sample_report):
        """IPs with fewer than 10 events don't appear in top sources."""
        # Create only 5 events
        events = []
        for i in range(5):
            event_data = SAMPLE_IPS_EVENT.copy()
            event_data["_id"] = f"event_{i}"
            events.append(IPSEvent.from_api_event(event_data))

        analyzer = IPSAnalyzer(event_threshold=10)
        ips_analysis = analyzer.process_events(events)

        # No IPs should be in sources
        assert len(ips_analysis.external_source_ips) == 0
        assert len(ips_analysis.internal_source_ips) == 0


class TestDetectionModeNoteAppears:
    """Tests that detection mode note shows when all events are detected-only."""

    def test_detection_mode_note_when_all_detected(self, sample_report):
        """Detection mode note shows when all events are detected-only."""
        # Create events with action=allowed (detected, not blocked)
        events = [IPSEvent.from_api_event(SAMPLE_DETECTED_EVENT)]

        analyzer = IPSAnalyzer()
        ips_analysis = analyzer.process_events(events)

        # Should have detection mode note
        assert ips_analysis.detection_mode_note is not None
        assert "detection" in ips_analysis.detection_mode_note.lower()

    def test_detection_mode_note_appears_in_html(self, sample_report):
        """Detection mode note appears in HTML report."""
        events = [IPSEvent.from_api_event(SAMPLE_DETECTED_EVENT)]

        analyzer = IPSAnalyzer()
        ips_analysis = analyzer.process_events(events)

        generator = ReportGenerator()
        html = generator.generate_html(sample_report, ips_analysis=ips_analysis)

        assert "DETECTION MODE" in html

    def test_no_detection_note_when_blocked_exists(self, sample_report):
        """No detection mode note when blocked events exist."""
        # Create blocked event
        events = [IPSEvent.from_api_event(SAMPLE_IPS_EVENT)]

        analyzer = IPSAnalyzer()
        ips_analysis = analyzer.process_events(events)

        # Should not have detection mode note
        assert ips_analysis.detection_mode_note is None


class TestIPSEventFromAPI:
    """Tests for IPSEvent.from_api_event factory method."""

    def test_ips_event_parses_nested_alert(self):
        """IPSEvent correctly parses nested inner_alert structure."""
        event = IPSEvent.from_api_event(SAMPLE_IPS_EVENT)

        assert event.id == "abc123"
        assert event.src_ip == "8.8.8.8"
        assert event.dest_ip == "192.168.1.100"
        assert event.signature == "ET SCAN Nmap Scripting Engine User-Agent"
        assert event.signature_id == 2009358
        assert event.severity == 2
        assert event.is_blocked is True

    def test_ips_event_category_friendly(self):
        """IPSEvent has friendly category name."""
        event = IPSEvent.from_api_event(SAMPLE_IPS_EVENT)

        # Should have a friendly name parsed from signature
        assert event.category_friendly is not None
        assert len(event.category_friendly) > 0

    def test_ips_event_timestamp_conversion(self):
        """IPSEvent correctly converts millisecond timestamps."""
        event = IPSEvent.from_api_event(SAMPLE_IPS_EVENT)

        # Timestamp 1706234567890 = 2024-01-26T00:42:47.890Z
        assert event.timestamp.year == 2024
        assert event.timestamp.month == 1
        assert event.timestamp.tzinfo == timezone.utc


class TestReportGeneratorIPSContext:
    """Tests for ReportGenerator IPS context handling."""

    def test_build_context_includes_ips_analysis(self, sample_report):
        """_build_context includes ips_analysis in context."""
        events = [IPSEvent.from_api_event(SAMPLE_IPS_EVENT)]
        analyzer = IPSAnalyzer()
        ips_analysis = analyzer.process_events(events)

        generator = ReportGenerator()
        context = generator._build_context(sample_report, ips_analysis=ips_analysis)

        assert "ips_analysis" in context
        assert context["ips_analysis"] is ips_analysis

    def test_build_context_ips_analysis_none(self, sample_report):
        """_build_context handles None ips_analysis."""
        generator = ReportGenerator()
        context = generator._build_context(sample_report, ips_analysis=None)

        assert "ips_analysis" in context
        assert context["ips_analysis"] is None

    def test_generate_html_accepts_ips_analysis(self, sample_report):
        """generate_html accepts optional ips_analysis parameter."""
        events = [IPSEvent.from_api_event(SAMPLE_IPS_EVENT)]
        analyzer = IPSAnalyzer()
        ips_analysis = analyzer.process_events(events)

        generator = ReportGenerator()
        # Should not raise
        html = generator.generate_html(sample_report, ips_analysis=ips_analysis)
        assert isinstance(html, str)

    def test_generate_text_accepts_ips_analysis(self, sample_report):
        """generate_text accepts optional ips_analysis parameter."""
        events = [IPSEvent.from_api_event(SAMPLE_IPS_EVENT)]
        analyzer = IPSAnalyzer()
        ips_analysis = analyzer.process_events(events)

        generator = ReportGenerator()
        # Should not raise
        text = generator.generate_text(sample_report, ips_analysis=ips_analysis)
        assert isinstance(text, str)
