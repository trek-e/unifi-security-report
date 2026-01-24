# Phase 1: Foundation & API Connection - Research

**Researched:** 2026-01-24
**Domain:** UniFi Controller API Integration, Python Configuration Management
**Confidence:** HIGH

## Summary

This phase establishes the foundation for connecting to UniFi Controllers across device types (UDM Pro, UCG Ultra, self-hosted). Research confirms that the UniFi API is undocumented but well-understood through community efforts. The critical distinction is between UniFi OS devices (UDM, UCG, Cloud Key Gen2+) which use `/api/auth/login` and `/proxy/network` prefix on port 443, versus legacy self-hosted controllers using `/api/login` directly on port 8443.

The Python ecosystem provides mature libraries for all required functionality: `pydantic-settings` for configuration management with YAML and environment variable support, `httpx` for HTTP client with cookie persistence, `structlog` for structured JSON logging, and `tenacity` for exponential backoff retry logic. Pydantic v2 provides robust data models with built-in JSON serialization.

A key finding is that UniFi authentication requires LOCAL admin accounts - cloud/SSO accounts will not work. Session handling should be fresh per-poll rather than persistent, matching the user's decision to authenticate fresh each poll cycle.

**Primary recommendation:** Use httpx Client with cookie persistence for API calls, pydantic-settings for layered config (YAML base, env override), and implement device type detection via response analysis from /status endpoint.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.11+ | Data models, validation | Type-safe models with JSON serialization |
| pydantic-settings | 2.x | Configuration management | Native YAML + env var support, validation |
| httpx | 0.27+ | HTTP client | Cookie persistence, sync/async, HTTP/2 support |
| structlog | 25.5+ | Structured logging | JSON output, dev/prod modes, processors |
| tenacity | 8.3+ | Retry with backoff | Exponential backoff, async support, logging |
| PyYAML | 6.0+ | YAML parsing | Standard choice, pydantic-settings integration |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | 1.0+ | .env file loading | Local development convenience |
| orjson | 3.10+ | Fast JSON serialization | Production JSON logging performance |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx | requests | requests lacks async, HTTP/2; httpx is drop-in compatible |
| httpx | unifi-controller-api | 3rd party lib adds complexity, prefer direct API for control |
| PyYAML | ruamel.yaml | ruamel preserves comments but adds complexity; PyYAML sufficient |
| structlog | logging (stdlib) | stdlib lacks structured output; structlog preferred for JSON |

**Installation:**
```bash
pip install pydantic pydantic-settings httpx structlog tenacity pyyaml python-dotenv orjson
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── unifi_scanner/
│   ├── __init__.py
│   ├── __main__.py          # Entry point, CLI handling
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py       # Pydantic settings classes
│   │   └── loader.py         # YAML loading, _FILE pattern
│   ├── api/
│   │   ├── __init__.py
│   │   ├── client.py         # UniFi API client
│   │   ├── auth.py           # Authentication logic
│   │   └── endpoints.py      # API endpoint definitions
│   ├── models/
│   │   ├── __init__.py
│   │   ├── log_entry.py      # LogEntry model
│   │   ├── finding.py        # Finding model
│   │   └── report.py         # Report model
│   └── logging.py            # structlog configuration
├── tests/
└── unifi-scanner.example.yaml
```

### Pattern 1: Device Type Detection
**What:** Detect UDM Pro/UCG Ultra vs self-hosted controller at connection time
**When to use:** During initial connection setup
**Example:**
```python
# Source: https://ubntwiki.com/products/software/unifi-controller/api
from enum import Enum
from dataclasses import dataclass

class DeviceType(Enum):
    UDM_PRO = "udm_pro"      # UDM, UDM Pro, UDR, UCG-Ultra
    SELF_HOSTED = "self_hosted"  # Software controller, legacy Cloud Key

@dataclass
class ControllerInfo:
    device_type: DeviceType
    base_url: str
    api_prefix: str

def detect_device_type(host: str, ports: list[int] = [443, 8443, 11443]) -> ControllerInfo:
    """
    Try ports in order. UDM uses 443, self-hosted uses 8443, UniFi OS Server uses 11443.
    Check /status endpoint (no auth required) to determine type.
    """
    for port in ports:
        try:
            # /status is accessible without auth on all controller types
            response = httpx.get(f"https://{host}:{port}/status", verify=False, timeout=5)
            if response.status_code == 200:
                # UDM devices return different status structure
                data = response.json()
                if "udm_version" in str(data) or port == 443:
                    return ControllerInfo(
                        device_type=DeviceType.UDM_PRO,
                        base_url=f"https://{host}:{port}",
                        api_prefix="/proxy/network"
                    )
                else:
                    return ControllerInfo(
                        device_type=DeviceType.SELF_HOSTED,
                        base_url=f"https://{host}:{port}",
                        api_prefix=""
                    )
        except httpx.ConnectError:
            continue
    raise ConnectionError(f"Could not connect to UniFi controller at {host}")
```

