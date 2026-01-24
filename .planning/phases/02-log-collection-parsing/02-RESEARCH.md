# Phase 2: Log Collection & Parsing - Research

**Researched:** 2026-01-24
**Domain:** UniFi API log retrieval, multi-format log parsing, SSH fallback
**Confidence:** MEDIUM (API endpoints reverse-engineered, not officially documented)

## Summary

This research covers how to collect logs from UniFi controllers via API and SSH fallback, normalize them into structured LogEntry objects, and handle the various timestamp formats encountered. The UniFi API provides endpoints for events and alarms, but these are undocumented and may vary between controller versions. SSH fallback is necessary when API log access is insufficient (per requirement COLL-04).

The key challenges are: (1) different API endpoint prefixes for UDM vs self-hosted controllers (already handled in Phase 1), (2) timestamps in milliseconds that may reflect local timezone without explicit offset, (3) syslog formats from SSH that don't conform strictly to RFC 3164/5424, and (4) defensive parsing needed for malformed or unexpected data.

**Primary recommendation:** Use the existing UnifiClient with new endpoint methods for events/alarms, paramiko for SSH fallback, and python-dateutil for flexible timestamp parsing. All timestamps must be normalized to UTC with explicit timezone awareness.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | >=0.27 | HTTP client | Already in use (Phase 1), async-capable |
| paramiko | >=3.4 | SSH client | Most mature Python SSH library, sync API |
| python-dateutil | >=2.8 | Timestamp parsing | Handles ambiguous formats, timezone-aware |
| pydantic | >=2.11 | Data validation | Already in use, defensive parsing |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | >=8.3 | Retry logic | Already configured in Phase 1 |
| structlog | >=25.5 | Structured logging | Already in use |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| paramiko | asyncssh | Better perf but EPL license, Python 3.10+ only |
| python-dateutil | pendulum | More features but heavier, dateutil sufficient |
| dateutil | arrow | Broken timezone handling per author's own blog |

**Installation:**
```bash
pip install paramiko>=3.4 python-dateutil>=2.8
```

## Architecture Patterns

### Recommended Project Structure
```
src/unifi_scanner/
├── api/
│   ├── client.py          # Add get_events(), get_alarms() methods
│   └── endpoints.py       # Add events/alarms endpoint definitions
├── logs/
│   ├── __init__.py
│   ├── collector.py       # LogCollector orchestrates API + SSH
│   ├── api_collector.py   # API-specific collection logic
│   ├── ssh_collector.py   # SSH fallback collection
│   └── parser.py          # Multi-format parser (JSON, syslog)
├── models/
│   └── log_entry.py       # Enhance from_unifi_event(), add from_syslog()
└── utils/
    └── timestamps.py      # UTC normalization utilities
```

### Pattern 1: Collector Strategy
**What:** Separate collectors for API and SSH with common interface
**When to use:** When multiple data sources provide similar data
**Example:**
```python
# Source: Standard strategy pattern
from abc import ABC, abstractmethod
from typing import List
from unifi_scanner.models import LogEntry

class LogCollectorStrategy(ABC):
    @abstractmethod
    def collect(self, site: str, hours: int = 24) -> List[LogEntry]:
        """Collect logs from the source."""
        pass

class APILogCollector(LogCollectorStrategy):
    def __init__(self, client: UnifiClient):
        self.client = client

    def collect(self, site: str, hours: int = 24) -> List[LogEntry]:
        events = self.client.get_events(site, history_hours=hours)
        alarms = self.client.get_alarms(site)
        return self._normalize(events + alarms)

class SSHLogCollector(LogCollectorStrategy):
    def __init__(self, host: str, username: str, password: str):
        self.host = host
        self.username = username
        self.password = password

    def collect(self, site: str, hours: int = 24) -> List[LogEntry]:
        # SSH into device, read log files, parse
        pass
```

