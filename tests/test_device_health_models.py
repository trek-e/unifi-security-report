"""Tests for Device Health models.

TDD tests for Phase 9: Device Health Monitoring.
Tests DeviceStats parsing, DeviceHealthFinding, and DeviceHealthResult models.
"""

import pytest


class TestDeviceStatsFromApiResponse:
    """Tests for DeviceStats.from_api_response factory method."""

    def test_full_device_response_parses_all_fields(self):
        """Full device response with all fields should populate all properties."""
        from unifi_scanner.analysis.device_health.models import DeviceStats

        raw_response = {
            "mac": "00:11:22:33:44:55",
            "name": "Office Switch",
            "model": "USW-24-PoE",
            "type": "usw",
            "system-stats": {
                "cpu": "15.2",
                "mem": "42.8",
            },
            "temps": {
                "Board (CPU)": "72 C",
            },
            "uptime": 7776000,  # 90 days
        }

        device = DeviceStats.from_api_response(raw_response)

        assert device.mac == "00:11:22:33:44:55"
        assert device.name == "Office Switch"
        assert device.model == "USW-24-PoE"
        assert device.device_type == "usw"
        assert device.cpu_percent == pytest.approx(15.2)
        assert device.memory_percent == pytest.approx(42.8)
        assert device.temperature_c == pytest.approx(72.0)
        assert device.has_temperature is True
        assert device.uptime_seconds == 7776000
        assert device.uptime_days == pytest.approx(90.0)
        assert device.uptime_display == "90d 0h 0m"

    def test_missing_system_stats_returns_none_for_cpu_memory(self):
        """Missing system-stats should result in None for cpu/memory."""
        from unifi_scanner.analysis.device_health.models import DeviceStats

        raw_response = {
            "mac": "aa:bb:cc:dd:ee:ff",
            "name": "Access Point",
            "model": "U6-LR",
            "type": "uap",
            # No system-stats key
            "uptime": 3600,
        }

        device = DeviceStats.from_api_response(raw_response)

        assert device.mac == "aa:bb:cc:dd:ee:ff"
        assert device.cpu_percent is None
        assert device.memory_percent is None
        assert device.uptime_seconds == 3600

    def test_temperature_from_temps_dict_string_format(self):
        """Temperature in temps dict '72 C' format should parse to float 72.0."""
        from unifi_scanner.analysis.device_health.models import DeviceStats

        raw_response = {
            "mac": "11:22:33:44:55:66",
            "temps": {
                "Board (CPU)": "72 C",
                "Board (PHY)": "68 C",
            },
        }

        device = DeviceStats.from_api_response(raw_response)

        assert device.temperature_c == pytest.approx(72.0)
        assert device.has_temperature is True

    def test_temperature_from_general_temperature_field(self):
        """Temperature in general_temperature field should be used directly."""
        from unifi_scanner.analysis.device_health.models import DeviceStats

        raw_response = {
            "mac": "11:22:33:44:55:66",
            "general_temperature": 65.5,
            # No temps dict
        }

        device = DeviceStats.from_api_response(raw_response)

        assert device.temperature_c == pytest.approx(65.5)
        assert device.has_temperature is True

    def test_no_temperature_data_results_in_none(self):
        """No temperature data should result in temperature_c=None and has_temperature=False."""
        from unifi_scanner.analysis.device_health.models import DeviceStats

        raw_response = {
            "mac": "11:22:33:44:55:66",
            # No temps or general_temperature
        }

        device = DeviceStats.from_api_response(raw_response)

        assert device.temperature_c is None
        assert device.has_temperature is False

    def test_uptime_90_days_formats_correctly(self):
        """Uptime of 90 days (7776000 seconds) should format as '90d 0h 0m'."""
        from unifi_scanner.analysis.device_health.models import DeviceStats

        raw_response = {
            "mac": "11:22:33:44:55:66",
            "uptime": 7776000,  # 90 days exactly
        }

        device = DeviceStats.from_api_response(raw_response)

        assert device.uptime_seconds == 7776000
        assert device.uptime_days == pytest.approx(90.0)
        assert device.uptime_display == "90d 0h 0m"

    def test_uptime_zero_formats_correctly(self):
        """Uptime of 0 seconds should format as '0m' and uptime_days=0.0."""
        from unifi_scanner.analysis.device_health.models import DeviceStats

        raw_response = {
            "mac": "11:22:33:44:55:66",
            "uptime": 0,
        }

        device = DeviceStats.from_api_response(raw_response)

        assert device.uptime_seconds == 0
        assert device.uptime_days == pytest.approx(0.0)
        assert device.uptime_display == "0m"

    def test_uptime_partial_days_formats_correctly(self):
        """Uptime with partial days should format with days, hours, minutes."""
        from unifi_scanner.analysis.device_health.models import DeviceStats

        # 2 days, 5 hours, 30 minutes = 2*86400 + 5*3600 + 30*60 = 192600 seconds
        raw_response = {
            "mac": "11:22:33:44:55:66",
            "uptime": 192600,
        }

        device = DeviceStats.from_api_response(raw_response)

        assert device.uptime_seconds == 192600
        assert device.uptime_days == pytest.approx(2.2292, rel=0.01)
        assert device.uptime_display == "2d 5h 30m"

    def test_missing_mac_uses_default(self):
        """Missing mac should use empty string default."""
        from unifi_scanner.analysis.device_health.models import DeviceStats

        raw_response = {}

        device = DeviceStats.from_api_response(raw_response)

        assert device.mac == ""

    def test_missing_name_uses_default(self):
        """Missing name should use 'Unknown' default."""
        from unifi_scanner.analysis.device_health.models import DeviceStats

        raw_response = {"mac": "aa:bb:cc:dd:ee:ff"}

        device = DeviceStats.from_api_response(raw_response)

        assert device.name == "Unknown"

    def test_temps_with_non_cpu_keys_uses_first_available(self):
        """Temps dict without 'Board (CPU)' should use first available temperature."""
        from unifi_scanner.analysis.device_health.models import DeviceStats

        raw_response = {
            "mac": "11:22:33:44:55:66",
            "temps": {
                "PHY": "55 C",
            },
        }

        device = DeviceStats.from_api_response(raw_response)

        assert device.temperature_c == pytest.approx(55.0)
        assert device.has_temperature is True


