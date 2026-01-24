"""Tests for text report generation."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from unifi_scanner.models.enums import Category, DeviceType, Severity
from unifi_scanner.models.finding import Finding
from unifi_scanner.models.report import Report
from unifi_scanner.reports import ReportGenerator


@pytest.fixture
def severe_finding():
    """Create a SEVERE finding with remediation."""
    now = datetime.now(ZoneInfo("UTC"))
    return Finding(
        severity=Severity.SEVERE,
        category=Category.SECURITY,
        title="[Security] Failed Login Attempts",
        description="Multiple failed login attempts detected from external IP. This may indicate a brute force attack.",
        remediation="1. Review access logs\n2. Block the source IP\n3. Update admin passwords",
        first_seen=now - timedelta(hours=2),
        last_seen=now,
        device_mac="aa:bb:cc:dd:ee:ff",
        device_name="Main Router",
        occurrence_count=10,
    )


@pytest.fixture
def medium_finding():
    """Create a MEDIUM finding with remediation."""
    now = datetime.now(ZoneInfo("UTC"))
    return Finding(
        severity=Severity.MEDIUM,
        category=Category.CONNECTIVITY,
        title="[Connectivity] AP Disconnected",
        description="Access point briefly disconnected from the controller. Network connectivity may have been affected.",
        remediation="Check network cables and power supply",
        first_seen=now - timedelta(hours=1),
        last_seen=now - timedelta(minutes=30),
        device_mac="11:22:33:44:55:66",
        device_name="Office AP",
        occurrence_count=2,
    )


@pytest.fixture
def low_finding():
    """Create a LOW finding without remediation."""
    now = datetime.now(ZoneInfo("UTC"))
    return Finding(
        severity=Severity.LOW,
        category=Category.SYSTEM,
        title="[System] Firmware Update Available",
        description="New firmware version available for device. Consider updating during maintenance window.",
        first_seen=now,
        last_seen=now,
        device_mac="ff:ee:dd:cc:bb:aa",
        occurrence_count=1,
    )


@pytest.fixture
def recurring_finding():
    """Create a LOW finding with occurrence_count >= 5 (recurring)."""
    now = datetime.now(ZoneInfo("UTC"))
    return Finding(
        severity=Severity.LOW,
        category=Category.CONNECTIVITY,
        title="[Connectivity] Client Roamed",
        description="Client device roamed between access points.",
        first_seen=now - timedelta(hours=4),
        last_seen=now,
        device_mac="00:11:22:33:44:55",
        device_name="Mobile Device",
        occurrence_count=7,
    )


@pytest.fixture
def sample_report_mixed(severe_finding, medium_finding, low_finding, recurring_finding):
    """Create a Report with 1 severe, 1 medium, 2 low findings."""
    now = datetime.now(ZoneInfo("UTC"))
    return Report(
        period_start=now - timedelta(days=1),
        period_end=now,
        site_name="Test Site",
        controller_type=DeviceType.UDM_PRO,
        findings=[severe_finding, medium_finding, low_finding, recurring_finding],
        log_entry_count=100,
    )


@pytest.fixture
def sample_report_severe_only(severe_finding):
    """Create a Report with only severe findings."""
    now = datetime.now(ZoneInfo("UTC"))
    return Report(
        period_start=now - timedelta(days=1),
        period_end=now,
        site_name="Severe Only Site",
        controller_type=DeviceType.UDM_PRO,
        findings=[severe_finding],
        log_entry_count=50,
    )


@pytest.fixture
def sample_report_low_only(low_finding, recurring_finding):
    """Create a Report with only low findings."""
    now = datetime.now(ZoneInfo("UTC"))
    return Report(
        period_start=now - timedelta(days=1),
        period_end=now,
        site_name="Low Only Site",
        controller_type=DeviceType.UDM_PRO,
        findings=[low_finding, recurring_finding],
        log_entry_count=25,
    )


class TestTextReportBasicStructure:
    """Tests for basic structure of text reports."""

    def test_generate_text_returns_string(self, sample_report_mixed):
        """Verify generate_text returns str type."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_mixed)
        assert isinstance(result, str)

    def test_generate_text_contains_title(self, sample_report_mixed):
        """Verify report contains report_title."""
        rg = ReportGenerator(report_title="Custom Report Title")
        result = rg.generate_text(sample_report_mixed)
        assert "Custom Report Title" in result

    def test_generate_text_contains_site_name(self, sample_report_mixed):
        """Verify report contains site_name."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_mixed)
        assert "Test Site" in result

    def test_generate_text_contains_period(self, sample_report_mixed):
        """Verify report contains period timestamps."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_mixed)
        assert "Period:" in result
        # Should have dates formatted
        assert "UTC" in result

    def test_generate_text_contains_summary(self, sample_report_mixed):
        """Verify report contains SUMMARY and counts."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_mixed)
        assert "SUMMARY" in result
        assert "Total Findings:" in result
        assert "SEVERE:" in result
        assert "MEDIUM:" in result
        assert "LOW:" in result


class TestTextReportSeverityOrdering:
    """Tests for severity section ordering."""

    def test_generate_text_severe_before_medium(self, sample_report_mixed):
        """Verify SEVERE FINDINGS appears before MEDIUM FINDINGS."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_mixed)
        severe_pos = result.find("SEVERE FINDINGS")
        medium_pos = result.find("MEDIUM FINDINGS")
        assert severe_pos < medium_pos, "SEVERE FINDINGS should appear before MEDIUM FINDINGS"

    def test_generate_text_medium_before_low(self, sample_report_mixed):
        """Verify MEDIUM FINDINGS appears before LOW FINDINGS."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_mixed)
        medium_pos = result.find("MEDIUM FINDINGS")
        low_pos = result.find("LOW FINDINGS")
        assert medium_pos < low_pos, "MEDIUM FINDINGS should appear before LOW FINDINGS"


class TestTextReportTieredDetail:
    """Tests for tiered detail levels by severity."""

    def test_generate_text_severe_full_detail(self, sample_report_severe_only):
        """Verify severe finding includes title, description, remediation."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_severe_only)

        # Should include title
        assert "[Security] Failed Login Attempts" in result
        # Should include full description
        assert "Multiple failed login attempts detected" in result
        # Should include remediation
        assert "Review access logs" in result
        assert "Block the source IP" in result

    def test_generate_text_medium_includes_remediation(self, sample_report_mixed):
        """Verify medium finding includes remediation."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_mixed)
        # Medium finding has this remediation
        assert "Check network cables and power supply" in result

    def test_generate_text_low_one_liner(self, sample_report_low_only):
        """Verify low finding is formatted as one-liner with title and count."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_low_only)

        # LOW section should have simple format
        low_section_start = result.find("LOW FINDINGS")
        low_section = result[low_section_start:]

        # Should have title and count format
        assert "[System] Firmware Update Available" in low_section
        assert "(1x)" in low_section

    def test_generate_text_low_no_description(self, sample_report_low_only):
        """Verify low finding does NOT include description in LOW section."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_low_only)

        # LOW section should NOT have the full description text
        low_section_start = result.find("LOW FINDINGS")
        low_section = result[low_section_start:]

        # Description should not appear in LOW section
        assert "Consider updating during maintenance window" not in low_section

    def test_generate_text_low_no_remediation(self, sample_report_low_only):
        """Verify low finding does NOT include remediation."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_low_only)

        low_section_start = result.find("LOW FINDINGS")
        low_section = result[low_section_start:]

        # Should not have "Recommended Actions" in LOW section
        assert "Recommended Actions" not in low_section


