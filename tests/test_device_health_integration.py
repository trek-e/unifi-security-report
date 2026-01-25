"""Integration tests for Device Health report integration.

Tests the end-to-end integration of device health analysis with report generation:
- Template rendering with health_analysis context
- Template rendering without health_analysis (None)
- Empty health result handling
- Text template formatting
- Full pipeline with mock device data
"""

from datetime import datetime, timezone

import pytest

from unifi_scanner.analysis.device_health import (
    DeviceHealthAnalyzer,
    DeviceHealthFinding,
    DeviceHealthResult,
    DeviceHealthSummary,
    DeviceStats,
)
from unifi_scanner.models.enums import DeviceType, Severity
from unifi_scanner.models.report import Report
from unifi_scanner.reports.generator import ReportGenerator

pytestmark = pytest.mark.asyncio


@pytest.fixture
def sample_device_stats():
    """Sample device stats with various health states."""
    return [
        DeviceStats(
            mac="00:11:22:33:44:55",
            name="Office Switch",
            model="USW-24-PoE",
            device_type="usw",
            cpu_percent=96.0,  # Critical (>95 threshold)
            memory_percent=45.0,
            uptime_seconds=7776000,  # 90 days
            temperature_c=75.0,
            has_temperature=True,
        ),
        DeviceStats(
            mac="aa:bb:cc:dd:ee:ff",
            name="Main AP",
            model="U6-LR",
            device_type="uap",
            cpu_percent=25.0,
            memory_percent=87.0,  # Warning (>85 threshold)
            uptime_seconds=259200,  # 3 days
            temperature_c=50.0,
            has_temperature=True,
        ),
        DeviceStats(
            mac="11:22:33:44:55:66",
            name="Gateway",
            model="UDM-Pro",
            device_type="ugw",
            cpu_percent=15.0,
            memory_percent=35.0,
            uptime_seconds=86400,  # 1 day
            temperature_c=45.0,
            has_temperature=True,
        ),
    ]


@pytest.fixture
def sample_health_result():
    """Sample health result with mixed findings."""
    critical = DeviceHealthFinding(
        device_mac="00:11:22:33:44:55",
        device_name="Office Switch",
        severity=Severity.SEVERE,
        category="cpu",
        title="Critical CPU Usage",
        description="Device CPU usage is critically high at 96.0%.",
        current_value=96.0,
        threshold_value=95.0,
        remediation="Identify and address the source of high load immediately.",
    )

    warning = DeviceHealthFinding(
        device_mac="aa:bb:cc:dd:ee:ff",
        device_name="Main AP",
        severity=Severity.MEDIUM,
        category="memory",
        title="High Memory Usage",
        description="Device memory usage is elevated at 82.0%.",
        current_value=82.0,
        threshold_value=80.0,
        remediation="Consider scheduling a device restart during a maintenance window.",
    )

    summaries = [
        DeviceHealthSummary(
            device_mac="00:11:22:33:44:55",
            device_name="Office Switch",
            device_type="usw",
            critical_count=1,
            warning_count=0,
            is_healthy=False,
        ),
        DeviceHealthSummary(
            device_mac="aa:bb:cc:dd:ee:ff",
            device_name="Main AP",
            device_type="uap",
            critical_count=0,
            warning_count=1,
            is_healthy=False,
        ),
        DeviceHealthSummary(
            device_mac="11:22:33:44:55:66",
            device_name="Gateway",
            device_type="ugw",
            critical_count=0,
            warning_count=0,
            is_healthy=True,
        ),
    ]

    return DeviceHealthResult(
        critical_findings=[critical],
        warning_findings=[warning],
        device_summaries=summaries,
        total_devices=3,
        healthy_devices=1,
        devices_with_warnings=1,
        devices_with_critical=1,
    )


@pytest.fixture
def empty_report():
    """Minimal report for testing."""
    return Report(
        period_start=datetime(2026, 1, 25, 10, 0, 0, tzinfo=timezone.utc),
        period_end=datetime(2026, 1, 25, 11, 0, 0, tzinfo=timezone.utc),
        site_name="default",
        controller_type=DeviceType.UDM_PRO,
        findings=[],
        log_entry_count=0,
    )