### Pattern 2: Defensive Parsing with Pydantic
**What:** Use Pydantic validators to handle malformed data gracefully
**When to use:** When input data may be incomplete or unexpected
**Example:**
```python
# Source: Pydantic v2 documentation
from pydantic import BaseModel, field_validator, ValidationError
from typing import Any, Dict, Optional
from datetime import datetime

class LogEntry(BaseModel):
    timestamp: datetime
    event_type: str
    message: str
    raw_data: Dict[str, Any] = {}

    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, v: Any) -> datetime:
        """Handle multiple timestamp formats defensively."""
        if isinstance(v, datetime):
            return v
        if isinstance(v, (int, float)):
            # UniFi uses milliseconds
            return datetime.utcfromtimestamp(v / 1000)
        if isinstance(v, str):
            from dateutil import parser
            return parser.parse(v)
        raise ValueError(f"Cannot parse timestamp: {v}")

    @field_validator('event_type', mode='before')
    @classmethod
    def default_event_type(cls, v: Any) -> str:
        """Default to UNKNOWN for missing event types."""
        return v if v else "UNKNOWN"
```

### Pattern 3: Fallback Chain
**What:** Try API first, fall back to SSH on failure or insufficient data
**When to use:** When primary source may be unavailable
**Example:**
```python
# Source: Standard fallback pattern
class LogCollector:
    def __init__(self, api_collector: APILogCollector, ssh_collector: Optional[SSHLogCollector]):
        self.api = api_collector
        self.ssh = ssh_collector

    def collect(self, site: str, hours: int = 24) -> List[LogEntry]:
        try:
            logs = self.api.collect(site, hours)
            if self._is_sufficient(logs):
                return logs
            logger.info("api_logs_insufficient", count=len(logs))
        except Exception as e:
            logger.warning("api_collection_failed", error=str(e))

        if self.ssh:
            logger.info("falling_back_to_ssh")
            return self.ssh.collect(site, hours)

        raise LogCollectionError("Cannot collect logs via API or SSH")
```

### Anti-Patterns to Avoid
- **Naive datetime parsing:** Never use `datetime.fromtimestamp()` without timezone awareness
- **Swallowing parse errors:** Log failed parses with raw data for debugging
- **Blocking SSH operations:** Use timeouts on all SSH operations
- **Assuming API response structure:** Always check for expected fields before access

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Timestamp parsing | Custom regex for each format | python-dateutil parser | Handles 100+ formats including ambiguous |
| SSH connection | Raw socket programming | paramiko SSHClient | Key exchange, auth, channel management |
| Retry with backoff | Simple sleep loops | tenacity decorators | Jitter, exponential backoff, exception filtering |
| JSON/syslog detection | Regex pattern matching | Try JSON parse first | JSON.parse is definitive; regex is fragile |
| Timezone conversion | Manual offset math | datetime.astimezone(UTC) | DST transitions, historical offsets |

**Key insight:** Log parsing appears simple but edge cases multiply - mixed timezones, truncated messages, encoding issues, version-specific formats. Use battle-tested libraries.

## Common Pitfalls

### Pitfall 1: UniFi Timestamps in Local Time Without Offset
**What goes wrong:** Timestamps appear correct but are silently wrong timezone
**Why it happens:** UniFi API `time` field is milliseconds, `datetime` field may be local time without offset
**How to avoid:**
1. Always use `time` field (milliseconds) not `datetime` string
2. Assume controller timezone or UTC, document assumption
3. Store timezone assumption in metadata for debugging
**Warning signs:** Logs appear hours off from expected times

### Pitfall 2: API Response Truncation
**What goes wrong:** Missing events when count exceeds limit
**Why it happens:** `stat/event` endpoint has 3000 result limit, returns `meta.count` when truncated
**How to avoid:**
1. Check for `meta.count` in response
2. Use pagination with `start` parameter
3. Log when truncation occurs
**Warning signs:** `meta.count` present and greater than `len(data)`

### Pitfall 3: SSH Command Deadlock
**What goes wrong:** SSH command hangs indefinitely
**Why it happens:** paramiko `exec_command` can deadlock if stdout/stderr buffers fill
**How to avoid:**
1. Always set channel timeout: `stdout.channel.settimeout(30.0)`
2. Read stdout and stderr in small chunks with polling
3. Check `exit_status_ready()` before blocking on `recv_exit_status()`
**Warning signs:** SSH operations hang without error

### Pitfall 4: Syslog Format Variations
**What goes wrong:** Parser fails on valid syslog messages
**Why it happens:** UniFi syslog is "non-standard" - doesn't strictly follow RFC 3164 or 5424
**How to avoid:**
1. Use lenient parsing with fallback
2. Extract timestamp and message minimally
3. Store unparsed remainder in raw_data
**Warning signs:** Parse failures on messages that look valid

