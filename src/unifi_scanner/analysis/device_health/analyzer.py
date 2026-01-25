"""Device health analyzer for processing device statistics and generating findings.

Analyzes device metrics against configurable thresholds and produces
health findings with remediation guidance.
"""

from typing import List, Optional

from unifi_scanner.models.enums import Severity
from unifi_scanner.analysis.device_health.models import (
    DeviceStats,
    DeviceHealthFinding,
    DeviceHealthSummary,
    DeviceHealthResult,
)
from unifi_scanner.analysis.device_health.thresholds import (
    HealthThresholds,
    DEFAULT_THRESHOLDS,
)


# Remediation templates by category
_REMEDIATION_TEMPLATES = {
    "temperature": {
        "warning": (
            "Check device ventilation and airflow. Ensure the device is not in "
            "an enclosed space or near heat sources. Consider adding cooling "
            "or relocating the device to a cooler area."
        ),
        "critical": (
            "URGENT: Device is at risk of thermal throttling or damage. "
            "Immediately check ventilation, reduce device load, and consider "
            "adding active cooling. Relocate device to a cooler location if possible. "
            "Schedule maintenance to clean dust from vents and fans."
        ),
    },
    "cpu": {
        "warning": (
            "Identify processes consuming high CPU. Check for runaway tasks "
            "or unusual network activity. Consider rebooting the device during "
            "a maintenance window to clear any stuck processes."
        ),
        "critical": (
            "URGENT: Device CPU is critically overloaded. Identify and address "
            "the source of high load immediately. Check for DoS attacks, "
            "runaway processes, or configuration issues. Reboot may be required."
        ),
    },
    "memory": {
        "warning": (
            "Memory usage is elevated. Consider scheduling a device restart "
            "during a maintenance window to clear memory. Check for memory leaks "
            "or unusual number of connected clients."
        ),
        "critical": (
            "URGENT: Device is nearly out of memory. Restart the device as soon "
            "as possible to prevent instability or crashes. Investigate cause "
            "of high memory usage after restart."
        ),
    },
    "uptime": {
        "warning": (
            "Device has been running for an extended period. Schedule a restart "
            "during your next maintenance window to apply any pending updates "
            "and clear accumulated memory fragmentation."
        ),
        "critical": (
            "Device uptime is very high. Strongly recommend scheduling a restart "
            "soon. Extended uptime can lead to instability, memory fragmentation, "
            "and missed security updates. Plan maintenance immediately."
        ),
    },
}


