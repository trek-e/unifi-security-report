"""Tests for DeviceHealthAnalyzer.

TDD tests for Phase 9: Device Health Monitoring.
Tests DeviceHealthAnalyzer threshold checking and result generation.
"""

import pytest


class TestHealthThresholds:
    """Tests for HealthThresholds dataclass."""

    def test_default_thresholds_have_expected_values(self):
        """DEFAULT_THRESHOLDS should have the documented threshold values."""
        from unifi_scanner.analysis.device_health.thresholds import (
            DEFAULT_THRESHOLDS,
        )

        # Temperature thresholds
        assert DEFAULT_THRESHOLDS.temp_warning == 80.0
        assert DEFAULT_THRESHOLDS.temp_critical == 90.0

        # CPU thresholds
        assert DEFAULT_THRESHOLDS.cpu_warning == 80
        assert DEFAULT_THRESHOLDS.cpu_critical == 95

        # Memory thresholds
        assert DEFAULT_THRESHOLDS.memory_warning == 85
        assert DEFAULT_THRESHOLDS.memory_critical == 95

        # Uptime thresholds (in days)
        assert DEFAULT_THRESHOLDS.uptime_warning == 90
        assert DEFAULT_THRESHOLDS.uptime_critical == 180

    def test_thresholds_are_frozen(self):
        """HealthThresholds should be immutable (frozen dataclass)."""
        from unifi_scanner.analysis.device_health.thresholds import (
            DEFAULT_THRESHOLDS,
        )

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            DEFAULT_THRESHOLDS.temp_warning = 70.0

    def test_custom_thresholds_can_be_created(self):
        """HealthThresholds can be instantiated with custom values."""
        from unifi_scanner.analysis.device_health.thresholds import HealthThresholds

        custom = HealthThresholds(
            temp_warning=75.0,
            temp_critical=85.0,
            cpu_warning=70,
            cpu_critical=90,
            memory_warning=80,
            memory_critical=90,
            uptime_warning=60,
            uptime_critical=120,
        )

        assert custom.temp_warning == 75.0
        assert custom.temp_critical == 85.0
        assert custom.cpu_warning == 70
        assert custom.cpu_critical == 90


