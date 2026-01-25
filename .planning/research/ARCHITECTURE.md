# Architecture Research: Optional Integrations

**Project:** UniFi Scanner - Cybersecure & Cloudflare Integrations
**Researched:** 2026-01-24
**Confidence:** HIGH

## Executive Summary

Optional Cybersecure and Cloudflare integrations should follow the established patterns in the existing codebase: a **Collector + Rules + Report** pipeline with graceful degradation. The key insight is that these integrations are **additional data sources**, not fundamentally different from the existing UniFi collector. They should:

1. **Be parallel collectors** alongside `LogCollector` (not nested inside it)
2. **Have dedicated rule categories** to distinguish findings by source
3. **Use independent configuration blocks** with `enabled` flags
4. **Fail independently** without blocking the UniFi pipeline

This follows the existing pattern where SSH fallback is optional (`ssh_enabled`) and delivery channels are optional (`email_enabled`, `file_enabled`).

## Existing Architecture Analysis

### Current Pipeline Flow

```
run_report_job()
    |
    v
StateManager.read_last_run()
    |
    v
UnifiClient.connect() + select_site()
    |
    v
LogCollector.collect(since_timestamp)     <-- Single data source
    |   |-- APILogCollector.collect()
    |   |-- SSHLogCollector.collect() [fallback]
    |
    v
AnalysisEngine.analyze(log_entries)       <-- All rules processed
    |   |-- SecurityRules
    |   |-- ConnectivityRules
    |   |-- PerformanceRules
    |   |-- SystemRules
    |
    v
Report(findings, period_start, period_end)
    |
    v
ReportGenerator.generate_html/text()
    |
    v
DeliveryManager.deliver()
    |
    v
StateManager.write_last_run() [if success]
```

### Established Patterns to Follow

| Pattern | Where Used | How It Works |
|---------|------------|--------------|
| **Optional features via `_enabled` flag** | `email_enabled`, `file_enabled`, `ssh_enabled` | Boolean flag in settings, `if enabled:` in orchestration |
| **Fallback chain** | LogCollector | Try primary, catch error, try secondary, report best result |
| **Independent failure** | DeliveryManager | Email failure triggers file fallback, one failing doesn't crash all |
| **Category-based rules** | RuleRegistry | Rules grouped by Category enum (SECURITY, CONNECTIVITY, etc.) |
| **Collector abstraction** | APILogCollector, SSHLogCollector | Each implements `.collect() -> List[LogEntry]` |

## Integration Architecture

### Recommended Approach: Parallel Collectors

Cybersecure and Cloudflare should be **parallel data sources** that produce LogEntry objects, processed by the same AnalysisEngine with source-specific rules.

```
run_report_job()
    |
    +---> UnifiLogCollector.collect()    [existing]
    |
    +---> CybersecureCollector.collect() [new, if enabled]
    |
    +---> CloudflareCollector.collect()  [new, if enabled]
    |
    v
all_entries = unifi_entries + cybersecure_entries + cloudflare_entries
    |
    v
AnalysisEngine.analyze(all_entries)
    |-- UniFi rules (existing)
    |-- Cybersecure rules (new)
    |-- Cloudflare rules (new)
```

### Why Parallel vs. Nested

| Approach | Pros | Cons |
|----------|------|------|
| **Parallel collectors** | Independent failures, clear responsibility, testable isolation | More code in orchestrator |
| **Nested in LogCollector** | Single collection call | Violates SRP, couples UniFi to external services, complex error handling |

**Decision:** Parallel collectors. Each integration is independently testable and can fail without affecting others.

## New Components

### 1. Integration Collectors

Each integration needs a collector that produces `List[LogEntry]` with appropriate metadata.

```
src/unifi_scanner/integrations/
    __init__.py
    base.py              # IntegrationCollector protocol/ABC
    cybersecure/
        __init__.py
        client.py        # API client for Cybersecure
        collector.py     # CybersecureCollector
    cloudflare/
        __init__.py
        client.py        # GraphQL client for Cloudflare
        collector.py     # CloudflareCollector
```

**IntegrationCollector Protocol:**
```python
class IntegrationCollector(Protocol):
    """Protocol for optional integration collectors."""

    @property
    def source_name(self) -> str:
        """Return the integration name (e.g., 'cybersecure', 'cloudflare')."""
        ...

    def is_configured(self) -> bool:
        """Return True if this integration has valid configuration."""
        ...

    def collect(self, since_timestamp: datetime) -> List[LogEntry]:
        """Collect events since the given timestamp.

        Returns empty list if not configured or on recoverable errors.
        Raises IntegrationError only on critical failures.
        """
        ...
```

### 2. Integration Manager

A coordinator that manages all optional integrations and collects from them safely.

