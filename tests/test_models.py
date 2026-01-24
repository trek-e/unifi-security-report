"""Tests for UniFi Scanner data models."""

import json
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from unifi_scanner.models import (
    Category,
    DeviceType,
    Finding,
    LogEntry,
    LogSource,
    Report,
    Severity,
)


class TestLogEntry:
    """Tests for LogEntry model."""

    def test_creation_with_all_fields(self):
        """Test LogEntry creation with all fields populated."""
        entry = LogEntry(
            timestamp=datetime(2026, 1, 24, 10, 0, 0),
            source=LogSource.API,
            device_mac="00:11:22:33:44:55",
            device_name="Office AP",
            event_type="EVT_AP_Connected",
            message="AP connected to network",
            raw_data={"key": "value"},
            metadata={"custom": "data"},
        )

        assert entry.timestamp == datetime(2026, 1, 24, 10, 0, 0)
        assert entry.source == LogSource.API
        assert entry.device_mac == "00:11:22:33:44:55"
        assert entry.device_name == "Office AP"
        assert entry.event_type == "EVT_AP_Connected"
        assert entry.message == "AP connected to network"
        assert entry.raw_data == {"key": "value"}
        assert entry.metadata == {"custom": "data"}
        assert isinstance(entry.id, UUID)

    def test_uuid_auto_generation(self):
        """Test that UUID is auto-generated for new entries."""
        entry1 = LogEntry(
            timestamp=datetime.now(),
            source=LogSource.API,
            event_type="test",
            message="test",
        )
        entry2 = LogEntry(
            timestamp=datetime.now(),
            source=LogSource.API,
            event_type="test",
            message="test",
        )

        assert isinstance(entry1.id, UUID)
        assert isinstance(entry2.id, UUID)
        assert entry1.id != entry2.id

    def test_json_serialization_roundtrip(self):
        """Test LogEntry serializes to JSON and back correctly."""
        original = LogEntry(
            timestamp=datetime(2026, 1, 24, 10, 0, 0),
            source=LogSource.SSH,
            device_mac="aa:bb:cc:dd:ee:ff",
            event_type="EVT_Test",
            message="Test message",
            raw_data={"nested": {"data": 123}},
        )

        # Serialize to JSON
        json_str = original.model_dump_json()
        data = json.loads(json_str)

        # Verify serialization
        assert data["timestamp"] == "2026-01-24T10:00:00"
        assert data["source"] == "ssh"
        assert isinstance(data["id"], str)

        # Deserialize back
        restored = LogEntry.model_validate_json(json_str)
        assert restored.timestamp == original.timestamp
        assert restored.source == original.source
        assert restored.device_mac == original.device_mac
        assert restored.event_type == original.event_type
        assert restored.message == original.message

    def test_metadata_defaults_to_empty_dict(self):
        """Test that metadata field defaults to empty dict."""
        entry = LogEntry(
            timestamp=datetime.now(),
            source=LogSource.API,
            event_type="test",
            message="test",
        )
        assert entry.metadata == {}

    def test_from_unifi_event_factory(self):
        """Test factory method for creating from UniFi API response."""
        event_data = {
            "time": 1706094000000,  # Milliseconds timestamp
            "key": "EVT_AP_Connected",
            "msg": "AP connected",
            "ap_mac": "00:11:22:33:44:55",
            "ap_name": "Office AP",
            "extra_field": "preserved",
        }

        entry = LogEntry.from_unifi_event(event_data)

        assert entry.source == LogSource.API
        assert entry.event_type == "EVT_AP_Connected"
        assert entry.message == "AP connected"
        assert entry.device_mac == "00:11:22:33:44:55"
        assert entry.device_name == "Office AP"
        assert entry.raw_data == event_data


