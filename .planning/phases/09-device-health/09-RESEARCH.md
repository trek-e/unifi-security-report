# Phase 9: Device Health Monitoring - Research

**Researched:** 2026-01-25
**Domain:** UniFi Device Metrics, System Statistics, PoE Monitoring, Proactive Health Alerting
**Confidence:** HIGH

## Summary

This phase implements proactive device health monitoring by extending the existing data collection and analysis architecture. The UniFi API provides device health metrics through the `/stat/device` endpoint, which returns system statistics (CPU, memory, uptime) and temperature data. The project already has:

1. **API client infrastructure** (`UnifiClient`) for authenticated requests
2. **Parallel analysis pattern** from Phase 8 (`IPSAnalyzer`) for dedicated data processors
3. **Report generation** with Jinja2 templates and section-based output
4. **Pydantic models** for data validation and normalization

Device health data is distinct from log events - it comes from device polling (stat/device) rather than event streams. This phase creates a new `DeviceHealthAnalyzer` following the Phase 8 pattern, with dedicated models for device metrics and health findings. PoE events already flow through the event API (EVT_SW_PoeDisconnect) but device-level statistics require the stat/device endpoint.

**Primary recommendation:** Create a dedicated DeviceHealthAnalyzer module that polls stat/device data, applies threshold-based health analysis, and generates a "Device Health" report section similar to the existing threat section pattern.

## Standard Stack

### Core (Already in Project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.x | Data models for device metrics | Already used for IPSEvent, Finding, LogEntry |
| structlog | latest | Structured logging | Already used project-wide |
| jinja2 | 3.x | Report templates | Already used for HTML/text reports |
| httpx | latest | API requests | Already used in UnifiClient |

### Supporting (stdlib - No Install Needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses | stdlib | Result containers | Lightweight result objects |
| typing | stdlib | Type hints | Already used throughout |
| datetime | stdlib | Uptime calculations | Convert seconds to human-readable |

### No New Dependencies Required

The existing stack fully supports device health monitoring. No external libraries needed.

## Architecture Patterns

### Recommended Project Structure
```
src/unifi_scanner/
├── api/
│   ├── client.py             # ADD: get_devices() method
│   └── endpoints.py          # ADD: stat/device endpoint
├── analysis/
│   ├── device_health/        # NEW: Device health module
│   │   ├── __init__.py
│   │   ├── analyzer.py       # DeviceHealthAnalyzer class
│   │   ├── models.py         # DeviceStats, DeviceHealthResult
│   │   └── thresholds.py     # Health threshold constants
│   └── ips/                  # Existing (Phase 8 pattern)
├── models/
│   └── enums.py              # EXTEND: Add HEALTH category
└── reports/
    └── templates/
        └── health_section.html  # NEW: Device health report section
```

### Pattern 1: Dedicated Device Health Analyzer (Following Phase 8)
**What:** Separate health analysis from generic rule-based analysis
**When to use:** Device metrics have different data structure than events
**Why:** Device stats come from stat/device (poll-based), not events (stream-based)

```python
# Source: Phase 8 IPSAnalyzer pattern
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class DeviceHealthResult:
    """Result of device health analysis."""
    temperature_warnings: List["DeviceHealthFinding"] = field(default_factory=list)
    poe_issues: List["DeviceHealthFinding"] = field(default_factory=list)
    uptime_flags: List["DeviceHealthFinding"] = field(default_factory=list)
    resource_alerts: List["DeviceHealthFinding"] = field(default_factory=list)


class DeviceHealthAnalyzer:
    """Analyzer for device health metrics.

    Processes stat/device data to detect:
    - Temperature warnings (approaching/exceeding thresholds)
    - PoE issues (from events + port status)
    - Uptime concerns (long uptime suggesting restart needed)
    - Resource utilization (high CPU/memory)
    """

    def __init__(
        self,
        temp_warning_c: float = 80.0,
        temp_critical_c: float = 90.0,
        cpu_warning_pct: int = 80,
        cpu_critical_pct: int = 95,
        memory_warning_pct: int = 85,
        memory_critical_pct: int = 95,
        uptime_warning_days: int = 90,
    ):
        self._thresholds = {
            "temp_warning": temp_warning_c,
            "temp_critical": temp_critical_c,
            "cpu_warning": cpu_warning_pct,
            "cpu_critical": cpu_critical_pct,
            "memory_warning": memory_warning_pct,
            "memory_critical": memory_critical_pct,
            "uptime_warning": uptime_warning_days,
        }

    def analyze_devices(
        self,
        devices: List["DeviceStats"],
        poe_events: Optional[List[dict]] = None,
    ) -> DeviceHealthResult:
        """Analyze device health and generate findings."""
        pass
```