```python
class IntegrationManager:
    """Manages optional external integrations."""

    def __init__(self, collectors: List[IntegrationCollector]):
        self._collectors = collectors

    def collect_all(self, since_timestamp: datetime) -> Dict[str, List[LogEntry]]:
        """Collect from all configured integrations.

        Returns:
            Dict mapping source name to entries.
            Failed integrations return empty lists (logged, not raised).
        """
        results = {}
        for collector in self._collectors:
            if not collector.is_configured():
                continue
            try:
                entries = collector.collect(since_timestamp)
                results[collector.source_name] = entries
            except Exception as e:
                log.warning(
                    "integration_failed",
                    source=collector.source_name,
                    error=str(e),
                )
                results[collector.source_name] = []
        return results
```

### 3. Extended Category/Source Enums

Add integration sources to the LogSource enum:

```python
class LogSource(str, Enum):
    """Source of log data."""
    API = "api"
    SSH = "ssh"
    SYSLOG = "syslog"
    CYBERSECURE = "cybersecure"  # NEW
    CLOUDFLARE = "cloudflare"    # NEW
```

Consider whether to extend Category or use metadata:

| Approach | Pros | Cons |
|----------|------|------|
| **New categories** (e.g., `CLOUDFLARE_WAF`) | Clear report sections | Category proliferation |
| **Use existing categories + metadata** | Reuses SECURITY, CONNECTIVITY | Source mixed in report |
| **Source-specific report sections** | Clear separation | More template work |

**Recommendation:** Use existing categories (SECURITY, CONNECTIVITY) but add `source` to Finding metadata. Report templates can optionally group by source.

### 4. Integration Rules

Each integration needs dedicated rules registered with the AnalysisEngine:

```
src/unifi_scanner/analysis/rules/
    __init__.py
    base.py
    security.py       # UniFi security rules
    connectivity.py   # UniFi connectivity rules
    performance.py    # UniFi performance rules
    system.py         # UniFi system rules
    cybersecure.py    # NEW: Cybersecure rules
    cloudflare.py     # NEW: Cloudflare rules
```

Rules should use event_type prefixes to avoid collision:

```python
# cybersecure.py
Rule(
    name="cybersecure_alert",
    event_types=["CS_ALERT", "CS_BLOCK"],  # Prefixed event types
    category=Category.SECURITY,
    severity=Severity.MEDIUM,
    title_template="Cybersecure Alert: {alert_type}",
    description_template="Cybersecure detected {description} from {source_ip}",
)

# cloudflare.py
Rule(
    name="cloudflare_waf_block",
    event_types=["CF_WAF_BLOCK", "CF_RATE_LIMIT"],
    category=Category.SECURITY,
    severity=Severity.LOW,
    title_template="Cloudflare WAF: {action} from {client_ip}",
    description_template="Cloudflare blocked request to {path} due to {rule_id}",
)
```

## Configuration Approach

### Settings Extension

Add integration configuration blocks to `UnifiSettings`:

```python
class UnifiSettings(BaseSettings):
    # ... existing fields ...

    # Cybersecure integration
    cybersecure_enabled: bool = Field(default=False)
    cybersecure_api_url: Optional[str] = Field(default=None)
    cybersecure_api_key: Optional[str] = Field(default=None)

    # Cloudflare integration
    cloudflare_enabled: bool = Field(default=False)
    cloudflare_api_token: Optional[str] = Field(default=None)
    cloudflare_zone_id: Optional[str] = Field(default=None)

    @model_validator(mode="after")
    def validate_cybersecure_config(self) -> "UnifiSettings":
        if self.cybersecure_enabled:
            if not self.cybersecure_api_url or not self.cybersecure_api_key:
                raise ValueError(
                    "cybersecure_api_url and cybersecure_api_key required when cybersecure_enabled=True"
                )
        return self

    @model_validator(mode="after")
    def validate_cloudflare_config(self) -> "UnifiSettings":
        if self.cloudflare_enabled:
            if not self.cloudflare_api_token or not self.cloudflare_zone_id:
                raise ValueError(
                    "cloudflare_api_token and cloudflare_zone_id required when cloudflare_enabled=True"
                )
        return self
```

### Environment Variables

```bash
# Cybersecure
UNIFI_CYBERSECURE_ENABLED=true
UNIFI_CYBERSECURE_API_URL=https://cybersecure.example.com/api
UNIFI_CYBERSECURE_API_KEY_FILE=/run/secrets/cybersecure_api_key

# Cloudflare
UNIFI_CLOUDFLARE_ENABLED=true
UNIFI_CLOUDFLARE_API_TOKEN_FILE=/run/secrets/cloudflare_token
UNIFI_CLOUDFLARE_ZONE_ID=abc123
```

### YAML Configuration