### Pattern 2: Layered Configuration (YAML + Env Override)
**What:** Load YAML as base, env vars override specific values
**When to use:** All configuration loading
**Example:**
```python
# Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
from pydantic import Field
from typing import Tuple, Type

class UnifiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UNIFI_",
        yaml_file="unifi-scanner.yaml",
        env_nested_delimiter="__",
    )

    host: str = Field(..., description="UniFi controller hostname")
    username: str = Field(..., description="Local admin username")
    password: str = Field(default="", description="Password (prefer _FILE)")
    port: int | None = Field(default=None, description="Override auto-detect")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    connect_timeout: int = Field(default=10, description="Connection timeout seconds")
    max_retries: int = Field(default=5, description="Max connection retries")
    poll_interval: int = Field(default=300, description="Poll interval seconds")
    log_level: str = Field(default="INFO", description="DEBUG/INFO/WARN/ERROR")
    log_format: str = Field(default="json", description="json or text")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ) -> Tuple:
        # Order: init > env > yaml (env overrides yaml)
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
        )
```

### Pattern 3: Docker Secrets _FILE Pattern
**What:** Read sensitive values from files (UNIFI_PASSWORD_FILE -> password)
**When to use:** Docker secrets, Kubernetes secrets
**Example:**
```python
# Custom implementation for _FILE suffix pattern
import os
from pathlib import Path

def resolve_file_secrets(config: dict) -> dict:
    """
    For any key with _FILE suffix in env, read file contents.
    UNIFI_PASSWORD_FILE=/run/secrets/password -> password from file
    """
    result = config.copy()

    for key in list(os.environ.keys()):
        if key.endswith("_FILE") and key.startswith("UNIFI_"):
            base_key = key[6:-5].lower()  # Remove UNIFI_ prefix and _FILE suffix
            file_path = Path(os.environ[key])
            if file_path.exists():
                result[base_key] = file_path.read_text().strip()

    return result
```

### Pattern 4: Exponential Backoff with Tenacity
**What:** Retry failed connections with increasing delays
**When to use:** All network operations
**Example:**
```python
# Source: https://tenacity.readthedocs.io/
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import structlog

logger = structlog.get_logger()

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def connect_with_retry(client: httpx.Client, url: str) -> httpx.Response:
    return client.get(url)
```

### Pattern 5: SIGHUP Config Reload
**What:** Reload configuration without restart on SIGHUP signal
**When to use:** Long-running daemon processes
**Example:**
```python
# Source: https://docs.python.org/3/library/signal.html
import signal
import threading

config_lock = threading.Lock()
current_config: UnifiSettings | None = None

def load_config() -> UnifiSettings:
    global current_config
    with config_lock:
        current_config = UnifiSettings()
        logger.info("Configuration loaded", host=current_config.host)
    return current_config

def handle_sighup(signum, frame):
    logger.info("SIGHUP received, reloading configuration")
    load_config()

signal.signal(signal.SIGHUP, handle_sighup)
```

### Pattern 6: File-Based Health Check
**What:** Write status to file for Docker health check
**When to use:** Container health monitoring
**Example:**
```python
from pathlib import Path
from datetime import datetime

HEALTH_FILE = Path("/tmp/unifi-scanner-health")

def update_health_status(status: str, details: dict = None):
    """Write health status to file for Docker healthcheck."""
    health_data = {
        "status": status,  # "healthy", "unhealthy", "starting"
        "timestamp": datetime.utcnow().isoformat(),
        "details": details or {}
    }
    HEALTH_FILE.write_text(json.dumps(health_data))

# Dockerfile HEALTHCHECK:
# HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
#   CMD python -c "import json; from pathlib import Path; \
#       h=json.loads(Path('/tmp/unifi-scanner-health').read_text()); \
#       exit(0 if h['status']=='healthy' else 1)"
```