### Pitfall 5: UDM vs Self-Hosted Endpoint Differences
**What goes wrong:** 404 errors on event/alarm endpoints
**Why it happens:** UDM needs `/proxy/network` prefix, self-hosted does not
**How to avoid:** Already handled in Phase 1 - use `api_prefix` from `get_api_prefix(device_type)`
**Warning signs:** 404 on endpoints that work manually

## Code Examples

Verified patterns from official sources and reverse-engineered API:

### Get Events from UniFi API
```python
# Source: unificontrol docs + ubiquiti community wiki
def get_events(
    self,
    site: str,
    history_hours: int = 720,
    start: int = 0,
    limit: int = 3000,
) -> List[Dict[str, Any]]:
    """Retrieve events from UniFi controller.

    Args:
        site: Site name (e.g., 'default')
        history_hours: How far back to retrieve (default 30 days)
        start: Starting index for pagination
        limit: Maximum results (API caps at 3000)

    Returns:
        List of event dictionaries
    """
    # Endpoint: POST /api/s/{site}/stat/event
    endpoint = f"{self.api_prefix}/api/s/{site}/stat/event"

    payload = {
        "_sort": "-time",
        "within": history_hours,
        "_start": start,
        "_limit": min(limit, 3000),  # API enforces max
    }

    response = self._request("POST", endpoint, json=payload)
    data = response.json()

    # Check for truncation
    if "meta" in data and "count" in data["meta"]:
        logger.warning(
            "events_truncated",
            returned=len(data.get("data", [])),
            total=data["meta"]["count"],
        )

    return data.get("data", [])
```

### Get Alarms from UniFi API
```python
# Source: unifi-controller-api docs + community wiki
def get_alarms(
    self,
    site: str,
    archived: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Retrieve alarms from UniFi controller.

    Args:
        site: Site name (e.g., 'default')
        archived: None=all, False=active only, True=archived only

    Returns:
        List of alarm dictionaries
    """
    # Endpoint: GET /api/s/{site}/list/alarm
    endpoint = f"{self.api_prefix}/api/s/{site}/list/alarm"

    params = {}
    if archived is not None:
        params["archived"] = str(archived).lower()

    response = self._request("GET", endpoint, params=params)
    data = response.json()

    return data.get("data", [])
```

### SSH Log Collection with Timeout
```python
# Source: paramiko docs + issue #1778 workaround
import paramiko
from typing import Tuple

def ssh_read_log(
    host: str,
    username: str,
    password: str,
    log_path: str,
    timeout: float = 30.0,
) -> str:
    """Read log file from UniFi device via SSH.

    Args:
        host: Device hostname or IP
        username: SSH username (usually 'root')
        password: SSH password
        log_path: Full path to log file
        timeout: Command timeout in seconds

    Returns:
        Log file contents as string
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=host,
            username=username,
            password=password,
            timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
        )

        # Use tail to limit output size
        command = f"tail -n 10000 {log_path}"
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)

        # Set channel timeout to prevent deadlock
        stdout.channel.settimeout(timeout)
        stderr.channel.settimeout(timeout)

        output = stdout.read().decode('utf-8', errors='replace')
        error = stderr.read().decode('utf-8', errors='replace')

        if error:
            logger.warning("ssh_stderr", error=error[:500])

        return output
    finally:
        client.close()
```

### Timestamp Normalization to UTC
```python
# Source: python-dateutil docs + stdlib
from datetime import datetime, timezone
from typing import Any, Optional
from dateutil import parser as dateutil_parser
from dateutil.tz import tzutc

def normalize_timestamp(
    value: Any,
    assume_utc: bool = True,
) -> datetime:
    """Convert various timestamp formats to UTC datetime.

    Args:
        value: Timestamp as int (ms), float (s), str, or datetime
        assume_utc: If True, treat naive timestamps as UTC

    Returns:
        Timezone-aware datetime in UTC
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        # UniFi uses milliseconds
        if value > 1e12:  # Likely milliseconds
            value = value / 1000
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
        return dt  # Already UTC
    elif isinstance(value, str):
        dt = dateutil_parser.parse(value)
    else:
        raise ValueError(f"Cannot parse timestamp: {value!r}")

    # Handle naive datetimes
    if dt.tzinfo is None:
        if assume_utc:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            # Assume local and convert
            dt = dt.astimezone(timezone.utc)
    else:
        # Convert to UTC
        dt = dt.astimezone(timezone.utc)

    return dt
```

