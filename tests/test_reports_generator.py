"""Tests for ReportGenerator foundation."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from jinja2 import Environment, PackageLoader

from unifi_scanner.analysis.formatter import FindingFormatter
from unifi_scanner.models.enums import Category, DeviceType, Severity
from unifi_scanner.models.finding import Finding
from unifi_scanner.models.report import Report
from unifi_scanner.reports import ReportGenerator

pytestmark = pytest.mark.asyncio


@pytest.fixture
def sample_findings():
    """Create sample findings with different severities."""
    now = datetime.now(ZoneInfo("UTC"))

    severe_finding = Finding(
        severity=Severity.SEVERE,
        category=Category.SECURITY,
        title="[Security] Failed Login Attempts",
        description="Multiple failed login attempts detected",
        remediation="1. Review access logs\n2. Update passwords",
        first_seen=now - timedelta(hours=2),
        last_seen=now,
        device_mac="aa:bb:cc:dd:ee:ff",
        device_name="Main Router",
        occurrence_count=10,
    )

    medium_finding = Finding(
        severity=Severity.MEDIUM,
        category=Category.CONNECTIVITY,
        title="[Connectivity] AP Disconnected",
        description="Access point briefly disconnected",
        remediation="Check network cables and power supply",
        first_seen=now - timedelta(hours=1),
        last_seen=now - timedelta(minutes=30),
        device_mac="11:22:33:44:55:66",
        device_name="Office AP",
        occurrence_count=2,
    )

    low_finding = Finding(
        severity=Severity.LOW,
        category=Category.SYSTEM,
        title="[System] Firmware Update Available",
        description="New firmware version available for device",
        first_seen=now,
        last_seen=now,
        device_mac="ff:ee:dd:cc:bb:aa",
        occurrence_count=1,
    )

    return [severe_finding, medium_finding, low_finding]


@pytest.fixture
def sample_report(sample_findings):
    """Create a sample Report containing findings."""
    now = datetime.now(ZoneInfo("UTC"))
    return Report(
        period_start=now - timedelta(days=1),
        period_end=now,
        site_name="Test Site",
        controller_type=DeviceType.UDM_PRO,
        findings=sample_findings,
        log_entry_count=100,
    )


class TestReportGeneratorEnvironment:
    """Tests for Jinja2 environment configuration."""

    def test_report_generator_creates_environment(self):
        """Verify env is a Jinja2 Environment."""
        rg = ReportGenerator()
        assert isinstance(rg.env, Environment)

    def test_report_generator_has_package_loader(self):
        """Verify loader is PackageLoader for unifi_scanner.reports."""
        rg = ReportGenerator()
        assert isinstance(rg.env.loader, PackageLoader)
        assert rg.env.loader.package_name == "unifi_scanner.reports"
        assert rg.env.loader.package_path == "templates"

    def test_report_generator_autoescape_enabled(self):
        """Verify autoescape is True for .html files."""
        rg = ReportGenerator()
        # select_autoescape returns a callable stored in env.autoescape
        autoescape_func = rg.env.autoescape
        assert callable(autoescape_func)
        # Verify autoescape behavior for different file types
        assert autoescape_func("test.html") is True
        assert autoescape_func("test.xml") is True
        assert autoescape_func("test.txt") is False


class TestReportGeneratorFormatter:
    """Tests for FindingFormatter composition."""

    def test_report_generator_uses_formatter(self):
        """Verify self.formatter is FindingFormatter instance."""
        rg = ReportGenerator()
        assert isinstance(rg.formatter, FindingFormatter)

    def test_custom_timezone_passed_to_formatter(self):
        """Verify formatter.display_timezone matches init param."""
        rg = ReportGenerator(display_timezone="America/New_York")
        assert rg.formatter.display_timezone == "America/New_York"

    def test_custom_report_title(self):
        """Verify report_title stored on instance."""
        rg = ReportGenerator(report_title="Custom Network Report")
        assert rg.report_title == "Custom Network Report"


class TestBuildContext:
    """Tests for _build_context method."""

    def test_build_context_groups_findings(self, sample_report):
        """Verify _build_context returns correct structure with grouped findings."""
        rg = ReportGenerator()
        context = rg._build_context(sample_report)

        # Verify structure
        assert "severe_findings" in context
        assert "medium_findings" in context
        assert "low_findings" in context

        # Verify correct grouping
        assert len(context["severe_findings"]) == 1
        assert len(context["medium_findings"]) == 1
        assert len(context["low_findings"]) == 1

        # Verify severe finding is the security one
        assert context["severe_findings"][0]["title"] == "[Security] Failed Login Attempts"

    def test_build_context_includes_counts(self, sample_report):
        """Verify counts dict has correct severe_count, medium_count, low_count, total."""
        rg = ReportGenerator()
        context = rg._build_context(sample_report)

        assert "counts" in context
        counts = context["counts"]
        assert counts["severe_count"] == 1
        assert counts["medium_count"] == 1
        assert counts["low_count"] == 1
        assert counts["total"] == 3

    def test_build_context_includes_report_metadata(self, sample_report):
        """Verify context includes report title and site info."""
        rg = ReportGenerator(report_title="Test Report Title")
        context = rg._build_context(sample_report)

        assert context["report_title"] == "Test Report Title"
        assert context["site_name"] == "Test Site"
        assert "period_start" in context
        assert "period_end" in context
        assert "generated_at" in context


class TestGenerateMethods:
    """Tests for generate methods now that they are implemented."""

    async def test_generate_html_returns_string(self, sample_report):
        """Verify generate_html returns string (detailed tests in test_reports_html.py)."""
        rg = ReportGenerator()
        result = await rg.generate_html(sample_report)
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result

    async def test_generate_text_returns_string(self, sample_report):
        """Verify generate_text returns string."""
        rg = ReportGenerator()
        result = await rg.generate_text(sample_report)
        assert isinstance(result, str)
