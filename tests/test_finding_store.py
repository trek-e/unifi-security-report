"""Tests for FindingStore time-window deduplication."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from unifi_scanner.analysis import FindingStore
from unifi_scanner.models import Category, Finding, Severity


class TestFindingStoreInit:
    """Tests for FindingStore initialization."""

    def test_default_cluster_window(self):
        """Test default cluster window is 1 hour."""
        store = FindingStore()
        assert store.cluster_window == timedelta(hours=1)

    def test_custom_cluster_window(self):
        """Test custom cluster window can be set."""
        store = FindingStore(cluster_window=timedelta(minutes=30))
        assert store.cluster_window == timedelta(minutes=30)

    def test_initial_stats(self):
        """Test initial stats are all zero."""
        store = FindingStore()
        assert store.stats == {
            "total_findings": 0,
            "total_merged": 0,
            "total_new": 0,
        }


class TestAddOrMerge:
    """Tests for add_or_merge deduplication logic."""

    def test_add_new_finding(self):
        """Test adding a completely new finding."""
        store = FindingStore()
        now = datetime.now(timezone.utc)
        log_id = uuid4()

        finding = Finding(
            severity=Severity.MEDIUM,
            category=Category.SECURITY,
            title="Failed Login",
            description="Multiple failed login attempts",
            first_seen=now,
            last_seen=now,
            device_mac="00:11:22:33:44:55",
        )

        result, was_merged = store.add_or_merge(
            event_type="EVT_FAILED_LOGIN",
            finding=finding,
            log_id=log_id,
            timestamp=now,
        )

        assert was_merged is False
        assert result == finding
        assert store.stats["total_new"] == 1
        assert store.stats["total_merged"] == 0
        assert store.stats["total_findings"] == 1
        assert log_id in result.source_log_ids

    def test_merge_within_time_window(self):
        """Test merging findings within the 1-hour window."""
        store = FindingStore()
        now = datetime.now(timezone.utc)
        log_id_1 = uuid4()
        log_id_2 = uuid4()

        # Add first finding
        finding1 = Finding(
            severity=Severity.MEDIUM,
            category=Category.SECURITY,
            title="Failed Login",
            description="Failed login attempt",
            first_seen=now,
            last_seen=now,
            device_mac="00:11:22:33:44:55",
        )
        store.add_or_merge("EVT_FAILED_LOGIN", finding1, log_id_1, now)

        # Add second occurrence 30 minutes later (within window)
        later = now + timedelta(minutes=30)
        finding2 = Finding(
            severity=Severity.MEDIUM,
            category=Category.SECURITY,
            title="Failed Login",
            description="Failed login attempt",
            first_seen=later,
            last_seen=later,
            device_mac="00:11:22:33:44:55",
        )
        result, was_merged = store.add_or_merge(
            "EVT_FAILED_LOGIN", finding2, log_id_2, later
        )

        assert was_merged is True
        assert result.occurrence_count == 2
        assert result.last_seen == later
        assert log_id_2 in result.source_log_ids
        assert store.stats["total_new"] == 1
        assert store.stats["total_merged"] == 1
        assert store.stats["total_findings"] == 1

    def test_no_merge_outside_time_window(self):
        """Test new finding created when outside time window."""
        store = FindingStore()
        now = datetime.now(timezone.utc)
        log_id_1 = uuid4()
        log_id_2 = uuid4()

        # Add first finding
        finding1 = Finding(
            severity=Severity.MEDIUM,
            category=Category.SECURITY,
            title="Failed Login",
            description="Failed login attempt",
            first_seen=now,
            last_seen=now,
            device_mac="00:11:22:33:44:55",
        )
        store.add_or_merge("EVT_FAILED_LOGIN", finding1, log_id_1, now)

        # Add second occurrence 2 hours later (outside window)
        later = now + timedelta(hours=2)
        finding2 = Finding(
            severity=Severity.MEDIUM,
            category=Category.SECURITY,
            title="Failed Login",
            description="Failed login attempt",
            first_seen=later,
            last_seen=later,
            device_mac="00:11:22:33:44:55",
        )
        result, was_merged = store.add_or_merge(
            "EVT_FAILED_LOGIN", finding2, log_id_2, later
        )

        assert was_merged is False
        assert result == finding2
        assert result.occurrence_count == 1
        # Old finding was replaced since same key
        assert store.stats["total_new"] == 2
        assert store.stats["total_merged"] == 0

    def test_different_device_mac_not_merged(self):
        """Test findings with different device_mac are not merged."""
        store = FindingStore()
        now = datetime.now(timezone.utc)
        log_id_1 = uuid4()
        log_id_2 = uuid4()

        # Add finding for device 1
        finding1 = Finding(
            severity=Severity.MEDIUM,
            category=Category.SECURITY,
            title="Failed Login",
            description="Failed login attempt",
            first_seen=now,
            last_seen=now,
            device_mac="00:11:22:33:44:55",
        )
        store.add_or_merge("EVT_FAILED_LOGIN", finding1, log_id_1, now)

        # Add finding for device 2 (same event type, different MAC)
        finding2 = Finding(
            severity=Severity.MEDIUM,
            category=Category.SECURITY,
            title="Failed Login",
            description="Failed login attempt",
            first_seen=now,
            last_seen=now,
            device_mac="aa:bb:cc:dd:ee:ff",
        )
        result, was_merged = store.add_or_merge(
            "EVT_FAILED_LOGIN", finding2, log_id_2, now
        )

        assert was_merged is False
        assert store.stats["total_findings"] == 2
        assert store.stats["total_new"] == 2

    def test_different_event_type_not_merged(self):
        """Test findings with different event_type are not merged."""
        store = FindingStore()
        now = datetime.now(timezone.utc)
        log_id_1 = uuid4()
        log_id_2 = uuid4()

        # Add finding for event type 1
        finding1 = Finding(
            severity=Severity.MEDIUM,
            category=Category.SECURITY,
            title="Failed Login",
            description="Failed login attempt",
            first_seen=now,
            last_seen=now,
            device_mac="00:11:22:33:44:55",
        )
        store.add_or_merge("EVT_FAILED_LOGIN", finding1, log_id_1, now)

        # Add finding for different event type (same MAC)
        finding2 = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Reboot",
            description="Device rebooted",
            first_seen=now,
            last_seen=now,
            device_mac="00:11:22:33:44:55",
        )
        result, was_merged = store.add_or_merge(
            "EVT_DEVICE_REBOOT", finding2, log_id_2, now
        )

        assert was_merged is False
        assert store.stats["total_findings"] == 2
        assert store.stats["total_new"] == 2

    def test_null_device_mac_deduplication(self):
        """Test that None device_mac is a valid deduplication key."""
        store = FindingStore()
        now = datetime.now(timezone.utc)
        log_id_1 = uuid4()
        log_id_2 = uuid4()

        # Add system-level finding (no device)
        finding1 = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Config Changed",
            description="Configuration updated",
            first_seen=now,
            last_seen=now,
            device_mac=None,
        )
        store.add_or_merge("EVT_CONFIG_CHANGE", finding1, log_id_1, now)

        # Add second occurrence (same event, no device)
        later = now + timedelta(minutes=15)
        finding2 = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Config Changed",
            description="Configuration updated",
            first_seen=later,
            last_seen=later,
            device_mac=None,
        )
        result, was_merged = store.add_or_merge(
            "EVT_CONFIG_CHANGE", finding2, log_id_2, later
        )

        assert was_merged is True
        assert result.occurrence_count == 2
        assert store.stats["total_findings"] == 1

    def test_custom_cluster_window_respected(self):
        """Test that custom cluster window is used for deduplication."""
        # Use 5 minute window
        store = FindingStore(cluster_window=timedelta(minutes=5))
        now = datetime.now(timezone.utc)
        log_id_1 = uuid4()
        log_id_2 = uuid4()

        # Add first finding
        finding1 = Finding(
            severity=Severity.MEDIUM,
            category=Category.SECURITY,
            title="Failed Login",
            description="Failed login attempt",
            first_seen=now,
            last_seen=now,
            device_mac="00:11:22:33:44:55",
        )
        store.add_or_merge("EVT_FAILED_LOGIN", finding1, log_id_1, now)

        # Add second occurrence 10 minutes later (outside 5 min window)
        later = now + timedelta(minutes=10)
        finding2 = Finding(
            severity=Severity.MEDIUM,
            category=Category.SECURITY,
            title="Failed Login",
            description="Failed login attempt",
            first_seen=later,
            last_seen=later,
            device_mac="00:11:22:33:44:55",
        )
        result, was_merged = store.add_or_merge(
            "EVT_FAILED_LOGIN", finding2, log_id_2, later
        )

        # Should NOT merge because 10 min > 5 min window
        assert was_merged is False


class TestRecurringFindings:
    """Tests for recurring finding detection."""

    def test_recurring_threshold(self):
        """Test that 5+ occurrences marks finding as recurring."""
        store = FindingStore()
        now = datetime.now(timezone.utc)
        device_mac = "00:11:22:33:44:55"

        # Add first finding
        finding = Finding(
            severity=Severity.LOW,
            category=Category.CONNECTIVITY,
            title="AP Disconnect",
            description="Access point disconnected",
            first_seen=now,
            last_seen=now,
            device_mac=device_mac,
        )
        store.add_or_merge("EVT_AP_DISCONNECT", finding, uuid4(), now)

        # Add 4 more occurrences (total 5)
        for i in range(4):
            ts = now + timedelta(minutes=i + 1)
            new_finding = Finding(
                severity=Severity.LOW,
                category=Category.CONNECTIVITY,
                title="AP Disconnect",
                description="Access point disconnected",
                first_seen=ts,
                last_seen=ts,
                device_mac=device_mac,
            )
            store.add_or_merge("EVT_AP_DISCONNECT", new_finding, uuid4(), ts)

        findings = store.get_all_findings()
        assert len(findings) == 1
        assert findings[0].occurrence_count == 5
        assert findings[0].is_recurring is True

    def test_not_recurring_below_threshold(self):
        """Test that <5 occurrences is not recurring."""
        store = FindingStore()
        now = datetime.now(timezone.utc)

        finding = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Test",
            description="Test",
            first_seen=now,
            last_seen=now,
            device_mac="00:11:22:33:44:55",
            occurrence_count=4,
        )
        store.add_or_merge("EVT_TEST", finding, uuid4(), now)

        assert store.get_recurring_findings() == []


class TestFiltering:
    """Tests for filtering methods."""

    def test_get_findings_by_severity(self):
        """Test filtering by severity level."""
        store = FindingStore()
        now = datetime.now(timezone.utc)

        # Add findings with different severities
        for i, severity in enumerate([Severity.LOW, Severity.MEDIUM, Severity.SEVERE, Severity.LOW]):
            finding = Finding(
                severity=severity,
                category=Category.SECURITY,
                title=f"Finding {i}",
                description="Test",
                first_seen=now,
                last_seen=now,
                device_mac=f"00:00:00:00:00:0{i}",
            )
            store.add_or_merge(f"EVT_{i}", finding, uuid4(), now)

        low_findings = store.get_findings_by_severity(Severity.LOW)
        medium_findings = store.get_findings_by_severity(Severity.MEDIUM)
        severe_findings = store.get_findings_by_severity(Severity.SEVERE)

        assert len(low_findings) == 2
        assert len(medium_findings) == 1
        assert len(severe_findings) == 1

    def test_get_findings_by_category(self):
        """Test filtering by category."""
        store = FindingStore()
        now = datetime.now(timezone.utc)

        # Add findings with different categories
        categories = [Category.SECURITY, Category.CONNECTIVITY, Category.SECURITY, Category.SYSTEM]
        for i, category in enumerate(categories):
            finding = Finding(
                severity=Severity.LOW,
                category=category,
                title=f"Finding {i}",
                description="Test",
                first_seen=now,
                last_seen=now,
                device_mac=f"00:00:00:00:00:0{i}",
            )
            store.add_or_merge(f"EVT_{i}", finding, uuid4(), now)

        security_findings = store.get_findings_by_category(Category.SECURITY)
        connectivity_findings = store.get_findings_by_category(Category.CONNECTIVITY)
        system_findings = store.get_findings_by_category(Category.SYSTEM)
        performance_findings = store.get_findings_by_category(Category.PERFORMANCE)

        assert len(security_findings) == 2
        assert len(connectivity_findings) == 1
        assert len(system_findings) == 1
        assert len(performance_findings) == 0

    def test_get_recurring_findings_only(self):
        """Test that get_recurring_findings returns only recurring ones."""
        store = FindingStore()
        now = datetime.now(timezone.utc)

        # Add a recurring finding (5 occurrences)
        finding1 = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Recurring",
            description="This recurs",
            first_seen=now,
            last_seen=now,
            device_mac="00:11:22:33:44:55",
            occurrence_count=5,
        )
        store.add_or_merge("EVT_RECURRING", finding1, uuid4(), now)

        # Add a non-recurring finding
        finding2 = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Single",
            description="This happened once",
            first_seen=now,
            last_seen=now,
            device_mac="aa:bb:cc:dd:ee:ff",
            occurrence_count=1,
        )
        store.add_or_merge("EVT_SINGLE", finding2, uuid4(), now)

        recurring = store.get_recurring_findings()
        assert len(recurring) == 1
        assert recurring[0].title == "Recurring"


class TestSummary:
    """Tests for summary generation."""

    def test_get_summary_by_severity_and_category(self):
        """Test summary counts by severity and category."""
        store = FindingStore()
        now = datetime.now(timezone.utc)

        findings_data = [
            (Severity.SEVERE, Category.SECURITY),
            (Severity.SEVERE, Category.SECURITY),
            (Severity.MEDIUM, Category.CONNECTIVITY),
            (Severity.LOW, Category.SYSTEM),
            (Severity.LOW, Category.PERFORMANCE),
        ]

        for i, (severity, category) in enumerate(findings_data):
            finding = Finding(
                severity=severity,
                category=category,
                title=f"Finding {i}",
                description="Test",
                first_seen=now,
                last_seen=now,
                device_mac=f"00:00:00:00:00:0{i}",
            )
            store.add_or_merge(f"EVT_{i}", finding, uuid4(), now)

        summary = store.get_summary()

        assert summary["by_severity"]["severe"] == 2
        assert summary["by_severity"]["medium"] == 1
        assert summary["by_severity"]["low"] == 2

        assert summary["by_category"]["security"] == 2
        assert summary["by_category"]["connectivity"] == 1
        assert summary["by_category"]["system"] == 1
        assert summary["by_category"]["performance"] == 1

    def test_empty_store_summary(self):
        """Test summary on empty store."""
        store = FindingStore()
        summary = store.get_summary()

        assert summary["by_severity"] == {}
        assert summary["by_category"] == {}


class TestOccurrenceSummaryFormat:
    """Tests for occurrence summary formatting."""

    def test_single_occurrence_format(self):
        """Test format for single occurrence."""
        now = datetime.now(timezone.utc)
        finding = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Test",
            description="Test",
            first_seen=now,
            last_seen=now,
            occurrence_count=1,
        )

        summary = finding.format_occurrence_summary()
        assert summary.startswith("Occurred 1 time at")
        assert "[Recurring]" not in summary

    def test_multiple_occurrence_format(self):
        """Test format for multiple occurrences."""
        first = datetime(2026, 1, 24, 14, 0, 0, tzinfo=timezone.utc)
        last = datetime(2026, 1, 24, 16, 30, 0, tzinfo=timezone.utc)
        finding = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Test",
            description="Test",
            first_seen=first,
            last_seen=last,
            occurrence_count=3,
        )

        summary = finding.format_occurrence_summary()
        assert "Occurred 3 times" in summary
        assert "first:" in summary
        assert "last:" in summary
        assert "[Recurring]" not in summary

    def test_recurring_format_includes_tag(self):
        """Test that recurring findings include [Recurring] tag."""
        first = datetime(2026, 1, 24, 14, 0, 0, tzinfo=timezone.utc)
        last = datetime(2026, 1, 24, 18, 0, 0, tzinfo=timezone.utc)
        finding = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Test",
            description="Test",
            first_seen=first,
            last_seen=last,
            occurrence_count=5,
        )

        summary = finding.format_occurrence_summary()
        assert "Occurred 5 times" in summary
        assert "[Recurring]" in summary


class TestGetAllFindings:
    """Tests for get_all_findings method."""

    def test_returns_sorted_by_last_seen_descending(self):
        """Test that findings are sorted by last_seen descending."""
        store = FindingStore()
        now = datetime.now(timezone.utc)

        # Add findings with different times
        times = [
            now - timedelta(hours=2),
            now - timedelta(hours=1),
            now,
        ]

        for i, ts in enumerate(times):
            finding = Finding(
                severity=Severity.LOW,
                category=Category.SYSTEM,
                title=f"Finding {i}",
                description="Test",
                first_seen=ts,
                last_seen=ts,
                device_mac=f"00:00:00:00:00:0{i}",
            )
            store.add_or_merge(f"EVT_{i}", finding, uuid4(), ts)

        all_findings = store.get_all_findings()

        # Should be in descending order (most recent first)
        assert all_findings[0].title == "Finding 2"  # now
        assert all_findings[1].title == "Finding 1"  # now - 1h
        assert all_findings[2].title == "Finding 0"  # now - 2h


class TestClear:
    """Tests for clear method."""

    def test_clear_resets_store(self):
        """Test that clear removes all findings and resets stats."""
        store = FindingStore()
        now = datetime.now(timezone.utc)

        # Add some findings
        for i in range(3):
            finding = Finding(
                severity=Severity.LOW,
                category=Category.SYSTEM,
                title=f"Finding {i}",
                description="Test",
                first_seen=now,
                last_seen=now,
                device_mac=f"00:00:00:00:00:0{i}",
            )
            store.add_or_merge(f"EVT_{i}", finding, uuid4(), now)

        assert store.stats["total_findings"] == 3

        store.clear()

        assert store.stats["total_findings"] == 0
        assert store.stats["total_merged"] == 0
        assert store.stats["total_new"] == 0
        assert store.get_all_findings() == []
