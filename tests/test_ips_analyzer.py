"""Tests for IPS analyzer and aggregation."""

import pytest
from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from unifi_scanner.models.enums import Severity
from unifi_scanner.analysis.ips.analyzer import (
    IPSAnalyzer,
    ThreatAnalysisResult,
    ThreatSummary,
)
from unifi_scanner.analysis.ips.aggregator import (
    aggregate_source_ips,
    SourceIPSummary,
)
from unifi_scanner.analysis.ips.models import IPSEvent


def make_ips_event(
    signature: str = "ET SCAN Nmap Scripting Engine",
    category_raw: str = "scan",
    src_ip: str = "192.168.1.100",
    dest_ip: str = "10.0.0.1",
    is_blocked: bool = False,
    severity: int = 2,  # 1=high, 2=medium, 3=low
    timestamp: datetime = None,
) -> IPSEvent:
    """Factory for creating test IPS events.

    Adapts to the pydantic IPSEvent model from 08-01.
    """
    return IPSEvent(
        id=str(uuid4()),
        timestamp=timestamp or datetime.now(timezone.utc),
        src_ip=src_ip,
        src_port=12345,
        dest_ip=dest_ip,
        dest_port=443,
        proto="TCP",
        signature=signature,
        signature_id=2000001,
        category_raw=category_raw,
        severity=severity,
        action="blocked" if is_blocked else "allowed",
        category_friendly="",  # Will be parsed
        is_blocked=is_blocked,
    )