class TestAnalyzerTemperatureChecks:
    """Tests for DeviceHealthAnalyzer temperature threshold checking."""

    def test_device_at_75c_no_finding(self):
        """Device at 75C should not generate temperature finding (below 80C warning)."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Cool Switch",
            temperature_c=75.0,
            has_temperature=True,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        # Should have no temperature findings
        temp_findings = [
            f for f in result.warning_findings + result.critical_findings
            if f.category == "temperature"
        ]
        assert len(temp_findings) == 0

    def test_device_at_82c_warning_finding(self):
        """Device at 82C should generate warning finding (above 80C warning threshold)."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer
        from unifi_scanner.models.enums import Severity

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Warm Switch",
            temperature_c=82.0,
            has_temperature=True,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        # Should have one warning finding for temperature
        assert len(result.warning_findings) == 1
        assert result.warning_findings[0].category == "temperature"
        assert result.warning_findings[0].severity == Severity.MEDIUM
        assert result.warning_findings[0].current_value == 82.0
        assert result.warning_findings[0].threshold_value == 80.0

    def test_device_at_92c_critical_finding(self):
        """Device at 92C should generate critical finding (above 90C critical threshold)."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer
        from unifi_scanner.models.enums import Severity

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Hot Switch",
            temperature_c=92.0,
            has_temperature=True,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        # Should have one critical finding for temperature
        assert len(result.critical_findings) == 1
        assert result.critical_findings[0].category == "temperature"
        assert result.critical_findings[0].severity == Severity.SEVERE
        assert result.critical_findings[0].current_value == 92.0
        assert result.critical_findings[0].threshold_value == 90.0

    def test_device_with_no_temperature_data_no_finding(self):
        """Device without temperature data should not generate temperature finding."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="No Temp Switch",
            temperature_c=None,
            has_temperature=False,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        # Should have no temperature findings
        temp_findings = [
            f for f in result.warning_findings + result.critical_findings
            if f.category == "temperature"
        ]
        assert len(temp_findings) == 0

    def test_temperature_at_exactly_80c_no_warning(self):
        """Device at exactly 80C should not generate warning (threshold is >80, not >=80)."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Threshold Switch",
            temperature_c=80.0,
            has_temperature=True,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        # Should have no findings (80.0 is not > 80.0)
        temp_findings = [
            f for f in result.warning_findings + result.critical_findings
            if f.category == "temperature"
        ]
        assert len(temp_findings) == 0


class TestAnalyzerCpuChecks:
    """Tests for DeviceHealthAnalyzer CPU threshold checking."""

    def test_cpu_at_50_percent_no_finding(self):
        """CPU at 50% should not generate finding."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Normal CPU",
            cpu_percent=50.0,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        cpu_findings = [
            f for f in result.warning_findings + result.critical_findings
            if f.category == "cpu"
        ]
        assert len(cpu_findings) == 0

    def test_cpu_at_82_percent_warning_finding(self):
        """CPU at 82% should generate warning finding (above 80% threshold)."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer
        from unifi_scanner.models.enums import Severity

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Busy CPU",
            cpu_percent=82.0,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        assert len(result.warning_findings) == 1
        assert result.warning_findings[0].category == "cpu"
        assert result.warning_findings[0].severity == Severity.MEDIUM
        assert result.warning_findings[0].current_value == 82.0
        assert result.warning_findings[0].threshold_value == 80

    def test_cpu_at_96_percent_critical_finding(self):
        """CPU at 96% should generate critical finding (above 95% threshold)."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer
        from unifi_scanner.models.enums import Severity

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Maxed CPU",
            cpu_percent=96.0,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        assert len(result.critical_findings) == 1
        assert result.critical_findings[0].category == "cpu"
        assert result.critical_findings[0].severity == Severity.SEVERE
        assert result.critical_findings[0].current_value == 96.0
        assert result.critical_findings[0].threshold_value == 95

    def test_cpu_none_no_finding(self):
        """Device with cpu_percent=None should not generate CPU finding."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="No CPU Data",
            cpu_percent=None,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        cpu_findings = [
            f for f in result.warning_findings + result.critical_findings
            if f.category == "cpu"
        ]
        assert len(cpu_findings) == 0


class TestAnalyzerMemoryChecks:
    """Tests for DeviceHealthAnalyzer memory threshold checking."""

    def test_memory_at_70_percent_no_finding(self):
        """Memory at 70% should not generate finding."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Normal Memory",
            memory_percent=70.0,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        memory_findings = [
            f for f in result.warning_findings + result.critical_findings
            if f.category == "memory"
        ]
        assert len(memory_findings) == 0

    def test_memory_at_87_percent_warning_finding(self):
        """Memory at 87% should generate warning finding (above 85% threshold)."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer
        from unifi_scanner.models.enums import Severity

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="High Memory",
            memory_percent=87.0,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        assert len(result.warning_findings) == 1
        assert result.warning_findings[0].category == "memory"
        assert result.warning_findings[0].severity == Severity.MEDIUM
        assert result.warning_findings[0].current_value == 87.0
        assert result.warning_findings[0].threshold_value == 85

    def test_memory_at_96_percent_critical_finding(self):
        """Memory at 96% should generate critical finding (above 95% threshold)."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer
        from unifi_scanner.models.enums import Severity

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Maxed Memory",
            memory_percent=96.0,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        assert len(result.critical_findings) == 1
        assert result.critical_findings[0].category == "memory"
        assert result.critical_findings[0].severity == Severity.SEVERE
        assert result.critical_findings[0].current_value == 96.0
        assert result.critical_findings[0].threshold_value == 95

    def test_memory_none_no_finding(self):
        """Device with memory_percent=None should not generate memory finding."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="No Memory Data",
            memory_percent=None,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        memory_findings = [
            f for f in result.warning_findings + result.critical_findings
            if f.category == "memory"
        ]
        assert len(memory_findings) == 0


class TestAnalyzerUptimeChecks:
    """Tests for DeviceHealthAnalyzer uptime threshold checking."""

    def test_uptime_30_days_no_finding(self):
        """Uptime of 30 days should not generate finding."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Fresh Device",
            uptime_seconds=30 * 86400,  # 30 days
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        uptime_findings = [
            f for f in result.warning_findings + result.critical_findings
            if f.category == "uptime"
        ]
        assert len(uptime_findings) == 0

    def test_uptime_95_days_warning_finding(self):
        """Uptime of 95 days should generate warning finding (above 90 day threshold)."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer
        from unifi_scanner.models.enums import Severity

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Long Running",
            uptime_seconds=95 * 86400,  # 95 days
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        assert len(result.warning_findings) == 1
        assert result.warning_findings[0].category == "uptime"
        assert result.warning_findings[0].severity == Severity.MEDIUM
        assert result.warning_findings[0].current_value == pytest.approx(95.0, rel=0.01)
        assert result.warning_findings[0].threshold_value == 90

    def test_uptime_200_days_critical_finding(self):
        """Uptime of 200 days should generate critical finding (above 180 day threshold)."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer
        from unifi_scanner.models.enums import Severity

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Ancient Device",
            uptime_seconds=200 * 86400,  # 200 days
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        assert len(result.critical_findings) == 1
        assert result.critical_findings[0].category == "uptime"
        assert result.critical_findings[0].severity == Severity.SEVERE
        assert result.critical_findings[0].current_value == pytest.approx(200.0, rel=0.01)
        assert result.critical_findings[0].threshold_value == 180

    def test_uptime_none_no_finding(self):
        """Device with uptime_seconds=None should not generate uptime finding."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="No Uptime Data",
            uptime_seconds=None,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        uptime_findings = [
            f for f in result.warning_findings + result.critical_findings
            if f.category == "uptime"
        ]
        assert len(uptime_findings) == 0


class TestAnalyzerResultStructure:
    """Tests for DeviceHealthAnalyzer result structure and aggregation."""

    def test_empty_device_list_returns_empty_result(self):
        """Empty device list should return empty result with zeros."""
        from unifi_scanner.analysis.device_health import DeviceHealthAnalyzer

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([])

        assert result.total_devices == 0
        assert result.healthy_devices == 0
        assert result.devices_with_warnings == 0
        assert result.devices_with_critical == 0
        assert len(result.critical_findings) == 0
        assert len(result.warning_findings) == 0
        assert len(result.device_summaries) == 0

    def test_three_healthy_devices_correct_counts(self):
        """Three healthy devices should show 3 summaries, 0 findings, healthy_devices=3."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        devices = [
            DeviceStats(mac="00:11:22:33:44:55", name="Healthy 1", cpu_percent=30.0),
            DeviceStats(mac="aa:bb:cc:dd:ee:ff", name="Healthy 2", cpu_percent=40.0),
            DeviceStats(mac="11:22:33:44:55:66", name="Healthy 3", cpu_percent=50.0),
        ]

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices(devices)

        assert result.total_devices == 3
        assert result.healthy_devices == 3
        assert result.devices_with_warnings == 0
        assert result.devices_with_critical == 0
        assert len(result.critical_findings) == 0
        assert len(result.warning_findings) == 0
        assert len(result.device_summaries) == 3

    def test_mixed_devices_correct_counts(self):
        """1 critical, 1 warning, 1 healthy should have correct counts."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        devices = [
            DeviceStats(
                mac="00:11:22:33:44:55",
                name="Critical Device",
                temperature_c=95.0,
                has_temperature=True,
            ),
            DeviceStats(
                mac="aa:bb:cc:dd:ee:ff",
                name="Warning Device",
                cpu_percent=85.0,
            ),
            DeviceStats(
                mac="11:22:33:44:55:66",
                name="Healthy Device",
                cpu_percent=30.0,
            ),
        ]

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices(devices)

        assert result.total_devices == 3
        assert result.healthy_devices == 1
        assert result.devices_with_warnings == 1
        assert result.devices_with_critical == 1
        assert len(result.critical_findings) == 1
        assert len(result.warning_findings) == 1
        assert len(result.device_summaries) == 3

    def test_device_with_multiple_issues(self):
        """Device with multiple issues (hot AND high CPU) should generate multiple findings."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Problem Device",
            temperature_c=92.0,
            has_temperature=True,
            cpu_percent=96.0,
            memory_percent=96.0,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        # Should have 3 critical findings (temp, cpu, memory)
        assert len(result.critical_findings) == 3

        # Verify each category is present
        categories = {f.category for f in result.critical_findings}
        assert categories == {"temperature", "cpu", "memory"}

        # Still counts as 1 device with critical issues
        assert result.devices_with_critical == 1
        assert result.total_devices == 1

    def test_findings_sorted_by_severity(self):
        """Findings should be sorted by severity (critical before warning)."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer
        from unifi_scanner.models.enums import Severity

        devices = [
            DeviceStats(
                mac="00:11:22:33:44:55",
                name="Warning Device",
                cpu_percent=85.0,  # Warning
            ),
            DeviceStats(
                mac="aa:bb:cc:dd:ee:ff",
                name="Critical Device",
                temperature_c=95.0,  # Critical
                has_temperature=True,
            ),
        ]

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices(devices)

        # Critical findings come before warning findings in the structure
        assert len(result.critical_findings) == 1
        assert len(result.warning_findings) == 1
        assert result.critical_findings[0].severity == Severity.SEVERE
        assert result.warning_findings[0].severity == Severity.MEDIUM


class TestAnalyzerRemediation:
    """Tests for DeviceHealthAnalyzer remediation guidance."""

    def test_temperature_warning_has_remediation(self):
        """Temperature warning should include remediation guidance."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Warm Device",
            temperature_c=82.0,
            has_temperature=True,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        assert len(result.warning_findings) == 1
        assert result.warning_findings[0].remediation is not None
        # Should mention ventilation or cooling
        remediation = result.warning_findings[0].remediation.lower()
        assert "ventilation" in remediation or "cooling" in remediation or "airflow" in remediation

    def test_cpu_warning_has_remediation(self):
        """CPU warning should include remediation guidance."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Busy Device",
            cpu_percent=85.0,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        assert len(result.warning_findings) == 1
        assert result.warning_findings[0].remediation is not None
        # Should mention processes or tasks
        remediation = result.warning_findings[0].remediation.lower()
        assert "process" in remediation or "task" in remediation or "load" in remediation

    def test_memory_warning_has_remediation(self):
        """Memory warning should include remediation guidance."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Memory Full",
            memory_percent=88.0,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        assert len(result.warning_findings) == 1
        assert result.warning_findings[0].remediation is not None
        # Should mention restart or memory
        remediation = result.warning_findings[0].remediation.lower()
        assert "restart" in remediation or "memory" in remediation or "reboot" in remediation

    def test_uptime_warning_has_remediation(self):
        """Uptime warning should include remediation guidance."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Long Running",
            uptime_seconds=100 * 86400,  # 100 days
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([device])

        assert len(result.warning_findings) == 1
        assert result.warning_findings[0].remediation is not None
        # Should mention restart or maintenance
        remediation = result.warning_findings[0].remediation.lower()
        assert "restart" in remediation or "maintenance" in remediation or "reboot" in remediation


class TestAnalyzerCustomThresholds:
    """Tests for DeviceHealthAnalyzer with custom thresholds."""

    def test_analyzer_with_custom_thresholds(self):
        """Analyzer should respect custom threshold values."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer
        from unifi_scanner.analysis.device_health.thresholds import HealthThresholds

        # Custom thresholds: warn at 60C instead of 80C
        custom = HealthThresholds(
            temp_warning=60.0,
            temp_critical=75.0,
            cpu_warning=80,
            cpu_critical=95,
            memory_warning=85,
            memory_critical=95,
            uptime_warning=90,
            uptime_critical=180,
        )

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Moderate Temp",
            temperature_c=65.0,
            has_temperature=True,
        )

        analyzer = DeviceHealthAnalyzer(thresholds=custom)
        result = analyzer.analyze_devices([device])

        # With custom thresholds, 65C is above 60C warning
        assert len(result.warning_findings) == 1
        assert result.warning_findings[0].threshold_value == 60.0

    def test_analyzer_defaults_to_default_thresholds(self):
        """Analyzer without explicit thresholds should use DEFAULT_THRESHOLDS."""
        from unifi_scanner.analysis.device_health import DeviceStats, DeviceHealthAnalyzer

        device = DeviceStats(
            mac="00:11:22:33:44:55",
            name="Normal Temp",
            temperature_c=75.0,  # Below default 80C warning
            has_temperature=True,
        )

        analyzer = DeviceHealthAnalyzer()  # No thresholds specified
        result = analyzer.analyze_devices([device])

        # Should not trigger warning with default 80C threshold
        temp_findings = [
            f for f in result.warning_findings + result.critical_findings
            if f.category == "temperature"
        ]
        assert len(temp_findings) == 0


class TestAnalyzerExports:
    """Tests for module exports."""

    def test_analyzer_exported_from_module(self):
        """DeviceHealthAnalyzer should be exported from device_health module."""
        from unifi_scanner.analysis.device_health import DeviceHealthAnalyzer

        assert DeviceHealthAnalyzer is not None

    def test_thresholds_exported_from_module(self):
        """HealthThresholds and DEFAULT_THRESHOLDS should be exported."""
        from unifi_scanner.analysis.device_health import (
            HealthThresholds,
            DEFAULT_THRESHOLDS,
        )

        assert HealthThresholds is not None
        assert DEFAULT_THRESHOLDS is not None

    def test_analyze_devices_returns_device_health_result(self):
        """analyze_devices method should return DeviceHealthResult type."""
        from unifi_scanner.analysis.device_health import (
            DeviceHealthAnalyzer,
            DeviceHealthResult,
        )

        analyzer = DeviceHealthAnalyzer()
        result = analyzer.analyze_devices([])

        assert isinstance(result, DeviceHealthResult)