### Defensive Log Entry Parsing
```python
# Source: Pydantic v2 patterns
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Dict, Optional
from datetime import datetime
from uuid import UUID, uuid4

class LogEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    source: str  # 'api', 'ssh', 'syslog'
    device_mac: Optional[str] = None
    device_name: Optional[str] = None
    event_type: str = "UNKNOWN"
    message: str = ""
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, v: Any) -> datetime:
        return normalize_timestamp(v)

    @field_validator('device_mac', mode='before')
    @classmethod
    def normalize_mac(cls, v: Any) -> Optional[str]:
        if not v:
            return None
        # Normalize to lowercase with colons
        mac = str(v).lower().replace('-', ':')
        return mac

    @classmethod
    def from_unifi_event(cls, event: Dict[str, Any]) -> "LogEntry":
        """Create LogEntry from UniFi API event data."""
        # Extract MAC from various fields
        device_mac = (
            event.get("ap_mac") or
            event.get("sw_mac") or
            event.get("gw_mac") or
            event.get("mac")
        )

        device_name = (
            event.get("ap_name") or
            event.get("sw_name") or
            event.get("gw_name") or
            event.get("hostname")
        )

        return cls(
            timestamp=event.get("time", event.get("datetime")),
            source="api",
            device_mac=device_mac,
            device_name=device_name,
            event_type=event.get("key", "UNKNOWN"),
            message=event.get("msg", ""),
            raw_data=event,
            metadata={"subsystem": event.get("subsystem")},
        )
```

## UniFi API Endpoints Reference

### Events Endpoint
| Device Type | Endpoint | Method | Notes |
|-------------|----------|--------|-------|
| UDM/UCG | `/proxy/network/api/s/{site}/stat/event` | POST | 3000 limit |
| Self-hosted | `/api/s/{site}/stat/event` | POST | 3000 limit |

**POST body parameters:**
- `_sort`: Sort order, use `-time` for newest first
- `within`: History in hours (default 720 = 30 days)
- `_start`: Pagination offset
- `_limit`: Max results (capped at 3000)

### Alarms Endpoint
| Device Type | Endpoint | Method | Notes |
|-------------|----------|--------|-------|
| UDM/UCG | `/proxy/network/api/s/{site}/list/alarm` | GET | No limit documented |
| Self-hosted | `/api/s/{site}/list/alarm` | GET | No limit documented |

**Query parameters:**
- `archived`: `true`, `false`, or omit for all

### Event JSON Structure
```json
{
  "time": 1705084800000,
  "datetime": "2024-01-12T12:00:00Z",
  "key": "EVT_AP_Connected",
  "msg": "AP[ap-office] connected",
  "subsystem": "wlan",
  "ap_mac": "fc:ec:da:ab:cd:ef",
  "ap_name": "ap-office",
  "site_id": "5f4dcc3b5aa765d61d8327de",
  "_id": "65a15a8012345678"
}
```

### Alarm JSON Structure
```json
{
  "time": 1705084800000,
  "datetime": "2024-01-12T12:00:00Z",
  "key": "EVT_IPS_Alert",
  "msg": "IPS Alert: Potential intrusion detected",
  "archived": false,
  "subsystem": "ips",
  "site_id": "5f4dcc3b5aa765d61d8327de",
  "_id": "65a15a8087654321"
}
```

## SSH Log File Locations

### UDM Pro / UDM SE / UCG Ultra
| Log | Path | Format |
|-----|------|--------|
| UniFi Network Server | `/mnt/data/unifi-os/unifi/logs/server.log` | Java log format |
| UniFi Core System | `/mnt/data/unifi-os/unifi-core/logs/system.log` | Syslog-like |
| System Messages | `/var/log/messages` | Syslog (mixed timezone!) |

### Self-Hosted Controller
| Log | Path | Format |
|-----|------|--------|
| Controller Log | `/var/log/unifi/server.log` | Java log format |
| MongoDB Log | `/var/log/unifi/mongod.log` | MongoDB format |