class TestIPSAnalyzerSeparation:
    """Tests for blocked/detected event separation."""

    def test_separate_blocked_detected(self):
        """Test that events are correctly separated by is_blocked flag."""
        events = [
            make_ips_event(signature="sig1", is_blocked=True),
            make_ips_event(signature="sig2", is_blocked=False),
            make_ips_event(signature="sig3", is_blocked=True),
            make_ips_event(signature="sig4", is_blocked=False),
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        # Should have 2 blocked and 2 detected
        # Note: threats are grouped by category, so check total counts
        blocked_count = sum(t.count for t in result.blocked_threats)
        detected_count = sum(t.count for t in result.detected_threats)

        assert blocked_count == 2
        assert detected_count == 2

    def test_all_blocked_goes_to_blocked_list(self):
        """Test that all blocked events end up in blocked_threats."""
        events = [
            make_ips_event(signature="sig1", is_blocked=True),
            make_ips_event(signature="sig2", is_blocked=True),
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        assert len(result.detected_threats) == 0
        assert sum(t.count for t in result.blocked_threats) == 2

    def test_all_detected_goes_to_detected_list(self):
        """Test that all detected events end up in detected_threats."""
        events = [
            make_ips_event(signature="sig1", is_blocked=False),
            make_ips_event(signature="sig2", is_blocked=False),
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        assert len(result.blocked_threats) == 0
        assert sum(t.count for t in result.detected_threats) == 2


class TestIPAggregation:
    """Tests for threshold-based IP aggregation."""

    def test_aggregate_by_threshold_includes_above(self):
        """Test that IPs with 10+ events are included in aggregation."""
        # Create 15 events from same IP - should be highlighted
        events = [
            make_ips_event(src_ip="192.168.1.50") for _ in range(15)
        ]

        result = aggregate_source_ips(events, threshold=10)

        assert len(result) == 1
        assert result[0].ip == "192.168.1.50"
        assert result[0].total_events == 15

    def test_aggregate_by_threshold_excludes_below(self):
        """Test that IPs with fewer than threshold events are excluded."""
        # Create 5 events from same IP - below threshold
        events = [
            make_ips_event(src_ip="192.168.1.50") for _ in range(5)
        ]

        result = aggregate_source_ips(events, threshold=10)

        assert len(result) == 0

    def test_aggregate_exact_threshold(self):
        """Test that exactly threshold events are included."""
        events = [
            make_ips_event(src_ip="192.168.1.50") for _ in range(10)
        ]

        result = aggregate_source_ips(events, threshold=10)

        assert len(result) == 1
        assert result[0].total_events == 10

    def test_aggregate_multiple_ips_mixed(self):
        """Test aggregation with mix of above/below threshold IPs."""
        events = []
        # IP with 15 events - included
        events.extend([make_ips_event(src_ip="1.2.3.4") for _ in range(15)])
        # IP with 5 events - excluded
        events.extend([make_ips_event(src_ip="5.6.7.8") for _ in range(5)])
        # IP with 12 events - included
        events.extend([make_ips_event(src_ip="9.10.11.12") for _ in range(12)])

        result = aggregate_source_ips(events, threshold=10)

        ips = [r.ip for r in result]
        assert "1.2.3.4" in ips
        assert "9.10.11.12" in ips
        assert "5.6.7.8" not in ips
        assert len(result) == 2

    def test_aggregate_category_breakdown(self):
        """Test that category breakdown is provided in summary."""
        events = [
            make_ips_event(src_ip="192.168.1.50", category_raw="scan"),
            make_ips_event(src_ip="192.168.1.50", category_raw="scan"),
            make_ips_event(src_ip="192.168.1.50", category_raw="scan"),
            make_ips_event(src_ip="192.168.1.50", category_raw="malware"),
            make_ips_event(src_ip="192.168.1.50", category_raw="malware"),
            make_ips_event(src_ip="192.168.1.50", category_raw="policy"),
        ] * 2  # 12 events total

        result = aggregate_source_ips(events, threshold=10)

        assert len(result) == 1
        breakdown = result[0].category_breakdown
        assert breakdown["scan"] == 6
        assert breakdown["malware"] == 4
        assert breakdown["policy"] == 2


class TestInternalExternalSeparation:
    """Tests for internal/external IP separation."""

    def test_internal_external_ip_separation(self):
        """Test that internal (RFC1918) and external IPs are separated."""
        events = []
        # Internal IPs (RFC1918: 10.x.x.x, 172.16-31.x.x, 192.168.x.x)
        events.extend([make_ips_event(src_ip="192.168.1.50") for _ in range(15)])
        events.extend([make_ips_event(src_ip="10.0.0.100") for _ in range(12)])
        # External IPs
        events.extend([make_ips_event(src_ip="8.8.8.8") for _ in range(11)])

        analyzer = IPSAnalyzer(event_threshold=10)
        result = analyzer.process_events(events)

        internal_ips = [s.ip for s in result.internal_source_ips]
        external_ips = [s.ip for s in result.external_source_ips]

        assert "192.168.1.50" in internal_ips
        assert "10.0.0.100" in internal_ips
        assert "8.8.8.8" in external_ips
        assert len(result.internal_source_ips) == 2
        assert len(result.external_source_ips) == 1

    def test_is_internal_flag_in_summary(self):
        """Test that SourceIPSummary has correct is_internal flag."""
        events = [make_ips_event(src_ip="192.168.1.50") for _ in range(15)]

        result = aggregate_source_ips(events, threshold=10)

        assert result[0].is_internal is True

    def test_external_ip_not_internal(self):
        """Test that external IPs have is_internal=False."""
        events = [make_ips_event(src_ip="8.8.8.8") for _ in range(15)]

        result = aggregate_source_ips(events, threshold=10)

        assert result[0].is_internal is False

    def test_172_16_range_is_internal(self):
        """Test that 172.16.x.x through 172.31.x.x are internal."""
        events = [make_ips_event(src_ip="172.20.1.50") for _ in range(15)]

        result = aggregate_source_ips(events, threshold=10)

        assert result[0].is_internal is True

    def test_172_outside_range_is_external(self):
        """Test that 172.1.x.x (outside 16-31) is external."""
        events = [make_ips_event(src_ip="172.1.1.50") for _ in range(15)]

        result = aggregate_source_ips(events, threshold=10)

        assert result[0].is_internal is False


class TestDetectionModeNote:
    """Tests for detection mode note."""

    def test_detection_mode_note_when_all_detected(self):
        """Test that detection_mode_note is set when all events are detected-only."""
        events = [
            make_ips_event(is_blocked=False),
            make_ips_event(is_blocked=False),
            make_ips_event(is_blocked=False),
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        assert result.detection_mode_note is not None
        assert "detection" in result.detection_mode_note.lower()

    def test_no_detection_note_when_blocked_exists(self):
        """Test that detection_mode_note is None when blocked events exist."""
        events = [
            make_ips_event(is_blocked=True),
            make_ips_event(is_blocked=False),
            make_ips_event(is_blocked=False),
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        assert result.detection_mode_note is None

    def test_no_detection_note_when_all_blocked(self):
        """Test that detection_mode_note is None when all events are blocked."""
        events = [
            make_ips_event(is_blocked=True),
            make_ips_event(is_blocked=True),
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        assert result.detection_mode_note is None


class TestDeduplication:
    """Tests for event deduplication."""

    def test_deduplicate_same_signature_source(self):
        """Test that same signature+source_ip combination is counted, not duplicated."""
        events = [
            make_ips_event(signature="ET SCAN Nmap", src_ip="192.168.1.50"),
            make_ips_event(signature="ET SCAN Nmap", src_ip="192.168.1.50"),
            make_ips_event(signature="ET SCAN Nmap", src_ip="192.168.1.50"),
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        # Should have one threat entry with count=3, not three entries
        all_threats = result.blocked_threats + result.detected_threats
        assert len(all_threats) == 1
        assert all_threats[0].count == 3

    def test_different_signatures_not_deduplicated(self):
        """Test that different signatures create separate entries."""
        events = [
            make_ips_event(signature="ET SCAN Nmap", src_ip="192.168.1.50"),
            make_ips_event(signature="ET MALWARE Trojan", src_ip="192.168.1.50"),
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        all_threats = result.blocked_threats + result.detected_threats
        assert len(all_threats) == 2

    def test_same_signature_different_ips_deduplicated(self):
        """Test that same signature from different IPs is still one threat entry."""
        events = [
            make_ips_event(signature="ET SCAN Nmap", src_ip="192.168.1.50"),
            make_ips_event(signature="ET SCAN Nmap", src_ip="192.168.1.51"),
            make_ips_event(signature="ET SCAN Nmap", src_ip="192.168.1.52"),
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        all_threats = result.blocked_threats + result.detected_threats
        # Same signature = one threat summary with count=3 and 3 source IPs
        assert len(all_threats) == 1
        assert all_threats[0].count == 3
        assert len(all_threats[0].source_ips) == 3


class TestThreatSummaryCounts:
    """Tests for threat summary structure and counts."""

    def test_threat_summary_counts(self):
        """Test that ThreatSummary has correct count."""
        events = [
            make_ips_event(signature="sig1", category_raw="scan"),
            make_ips_event(signature="sig1", category_raw="scan"),
            make_ips_event(signature="sig1", category_raw="scan"),
            make_ips_event(signature="sig1", category_raw="scan"),
            make_ips_event(signature="sig1", category_raw="scan"),
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        all_threats = result.blocked_threats + result.detected_threats
        assert len(all_threats) == 1
        assert all_threats[0].count == 5

    def test_threat_summary_has_category_friendly(self):
        """Test that ThreatSummary has friendly category name."""
        events = [make_ips_event(category_raw="scan")]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        all_threats = result.blocked_threats + result.detected_threats
        assert len(all_threats) == 1
        # Category should be translated to friendly name
        assert all_threats[0].category_friendly is not None
        assert len(all_threats[0].category_friendly) > 0

    def test_threat_summary_has_sample_signature(self):
        """Test that ThreatSummary includes sample signature."""
        events = [make_ips_event(signature="ET SCAN Nmap Scripting Engine")]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        all_threats = result.blocked_threats + result.detected_threats
        assert all_threats[0].sample_signature == "ET SCAN Nmap Scripting Engine"

    def test_threat_summary_source_ips_unique(self):
        """Test that source_ips in ThreatSummary are unique."""
        events = [
            make_ips_event(signature="sig1", src_ip="192.168.1.50"),
            make_ips_event(signature="sig1", src_ip="192.168.1.50"),  # Duplicate
            make_ips_event(signature="sig1", src_ip="192.168.1.51"),
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        all_threats = result.blocked_threats + result.detected_threats
        assert len(all_threats[0].source_ips) == 2  # Only unique IPs
        assert "192.168.1.50" in all_threats[0].source_ips
        assert "192.168.1.51" in all_threats[0].source_ips

    def test_threat_summary_severity(self):
        """Test that ThreatSummary includes severity."""
        # Use severity=1 (high) which maps to SEVERE
        events = [make_ips_event(severity=1)]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        all_threats = result.blocked_threats + result.detected_threats
        assert all_threats[0].severity == Severity.SEVERE


class TestEmptyInput:
    """Tests for empty/edge case input handling."""

    def test_empty_events_list(self):
        """Test handling of empty events list."""
        analyzer = IPSAnalyzer()
        result = analyzer.process_events([])

        assert result.blocked_threats == []
        assert result.detected_threats == []
        assert result.external_source_ips == []
        assert result.internal_source_ips == []
        assert result.detection_mode_note is None

    def test_aggregate_empty_list(self):
        """Test aggregation of empty list."""
        result = aggregate_source_ips([], threshold=10)
        assert result == []


class TestSourceIPSummary:
    """Tests for SourceIPSummary structure."""

    def test_source_ip_summary_has_sample_signatures(self):
        """Test that SourceIPSummary includes sample signatures."""
        events = [
            make_ips_event(src_ip="192.168.1.50", signature="sig1"),
            make_ips_event(src_ip="192.168.1.50", signature="sig2"),
        ] * 6  # 12 events total

        result = aggregate_source_ips(events, threshold=10)

        assert len(result) == 1
        assert "sig1" in result[0].sample_signatures
        assert "sig2" in result[0].sample_signatures

    def test_source_ip_summary_sorted_by_event_count(self):
        """Test that results are sorted by total event count descending."""
        events = []
        events.extend([make_ips_event(src_ip="1.2.3.4") for _ in range(15)])
        events.extend([make_ips_event(src_ip="5.6.7.8") for _ in range(25)])
        events.extend([make_ips_event(src_ip="9.10.11.12") for _ in range(12)])

        result = aggregate_source_ips(events, threshold=10)

        assert len(result) == 3
        assert result[0].ip == "5.6.7.8"  # 25 events
        assert result[1].ip == "1.2.3.4"  # 15 events
        assert result[2].ip == "9.10.11.12"  # 12 events


class TestRemediationIntegration:
    """Test remediation integration in IPSAnalyzer."""

    def test_threat_summary_includes_remediation(self):
        """ThreatSummary should have remediation populated from get_remediation()."""
        events = [
            make_ips_event(
                signature="ET SCAN Potential SSH Scan",
                category_raw="scan",
                src_ip="203.0.113.50",
                dest_ip="192.168.1.100",
                is_blocked=False,
                severity=2,
            )
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        # Should have one detected threat
        assert len(result.detected_threats) == 1
        threat = result.detected_threats[0]

        # Remediation should be populated
        assert threat.remediation is not None
        assert len(threat.remediation) > 0
        # SCAN category remediation mentions source IP investigation
        assert "source" in threat.remediation.lower() or "scan" in threat.remediation.lower()

    def test_blocked_threat_also_has_remediation(self):
        """Even blocked threats should have remediation (for awareness)."""
        events = [
            make_ips_event(
                signature="ET MALWARE Known Trojan",
                category_raw="malware",
                src_ip="8.8.8.8",
                dest_ip="192.168.1.100",
                is_blocked=True,
                severity=1,
            )
        ]

        analyzer = IPSAnalyzer()
        result = analyzer.process_events(events)

        assert len(result.blocked_threats) == 1
        threat = result.blocked_threats[0]

        # Remediation should still be populated
        assert threat.remediation is not None
        # MALWARE severe remediation mentions isolation
        assert "isolate" in threat.remediation.lower() or "scan" in threat.remediation.lower()

    def test_remediation_uses_severity_adjusted_template(self):
        """Remediation detail should vary by severity."""
        # Create severe event (severity=1)
        severe_event = make_ips_event(
            signature="ET MALWARE Severe Threat",
            category_raw="malware",
            is_blocked=False,
            severity=1,  # severity 1 = severe
        )

        # Create low severity event (severity=3)
        low_event = make_ips_event(
            signature="ET INFO Low Priority",
            category_raw="info",
            is_blocked=False,
            severity=3,  # severity 3 = low
        )

        analyzer = IPSAnalyzer()
        severe_result = analyzer.process_events([severe_event])
        low_result = analyzer.process_events([low_event])

        severe_remediation = severe_result.detected_threats[0].remediation
        low_remediation = low_result.detected_threats[0].remediation

        # Severe should have numbered steps (step-by-step)
        # Low should be shorter (explanation only)
        assert severe_remediation is not None
        # Severe MALWARE remediation has numbered steps
        if "1." in severe_remediation:
            assert len(severe_remediation) > len(low_remediation or "")