class TestDeviceHealthFinding:
    """Tests for DeviceHealthFinding dataclass."""

    def test_finding_creation_with_all_fields(self):
        """Finding should store all provided fields correctly."""
        from unifi_scanner.analysis.device_health.models import DeviceHealthFinding
        from unifi_scanner.models.enums import Severity

        finding = DeviceHealthFinding(
            device_mac="00:11:22:33:44:55",
            device_name="Office Switch",
            severity=Severity.SEVERE,
            category="temperature",
            title="High Temperature Alert",
            description="Device temperature is critically high",
            current_value=95.0,
            threshold_value=90.0,
            remediation="Check ventilation and clean dust filters",
        )

        assert finding.device_mac == "00:11:22:33:44:55"
        assert finding.device_name == "Office Switch"
        assert finding.severity == Severity.SEVERE
        assert finding.category == "temperature"
        assert finding.title == "High Temperature Alert"
        assert finding.description == "Device temperature is critically high"
        assert finding.current_value == 95.0
        assert finding.threshold_value == 90.0
        assert finding.remediation == "Check ventilation and clean dust filters"

    def test_is_critical_returns_true_for_severe_severity(self):
        """is_critical property should return True when severity is SEVERE."""
        from unifi_scanner.analysis.device_health.models import DeviceHealthFinding
        from unifi_scanner.models.enums import Severity

        finding = DeviceHealthFinding(
            device_mac="00:11:22:33:44:55",
            device_name="Switch",
            severity=Severity.SEVERE,
            category="temperature",
            title="Critical Temperature",
            description="Temperature is critical",
            current_value=95.0,
            threshold_value=90.0,
        )

        assert finding.is_critical is True

    def test_is_critical_returns_false_for_medium_severity(self):
        """is_critical property should return False when severity is MEDIUM."""
        from unifi_scanner.analysis.device_health.models import DeviceHealthFinding
        from unifi_scanner.models.enums import Severity

        finding = DeviceHealthFinding(
            device_mac="00:11:22:33:44:55",
            device_name="Switch",
            severity=Severity.MEDIUM,
            category="temperature",
            title="Temperature Warning",
            description="Temperature is elevated",
            current_value=82.0,
            threshold_value=80.0,
        )

        assert finding.is_critical is False

    def test_is_critical_returns_false_for_low_severity(self):
        """is_critical property should return False when severity is LOW."""
        from unifi_scanner.analysis.device_health.models import DeviceHealthFinding
        from unifi_scanner.models.enums import Severity

        finding = DeviceHealthFinding(
            device_mac="00:11:22:33:44:55",
            device_name="Switch",
            severity=Severity.LOW,
            category="uptime",
            title="Extended Uptime",
            description="Device has been running for a long time",
            current_value=100.0,
            threshold_value=90.0,
        )

        assert finding.is_critical is False

    def test_finding_with_optional_remediation_none(self):
        """Finding with no remediation should have remediation as None."""
        from unifi_scanner.analysis.device_health.models import DeviceHealthFinding
        from unifi_scanner.models.enums import Severity

        finding = DeviceHealthFinding(
            device_mac="00:11:22:33:44:55",
            device_name="Switch",
            severity=Severity.MEDIUM,
            category="cpu",
            title="High CPU",
            description="CPU usage is high",
            current_value=85.0,
            threshold_value=80.0,
        )

        assert finding.remediation is None