class TestHealthSectionHtmlRendering:
    """Tests for HTML template rendering with health_analysis."""

    async def test_html_includes_health_summary_header(self, empty_report, sample_health_result):
        """Device Health Summary header should appear when health_analysis provided."""
        generator = ReportGenerator()
        html = await generator.generate_html(empty_report, health_analysis=sample_health_result)

        assert "Device Health Summary" in html

    async def test_html_shows_device_counts(self, empty_report, sample_health_result):
        """Executive summary should show total, healthy, warnings, critical counts."""
        generator = ReportGenerator()
        html = await generator.generate_html(empty_report, health_analysis=sample_health_result)

        # Check for count values
        assert ">3</div>" in html  # total devices
        assert ">1</div>" in html  # healthy devices

    async def test_html_shows_critical_findings_with_badge(self, empty_report, sample_health_result):
        """Critical findings should appear with CRITICAL badge."""
        generator = ReportGenerator()
        html = await generator.generate_html(empty_report, health_analysis=sample_health_result)

        assert "Critical Issues" in html
        assert "CRITICAL" in html
        assert "Critical CPU Usage" in html
        assert "Office Switch" in html

    async def test_html_shows_warning_findings_with_badge(self, empty_report, sample_health_result):
        """Warning findings should appear with WARNING badge."""
        generator = ReportGenerator()
        html = await generator.generate_html(empty_report, health_analysis=sample_health_result)

        assert "Warnings" in html
        assert "WARNING" in html
        assert "High Memory Usage" in html
        assert "Main AP" in html

    async def test_html_shows_device_status_table(self, empty_report, sample_health_result):
        """Device status table should list all devices with status."""
        generator = ReportGenerator()
        html = await generator.generate_html(empty_report, health_analysis=sample_health_result)

        assert "Device Status" in html
        assert "Office Switch" in html
        assert "Main AP" in html
        assert "Gateway" in html
        assert "USW" in html  # device type uppercase
        assert "UAP" in html
        assert "UGW" in html

    async def test_html_shows_remediation_boxes(self, empty_report, sample_health_result):
        """Remediation guidance should appear in styled boxes."""
        generator = ReportGenerator()
        html = await generator.generate_html(empty_report, health_analysis=sample_health_result)

        assert "Recommended Actions" in html
        assert "Identify and address" in html
        assert "Consider scheduling" in html

    async def test_html_shows_current_vs_threshold_values(self, empty_report, sample_health_result):
        """Current and threshold values should be displayed."""
        generator = ReportGenerator()
        html = await generator.generate_html(empty_report, health_analysis=sample_health_result)

        assert "Current:" in html
        assert "Threshold:" in html
        assert "96.0%" in html
        assert "95.0%" in html


class TestHealthSectionWithoutData:
    """Tests for template rendering when health_analysis is None."""

    async def test_html_omits_health_section_when_none(self, empty_report):
        """Health section should not appear when health_analysis is None."""
        generator = ReportGenerator()
        html = await generator.generate_html(empty_report, health_analysis=None)

        # Check for actual rendered content, not HTML comments
        # The h2 header with blue border only appears when health_analysis is provided
        assert "Total Devices" not in html
        assert "Healthy</div>" not in html

    async def test_html_omits_health_section_when_not_provided(self, empty_report):
        """Health section should not appear when health_analysis not passed."""
        generator = ReportGenerator()
        html = await generator.generate_html(empty_report)

        # Check for actual rendered content, not HTML comments
        assert "Total Devices" not in html
        assert "Healthy</div>" not in html


class TestEmptyHealthResult:
    """Tests for template rendering with empty health result."""

    async def test_html_shows_all_healthy_message(self, empty_report):
        """When no issues, should show all healthy message."""
        healthy_result = DeviceHealthResult(
            critical_findings=[],
            warning_findings=[],
            device_summaries=[
                DeviceHealthSummary(
                    device_mac="00:11:22:33:44:55",
                    device_name="Healthy Switch",
                    device_type="usw",
                    critical_count=0,
                    warning_count=0,
                    is_healthy=True,
                ),
            ],
            total_devices=1,
            healthy_devices=1,
            devices_with_warnings=0,
            devices_with_critical=0,
        )

        generator = ReportGenerator()
        html = await generator.generate_html(empty_report, health_analysis=healthy_result)

        assert "Total Devices" in html  # Executive summary appears
        assert "All devices healthy" in html
        # Critical Issues and Warnings sections (h3 headers) should not appear
        assert ">Critical Issues<" not in html
        assert 'color: #fd7e14; font-size: 16px; font-weight: 600;">Warnings' not in html

    async def test_html_shows_device_table_even_when_healthy(self, empty_report):
        """Device status table should appear even when all devices healthy."""
        healthy_result = DeviceHealthResult(
            critical_findings=[],
            warning_findings=[],
            device_summaries=[
                DeviceHealthSummary(
                    device_mac="00:11:22:33:44:55",
                    device_name="Healthy Switch",
                    device_type="usw",
                    critical_count=0,
                    warning_count=0,
                    is_healthy=True,
                ),
            ],
            total_devices=1,
            healthy_devices=1,
            devices_with_warnings=0,
            devices_with_critical=0,
        )

        generator = ReportGenerator()
        html = await generator.generate_html(empty_report, health_analysis=healthy_result)

        assert "Device Status" in html
        assert "Healthy Switch" in html
        assert ">OK</span>" in html