### Pattern 2: Device Stats Model with UniFi API Mapping
**What:** Pydantic model for normalized device statistics
**When to use:** Processing raw stat/device API response

```python
# Source: unpoller/unifi Go package documentation, UniFi API research
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, computed_field

class DeviceStats(BaseModel):
    """Normalized device statistics from UniFi stat/device API."""

    # Device identification
    mac: str = Field(..., description="Device MAC address")
    name: str = Field(default="Unknown", description="Device name")
    model: str = Field(default="Unknown", description="Device model")
    device_type: str = Field(default="unknown", description="Device type: uap, usw, ugw, udm")

    # System stats (from system-stats object)
    cpu_percent: Optional[float] = Field(default=None, description="CPU usage percentage")
    memory_percent: Optional[float] = Field(default=None, description="Memory usage percentage")
    uptime_seconds: Optional[int] = Field(default=None, description="Uptime in seconds")

    # Temperature (from temps object or general_temperature)
    temperature_c: Optional[float] = Field(default=None, description="Device temperature in Celsius")
    has_temperature: bool = Field(default=False, description="Whether device reports temperature")

    # PoE info (switches only)
    poe_available_watts: Optional[float] = Field(default=None, description="Total PoE budget")
    poe_consumed_watts: Optional[float] = Field(default=None, description="PoE power in use")
    port_table: List[Dict[str, Any]] = Field(default_factory=list, description="Port details including PoE")

    # State
    state: int = Field(default=1, description="Device state: 1=connected")
    adopted: bool = Field(default=True, description="Whether device is adopted")
    last_seen: Optional[datetime] = Field(default=None, description="Last seen timestamp")

    @computed_field
    @property
    def uptime_display(self) -> str:
        """Human-readable uptime string."""
        if self.uptime_seconds is None:
            return "Unknown"
        delta = timedelta(seconds=self.uptime_seconds)
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes = remainder // 60
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    @computed_field
    @property
    def uptime_days(self) -> float:
        """Uptime in days (for threshold checks)."""
        if self.uptime_seconds is None:
            return 0.0
        return self.uptime_seconds / 86400

    @computed_field
    @property
    def poe_utilization_percent(self) -> Optional[float]:
        """PoE budget utilization percentage."""
        if self.poe_available_watts and self.poe_consumed_watts:
            return (self.poe_consumed_watts / self.poe_available_watts) * 100
        return None

    @classmethod
    def from_api_response(cls, device: Dict[str, Any]) -> "DeviceStats":
        """Factory from raw stat/device API response."""
        # Extract system-stats (nested object)
        sys_stats = device.get("system-stats", {})

        # Handle temperature - can be in temps object or general_temperature
        temps = device.get("temps", {})
        temperature = None
        has_temp = device.get("has_temperature", False)
        if temps:
            # temps is dict like {"Board (CPU)":"51 C","CPU":"72 C"}
            # Take the highest temperature
            for name, temp_str in temps.items():
                if isinstance(temp_str, str) and "C" in temp_str:
                    try:
                        temp_val = float(temp_str.replace("C", "").strip())
                        if temperature is None or temp_val > temperature:
                            temperature = temp_val
                    except ValueError:
                        pass
        elif "general_temperature" in device:
            temperature = device.get("general_temperature")
            has_temp = True

        # Determine device type from type field
        device_type = device.get("type", "unknown")

        return cls(
            mac=device.get("mac", ""),
            name=device.get("name", device.get("mac", "Unknown")),
            model=device.get("model", "Unknown"),
            device_type=device_type,
            cpu_percent=sys_stats.get("cpu"),
            memory_percent=sys_stats.get("mem"),
            uptime_seconds=device.get("uptime") or sys_stats.get("uptime"),
            temperature_c=temperature,
            has_temperature=has_temp or temperature is not None,
            poe_available_watts=device.get("total_max_power"),
            poe_consumed_watts=device.get("poe_consumption") or device.get("port_power"),
            port_table=device.get("port_table", []),
            state=device.get("state", 1),
            adopted=device.get("adopted", True),
            last_seen=device.get("last_seen"),
        )
```