class TestDeviceHealthSummary:
    """Tests for DeviceHealthSummary dataclass."""

    def test_summary_creation(self):
        """DeviceHealthSummary should store device-level summary correctly."""
        from unifi_scanner.analysis.device_health.models import DeviceHealthSummary

        summary = DeviceHealthSummary(
            device_mac="00:11:22:33:44:55",
            device_name="Office Switch",
            device_type="usw",
            critical_count=1,
            warning_count=2,
            is_healthy=False,
        )

        assert summary.device_mac == "00:11:22:33:44:55"
        assert summary.device_name == "Office Switch"
        assert summary.device_type == "usw"
        assert summary.critical_count == 1
        assert summary.warning_count == 2
        assert summary.is_healthy is False

    def test_healthy_device_summary(self):
        """Healthy device should have zero counts and is_healthy=True."""
        from unifi_scanner.analysis.device_health.models import DeviceHealthSummary

        summary = DeviceHealthSummary(
            device_mac="00:11:22:33:44:55",
            device_name="Healthy AP",
            device_type="uap",
            critical_count=0,
            warning_count=0,
            is_healthy=True,
        )

        assert summary.critical_count == 0
        assert summary.warning_count == 0
        assert summary.is_healthy is True


class TestDeviceHealthResult:
    """Tests for DeviceHealthResult dataclass."""

    def test_empty_result_has_no_issues(self):
        """Empty DeviceHealthResult should have has_issues=False."""
        from unifi_scanner.analysis.device_health.models import DeviceHealthResult

        result = DeviceHealthResult(
            critical_findings=[],
            warning_findings=[],
            device_summaries=[],
            total_devices=5,
            healthy_devices=5,
            devices_with_warnings=0,
            devices_with_critical=0,
        )

        assert result.has_issues is False
        assert result.total_devices == 5
        assert result.healthy_devices == 5

    def test_result_with_critical_findings_has_issues(self):
        """DeviceHealthResult with critical findings should have has_issues=True."""
        from unifi_scanner.analysis.device_health.models import (
            DeviceHealthResult,
            DeviceHealthFinding,
        )
        from unifi_scanner.models.enums import Severity

        critical = DeviceHealthFinding(
            device_mac="00:11:22:33:44:55",
            device_name="Switch",
            severity=Severity.SEVERE,
            category="temperature",
            title="Critical Temperature",
            description="Temperature is critical",
            current_value=95.0,
            threshold_value=90.0,
        )

        result = DeviceHealthResult(
            critical_findings=[critical],
            warning_findings=[],
            device_summaries=[],
            total_devices=5,
            healthy_devices=4,
            devices_with_warnings=0,
            devices_with_critical=1,
        )

        assert result.has_issues is True
        assert len(result.critical_findings) == 1
        assert result.devices_with_critical == 1

    def test_result_with_warning_findings_has_issues(self):
        """DeviceHealthResult with warning findings should have has_issues=True."""
        from unifi_scanner.analysis.device_health.models import (
            DeviceHealthResult,
            DeviceHealthFinding,
        )
        from unifi_scanner.models.enums import Severity

        warning = DeviceHealthFinding(
            device_mac="00:11:22:33:44:55",
            device_name="Switch",
            severity=Severity.MEDIUM,
            category="cpu",
            title="High CPU",
            description="CPU usage elevated",
            current_value=85.0,
            threshold_value=80.0,
        )

        result = DeviceHealthResult(
            critical_findings=[],
            warning_findings=[warning],
            device_summaries=[],
            total_devices=5,
            healthy_devices=4,
            devices_with_warnings=1,
            devices_with_critical=0,
        )

        assert result.has_issues is True
        assert len(result.warning_findings) == 1
        assert result.devices_with_warnings == 1

    def test_result_counts_match_findings(self):
        """Device counts should reflect actual findings."""
        from unifi_scanner.analysis.device_health.models import (
            DeviceHealthResult,
            DeviceHealthFinding,
            DeviceHealthSummary,
        )
        from unifi_scanner.models.enums import Severity

        critical = DeviceHealthFinding(
            device_mac="00:11:22:33:44:55",
            device_name="Switch 1",
            severity=Severity.SEVERE,
            category="temperature",
            title="Critical",
            description="Critical issue",
            current_value=95.0,
            threshold_value=90.0,
        )

        warning1 = DeviceHealthFinding(
            device_mac="aa:bb:cc:dd:ee:ff",
            device_name="Switch 2",
            severity=Severity.MEDIUM,
            category="cpu",
            title="Warning",
            description="Warning issue",
            current_value=85.0,
            threshold_value=80.0,
        )

        warning2 = DeviceHealthFinding(
            device_mac="aa:bb:cc:dd:ee:ff",
            device_name="Switch 2",
            severity=Severity.MEDIUM,
            category="memory",
            title="Warning 2",
            description="Another warning",
            current_value=88.0,
            threshold_value=85.0,
        )

        summary1 = DeviceHealthSummary(
            device_mac="00:11:22:33:44:55",
            device_name="Switch 1",
            device_type="usw",
            critical_count=1,
            warning_count=0,
            is_healthy=False,
        )

        summary2 = DeviceHealthSummary(
            device_mac="aa:bb:cc:dd:ee:ff",
            device_name="Switch 2",
            device_type="usw",
            critical_count=0,
            warning_count=2,
            is_healthy=False,
        )

        result = DeviceHealthResult(
            critical_findings=[critical],
            warning_findings=[warning1, warning2],
            device_summaries=[summary1, summary2],
            total_devices=5,
            healthy_devices=3,
            devices_with_warnings=1,
            devices_with_critical=1,
        )

        assert result.total_devices == 5
        assert result.healthy_devices == 3
        assert result.devices_with_warnings == 1
        assert result.devices_with_critical == 1
        assert len(result.device_summaries) == 2