class DeviceHealthAnalyzer:
    """Analyzer for device health metrics.

    Processes device statistics and generates health findings when metrics
    exceed configured thresholds. Follows the IPSAnalyzer pattern from Phase 8.
    """

    def __init__(self, thresholds: Optional[HealthThresholds] = None):
        """Initialize the analyzer with optional custom thresholds.

        Args:
            thresholds: Custom health thresholds. Defaults to DEFAULT_THRESHOLDS.
        """
        self._thresholds = thresholds or DEFAULT_THRESHOLDS

    def analyze_devices(self, devices: List[DeviceStats]) -> DeviceHealthResult:
        """Analyze device statistics and produce health findings.

        Args:
            devices: List of DeviceStats to analyze

        Returns:
            DeviceHealthResult with categorized findings and summaries
        """
        if not devices:
            return DeviceHealthResult(
                critical_findings=[],
                warning_findings=[],
                device_summaries=[],
                total_devices=0,
                healthy_devices=0,
                devices_with_warnings=0,
                devices_with_critical=0,
            )

        critical_findings: List[DeviceHealthFinding] = []
        warning_findings: List[DeviceHealthFinding] = []
        device_summaries: List[DeviceHealthSummary] = []

        devices_with_critical = 0
        devices_with_warnings = 0
        healthy_devices = 0

        for device in devices:
            device_critical: List[DeviceHealthFinding] = []
            device_warnings: List[DeviceHealthFinding] = []

            # Check all metrics for this device
            temp_finding = self._check_temperature(device)
            if temp_finding:
                if temp_finding.severity == Severity.SEVERE:
                    device_critical.append(temp_finding)
                else:
                    device_warnings.append(temp_finding)

            cpu_finding = self._check_cpu(device)
            if cpu_finding:
                if cpu_finding.severity == Severity.SEVERE:
                    device_critical.append(cpu_finding)
                else:
                    device_warnings.append(cpu_finding)

            memory_finding = self._check_memory(device)
            if memory_finding:
                if memory_finding.severity == Severity.SEVERE:
                    device_critical.append(memory_finding)
                else:
                    device_warnings.append(memory_finding)

            uptime_finding = self._check_uptime(device)
            if uptime_finding:
                if uptime_finding.severity == Severity.SEVERE:
                    device_critical.append(uptime_finding)
                else:
                    device_warnings.append(uptime_finding)

            # Aggregate findings
            critical_findings.extend(device_critical)
            warning_findings.extend(device_warnings)

            # Determine device health status
            has_critical = len(device_critical) > 0
            has_warnings = len(device_warnings) > 0
            is_healthy = not has_critical and not has_warnings

            if has_critical:
                devices_with_critical += 1
            elif has_warnings:
                devices_with_warnings += 1
            else:
                healthy_devices += 1

            # Create device summary
            summary = DeviceHealthSummary(
                device_mac=device.mac,
                device_name=device.name,
                device_type=device.device_type,
                critical_count=len(device_critical),
                warning_count=len(device_warnings),
                is_healthy=is_healthy,
            )
            device_summaries.append(summary)

        return DeviceHealthResult(
            critical_findings=critical_findings,
            warning_findings=warning_findings,
            device_summaries=device_summaries,
            total_devices=len(devices),
            healthy_devices=healthy_devices,
            devices_with_warnings=devices_with_warnings,
            devices_with_critical=devices_with_critical,
        )

    def _check_temperature(self, device: DeviceStats) -> Optional[DeviceHealthFinding]:
        """Check device temperature against thresholds.

        Args:
            device: Device statistics to check

        Returns:
            DeviceHealthFinding if threshold exceeded, None otherwise
        """
        if not device.has_temperature or device.temperature_c is None:
            return None

        temp = device.temperature_c

        # Check critical first
        if temp > self._thresholds.temp_critical:
            return DeviceHealthFinding(
                device_mac=device.mac,
                device_name=device.name,
                severity=Severity.SEVERE,
                category="temperature",
                title="Critical Temperature Alert",
                description=(
                    f"Device temperature is critically high at {temp:.1f}C. "
                    f"Thermal throttling may occur above {self._thresholds.temp_critical}C."
                ),
                current_value=temp,
                threshold_value=self._thresholds.temp_critical,
                remediation=_REMEDIATION_TEMPLATES["temperature"]["critical"],
            )

        # Check warning
        if temp > self._thresholds.temp_warning:
            return DeviceHealthFinding(
                device_mac=device.mac,
                device_name=device.name,
                severity=Severity.MEDIUM,
                category="temperature",
                title="High Temperature Warning",
                description=(
                    f"Device temperature is elevated at {temp:.1f}C. "
                    f"Consider improving cooling when temperature exceeds "
                    f"{self._thresholds.temp_warning}C."
                ),
                current_value=temp,
                threshold_value=self._thresholds.temp_warning,
                remediation=_REMEDIATION_TEMPLATES["temperature"]["warning"],
            )

        return None

    def _check_cpu(self, device: DeviceStats) -> Optional[DeviceHealthFinding]:
        """Check device CPU usage against thresholds.

        Args:
            device: Device statistics to check

        Returns:
            DeviceHealthFinding if threshold exceeded, None otherwise
        """
        if device.cpu_percent is None:
            return None

        cpu = device.cpu_percent

        # Check critical first
        if cpu > self._thresholds.cpu_critical:
            return DeviceHealthFinding(
                device_mac=device.mac,
                device_name=device.name,
                severity=Severity.SEVERE,
                category="cpu",
                title="Critical CPU Usage",
                description=(
                    f"Device CPU usage is critically high at {cpu:.1f}%. "
                    f"Performance degradation likely above {self._thresholds.cpu_critical}%."
                ),
                current_value=cpu,
                threshold_value=self._thresholds.cpu_critical,
                remediation=_REMEDIATION_TEMPLATES["cpu"]["critical"],
            )

        # Check warning
        if cpu > self._thresholds.cpu_warning:
            return DeviceHealthFinding(
                device_mac=device.mac,
                device_name=device.name,
                severity=Severity.MEDIUM,
                category="cpu",
                title="High CPU Usage",
                description=(
                    f"Device CPU usage is elevated at {cpu:.1f}%. "
                    f"Monitor for performance issues when above "
                    f"{self._thresholds.cpu_warning}%."
                ),
                current_value=cpu,
                threshold_value=self._thresholds.cpu_warning,
                remediation=_REMEDIATION_TEMPLATES["cpu"]["warning"],
            )

        return None

    def _check_memory(self, device: DeviceStats) -> Optional[DeviceHealthFinding]:
        """Check device memory usage against thresholds.

        Args:
            device: Device statistics to check

        Returns:
            DeviceHealthFinding if threshold exceeded, None otherwise
        """
        if device.memory_percent is None:
            return None

        memory = device.memory_percent

        # Check critical first
        if memory > self._thresholds.memory_critical:
            return DeviceHealthFinding(
                device_mac=device.mac,
                device_name=device.name,
                severity=Severity.SEVERE,
                category="memory",
                title="Critical Memory Usage",
                description=(
                    f"Device memory usage is critically high at {memory:.1f}%. "
                    f"System instability possible above {self._thresholds.memory_critical}%."
                ),
                current_value=memory,
                threshold_value=self._thresholds.memory_critical,
                remediation=_REMEDIATION_TEMPLATES["memory"]["critical"],
            )

        # Check warning
        if memory > self._thresholds.memory_warning:
            return DeviceHealthFinding(
                device_mac=device.mac,
                device_name=device.name,
                severity=Severity.MEDIUM,
                category="memory",
                title="High Memory Usage",
                description=(
                    f"Device memory usage is elevated at {memory:.1f}%. "
                    f"Consider a restart when above {self._thresholds.memory_warning}%."
                ),
                current_value=memory,
                threshold_value=self._thresholds.memory_warning,
                remediation=_REMEDIATION_TEMPLATES["memory"]["warning"],
            )

        return None

    def _check_uptime(self, device: DeviceStats) -> Optional[DeviceHealthFinding]:
        """Check device uptime against thresholds.

        Args:
            device: Device statistics to check

        Returns:
            DeviceHealthFinding if threshold exceeded, None otherwise
        """
        if device.uptime_seconds is None:
            return None

        uptime_days = device.uptime_days

        # Check critical first
        if uptime_days > self._thresholds.uptime_critical:
            return DeviceHealthFinding(
                device_mac=device.mac,
                device_name=device.name,
                severity=Severity.SEVERE,
                category="uptime",
                title="Extended Uptime - Restart Required",
                description=(
                    f"Device has been running for {uptime_days:.0f} days. "
                    f"Strongly recommend restart after {self._thresholds.uptime_critical} days."
                ),
                current_value=uptime_days,
                threshold_value=self._thresholds.uptime_critical,
                remediation=_REMEDIATION_TEMPLATES["uptime"]["critical"],
            )

        # Check warning
        if uptime_days > self._thresholds.uptime_warning:
            return DeviceHealthFinding(
                device_mac=device.mac,
                device_name=device.name,
                severity=Severity.MEDIUM,
                category="uptime",
                title="Extended Uptime - Consider Restart",
                description=(
                    f"Device has been running for {uptime_days:.0f} days. "
                    f"Consider scheduling restart after {self._thresholds.uptime_warning} days."
                ),
                current_value=uptime_days,
                threshold_value=self._thresholds.uptime_warning,
                remediation=_REMEDIATION_TEMPLATES["uptime"]["warning"],
            )

        return None