```yaml
# Optional integrations
cybersecure_enabled: true
cybersecure_api_url: "https://cybersecure.example.com/api"
cybersecure_api_key: "${CYBERSECURE_API_KEY}"

cloudflare_enabled: true
cloudflare_zone_id: "abc123def456"
cloudflare_api_token: "${CLOUDFLARE_TOKEN}"
```

## Error Handling Strategy

### Failure Isolation Matrix

| Failure | Impact | Recovery |
|---------|--------|----------|
| Cybersecure API unreachable | No Cybersecure findings | Log warning, continue with UniFi + Cloudflare |
| Cybersecure auth fails | No Cybersecure findings | Log error, continue with UniFi + Cloudflare |
| Cloudflare API unreachable | No Cloudflare findings | Log warning, continue with UniFi + Cybersecure |
| Cloudflare rate limited | Partial/no Cloudflare findings | Log warning, continue with what we have |
| All integrations fail | Only UniFi findings | Log warnings, report based on UniFi only |
| UniFi fails | No core data | CRITICAL - this is existing behavior |

### Implementation Pattern

```python
def run_report_job():
    # ... existing state and UniFi collection ...

    # Collect from integrations (non-blocking)
    integration_manager = IntegrationManager([
        CybersecureCollector(config) if config.cybersecure_enabled else None,
        CloudflareCollector(config) if config.cloudflare_enabled else None,
    ])

    integration_entries = integration_manager.collect_all(since_timestamp)

    # Merge entries for analysis
    all_entries = log_entries  # UniFi entries
    for source, entries in integration_entries.items():
        log.info("integration_collected", source=source, count=len(entries))
        all_entries.extend(entries)

    # Continue with analysis (rules will match based on event_type)
    findings = engine.analyze(all_entries)
```

## Data Flow with Integrations

### Complete Flow Diagram

```
run_report_job()
    |
    +------------------+---------------------+
    |                  |                     |
    v                  v                     v
UnifiClient       CybersecureClient    CloudflareClient
.collect()        .collect()           .collect()
    |                  |                     |
    |             (if enabled)          (if enabled)
    |                  |                     |
    v                  v                     v
List[LogEntry]    List[LogEntry]       List[LogEntry]
source=api/ssh    source=cybersecure   source=cloudflare
    |                  |                     |
    +------------------+---------------------+
                       |
                       v
              all_entries: List[LogEntry]
                       |
                       v
              AnalysisEngine.analyze()
                       |
    +------------------+------------------+------------------+
    |                  |                  |                  |
    v                  v                  v                  v
UniFi Rules      Cybersec Rules    Cloudflare Rules    Other Rules
    |                  |                  |                  |
    +------------------+------------------+------------------+
                       |
                       v
              findings: List[Finding]
              (mixed sources, sorted by severity)
                       |
                       v
              Report (unified)
                       |
                       v
              ReportGenerator
              (can optionally group by source)
```

## Cloudflare Integration Specifics

### API Details

**Endpoint:** `https://api.cloudflare.com/client/v4/graphql`

**Authentication:** Bearer token via `Authorization` header

**Query:** Uses `firewallEventsAdaptive` node with time-based filters

```python
class CloudflareClient:
    def __init__(self, api_token: str, zone_id: str):
        self.api_token = api_token
        self.zone_id = zone_id
        self.endpoint = "https://api.cloudflare.com/client/v4/graphql"

    def query_firewall_events(
        self,
        since: datetime,
        until: datetime,
        limit: int = 1000,
    ) -> List[Dict]:
        query = """
        query FirewallEvents($zoneTag: string!, $filter: FirewallEventsAdaptiveFilter_InputObject!) {
            viewer {
                zones(filter: {zoneTag: $zoneTag}) {
                    firewallEventsAdaptive(filter: $filter, limit: 1000, orderBy: [datetime_DESC]) {
                        action
                        clientAsn
                        clientCountryName
                        clientIP
                        clientRequestPath
                        datetime
                        source
                        userAgent
                    }
                }
            }
        }
        """
        # ... execute query and parse response ...
```

**LogEntry Mapping:**
| Cloudflare Field | LogEntry Field |
|------------------|----------------|
| `datetime` | `timestamp` |
| `action` | `event_type` (prefixed: `CF_{action}`) |
| `source` + message | `message` |
| `clientIP` | `metadata["client_ip"]` |
| zone info | `device_name` |

## Cybersecure Integration Specifics

**Note:** "Cybersecure" is assumed to be CrowdSec or similar. If different, adjust accordingly.

### CrowdSec API (if applicable)

**Python SDK:** `pycrowdsec` or `crowdsec-service-api-sdk-python`

**Key Features:**
- StreamClient for polling LAPI
- Decision tracking (bans, captchas)
- Alert queries