### Anti-Patterns to Avoid
- **Using cloud/SSO accounts:** UniFi API requires LOCAL admin accounts only
- **Persistent session across polls:** Fresh auth per poll is more reliable than managing session expiry
- **Hardcoding device type:** Always auto-detect - deployments change
- **Logging passwords:** Never log sensitive data, even at DEBUG level
- **Single error message:** Report ALL config validation errors at once, not one at a time
- **Silent failure on config error:** Fail fast with clear exit codes

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff | Custom sleep loops | tenacity | Handles jitter, async, logging, edge cases |
| Config validation | Manual type checking | pydantic | Complete validation, clear errors, types |
| YAML + env merging | Custom dict merge | pydantic-settings | Handles precedence, nested values, types |
| HTTP cookie handling | Manual cookie parsing | httpx.Client | Automatic persistence, thread safety |
| JSON logging | Custom formatters | structlog | Processor chain, dev/prod modes, performance |
| Datetime handling | strftime/strptime | Pydantic datetime | Timezone handling, ISO8601, validation |

**Key insight:** Configuration and retry logic have many edge cases (nested values, type coercion, jitter, async). Libraries encode years of production experience.

## Common Pitfalls

### Pitfall 1: Using Cloud/SSO Account for API Access
**What goes wrong:** Authentication fails with 401 Unauthorized
**Why it happens:** UniFi API only accepts LOCAL admin accounts, not Ubiquiti cloud SSO
**How to avoid:** Create dedicated local admin in UniFi OS Console > Admins & Users
**Warning signs:** Login works in browser but fails via API; error mentions "authentication challenge"

### Pitfall 2: Wrong API Path Prefix for Device Type
**What goes wrong:** 404 errors on all API calls
**Why it happens:** UDM devices require `/proxy/network` prefix; self-hosted do not
**How to avoid:** Auto-detect device type and set prefix accordingly
**Warning signs:** /status works but /api/self returns 404

### Pitfall 3: Wrong Port for Device Type
**What goes wrong:** Connection refused or timeout
**Why it happens:** UDM uses 443, self-hosted uses 8443, UniFi OS Server uses 11443
**How to avoid:** Auto-detect by trying ports in order: 443, 8443, 11443
**Warning signs:** Connection works on one controller type but not another

### Pitfall 4: Session Expiration Without Recovery
**What goes wrong:** API calls fail after period of operation
**Why it happens:** Session cookies expire (typically 2 hours for API clients)
**How to avoid:** Fresh authentication each poll cycle (user decision); alternatively detect 401 and re-auth
**Warning signs:** Service works initially then starts failing after hours

### Pitfall 5: Self-Signed Certificate Errors
**What goes wrong:** SSL verification failures
**Why it happens:** UniFi controllers use self-signed certificates by default
**How to avoid:** Allow UNIFI_VERIFY_SSL=false option (default should still be true for security)
**Warning signs:** SSL_CERTIFICATE_VERIFY_FAILED errors

### Pitfall 6: Rate Limiting on Authentication
**What goes wrong:** 429 Too Many Requests on login attempts
**Why it happens:** Rapid retry without backoff triggers rate limiting
**How to avoid:** Use exponential backoff (tenacity) with reasonable delays
**Warning signs:** Login works once but fails on retries

### Pitfall 7: Config Errors Reported One at a Time
**What goes wrong:** User fixes one error, runs again, sees another error, repeat
**Why it happens:** Validation stops at first error
**How to avoid:** Use Pydantic's collect all errors mode; show all validation errors at once
**Warning signs:** User frustration, multiple restart cycles

## Code Examples

Verified patterns from official sources:

### UniFi Authentication (UDM Pro)
```python
# Source: https://ubntwiki.com/products/software/unifi-controller/api
import httpx

def authenticate_udm(base_url: str, username: str, password: str) -> httpx.Client:
    """Authenticate to UDM Pro/UCG Ultra and return client with session cookie."""
    client = httpx.Client(verify=False, timeout=10.0)

    # UDM uses /api/auth/login
    response = client.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password}
    )

    if response.status_code != 200:
        raise AuthenticationError(
            f"Authentication failed: {response.status_code}. "
            "Ensure you're using a LOCAL admin account, not cloud SSO."
        )

    # Cookie is automatically stored in client
    return client

def authenticate_self_hosted(base_url: str, username: str, password: str) -> httpx.Client:
    """Authenticate to self-hosted controller."""
    client = httpx.Client(verify=False, timeout=10.0)

    # Self-hosted uses /api/login
    response = client.post(
        f"{base_url}/api/login",
        json={"username": username, "password": password}
    )

    if response.status_code != 200:
        raise AuthenticationError(f"Authentication failed: {response.status_code}")

    return client
```

