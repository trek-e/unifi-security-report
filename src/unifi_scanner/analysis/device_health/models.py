"""Device health models for normalized UniFi device statistics and health findings.

Provides pydantic models for processing device stats from the UniFi API,
and dataclasses for health analysis findings and results.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from unifi_scanner.models.enums import Severity


class DeviceStats(BaseModel):
    """Normalized device statistics from UniFi stat/device API.

    Captures all relevant fields from UniFi device statistics with
    parsed temperature and computed uptime display.
    """

    model_config = ConfigDict(from_attributes=True)

    # Device identification
    mac: str = Field(default="", description="Device MAC address")
    name: str = Field(default="Unknown", description="Device name")
    model: str = Field(default="Unknown", description="Device model")
    device_type: str = Field(
        default="unknown", description="Device type: uap, usw, ugw, udm"
    )

    # System stats (from system-stats object)
    cpu_percent: Optional[float] = Field(
        default=None, description="CPU usage percentage"
    )
    memory_percent: Optional[float] = Field(
        default=None, description="Memory usage percentage"
    )
    uptime_seconds: Optional[int] = Field(default=None, description="Uptime in seconds")

    # Temperature (from temps object or general_temperature)
    temperature_c: Optional[float] = Field(
        default=None, description="Device temperature in Celsius"
    )
    has_temperature: bool = Field(
        default=False, description="Whether device reports temperature"
    )

    @property
    def uptime_days(self) -> float:
        """Calculate uptime in days."""
        if self.uptime_seconds is None:
            return 0.0
        return self.uptime_seconds / 86400.0

    @property
    def uptime_display(self) -> str:
        """Format uptime as human-readable string (e.g., '2d 5h 30m')."""
        if self.uptime_seconds is None or self.uptime_seconds == 0:
            return "0m"

        seconds = self.uptime_seconds
        days = seconds // 86400
        seconds %= 86400
        hours = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0 or days > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")

        return " ".join(parts)

    @classmethod
    def from_api_response(cls, response: Dict[str, Any]) -> "DeviceStats":
        """Factory for creating DeviceStats from raw UniFi stat/device API response.

        Args:
            response: Raw device dictionary from UniFi stat/device API

        Returns:
            DeviceStats instance with parsed fields
        """
        # Extract system stats if present
        system_stats = response.get("system-stats", {})
        cpu_percent: Optional[float] = None
        memory_percent: Optional[float] = None

        if system_stats:
            cpu_str = system_stats.get("cpu")
            if cpu_str is not None:
                try:
                    cpu_percent = float(cpu_str)
                except (ValueError, TypeError):
                    pass

            mem_str = system_stats.get("mem")
            if mem_str is not None:
                try:
                    memory_percent = float(mem_str)
                except (ValueError, TypeError):
                    pass

        # Parse temperature from temps dict or general_temperature
        temperature_c: Optional[float] = None
        has_temperature = False

        # Try general_temperature first (simple float)
        general_temp = response.get("general_temperature")
        if general_temp is not None:
            try:
                temperature_c = float(general_temp)
                has_temperature = True
            except (ValueError, TypeError):
                pass

        # Try temps dict if general_temperature not found
        if temperature_c is None:
            temps = response.get("temps", {})
            if temps:
                # Prefer "Board (CPU)" if available, otherwise take first available
                temp_str = temps.get("Board (CPU)")
                if temp_str is None and temps:
                    # Get first available temperature
                    temp_str = next(iter(temps.values()), None)

                if temp_str is not None:
                    # Parse format like "72 C"
                    temperature_c = _parse_temperature_string(temp_str)
                    if temperature_c is not None:
                        has_temperature = True

        return cls(
            mac=response.get("mac", ""),
            name=response.get("name", "Unknown"),
            model=response.get("model", "Unknown"),
            device_type=response.get("type", "unknown"),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            uptime_seconds=response.get("uptime"),
            temperature_c=temperature_c,
            has_temperature=has_temperature,
        )


def _parse_temperature_string(temp_str: str) -> Optional[float]:
    """Parse temperature string like '72 C' to float.

    Args:
        temp_str: Temperature string in format like '72 C' or '72.5 C'

    Returns:
        Temperature as float, or None if parsing fails
    """
    if not isinstance(temp_str, str):
        return None

    # Remove units and whitespace
    cleaned = temp_str.replace("C", "").replace("F", "").strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


@dataclass
class DeviceHealthFinding:
    """Individual health finding for a device.

    Captures a specific health issue with threshold context and optional
    remediation guidance.
    """

    device_mac: str
    device_name: str
    severity: Severity
    category: str  # temp, poe, uptime, cpu, memory
    title: str
    description: str
    current_value: float
    threshold_value: float
    remediation: Optional[str] = None

    @property
    def is_critical(self) -> bool:
        """Check if this finding is critical (SEVERE severity)."""
        return self.severity == Severity.SEVERE


@dataclass
class DeviceHealthSummary:
    """Per-device health status summary."""

    device_mac: str
    device_name: str
    device_type: str
    critical_count: int
    warning_count: int
    is_healthy: bool


@dataclass
class DeviceHealthResult:
    """Aggregated device health analysis result.

    Contains all health findings grouped by severity, plus per-device
    summaries and overall counts.
    """

    critical_findings: List[DeviceHealthFinding] = field(default_factory=list)
    warning_findings: List[DeviceHealthFinding] = field(default_factory=list)
    device_summaries: List[DeviceHealthSummary] = field(default_factory=list)
    total_devices: int = 0
    healthy_devices: int = 0
    devices_with_warnings: int = 0
    devices_with_critical: int = 0

    @property
    def has_issues(self) -> bool:
        """Check if there are any health issues."""
        return len(self.critical_findings) > 0 or len(self.warning_findings) > 0