```python
class CybersecureClient:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    def query_alerts(self, since: datetime) -> List[Dict]:
        """Query CrowdSec LAPI for alerts since timestamp."""
        # Use pycrowdsec or direct HTTP
        ...
```

**LogEntry Mapping:**
| Cybersecure Field | LogEntry Field |
|------------------|----------------|
| `timestamp` | `timestamp` |
| `alert_type` | `event_type` (prefixed: `CS_{type}`) |
| `message` | `message` |
| `source_ip` | `metadata["source_ip"]` |
| `scenario` | `metadata["scenario"]` |

## Build Order Recommendation

### Phase 1: Infrastructure (Foundation)

1. **Create integration module structure**
   - `src/unifi_scanner/integrations/__init__.py`
   - `src/unifi_scanner/integrations/base.py` (IntegrationCollector protocol)

2. **Extend LogSource enum**
   - Add CYBERSECURE and CLOUDFLARE values

3. **Create IntegrationManager**
   - Orchestration for parallel collection
   - Error isolation logic

### Phase 2: Cloudflare Integration

1. **CloudflareClient** - GraphQL API wrapper
2. **CloudflareCollector** - Implements IntegrationCollector
3. **Cloudflare rules** in analysis/rules/
4. **Settings extension** for Cloudflare config
5. **Tests** for client and collector

### Phase 3: Cybersecure Integration

1. **CybersecureClient** - API wrapper (depends on actual API)
2. **CybersecureCollector** - Implements IntegrationCollector
3. **Cybersecure rules** in analysis/rules/
4. **Settings extension** for Cybersecure config
5. **Tests** for client and collector

### Phase 4: Pipeline Integration

1. **Update `run_report_job()`** to use IntegrationManager
2. **Register integration rules** in default registry
3. **Update report templates** (optional: source grouping)
4. **End-to-end testing** with all sources

### Phase 5: Polish

1. **Documentation** - Configuration guide
2. **Docker secrets** support for API keys
3. **Health checks** for integration status

## Anti-Patterns to Avoid

### 1. Coupling UniFi to Integrations

**Bad:**
```python
class LogCollector:
    def collect(self):
        entries = self._collect_unifi()
        entries += self._collect_cloudflare()  # DON'T do this
        return entries
```

**Good:** Keep collectors independent, merge in orchestrator.

### 2. Required Integrations

**Bad:**
```python
if not cloudflare_entries:
    raise IntegrationError("Cloudflare required")
```

**Good:** Integrations are always optional. Empty result is valid.

### 3. Shared State Between Integrations

**Bad:** Using single `since_timestamp` that advances based on any integration.

**Good:** Each integration could have its own state tracking if needed (future enhancement), or use unified state with source-aware timestamps.

### 4. Blocking on Integration Failure

**Bad:**
```python
try:
    cloudflare_entries = cloudflare.collect()
except CloudflareError:
    raise  # Blocks entire job
```

**Good:**
```python
try:
    cloudflare_entries = cloudflare.collect()
except Exception as e:
    log.warning("cloudflare_failed", error=str(e))
    cloudflare_entries = []  # Continue with empty
```

## Testing Strategy

### Unit Tests

- Each collector independently testable with mocked API responses
- IntegrationManager tested with mock collectors (some failing, some succeeding)
- Rules tested with synthetic LogEntry objects

### Integration Tests

- Test with real APIs (behind feature flags or CI secrets)
- Verify LogEntry mapping correctness
- Verify rule matching

### End-to-End Tests

- Full pipeline with mock external APIs
- Verify findings appear in report with correct source attribution

## Sources

### Architecture Patterns
- [Graceful Service Degradation Patterns](https://systemdr.substack.com/p/graceful-service-degradation-patterns)
- [Registry Pattern with Decorators in Python (Dec 2025)](https://medium.com/@tihomir.manushev/implementing-the-registry-pattern-with-decorators-in-python-de8daf4a452a)
- [Building a Plugin Architecture with Python](https://mwax911.medium.com/building-a-plugin-architecture-with-python-7b4ab39ad4fc)

### Cloudflare API
- [Cloudflare GraphQL Analytics API](https://developers.cloudflare.com/analytics/graphql-api/)
- [Querying Firewall Events with GraphQL](https://developers.cloudflare.com/analytics/graphql-api/tutorials/querying-firewall-events/)
- [Security Analytics](https://developers.cloudflare.com/waf/analytics/security-analytics/)

### CrowdSec/Cybersecure
- [PyCrowdSec GitHub](https://github.com/crowdsecurity/pycrowdsec)
- [CrowdSec Service API Python SDK](https://github.com/crowdsecurity/crowdsec-service-api-sdk-python)
- [CrowdSec Local API Introduction](https://docs.crowdsec.net/docs/local_api/intro/)