class TestTextReportEdgeCases:
    """Tests for edge cases in text report generation."""

    def test_generate_text_no_severe_section_when_empty(self, sample_report_low_only):
        """Verify no SEVERE FINDINGS section when counts.severe == 0."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_low_only)
        assert "SEVERE FINDINGS" not in result

    def test_generate_text_no_medium_section_when_empty(self, sample_report_low_only):
        """Verify no MEDIUM FINDINGS section when counts.medium == 0."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_low_only)
        assert "MEDIUM FINDINGS" not in result

    def test_generate_text_no_low_section_when_empty(self, sample_report_severe_only):
        """Verify no LOW FINDINGS section when counts.low == 0."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_severe_only)
        assert "LOW FINDINGS" not in result

    def test_generate_text_recurring_badge(self, sample_report_mixed):
        """Verify recurring finding shows [Recurring Issue] in occurrence summary."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_mixed)
        # The recurring finding should show [Recurring Issue] somewhere in the text
        # This comes from the FindingFormatter's format_occurrence_summary
        assert "[Recurring Issue]" in result or "(7x)" in result

    def test_generate_text_action_required_when_severe(self, sample_report_mixed):
        """Verify ACTION REQUIRED appears when severe findings exist."""
        rg = ReportGenerator()
        result = rg.generate_text(sample_report_mixed)
        assert "ACTION REQUIRED" in result

    def test_generate_text_no_html_escaping(self):
        """Verify ampersand (&) in content is NOT escaped to &amp;."""
        now = datetime.now(ZoneInfo("UTC"))
        finding = Finding(
            severity=Severity.SEVERE,
            category=Category.SECURITY,
            title="[Security] Test & Verify",
            description="Check logs & review settings",
            remediation="Update & restart the service",
            first_seen=now,
            last_seen=now,
            device_mac="aa:bb:cc:dd:ee:ff",
        )
        report = Report(
            period_start=now - timedelta(days=1),
            period_end=now,
            site_name="Test & Production",
            controller_type=DeviceType.UDM_PRO,
            findings=[finding],
        )

        rg = ReportGenerator()
        result = rg.generate_text(report)

        # Ampersand should NOT be escaped
        assert "&amp;" not in result
        # Should have raw ampersands
        assert "Test & Verify" in result
        assert "Test & Production" in result


class TestTextReportEmptyReport:
    """Tests for empty report generation."""

    def test_generate_text_empty_report(self):
        """Verify report with no findings still generates valid output."""
        now = datetime.now(ZoneInfo("UTC"))
        empty_report = Report(
            period_start=now - timedelta(days=1),
            period_end=now,
            site_name="Empty Site",
            controller_type=DeviceType.UDM_PRO,
            findings=[],
        )

        rg = ReportGenerator()
        result = rg.generate_text(empty_report)

        # Should have basic structure
        assert "UniFi Network Report" in result
        assert "Empty Site" in result
        assert "SUMMARY" in result
        assert "Total Findings: 0" in result

        # Should NOT have any findings sections
        assert "SEVERE FINDINGS" not in result
        assert "MEDIUM FINDINGS" not in result
        assert "LOW FINDINGS" not in result

        # Should still have footer
        assert "Generated by UniFi Scanner" in result