### Pattern 3: Health Thresholds Configuration
**What:** Configurable thresholds for health analysis
**When to use:** Defining warning/critical levels

```python
# Source: UniFi community research, industry best practices
from dataclasses import dataclass

@dataclass(frozen=True)
class HealthThresholds:
    """Configurable health thresholds.

    Default values based on:
    - UniFi device specifications (temperature)
    - Industry standards for network equipment (CPU/memory)
    - Ubiquiti community recommendations (uptime)
    """

    # Temperature thresholds (Celsius)
    temp_warning: float = 80.0    # Fan threshold on most UniFi devices
    temp_critical: float = 90.0   # Risk of thermal throttling

    # CPU thresholds (percentage)
    cpu_warning: int = 80         # Performance may degrade
    cpu_critical: int = 95        # Likely causing issues

    # Memory thresholds (percentage)
    memory_warning: int = 85      # May affect services
    memory_critical: int = 95     # OOM risk

    # Uptime threshold (days)
    uptime_warning: int = 90      # Consider scheduled restart
    uptime_critical: int = 180    # Strongly recommend restart

    # PoE thresholds (percentage of budget)
    poe_warning: int = 80         # Approaching budget limit
    poe_critical: int = 95        # Risk of disconnect events

DEFAULT_THRESHOLDS = HealthThresholds()
```

### Pattern 4: PoE Event Processing (Extend Existing Rules)
**What:** Handle PoE disconnect/overload events from event stream
**When to use:** Processing EVT_SW_PoeDisconnect events

```python
# Source: dim13/unifi event.go, existing SYSTEM_RULES pattern
from unifi_scanner.analysis.rules.base import Rule
from unifi_scanner.models.enums import Category, Severity

POE_HEALTH_RULES = [
    Rule(
        name="poe_disconnect",
        event_types=["EVT_SW_PoeDisconnect"],
        category=Category.SYSTEM,  # Or new Category.HEALTH
        severity=Severity.MEDIUM,
        title_template="[Device Health] PoE device disconnected on {device_name} port {port}",
        description_template=(
            "A PoE-powered device on {device_name} port {port} lost power and disconnected. "
            "This can indicate power budget exceeded, cable issues, or device failure."
        ),
        remediation_template=(
            "1. Check if the switch's PoE budget has been exceeded\n"
            "2. Verify the Ethernet cable is properly connected\n"
            "3. Check for damage to the cable or port\n"
            "4. If budget exceeded, consider using PoE injectors for high-power devices\n"
            "5. Review the connected device for power issues"
        ),
    ),
    Rule(
        name="poe_overload",
        event_types=["EVT_SW_PoeOverload", "EVT_SW_PoeBudgetExceeded"],
        category=Category.SYSTEM,
        severity=Severity.SEVERE,
        title_template="[Device Health] PoE power budget exceeded on {device_name}",
        description_template=(
            "Switch {device_name} has exceeded its PoE power budget. Some devices may "
            "lose power unexpectedly. This requires immediate attention to prevent "
            "network disruptions."
        ),
        remediation_template=(
            "1. IMMEDIATELY check which devices are still powered\n"
            "2. Disconnect non-critical PoE devices to reduce load\n"
            "3. Review total power consumption vs switch budget\n"
            "4. Consider upgrading to a switch with higher PoE budget\n"
            "5. Use external PoE injectors for high-power devices\n"
            "6. Set port power limits to prevent overload"
        ),
    ),
]
```

### Pattern 5: API Client Extension for stat/device
**What:** Add get_devices() method to UnifiClient
**When to use:** Fetching device health data

```python
# Source: Existing UnifiClient pattern, UniFi API wiki
def get_devices(
    self,
    site: str,
    device_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get device statistics from the controller.

    Returns detailed device information including system stats,
    temperatures, PoE status, and port information.

    Args:
        site: Site name to retrieve devices from.
        device_type: Optional filter by type (uap, usw, ugw, udm).

    Returns:
        List of device dictionaries with system-stats, temps, etc.
    """
    self._ensure_connected()
    assert self.device_type is not None

    endpoints = get_endpoints(self.device_type)
    # Use stat/device endpoint (not stat/device-basic)
    endpoint = endpoints.devices.format(site=site)

    response = self._request("GET", endpoint)
    data = response.json()

    devices = data.get("data", data) if isinstance(data, dict) else data

    # Optional type filter
    if device_type:
        devices = [d for d in devices if d.get("type") == device_type]

    logger.debug("devices_retrieved", count=len(devices), site=site)
    return devices
```