class TestHealthSectionTextRendering:
    """Tests for plain text template rendering."""

    async def test_text_includes_health_summary_header(self, empty_report, sample_health_result):
        """DEVICE HEALTH SUMMARY header should appear in text output."""
        generator = ReportGenerator()
        text = await generator.generate_text(empty_report, health_analysis=sample_health_result)

        assert "DEVICE HEALTH SUMMARY" in text

    async def test_text_shows_device_counts(self, empty_report, sample_health_result):
        """Executive summary line should show all counts."""
        generator = ReportGenerator()
        text = await generator.generate_text(empty_report, health_analysis=sample_health_result)

        assert "3 total" in text
        assert "1 healthy" in text
        assert "1 with warnings" in text
        assert "1 critical" in text

    async def test_text_shows_critical_issues_section(self, empty_report, sample_health_result):
        """CRITICAL ISSUES section should appear with findings."""
        generator = ReportGenerator()
        text = await generator.generate_text(empty_report, health_analysis=sample_health_result)

        assert "CRITICAL ISSUES" in text
        assert "[CRITICAL]" in text
        assert "Critical CPU Usage" in text
        assert "Office Switch" in text

    async def test_text_shows_warnings_section(self, empty_report, sample_health_result):
        """WARNINGS section should appear with findings."""
        generator = ReportGenerator()
        text = await generator.generate_text(empty_report, health_analysis=sample_health_result)

        assert "WARNINGS" in text
        assert "[WARNING]" in text
        assert "High Memory Usage" in text
        assert "Main AP" in text

    async def test_text_shows_device_status(self, empty_report, sample_health_result):
        """DEVICE STATUS section should list devices."""
        generator = ReportGenerator()
        text = await generator.generate_text(empty_report, health_analysis=sample_health_result)

        assert "DEVICE STATUS" in text
        assert "Office Switch" in text
        assert "USW" in text

    async def test_text_omits_health_section_when_none(self, empty_report):
        """Health section should not appear when health_analysis is None."""
        generator = ReportGenerator()
        text = await generator.generate_text(empty_report, health_analysis=None)

        assert "DEVICE HEALTH SUMMARY" not in text


class TestFullPipelineMock:
    """Tests for full pipeline with mock device data."""

    def test_device_stats_from_api_response_processes_raw_data(self):
        """DeviceStats.from_api_response should parse raw API data correctly."""
        raw_device = {
            "mac": "00:11:22:33:44:55",
            "name": "Test Switch",
            "model": "USW-24-PoE",
            "type": "usw",
            "system-stats": {
                "cpu": "45.2",
                "mem": "62.8",
            },
            "general_temperature": 55.0,
            "uptime": 172800,
        }

        device_stats = DeviceStats.from_api_response(raw_device)

        assert device_stats.mac == "00:11:22:33:44:55"
        assert device_stats.name == "Test Switch"
        assert device_stats.cpu_percent == pytest.approx(45.2)
        assert device_stats.memory_percent == pytest.approx(62.8)
        assert device_stats.temperature_c == pytest.approx(55.0)
        assert device_stats.uptime_seconds == 172800

    def test_analyzer_produces_expected_findings(self, sample_device_stats):
        """DeviceHealthAnalyzer should produce findings based on thresholds."""
        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices(sample_device_stats)

        # Office Switch should have critical CPU finding (96% > 95 threshold)
        assert len(result.critical_findings) >= 1
        cpu_critical = [f for f in result.critical_findings if f.category == "cpu"]
        assert len(cpu_critical) == 1
        assert cpu_critical[0].device_name == "Office Switch"

        # Main AP should have warning memory finding (82% > 80 threshold)
        assert len(result.warning_findings) >= 1
        memory_warning = [f for f in result.warning_findings if f.category == "memory"]
        assert len(memory_warning) == 1
        assert memory_warning[0].device_name == "Main AP"

    async def test_full_pipeline_produces_valid_html(self, sample_device_stats, empty_report):
        """Full pipeline from raw data to HTML should work correctly."""
        # Simulate the pipeline
        analyzer = DeviceHealthAnalyzer()
        health_result = analyzer.analyze_devices(sample_device_stats)

        generator = ReportGenerator()
        html = await generator.generate_html(empty_report, health_analysis=health_result)

        # Verify all expected content appears
        assert "Device Health Summary" in html
        assert "Office Switch" in html
        assert "Main AP" in html
        assert "Gateway" in html
        assert "Critical Issues" in html
        assert "Warnings" in html

    async def test_full_pipeline_produces_valid_text(self, sample_device_stats, empty_report):
        """Full pipeline from raw data to text should work correctly."""
        # Simulate the pipeline
        analyzer = DeviceHealthAnalyzer()
        health_result = analyzer.analyze_devices(sample_device_stats)

        generator = ReportGenerator()
        text = await generator.generate_text(empty_report, health_analysis=health_result)

        # Verify all expected content appears
        assert "DEVICE HEALTH SUMMARY" in text
        assert "Office Switch" in text
        assert "Main AP" in text
        assert "Gateway" in text
        assert "CRITICAL ISSUES" in text
        assert "WARNINGS" in text