### Get Sites List
```python
# Source: https://ubntwiki.com/products/software/unifi-controller/api
def get_sites(client: httpx.Client, base_url: str, api_prefix: str) -> list[dict]:
    """Get list of sites from controller."""
    response = client.get(f"{base_url}{api_prefix}/api/self/sites")
    response.raise_for_status()

    data = response.json()
    if data.get("meta", {}).get("rc") != "ok":
        raise APIError(f"API error: {data}")

    return data.get("data", [])
```

### structlog JSON Configuration
```python
# Source: https://www.structlog.org/en/stable/logging-best-practices.html
import sys
import structlog

def configure_logging(log_format: str = "json", log_level: str = "INFO"):
    """Configure structlog for JSON (production) or console (development)."""

    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Pretty console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

### Pydantic Data Models
```python
# Source: https://docs.pydantic.dev/latest/concepts/models/
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

class LogEntry(BaseModel):
    """Normalized log entry from UniFi controller."""
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    source: str  # "api", "ssh", "syslog"
    device_mac: str | None = None
    event_type: str
    message: str
    raw_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)  # Extensibility

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: str,
        }

class Finding(BaseModel):
    """Analysis finding derived from log entries."""
    id: UUID = Field(default_factory=uuid4)
    severity: str  # "low", "medium", "severe"
    category: str  # "security", "connectivity", "performance"
    title: str
    description: str
    remediation: str | None = None
    source_log_ids: list[UUID] = Field(default_factory=list)
    occurrence_count: int = 1
    first_seen: datetime
    last_seen: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

class Report(BaseModel):
    """Complete analysis report."""
    id: UUID = Field(default_factory=uuid4)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    period_start: datetime
    period_end: datetime
    site_name: str
    controller_type: str
    findings: list[Finding] = Field(default_factory=list)
    log_entry_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| requests library | httpx | 2020+ | Async support, HTTP/2, drop-in replacement |
| Pydantic v1 | Pydantic v2 | 2023 | Performance, better validation, model_config |
| logging (stdlib) | structlog | Mainstream 2020+ | Structured JSON, processors, dev/prod modes |
| Custom retry loops | tenacity | Established | Reliable backoff, jitter, async support |
| Manual config parsing | pydantic-settings | Pydantic v2 | Type-safe, validation, multiple sources |

**Deprecated/outdated:**
- `requests.Session`: Still works but httpx.Client preferred for new projects
- Pydantic v1 `Config` class: Use `model_config = SettingsConfigDict(...)` in v2
- `unificontrol` library: Unmaintained, use direct API or unifi-controller-api

## Open Questions

Things that couldn't be fully resolved:

1. **Exact session timeout duration**
   - What we know: Default is ~2 hours for API clients per UniFi docs
   - What's unclear: Whether this varies by controller version or config
   - Recommendation: Fresh auth per poll makes this moot (user decision)

2. **UniFi OS Server (new self-hosted) port**
   - What we know: Uses port 11443, requires /proxy/network prefix
   - What's unclear: Exact feature parity with legacy self-hosted
   - Recommendation: Include 11443 in port auto-detect sequence

3. **Rate limit thresholds**
   - What we know: 429 errors occur with rapid auth attempts
   - What's unclear: Exact limits (requests per minute)
   - Recommendation: Conservative backoff (1s, 2s, 4s, 8s... max 60s)

## Sources

### Primary (HIGH confidence)
- [Ubiquiti Community Wiki - UniFi Controller API](https://ubntwiki.com/products/software/unifi-controller/api) - Complete API reference
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - Configuration patterns
- [structlog Documentation](https://www.structlog.org/en/stable/) - Logging best practices
- [Tenacity Documentation](https://tenacity.readthedocs.io/) - Retry patterns
- [httpx Documentation](https://www.python-httpx.org/) - HTTP client usage

### Secondary (MEDIUM confidence)
- [unifi-controller-api GitHub](https://github.com/tnware/unifi-controller-api) - Python library patterns (v0.3.2)
- [UniFi Best Practices GitHub](https://github.com/uchkunrakhimow/unifi-best-practices) - API patterns, WebSocket
- [Ubiquiti Help Center - Official API](https://help.ui.com/hc/en-us/articles/30076656117655-Getting-Started-with-the-Official-UniFi-API) - Official guidance

### Tertiary (LOW confidence)
- Various Medium articles on configuration patterns - Verified against official docs
- Community discussions on session handling - Cross-referenced with multiple sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official documentation for all libraries
- Architecture: HIGH - Well-established patterns in Python ecosystem
- UniFi API specifics: MEDIUM - Undocumented API, community knowledge
- Pitfalls: HIGH - Documented in multiple sources, verified patterns

**Research date:** 2026-01-24
**Valid until:** 2026-02-24 (30 days - stable ecosystem)