### Anti-Patterns to Avoid
- **Polling too frequently:** stat/device returns current state; polling every second wastes resources. Use 5-15 minute intervals.
- **Ignoring device type differences:** APs, switches, and gateways have different metrics available. Check device_type before accessing fields.
- **Absolute thresholds for all devices:** Different UniFi models have different safe operating ranges. Use conservative defaults.
- **Creating findings for every device:** Only create findings for devices with issues. Report healthy devices as summary.
- **Mixing event-based and poll-based data:** PoE events come from events API; device stats from stat/device. Keep data sources clear.

## Don't Hand-Roll

Problems with existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Uptime formatting | Manual calculation | `datetime.timedelta` | Handles edge cases (months, years) |
| Temperature parsing | Regex extraction | Type checking + split | UniFi returns "51 C" strings |
| Device name fallback | Complex conditionals | `.get("name", mac)` pattern | Already used in codebase |
| Severity classification | Multi-level if chains | Threshold ranges with dataclass | Cleaner, configurable |
| Report section rendering | String concatenation | Jinja2 templates | Already established pattern |

**Key insight:** Follow Phase 8's IPSAnalyzer pattern - dedicated analyzer class with dataclass results, separate from generic rule processing.

## Common Pitfalls

### Pitfall 1: Missing system-stats on Some Devices
**What goes wrong:** KeyError or None when accessing CPU/memory
**Why it happens:** Not all devices report system-stats (older firmware, specific models)
**How to avoid:** Always use `.get()` with defaults; check `has_temperature` flag
**Warning signs:** Crashes when processing device list

### Pitfall 2: Temperature Units Confusion
**What goes wrong:** Displaying 72 when device is at 72C (very hot!)
**Why it happens:** API returns temps as strings like "72 C" in some cases, integers in others
**How to avoid:** Parse consistently, always display with unit suffix
**Warning signs:** Missing units in reports, user confusion about severity

### Pitfall 3: Uptime Overflow on Long-Running Devices
**What goes wrong:** Incorrect uptime display for devices up > 1 year
**Why it happens:** Manual day/hour/minute calculation without proper handling
**How to avoid:** Use `timedelta` for all uptime formatting
**Warning signs:** Negative numbers, wrap-around values

### Pitfall 4: PoE Events Without Device Context
**What goes wrong:** "PoE disconnect on port 5" without identifying which switch
**Why it happens:** Event message doesn't always include device name
**How to avoid:** Correlate event device_mac with device name from stat/device
**Warning signs:** Generic port numbers without switch identification

### Pitfall 5: Creating Findings for Normal Operation
**What goes wrong:** Every report shows "CPU at 15%" as a finding
**Why it happens:** Creating findings for all metrics, not just concerning ones
**How to avoid:** Only generate findings when thresholds exceeded; show healthy devices in summary
**Warning signs:** Report flooded with "all is well" findings

## Code Examples

### Device Health Finding Model
```python
# Source: Existing Finding pattern extended for health metrics
from dataclasses import dataclass
from typing import Optional
from unifi_scanner.models.enums import Severity

@dataclass
class DeviceHealthFinding:
    """A device health issue that needs attention."""

    device_mac: str
    device_name: str
    severity: Severity
    category: str  # "temperature", "poe", "uptime", "cpu", "memory"
    title: str
    description: str
    current_value: str  # e.g., "87C", "92%", "145 days"
    threshold_value: str  # e.g., "80C", "85%", "90 days"
    remediation: Optional[str] = None

    @property
    def is_critical(self) -> bool:
        return self.severity == Severity.SEVERE
```

### Health Analysis Result Model
```python
# Source: Phase 8 ThreatAnalysisResult pattern
from dataclasses import dataclass, field
from typing import List

@dataclass
class DeviceHealthSummary:
    """Summary of a device's health status."""
    device_mac: str
    device_name: str
    device_type: str
    cpu_percent: Optional[float]
    memory_percent: Optional[float]
    temperature_c: Optional[float]
    uptime_display: str
    is_healthy: bool
    issues: List[str] = field(default_factory=list)


@dataclass
class DeviceHealthResult:
    """Complete health analysis result for report generation."""

    # Critical issues (need immediate attention)
    critical_findings: List[DeviceHealthFinding] = field(default_factory=list)

    # Warning issues (should be addressed soon)
    warning_findings: List[DeviceHealthFinding] = field(default_factory=list)

    # Device summaries (all devices with status)
    device_summaries: List[DeviceHealthSummary] = field(default_factory=list)

    # Counters for executive summary
    total_devices: int = 0
    healthy_devices: int = 0
    devices_with_warnings: int = 0
    devices_with_critical: int = 0

    @property
    def has_issues(self) -> bool:
        return bool(self.critical_findings or self.warning_findings)
```

