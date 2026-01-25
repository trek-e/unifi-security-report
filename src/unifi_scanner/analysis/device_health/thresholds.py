"""Device health threshold configuration.

Defines configurable thresholds for device health monitoring including
temperature, CPU, memory, and uptime limits.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthThresholds:
    """Configurable thresholds for device health monitoring.

    All thresholds use > comparison (value > threshold triggers alert).

    Attributes:
        temp_warning: Temperature warning threshold in Celsius (fan threshold)
        temp_critical: Temperature critical threshold (thermal throttling risk)
        cpu_warning: CPU usage warning threshold (percent)
        cpu_critical: CPU usage critical threshold (percent)
        memory_warning: Memory usage warning threshold (percent)
        memory_critical: Memory usage critical threshold (percent)
        uptime_warning: Uptime warning threshold in days
        uptime_critical: Uptime critical threshold in days
    """

    # Temperature thresholds (Celsius)
    temp_warning: float = 80.0
    temp_critical: float = 90.0

    # CPU thresholds (percent)
    cpu_warning: int = 80
    cpu_critical: int = 95

    # Memory thresholds (percent)
    memory_warning: int = 85
    memory_critical: int = 95

    # Uptime thresholds (days)
    uptime_warning: int = 90
    uptime_critical: int = 180


# Default thresholds for production use
DEFAULT_THRESHOLDS = HealthThresholds()