### Access Points (via SSH to AP)
| Log | Path | Format |
|-----|------|--------|
| System Log | `/var/log/messages` | Syslog RFC 3164-like |
| Kernel Log | `/var/log/dmesg` | Kernel messages |

## Syslog Format Notes

UniFi devices produce syslog-like messages that don't strictly conform to RFC 3164 or RFC 5424:

**Typical format:**
```
Jan 24 10:30:15 hostname program[pid]: message content
```

**Known variations:**
- Year is never included (RFC 3164 limitation)
- Timezone may be absent or inconsistent
- Priority (PRI) field often omitted
- Some messages lack program/PID component

**Parsing strategy:**
1. Try regex for standard format first
2. Extract timestamp, hostname, message at minimum
3. Store full line in `raw_data` for fallback
4. Use current year for dateless timestamps

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Polling API | WebSocket events | UniFi 5.x+ | Real-time, but complex auth |
| `/rest/alarm` | `/list/alarm` | v7.1.66+ | `/rest/` returns 404 now |
| Direct syslog | CEF via SIEM | UniFi 9.x | Cleaner format, requires setup |

**Deprecated/outdated:**
- `api/s/{site}/rest/event`: Returns 404 on v7.1.66+
- `api/s/{site}/rest/alarm`: Returns 404 on v7.1.66+
- Direct syslog port 514: Non-standard format, use CEF instead

## Open Questions

Things that couldn't be fully resolved:

1. **Exact timestamp timezone behavior**
   - What we know: `time` field is milliseconds, likely UTC
   - What's unclear: Whether controller timezone affects `time` or just `datetime`
   - Recommendation: Test with known events, document findings in code

2. **Rate limiting on API endpoints**
   - What we know: 3000 event limit per request
   - What's unclear: Any rate limiting between requests
   - Recommendation: Add configurable delay between paginated requests

3. **SSH access to Cloud Key Gen2**
   - What we know: UDM Pro SSH works on port 22
   - What's unclear: Cloud Key Gen2+ may have different access
   - Recommendation: Test and document, may need device-specific handling

4. **Event types comprehensive list**
   - What we know: Available at https://demo.ubnt.com/manage/locales/en/eventStrings.json
   - What's unclear: How current this list is
   - Recommendation: Fetch at runtime or bundle known subset

## Sources

### Primary (HIGH confidence)
- [Ubiquiti Community Wiki - UniFi Controller API](https://ubntwiki.com/products/software/unifi-controller/api) - Endpoint reference
- [unificontrol documentation](https://unificontrol.readthedocs.io/en/latest/API.html) - Python library API
- [unifi-controller-api documentation](https://tnware.github.io/unifi-controller-api/api/client.html) - Method signatures
- [Paramiko documentation](https://docs.paramiko.org/en/stable/api/client.html) - SSHClient reference
- [Pydantic v2 documentation](https://docs.pydantic.dev/latest/) - Validation patterns

### Secondary (MEDIUM confidence)
- [GitHub: Art-of-WiFi/UniFi-API-client](https://github.com/Art-of-WiFi/UniFi-API-client) - PHP reference implementation
- [GitHub: uchkunrakhimow/unifi-best-practices](https://github.com/uchkunrakhimow/unifi-best-practices) - Developer guide
- [Ubiquiti Help Center - SIEM Integration](https://help.ui.com/hc/en-us/articles/33349041044119-UniFi-System-Logs-SIEM-Integration) - Official logging docs
- [python-dateutil documentation](https://dateutil.readthedocs.io/) - Timestamp parsing

### Tertiary (LOW confidence)
- Community forum posts about timezone issues - Anecdotal but consistent
- SSH log paths from blog posts - Verify on actual hardware

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using established libraries with good documentation
- API endpoints: MEDIUM - Reverse-engineered, may vary by version
- SSH log paths: MEDIUM - Community-sourced, verify on target hardware
- Timestamp handling: MEDIUM - Multiple sources agree but edge cases exist
- Syslog parsing: LOW - "Non-standard" per multiple sources, needs testing

**Research date:** 2026-01-24
**Valid until:** 2026-02-24 (30 days - API changes slowly, but verify endpoints)