### Report Template Section
```jinja2
{# Source: Phase 8 threat_section.html pattern #}
{% if health_analysis %}
<!-- Device Health Summary -->
<div style="margin-top: 30px;">
    <h2 style="color: #333333; font-size: 20px; font-weight: 600; margin: 0 0 15px 0; border-bottom: 2px solid #2282FF; padding-bottom: 8px;">Device Health Summary</h2>

    {# Executive summary #}
    <div style="margin-bottom: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 4px;">
        <p style="margin: 0; font-size: 14px; color: #333;">
            <strong>{{ health_analysis.total_devices }}</strong> devices monitored:
            <span style="color: #28a745;">{{ health_analysis.healthy_devices }} healthy</span>
            {% if health_analysis.devices_with_warnings %}
            | <span style="color: #fd7e14;">{{ health_analysis.devices_with_warnings }} with warnings</span>
            {% endif %}
            {% if health_analysis.devices_with_critical %}
            | <span style="color: #dc3545;">{{ health_analysis.devices_with_critical }} critical</span>
            {% endif %}
        </p>
    </div>

    {# Critical issues first #}
    {% if health_analysis.critical_findings %}
    <div style="margin-bottom: 25px;">
        <h3 style="color: #dc3545; font-size: 16px; font-weight: 600; margin: 0 0 12px 0;">
            Critical Issues ({{ health_analysis.critical_findings | length }})
        </h3>
        {% for finding in health_analysis.critical_findings %}
        <div style="margin-bottom: 15px; padding: 12px 15px; background-color: #ffffff; border-left: 4px solid #dc3545; border-radius: 0 4px 4px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
            <div style="margin-bottom: 6px;">
                <span style="display: inline-block; padding: 2px 8px; font-size: 11px; font-weight: 600; text-transform: uppercase; color: #ffffff; background-color: #dc3545; border-radius: 3px;">CRITICAL</span>
                <strong style="color: #333333; font-size: 15px; margin-left: 8px;">{{ finding.device_name }}</strong>
            </div>
            <p style="margin: 0 0 8px 0; color: #555555; font-size: 14px;">
                {{ finding.description }}
            </p>
            <p style="margin: 0 0 8px 0; color: #666666; font-size: 13px;">
                <strong>Current:</strong> {{ finding.current_value }}
                | <strong>Threshold:</strong> {{ finding.threshold_value }}
            </p>
            {% if finding.remediation %}
            <div style="margin-top: 10px; padding: 10px 12px; background-color: #f8f9fa; border-radius: 4px; border-left: 3px solid #17a2b8;">
                <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: 600; color: #17a2b8; text-transform: uppercase;">Recommended Actions</p>
                <p style="margin: 0; color: #495057; font-size: 13px; white-space: pre-line;">{{ finding.remediation }}</p>
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {# Device overview table #}
    <h3 style="color: #333333; font-size: 16px; font-weight: 600; margin: 0 0 12px 0;">Device Status</h3>
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="font-size: 13px;">
        <tr style="background-color: #f8f9fa;">
            <th style="padding: 8px; text-align: left; border-bottom: 2px solid #dee2e6;">Device</th>
            <th style="padding: 8px; text-align: center; border-bottom: 2px solid #dee2e6;">CPU</th>
            <th style="padding: 8px; text-align: center; border-bottom: 2px solid #dee2e6;">Memory</th>
            <th style="padding: 8px; text-align: center; border-bottom: 2px solid #dee2e6;">Temp</th>
            <th style="padding: 8px; text-align: center; border-bottom: 2px solid #dee2e6;">Uptime</th>
            <th style="padding: 8px; text-align: center; border-bottom: 2px solid #dee2e6;">Status</th>
        </tr>
        {% for device in health_analysis.device_summaries %}
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e9ecef;">{{ device.device_name }}</td>
            <td style="padding: 8px; text-align: center; border-bottom: 1px solid #e9ecef;">
                {% if device.cpu_percent is not none %}{{ device.cpu_percent|round|int }}%{% else %}-{% endif %}
            </td>
            <td style="padding: 8px; text-align: center; border-bottom: 1px solid #e9ecef;">
                {% if device.memory_percent is not none %}{{ device.memory_percent|round|int }}%{% else %}-{% endif %}
            </td>
            <td style="padding: 8px; text-align: center; border-bottom: 1px solid #e9ecef;">
                {% if device.temperature_c is not none %}{{ device.temperature_c|round|int }}C{% else %}-{% endif %}
            </td>
            <td style="padding: 8px; text-align: center; border-bottom: 1px solid #e9ecef;">{{ device.uptime_display }}</td>
            <td style="padding: 8px; text-align: center; border-bottom: 1px solid #e9ecef;">
                {% if device.is_healthy %}
                <span style="color: #28a745;">OK</span>
                {% else %}
                <span style="color: #dc3545;">{{ device.issues|join(', ') }}</span>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endif %}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SNMP polling for metrics | REST API stat/device | UniFi OS (2020+) | SNMP unreliable for CPU/memory on UniFi |
| Separate temp/stats endpoints | Unified stat/device response | UniFi 6.x+ | One call gets all metrics |
| Manual threshold configuration | Default thresholds with override | Phase 9 design | Simpler initial setup |

**Deprecated/outdated:**
- `stat/device-basic`: Only returns adoption state, not health metrics
- SNMP for UniFi monitoring: Inconsistent results for CPU/memory per LogicMonitor research
- External temperature monitoring scripts: UniFi now exposes temps via API

## Open Questions

1. **Temperature Field Availability by Model**
   - What we know: UDM Pro reports temps in `temps` object; not all devices have temperature sensors
   - What's unclear: Which specific models report temperature (has_temperature flag helps)
   - Recommendation: Check `has_temperature` flag; gracefully handle missing data

2. **PoE Event Types Coverage**
   - What we know: EVT_SW_PoeDisconnect exists (confirmed in Go packages)
   - What's unclear: Full list of PoE-related event types (budget exceeded, etc.)
   - Recommendation: Start with PoeDisconnect; add more types as discovered in testing

3. **Uptime Restart Recommendation Threshold**
   - What we know: Long uptime can cause memory leaks, missed firmware updates
   - What's unclear: Optimal threshold (30 days? 90 days? 180 days?)
   - Recommendation: Default 90 days as warning, make configurable. Community feedback varies.

## Sources

### Primary (HIGH confidence)
- [unpoller/unifi Go package documentation](https://pkg.go.dev/github.com/unpoller/unifi) - Device struct fields, SystemStats structure, Port PoE fields
- [dim13/unifi event.go](https://github.com/dim13/unifi/blob/master/event.go) - UniFi event types including EVT_SW_PoeDisconnect
- Project codebase: Phase 8 IPSAnalyzer pattern - Architecture model to follow

### Secondary (MEDIUM confidence)
- [Ubiquiti Community Wiki - API](https://ubntwiki.com/products/software/unifi-controller/api) - stat/device endpoint documentation
- [LogicMonitor UniFi Monitoring](https://www.logicmonitor.com/blog/how-to-monitor-cpu-and-memory-on-ubiquiti-unifi-devices) - Confirmed CPU/memory via system-stats
- [Home Assistant UniFi Integration](https://www.home-assistant.io/integrations/unifi/) - Validates uptime, temperature, CPU, memory entities available

### Tertiary (LOW confidence)
- [Ubiquiti Community Temperature Discussions](https://community.ui.com/questions/UniFi-switches-running-HOT-What-is-the-acceptable-temperature/56a426ca-5525-43e8-8401-0f4025111d5f) - Community temperature thresholds
- [UDM Pro Fan Speed Research](https://github.com/heXeo/ubnt-fan-speed/blob/master/README.md) - Temperature threshold values (85C low, 94C critical)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies; extends existing patterns
- Architecture: HIGH - Follows proven Phase 8 IPSAnalyzer pattern
- API fields: MEDIUM - Based on third-party Go packages; needs validation with real API
- Thresholds: MEDIUM - Based on community research; defaults conservative, configurable
- PoE events: MEDIUM - Limited event type documentation; start simple, expand

**Research date:** 2026-01-25
**Valid until:** 60 days (UniFi API stable but device model variations may affect field availability)