class TestFinding:
    """Tests for Finding model."""

    def test_severity_constraint(self):
        """Test that severity is constrained to valid enum values."""
        now = datetime.now()

        # Valid severities work
        for severity in [Severity.LOW, Severity.MEDIUM, Severity.SEVERE]:
            finding = Finding(
                severity=severity,
                category=Category.SECURITY,
                title="Test",
                description="Test desc",
                first_seen=now,
                last_seen=now,
            )
            assert finding.severity == severity

        # Invalid severity raises error
        with pytest.raises(ValueError):
            Finding(
                severity="critical",  # Invalid
                category=Category.SECURITY,
                title="Test",
                description="Test desc",
                first_seen=now,
                last_seen=now,
            )

    def test_add_occurrence_updates_correctly(self):
        """Test add_occurrence increments count and updates last_seen."""
        now = datetime.now()
        finding = Finding(
            severity=Severity.MEDIUM,
            category=Category.CONNECTIVITY,
            title="Test Finding",
            description="A test finding",
            first_seen=now,
            last_seen=now,
        )

        # Add first occurrence
        log_id_1 = uuid4()
        later = now + timedelta(hours=1)
        finding.add_occurrence(log_id_1, later)

        assert finding.occurrence_count == 2
        assert finding.last_seen == later
        assert log_id_1 in finding.source_log_ids

        # Add second occurrence with even later timestamp
        log_id_2 = uuid4()
        even_later = now + timedelta(hours=2)
        finding.add_occurrence(log_id_2, even_later)

        assert finding.occurrence_count == 3
        assert finding.last_seen == even_later
        assert log_id_2 in finding.source_log_ids

    def test_add_occurrence_does_not_update_last_seen_if_earlier(self):
        """Test add_occurrence doesn't update last_seen for earlier timestamps."""
        now = datetime.now()
        finding = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Test",
            description="Test",
            first_seen=now,
            last_seen=now + timedelta(hours=2),
        )

        # Add occurrence with earlier timestamp
        log_id = uuid4()
        earlier = now + timedelta(hours=1)
        finding.add_occurrence(log_id, earlier)

        assert finding.occurrence_count == 2
        assert finding.last_seen == now + timedelta(hours=2)  # Unchanged

    def test_is_actionable_property(self):
        """Test is_actionable property logic."""
        now = datetime.now()

        # SEVERE with remediation = actionable
        finding1 = Finding(
            severity=Severity.SEVERE,
            category=Category.SECURITY,
            title="Critical Issue",
            description="Very bad",
            remediation="Fix it by doing X",
            first_seen=now,
            last_seen=now,
        )
        assert finding1.is_actionable is True

        # SEVERE without remediation = not actionable
        finding2 = Finding(
            severity=Severity.SEVERE,
            category=Category.SECURITY,
            title="Critical Issue",
            description="Very bad",
            first_seen=now,
            last_seen=now,
        )
        assert finding2.is_actionable is False

        # MEDIUM with remediation = not actionable (not severe)
        finding3 = Finding(
            severity=Severity.MEDIUM,
            category=Category.SECURITY,
            title="Issue",
            description="Bad",
            remediation="Fix it",
            first_seen=now,
            last_seen=now,
        )
        assert finding3.is_actionable is False

    def test_last_seen_validation(self):
        """Test that last_seen must be >= first_seen."""
        now = datetime.now()
        earlier = now - timedelta(hours=1)

        with pytest.raises(ValueError, match="last_seen must be >= first_seen"):
            Finding(
                severity=Severity.LOW,
                category=Category.SYSTEM,
                title="Test",
                description="Test",
                first_seen=now,
                last_seen=earlier,
            )

    def test_metadata_defaults_to_empty_dict(self):
        """Test that metadata field defaults to empty dict."""
        now = datetime.now()
        finding = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Test",
            description="Test",
            first_seen=now,
            last_seen=now,
        )
        assert finding.metadata == {}


class TestReport:
    """Tests for Report model."""

    def test_computed_properties(self):
        """Test severe_count, medium_count, low_count computed properties."""
        now = datetime.now()

        findings = [
            Finding(
                severity=Severity.SEVERE,
                category=Category.SECURITY,
                title="Severe 1",
                description="desc",
                first_seen=now,
                last_seen=now,
            ),
            Finding(
                severity=Severity.SEVERE,
                category=Category.SECURITY,
                title="Severe 2",
                description="desc",
                first_seen=now,
                last_seen=now,
            ),
            Finding(
                severity=Severity.MEDIUM,
                category=Category.CONNECTIVITY,
                title="Medium 1",
                description="desc",
                first_seen=now,
                last_seen=now,
            ),
            Finding(
                severity=Severity.LOW,
                category=Category.SYSTEM,
                title="Low 1",
                description="desc",
                first_seen=now,
                last_seen=now,
            ),
            Finding(
                severity=Severity.LOW,
                category=Category.PERFORMANCE,
                title="Low 2",
                description="desc",
                first_seen=now,
                last_seen=now,
            ),
            Finding(
                severity=Severity.LOW,
                category=Category.SYSTEM,
                title="Low 3",
                description="desc",
                first_seen=now,
                last_seen=now,
            ),
        ]

        report = Report(
            period_start=now - timedelta(days=1),
            period_end=now,
            site_name="default",
            controller_type=DeviceType.UDM_PRO,
            findings=findings,
            log_entry_count=100,
        )

        assert report.severe_count == 2
        assert report.medium_count == 1
        assert report.low_count == 3

    def test_empty_findings(self):
        """Test report with no findings has zero counts."""
        now = datetime.now()

        report = Report(
            period_start=now - timedelta(days=1),
            period_end=now,
            site_name="default",
            controller_type=DeviceType.SELF_HOSTED,
        )

        assert report.findings == []
        assert report.severe_count == 0
        assert report.medium_count == 0
        assert report.low_count == 0

    def test_metadata_defaults_to_empty_dict(self):
        """Test that metadata field defaults to empty dict."""
        now = datetime.now()
        report = Report(
            period_start=now,
            period_end=now,
            site_name="default",
            controller_type=DeviceType.UDM_PRO,
        )
        assert report.metadata == {}

    def test_json_serialization_with_findings(self):
        """Test Report serializes to JSON with nested findings."""
        now = datetime.now()

        finding = Finding(
            severity=Severity.SEVERE,
            category=Category.SECURITY,
            title="Test Finding",
            description="A test",
            first_seen=now,
            last_seen=now,
        )

        report = Report(
            period_start=now - timedelta(days=1),
            period_end=now,
            site_name="main",
            controller_type=DeviceType.UDM_PRO,
            findings=[finding],
            log_entry_count=50,
        )

        json_str = report.model_dump_json()
        data = json.loads(json_str)

        assert data["site_name"] == "main"
        assert data["controller_type"] == "udm_pro"
        assert len(data["findings"]) == 1
        assert data["findings"][0]["severity"] == "severe"
        assert data["severe_count"] == 1
        assert data["log_entry_count"] == 50
