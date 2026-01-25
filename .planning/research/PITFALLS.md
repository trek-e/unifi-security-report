# Pitfalls Research: Expanding Analysis Rules and Optional API Integrations

**Domain:** Rule engine expansion, UniFi Cybersecure API, Cloudflare API integration
**Researched:** 2026-01-24
**Confidence:** HIGH (verified with official API documentation and production patterns)

## Executive Summary

Adding many new analysis rules and optional external API integrations presents 12 critical pitfalls that can cause false positives, API rate limiting, runtime failures, or code complexity explosion. The three most dangerous are: (1) rule explosion creating maintenance burden and unpredictable behavior, (2) Cloudflare API rate limits causing service degradation, and (3) tight coupling of optional integrations making the codebase fragile. All are preventable with rule categorization, circuit breaker patterns, and adapter-based optional dependency design.

---

## Critical Pitfalls

### Pitfall 1: Rule Explosion and Maintenance Burden

**What goes wrong:**
Starting with 15 rules, expanding to 50+ rules across wireless, security, and device health categories. Rules become difficult to maintain, test comprehensively, and reason about. Adding one rule causes unexpected interactions with existing rules. Time to add new rules increases exponentially.

**Why it happens:**
- Each new event type gets its own rule instead of composing from patterns
- No categorization strategy - rules dumped into large lists
- No severity or priority framework - everything treated equally
- Copy-paste rule creation without refactoring common patterns

**Consequences:**
- **Unpredictable behavior:** New rules conflict with existing rules, same event matches multiple rules unexpectedly
- **Testing burden:** 50 rules with 3 test cases each = 150 tests minimum, but interaction testing explodes combinatorially
- **Stale rules:** Old rules never reviewed, may reference deprecated event types
- **Developer friction:** New contributors can't understand rule priorities or interactions

**Warning signs:**
- PR adding a rule requires modifying 5+ existing rules
- Test failures when adding seemingly unrelated rules
- `find_matching_rule()` returning unexpected rule
- Multiple rules with near-identical `description_template` values
- Rules with overlapping `event_types` lists

**Detection:**
```python
# Check for rule conflicts in test suite
def test_no_duplicate_event_type_coverage():
    """Ensure each event_type has clear rule priority."""
    registry = get_default_registry()
    event_type_rules = {}
    for rule in registry.all_rules:
        for et in rule.event_types:
            if et in event_type_rules:
                # Multiple rules handle same event - document why
                existing = event_type_rules[et]
                assert rule.pattern or existing.pattern, (
                    f"Event {et} handled by {existing.name} and {rule.name} "
                    "with no pattern disambiguation"
                )
            event_type_rules[et] = rule
```

**Prevention:**

1. **Rule categorization by domain:**
```python
# wireless_rules.py - All wireless-specific rules
WIRELESS_RULES = [
    Rule(name="wifi_client_roaming", ...),
    Rule(name="wifi_channel_change", ...),
]

# security_rules.py - Existing, add new
# device_health_rules.py - New category
```

2. **Rule priority levels (if multiple rules match):**
```python
@dataclass
class Rule:
    name: str
    event_types: List[str]
    # NEW: Priority for disambiguation
    priority: int = 100  # Higher = matches first
```

3. **Rule composition for common patterns:**
```python
# Instead of 10 nearly-identical device offline rules
def create_device_offline_rule(device_type: str, event_type: str) -> Rule:
    return Rule(
        name=f"{device_type}_offline",
        event_types=[event_type],
        category=Category.CONNECTIVITY,
        severity=Severity.SEVERE,
        title_template=f"[Connectivity] {device_type.title()} {{device_name}} went offline",
        description_template=OFFLINE_DESCRIPTION_TEMPLATE.format(device_type=device_type),
        remediation_template=OFFLINE_REMEDIATION_TEMPLATE,
    )

AP_OFFLINE = create_device_offline_rule("access point", "EVT_AP_Lost_Contact")
SW_OFFLINE = create_device_offline_rule("switch", "EVT_SW_Lost_Contact")
```

4. **Quarterly rule review process:**
```markdown
# Rule Maintenance Checklist
- [ ] Remove rules for deprecated event types
- [ ] Consolidate rules with >90% similar templates
- [ ] Review false positive rates from production logs
- [ ] Update severity based on user feedback
```

**Implementation phase:** Phase planning - establish rule organization before adding rules

**Source confidence:** HIGH - Based on [SIEM rule maintenance best practices](https://www.redlegg.com/blog/siem-alert) and [rule engine scalability patterns](https://www.nected.ai/us/blog-us/rules-engine-design-pattern).

---

### Pitfall 2: Cloudflare API Rate Limits Causing Service Degradation

**What goes wrong:**
Integration calls Cloudflare API for threat intelligence enrichment. Cloudflare enforces 1,200 requests per 5 minutes globally. Scanner processes 100 events, each making 2 Cloudflare calls = 200 requests. Batch of 700 events exceeds limit, service gets HTTP 429 for 5 minutes, entire scan fails.

**Why it happens:**
- Per-event API calls without batching
- No awareness of global rate limit across all Cloudflare endpoints
- No caching of repeated lookups (same IP appears in multiple events)
- No backoff when approaching limit

**Consequences:**
- **Service outage:** HTTP 429 blocks ALL Cloudflare API calls for 5 minutes
- **Incomplete analysis:** Events processed before rate limit get enrichment, later events don't
- **Cascading failures:** Retry logic hammers API, extends rate limit window
- **Cost impact:** Enterprise plans have higher limits but cost money

**Warning signs:**
- HTTP 429 errors in logs with `retry-after` header
- `Ratelimit` header showing `r=0` (remaining quota exhausted)
- Enrichment data present on some findings but not others in same batch
- Scan duration spikes (waiting for rate limit recovery)

**Detection:**
```python
def check_cloudflare_rate_limit(response: httpx.Response) -> None:
    """Log warning if approaching rate limit."""
    if "Ratelimit" in response.headers:
        # Format: "default";r=50;t=30
        match = re.search(r'r=(\d+)', response.headers["Ratelimit"])
        if match:
            remaining = int(match.group(1))
            if remaining < 100:
                log.warning("cloudflare_rate_limit_low", remaining=remaining)
```

**Prevention:**

1. **Request batching where API supports it:**
```python
# BAD: Per-IP lookup
for event in events:
    threat_info = cloudflare.lookup_ip(event.source_ip)

# GOOD: Batch lookup (if Cloudflare supports batch endpoint)
# Note: Verify Cloudflare batch API availability before implementing
unique_ips = {e.source_ip for e in events}
threat_map = cloudflare.batch_lookup_ips(list(unique_ips))
for event in events:
    event.threat_info = threat_map.get(event.source_ip)
```

2. **Aggressive caching with TTL:**
```python
from functools import lru_cache
from datetime import datetime, timedelta

# Cache IP lookups for 1 hour (threat data doesn't change that fast)
@lru_cache(maxsize=10000)
def lookup_ip_cached(ip: str) -> Optional[ThreatInfo]:
    return cloudflare.lookup_ip(ip)

# For production: Use Redis with TTL
# redis.setex(f"cf:threat:{ip}", 3600, json.dumps(threat_info))
```

3. **Rate limiter with backoff:**
```python
from ratelimit import limits, sleep_and_retry

# Cloudflare: 1200 requests / 5 minutes = 4 requests/second sustainable
@sleep_and_retry
@limits(calls=4, period=1)  # 4 per second, will sleep if exceeded
def cloudflare_api_call(endpoint: str, **kwargs) -> httpx.Response:
    return httpx.get(f"https://api.cloudflare.com/client/v4/{endpoint}", **kwargs)
```

4. **Graceful degradation when rate limited:**
```python
class CloudflareClient:
    def __init__(self):
        self._rate_limited_until: Optional[datetime] = None

    def lookup_ip(self, ip: str) -> Optional[ThreatInfo]:
        # Skip API if we're in rate limit window
        if self._rate_limited_until and datetime.now() < self._rate_limited_until:
            log.debug("skipping_cloudflare_rate_limited", ip=ip)
            return None

        response = self._request(f"intel/domain?domain={ip}")
        if response.status_code == 429:
            retry_after = int(response.headers.get("retry-after", 300))
            self._rate_limited_until = datetime.now() + timedelta(seconds=retry_after)
            log.warning("cloudflare_rate_limited", retry_after=retry_after)
            return None
        return self._parse_response(response)
```

**Implementation phase:** Cloudflare integration module - implement rate limiting from day one

**Source confidence:** HIGH - [Cloudflare API rate limits documentation](https://developers.cloudflare.com/fundamentals/api/reference/limits/) states 1,200 requests per 5 minutes globally.

---

### Pitfall 3: UniFi API Rate Limiting (Undocumented)

**What goes wrong:**
UniFi controller API lacks official rate limit documentation. Scanner makes rapid requests to fetch events, then Cybersecure threat data, then device status. Controller starts returning HTTP 403 or silently dropping requests. Scanner sees partial data or authentication failures.

**Why it happens:**
- No official Ubiquiti API rate limit documentation
- Self-hosted controllers have different limits than UniFi Cloud
- Rate limits may vary by controller hardware (UDM vs Cloud Key vs self-hosted)
- Aggressive polling frequency set to get "real-time" data

**Consequences:**
- **Silent data loss:** API returns partial results without error
- **Authentication failures:** Rate limiting may manifest as 403 triggering re-auth loops
- **Inconsistent behavior:** Works in dev (low load), fails in production (concurrent requests)

**Warning signs:**
- HTTP 403 errors after successful authentication
- Fewer events returned than expected
- `get_events()` returns empty list when events exist
- Re-authentication loops in logs

**Detection:**
```python
def get_events(self, site: str, ...) -> List[Dict[str, Any]]:
    # ... existing code ...

    # NEW: Detect potential rate limiting
    if len(events) == 0 and history_hours > 1:
        log.warning(
            "possible_rate_limiting",
            msg="Zero events returned despite requesting history - possible rate limiting",
            site=site,
            history_hours=history_hours,
        )
```

**Prevention:**

1. **Conservative polling interval:**
```python
# Default: Poll every 5 minutes, not faster
MINIMUM_POLL_INTERVAL_SECONDS = 300

# If user configures faster, warn them
if poll_interval < MINIMUM_POLL_INTERVAL_SECONDS:
    log.warning(
        "aggressive_poll_interval",
        configured=poll_interval,
        recommended=MINIMUM_POLL_INTERVAL_SECONDS,
        msg="Fast polling may trigger UniFi rate limiting"
    )
```

2. **Request spacing for bulk operations:**
```python
import time

def fetch_all_data(self, site: str) -> ScanData:
    """Fetch events, alarms, and device status with spacing."""
    events = self.get_events(site)
    time.sleep(0.5)  # 500ms between different API calls

    alarms = self.get_alarms(site)
    time.sleep(0.5)

    # Cybersecure data (if enabled)
    if self.cybersecure_enabled:
        threats = self.get_cybersecure_threats(site)
        time.sleep(0.5)

    return ScanData(events=events, alarms=alarms, threats=threats)
```

3. **Exponential backoff on failures:**
```python
# Already implemented in existing client - ensure it covers 403
self._retry = create_retry_decorator(
    max_retries=settings.max_retries,
    min_wait=1,
    max_wait=60,
    retry_on=(httpx.RequestError, httpx.HTTPStatusError),
)
```

**Implementation phase:** API client modifications for Cybersecure integration

**Source confidence:** MEDIUM - No official documentation; based on [community reports of rate limiting](https://github.com/Art-of-WiFi/UniFi-API-client/issues/194) and [Ubiquiti Community discussions](https://community.ui.com/questions/Unifi-API-Rate-Limited/ba82a718-9418-46b0-8f2f-235bfc647f9b).

---

### Pitfall 4: Tight Coupling of Optional Integrations

**What goes wrong:**
Cloudflare integration added directly to `AnalysisEngine`. When Cloudflare is unavailable or unconfigured, engine crashes or requires complex conditionals throughout codebase. Testing requires mocking Cloudflare everywhere. Adding a third integration (e.g., VirusTotal) means touching all the same files again.

**Why it happens:**
- Direct API calls in core business logic
- Boolean flags: `if self.cloudflare_enabled: ...` scattered everywhere
- Missing interface abstraction for "threat intelligence provider"
- Optional dependencies not isolated

**Consequences:**
- **Fragile code:** Network failure in Cloudflare crashes entire analysis
- **Testing nightmare:** Every test needs Cloudflare mocks even if testing unrelated code
- **Feature creep:** Each integration adds more conditionals
- **Configuration complexity:** Users don't know which integrations are active

**Warning signs:**
- `if cloudflare_client:` appearing in multiple files
- Tests failing due to unmocked API calls
- Adding new integration requires modifying 10+ files
- Import errors when optional dependency not installed

**Detection:**
```python
# Code smell: Conditional imports at module level
try:
    import cloudflare
    CLOUDFLARE_AVAILABLE = True
except ImportError:
    CLOUDFLARE_AVAILABLE = False

# Code smell: Integration checks scattered in business logic
def analyze_entry(self, entry: LogEntry) -> Finding:
    finding = self._create_finding(entry, rule)
    if CLOUDFLARE_AVAILABLE and self.cloudflare_client:
        finding.threat_info = self.cloudflare_client.lookup(entry.source_ip)
    return finding
```

**Prevention:**

1. **Adapter pattern for integrations:**
```python
# integrations/base.py
from abc import ABC, abstractmethod
from typing import Optional

class ThreatIntelProvider(ABC):
    """Abstract interface for threat intelligence enrichment."""

    @abstractmethod
    def lookup_ip(self, ip: str) -> Optional[ThreatInfo]:
        """Look up threat information for an IP address."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and reachable."""
        pass


class NullThreatIntelProvider(ThreatIntelProvider):
    """No-op provider when no integration is configured."""

    def lookup_ip(self, ip: str) -> Optional[ThreatInfo]:
        return None

    def is_available(self) -> bool:
        return True  # Always "works" (does nothing)
```

2. **Provider implementations in isolated modules:**
```python
# integrations/cloudflare.py
class CloudflareThreatIntel(ThreatIntelProvider):
    def __init__(self, api_token: str):
        self._client = CloudflareClient(api_token)

    def lookup_ip(self, ip: str) -> Optional[ThreatInfo]:
        # All Cloudflare-specific logic here
        return self._client.intel.ip(ip)

    def is_available(self) -> bool:
        try:
            self._client.user.tokens.verify()
            return True
        except Exception:
            return False
```

3. **Factory function for provider selection:**
```python
# integrations/__init__.py
def get_threat_intel_provider(settings: UnifiSettings) -> ThreatIntelProvider:
    """Create appropriate threat intel provider based on configuration."""
    if settings.cloudflare_api_token:
        try:
            from unifi_scanner.integrations.cloudflare import CloudflareThreatIntel
            provider = CloudflareThreatIntel(settings.cloudflare_api_token)
            if provider.is_available():
                return provider
            log.warning("cloudflare_configured_but_unavailable")
        except ImportError:
            log.warning("cloudflare_token_set_but_package_not_installed")

    # Default: No threat intelligence enrichment
    return NullThreatIntelProvider()
```

4. **Engine uses interface, not implementation:**
```python
class AnalysisEngine:
    def __init__(
        self,
        registry: Optional[RuleRegistry] = None,
        threat_intel: Optional[ThreatIntelProvider] = None,
    ):
        self._registry = registry or RuleRegistry()
        self._threat_intel = threat_intel or NullThreatIntelProvider()

    def analyze_entry(self, entry: LogEntry) -> Optional[Finding]:
        finding = self._create_finding(entry, rule)
        # Always call - NullProvider returns None gracefully
        finding.threat_info = self._threat_intel.lookup_ip(entry.source_ip)
        return finding
```

**Implementation phase:** Design integrations architecture before implementing any integration

**Source confidence:** HIGH - [Adapter pattern for optional dependencies](https://medium.com/@hieutrantrung.it/designing-modular-python-packages-with-adapters-and-optional-dependencies-63efd8b07715) and [Python optional dependencies best practices](https://pydevtools.com/handbook/explanation/what-are-optional-dependencies-and-dependency-groups/).

---

### Pitfall 5: Circuit Breaker Missing for External APIs

**What goes wrong:**
Cloudflare API goes down for maintenance. Scanner keeps trying every event, accumulating timeouts. 1000 events * 30 second timeout = 8+ hours to complete a scan that should take 30 seconds. No circuit breaker to fail fast.

**Why it happens:**
- Naive retry logic retries forever
- No tracking of consecutive failures
- Each event processed independently, no awareness of prior failures
- Timeout set too high for integration calls

**Consequences:**
- **Extreme latency:** Scan takes hours instead of seconds
- **Resource exhaustion:** Connections pile up waiting for timeouts
- **Poor user experience:** Report delayed indefinitely
- **Log spam:** Thousands of timeout errors

**Warning signs:**
- Scan duration increases 100x when external API slow
- Memory/connection growth during API outages
- Same timeout error repeated thousands of times in logs

**Prevention:**

1. **Implement circuit breaker pattern:**
```python
from pybreaker import CircuitBreaker

# Circuit opens after 5 failures, stays open for 60 seconds
cloudflare_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    exclude=[httpx.HTTPStatusError],  # Don't trip on 4xx errors
)

class CloudflareThreatIntel(ThreatIntelProvider):
    def __init__(self, api_token: str):
        self._client = CloudflareClient(api_token)
        self._breaker = cloudflare_breaker

    @cloudflare_breaker
    def lookup_ip(self, ip: str) -> Optional[ThreatInfo]:
        return self._client.intel.ip(ip)

    def lookup_ip_safe(self, ip: str) -> Optional[ThreatInfo]:
        """Lookup with circuit breaker - returns None if circuit open."""
        try:
            return self.lookup_ip(ip)
        except CircuitBreakerError:
            log.debug("cloudflare_circuit_open", ip=ip)
            return None
```

2. **Short timeouts for enrichment calls:**
```python
# Enrichment is optional - don't wait long
ENRICHMENT_TIMEOUT = 5.0  # 5 seconds max

def lookup_ip(self, ip: str) -> Optional[ThreatInfo]:
    try:
        response = httpx.get(
            f"{self.base_url}/intel/ip/{ip}",
            timeout=ENRICHMENT_TIMEOUT,
        )
        return self._parse_response(response)
    except httpx.TimeoutException:
        log.debug("cloudflare_timeout", ip=ip)
        return None
```

3. **Aggregate circuit state in logs:**
```python
def on_scan_complete(self):
    """Log integration health summary."""
    if hasattr(self._threat_intel, '_breaker'):
        breaker = self._threat_intel._breaker
        log.info(
            "threat_intel_health",
            state=breaker.current_state,
            failure_count=breaker.failure_count,
            success_count=breaker.success_count,
        )
```

**Implementation phase:** Integration client base class

**Source confidence:** HIGH - [Circuit breaker pattern in Python](https://github.com/danielfm/pybreaker) and [resilient API patterns](https://medium.com/@fahimad/resilient-apis-retry-logic-circuit-breakers-and-fallback-mechanisms-cfd37f523f43).

---

## Moderate Pitfalls

### Pitfall 6: False Positive Explosion with New Rules

**What goes wrong:**
Adding 30 new rules causes false positive rate to jump from 5% to 40%. Users disable the scanner because reports are noise. Rules were tested with synthetic data but not real-world UniFi logs.

**Why it happens:**
- Rules tuned for "what should happen" not "what actually happens"
- No baseline establishment before enabling rules
- Severity levels guessed, not derived from impact data
- Default thresholds too aggressive

**Consequences:**
- **Alert fatigue:** Users ignore all findings, including real issues
- **Lost trust:** Scanner seen as "crying wolf"
- **Support burden:** Users complain about false positives

**Warning signs:**
- New rule generates findings for >20% of events
- Multiple reports with 100+ findings (normal is 5-20)
- Users asking "why is X reported as a problem?"

**Prevention:**

1. **Shadow mode for new rules:**
```python
@dataclass
class Rule:
    # ... existing fields ...
    # NEW: Rules can be in shadow mode (logged but not reported)
    shadow_mode: bool = False

class AnalysisEngine:
    def analyze_entry(self, entry: LogEntry) -> Optional[Finding]:
        rule = self._registry.find_matching_rule(entry.event_type, entry.message)
        if rule is None:
            return None

        finding = self._create_finding(entry, rule)

        if rule.shadow_mode:
            log.info("shadow_finding", rule=rule.name, finding=finding.title)
            return None  # Don't include in report

        return finding
```

2. **Baseline period before alerting:**
```python
# Run for 2 weeks in shadow mode to establish normal patterns
NEW_RULE_SHADOW_PERIOD_DAYS = 14

def should_rule_be_shadowed(rule: Rule) -> bool:
    """Check if rule should be in shadow mode based on age."""
    if not rule.introduced_version:
        return False
    rule_age = datetime.now() - rule.introduced_date
    return rule_age.days < NEW_RULE_SHADOW_PERIOD_DAYS
```

3. **Configurable thresholds:**
```yaml
# config.yaml
rules:
  wifi_client_disconnect:
    enabled: true
    severity_override: LOW  # User demotes from MEDIUM
  high_cpu_usage:
    threshold_percent: 90  # Default was 80, too noisy
```

4. **False positive feedback mechanism:**
```python
# In remediation template for questionable rules
remediation_template = """
If this finding is not relevant to your environment:
1. You can tune this rule in your configuration
2. Report false positives at: [feedback link]

Current threshold: {threshold}
To adjust: Set RULE_XYZ_THRESHOLD in your config
"""
```

**Implementation phase:** Rule design guidelines, before adding new rules

**Source confidence:** HIGH - [SIEM false positive tuning best practices](https://www.connectwise.com/blog/9-ways-to-eliminate-siem-false-positives) and [alert tuning strategies](https://www.prophetsecurity.ai/blog/security-operations-center-soc-best-practices-alert-tuning).

---

### Pitfall 7: Optional Dependency Import Failures

**What goes wrong:**
User installs `unifi-scanner` without `[cloudflare]` extra. Code has `import cloudflare` at module level. Scanner crashes on startup with `ModuleNotFoundError` even though Cloudflare integration is disabled in config.

**Why it happens:**
- Eager imports at module level
- No lazy loading of optional dependencies
- Missing try/except around optional imports
- Optional dependency listed in main requirements instead of extras

**Consequences:**
- **Startup crash:** Scanner won't run without optional packages
- **User confusion:** "I didn't configure Cloudflare, why do I need it?"
- **Packaging issues:** Dependency graph includes optional packages as required

**Warning signs:**
- `ModuleNotFoundError: No module named 'cloudflare'` on startup
- Users reporting they have to install packages they don't use
- pyproject.toml has optional packages in main `dependencies`

**Prevention:**

1. **Lazy imports inside functions:**
```python
# BAD: Module-level import
import cloudflare

# GOOD: Lazy import when needed
def create_cloudflare_client(api_token: str):
    try:
        import cloudflare
    except ImportError:
        raise ConfigurationError(
            "Cloudflare integration requires the 'cloudflare' package. "
            "Install with: pip install unifi-scanner[cloudflare]"
        )
    return cloudflare.Cloudflare(api_token=api_token)
```

2. **Optional dependencies in pyproject.toml:**
```toml
[project]
dependencies = [
    "httpx>=0.24.0",
    "structlog>=23.1.0",
    # Core dependencies only
]

[project.optional-dependencies]
cloudflare = ["cloudflare>=3.0.0"]
cybersecure = []  # Uses existing UniFi API, no extra deps
all = ["unifi-scanner[cloudflare]"]
```

3. **Feature detection at config time:**
```python
def validate_config(settings: UnifiSettings) -> List[str]:
    """Validate configuration and return warnings."""
    warnings = []

    if settings.cloudflare_api_token:
        try:
            import cloudflare
        except ImportError:
            warnings.append(
                "CLOUDFLARE_API_TOKEN is set but 'cloudflare' package not installed. "
                "Cloudflare integration will be disabled."
            )
            settings.cloudflare_api_token = None  # Disable integration

    return warnings
```

4. **Startup health check with clear messaging:**
```python
def check_integrations() -> Dict[str, bool]:
    """Check which optional integrations are available."""
    status = {
        "cloudflare": False,
        "cybersecure": False,
    }

    try:
        import cloudflare
        status["cloudflare"] = True
    except ImportError:
        pass

    # Cybersecure uses existing UniFi API
    status["cybersecure"] = True

    return status

# At startup
integrations = check_integrations()
log.info("integrations_available", **integrations)
```

**Implementation phase:** Package structure setup before implementing integrations

**Source confidence:** HIGH - [Python optional dependencies handling](https://www.pyopensci.org/python-package-guide/package-structure-code/declare-dependencies.html) and [PEP 771 default extras](https://peps.python.org/pep-0771/).

---

### Pitfall 8: Cybersecure API Version Compatibility

**What goes wrong:**
Cybersecure integration built against UniFi Network 9.3. User running 8.x doesn't have Cybersecure endpoints. API calls return 404. Scanner crashes or logs cryptic errors about missing endpoints.

**Why it happens:**
- Cybersecure is a premium feature requiring UniFi Network 9.3+
- No feature detection before calling Cybersecure endpoints
- Assumes all UniFi deployments have same capabilities

**Consequences:**
- **Crashes on older firmware:** 404 errors treated as failures
- **User confusion:** "I have UniFi, why doesn't Cybersecure work?"
- **Support burden:** Explaining version requirements

**Warning signs:**
- HTTP 404 on `/api/cybersecure/*` endpoints
- Errors on users with older UniFi versions
- Reports working on some deployments but not others

**Detection:**
```python
def check_cybersecure_available(self) -> bool:
    """Check if Cybersecure API is available on this controller."""
    try:
        response = self._request("GET", "/api/cybersecure/status")
        return response.status_code == 200
    except UnifiAPIError as e:
        if "404" in str(e):
            return False
        raise
```

**Prevention:**

1. **Version detection at connection time:**
```python
def connect(self) -> None:
    """Connect to UniFi Controller."""
    # ... existing connection logic ...

    # NEW: Detect available features
    self.features = self._detect_features()
    log.info("controller_features", **self.features)

def _detect_features(self) -> Dict[str, bool]:
    """Detect optional API features."""
    features = {
        "cybersecure": False,
        "traffic_identification": False,
    }

    # Check Cybersecure availability
    try:
        self._request("GET", "/api/cybersecure/status")
        features["cybersecure"] = True
    except UnifiAPIError:
        pass

    return features
```

2. **Graceful degradation when unavailable:**
```python
def get_cybersecure_threats(self, site: str) -> List[Dict]:
    """Get Cybersecure threat data if available."""
    if not self.features.get("cybersecure"):
        log.debug("cybersecure_not_available")
        return []

    return self._request("GET", f"/api/s/{site}/cybersecure/threats")
```

3. **Clear configuration documentation:**
```markdown
## UniFi Cybersecure Integration

**Requirements:**
- UniFi Network 9.3 or newer
- UniFi OS Server (not self-hosted UniFi Network Server)
- Active CyberSecure subscription ($99/year or $499/year Enterprise)

**Checking compatibility:**
1. Log into your UniFi controller
2. Navigate to Settings > Security
3. If you see "CyberSecure" options, integration is available
```

**Implementation phase:** Cybersecure integration - feature detection first

**Source confidence:** HIGH - [UniFi CyberSecure requirements](https://help.ui.com/hc/en-us/articles/30426718447639-UniFi-CyberSecure) specifies UniFi Network 9.3+ requirement.

---

### Pitfall 9: Overlapping Rule Categories Creating Confusion

**What goes wrong:**
New "wireless" rules overlap with existing "connectivity" rules. Same event (client disconnect) matches both a wireless roaming rule and a connectivity disconnect rule. Report shows duplicate findings with different severities/categories. User confused which to act on.

**Why it happens:**
- Category boundaries not clearly defined
- No ownership of event types across categories
- Rules added independently without cross-category review
- event_types lists overlap between rules

**Consequences:**
- **Duplicate findings:** Same event reported multiple ways
- **Inconsistent severity:** Wireless says LOW, connectivity says MEDIUM
- **User confusion:** "Which finding is correct?"

**Warning signs:**
- Same event appearing multiple times in report with different categories
- Tests showing multiple rules matching same event_type
- Category counts don't add up to total findings

**Detection:**
```python
def test_no_cross_category_overlap():
    """Ensure event types belong to exactly one category."""
    registry = get_default_registry()
    event_to_category = {}

    for rule in registry.all_rules:
        for event_type in rule.event_types:
            if event_type in event_to_category:
                existing_cat = event_to_category[event_type]
                if existing_cat != rule.category:
                    pytest.fail(
                        f"Event {event_type} in both {existing_cat} and {rule.category}"
                    )
            event_to_category[event_type] = rule.category
```

**Prevention:**

1. **Event type ownership table:**
```markdown
# Rule Category Boundaries

| Event Prefix | Category | Owner |
|--------------|----------|-------|
| EVT_WU_*, EVT_WG_* | Wireless | wireless_rules.py |
| EVT_AP_Lost_*, EVT_SW_Lost_* | Connectivity | connectivity_rules.py |
| EVT_AP_HIGH_*, EVT_GW_HIGH_* | Performance | performance_rules.py |
| EVT_AD_*, EVT_IPS_* | Security | security_rules.py |
| EVT_*_Upgraded, EVT_*_Restarted | System | system_rules.py |
```

2. **Rule registry validation:**
```python
def get_default_registry() -> RuleRegistry:
    """Create registry with validation."""
    registry = RuleRegistry()
    for rule in ALL_RULES:
        registry.register(rule)

    # Validate no overlapping categories
    registry.validate_category_ownership()
    return registry
```

3. **Clear category definitions:**
```python
class Category(Enum):
    SECURITY = "Security"      # Authentication, threats, IPS
    CONNECTIVITY = "Connectivity"  # Device online/offline, WAN
    PERFORMANCE = "Performance"   # CPU, memory, speed, interference
    SYSTEM = "System"            # Firmware, config, adoption
    WIRELESS = "Wireless"        # NEW: Client roaming, signal quality
    DEVICE_HEALTH = "Device Health"  # NEW: Hardware status, temperature
```

**Implementation phase:** Category design - before adding wireless/device health rules

**Source confidence:** MEDIUM - Based on rule engine design principles and existing codebase analysis.

---

### Pitfall 10: Integration Credentials in Logs

**What goes wrong:**
Debug logging enabled for troubleshooting. Cloudflare API calls log full request including `Authorization: Bearer <token>`. User shares logs for support, credentials exposed.

**Why it happens:**
- structlog logs all context by default
- httpx debug mode logs headers
- Error messages include request details
- No credential scrubbing in log pipeline

**Consequences:**
- **Credential leak:** API tokens exposed in logs
- **Security incident:** Shared logs compromise accounts
- **Compliance violation:** Secrets in log files

**Warning signs:**
- `Bearer` appearing in log files
- Full HTTP headers in debug logs
- API tokens visible in error messages

**Prevention:**

1. **Credential scrubbing processor:**
```python
import structlog
import re

SENSITIVE_PATTERNS = [
    (re.compile(r'Bearer [A-Za-z0-9\-._~+/]+=*'), 'Bearer [REDACTED]'),
    (re.compile(r'api[_-]?token["\s:=]+["\']?[\w\-]+["\']?', re.I), 'api_token=[REDACTED]'),
    (re.compile(r'password["\s:=]+["\']?[^"\'\s]+["\']?', re.I), 'password=[REDACTED]'),
]

def scrub_credentials(_, __, event_dict):
    """Scrub sensitive data from log events."""
    for key, value in list(event_dict.items()):
        if isinstance(value, str):
            for pattern, replacement in SENSITIVE_PATTERNS:
                value = pattern.sub(replacement, value)
            event_dict[key] = value
    return event_dict

# Configure structlog
structlog.configure(
    processors=[
        scrub_credentials,  # Add early in chain
        # ... other processors
    ]
)
```

2. **Mask credentials in config display:**
```python
def log_config_summary(settings: UnifiSettings) -> None:
    """Log configuration without exposing secrets."""
    log.info(
        "configuration_loaded",
        host=settings.host,
        username=settings.username,
        password="***" if settings.password else None,
        cloudflare_token="***" if settings.cloudflare_api_token else None,
        # Never log actual credential values
    )
```

3. **httpx logging without headers:**
```python
# Don't enable httpx debug logging in production
# If needed, filter headers:
class SafeEventHook:
    def __call__(self, event: str, info: dict):
        if "headers" in info:
            info["headers"] = {
                k: v for k, v in info["headers"].items()
                if k.lower() not in ("authorization", "x-auth-token")
            }
        log.debug(event, **info)
```

**Implementation phase:** Logging configuration - before adding any integration

**Source confidence:** HIGH - Standard security practice, existing `structlog` setup in codebase.

---

## Minor Pitfalls

### Pitfall 11: Test Fixtures Becoming Stale

**What goes wrong:**
Test fixtures created from UniFi API captures in 2026. UniFi Network 10.x changes event format. Tests pass (using old fixtures) but production fails on new format. Rules never updated to handle format changes.

**Why it happens:**
- Fixtures captured once, never refreshed
- No mechanism to detect API format drift
- Tests use synthetic data that doesn't evolve with real API

**Prevention:**
```python
# fixtures/events/metadata.json
{
    "captured_from": "UniFi Network 9.3.43",
    "captured_date": "2026-01-24",
    "refresh_recommended_after": "2026-07-24"
}

def test_fixtures_not_stale():
    """Warn if fixtures are old."""
    metadata = json.load(open("fixtures/events/metadata.json"))
    refresh_date = datetime.fromisoformat(metadata["refresh_recommended_after"])
    if datetime.now() > refresh_date:
        warnings.warn(
            f"Test fixtures captured from {metadata['captured_from']} "
            f"are over 6 months old. Consider refreshing."
        )
```

**Implementation phase:** Test infrastructure

**Source confidence:** MEDIUM - General testing best practice.

---

### Pitfall 12: Missing Graceful Shutdown During API Calls

**What goes wrong:**
Scanner in middle of Cloudflare API batch when SIGTERM received (container shutdown). HTTP connections abandoned mid-request. No cleanup, potentially corrupted state.

**Why it happens:**
- No signal handling for graceful shutdown
- Long-running API operations not cancellable
- State saved only at end of scan, not incrementally

**Prevention:**
```python
import signal
import sys

class Scanner:
    def __init__(self):
        self._shutdown_requested = False
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        log.info("shutdown_requested", signal=signum)
        self._shutdown_requested = True

    def scan(self):
        for event in events:
            if self._shutdown_requested:
                log.info("scan_interrupted", processed=count)
                self._save_partial_state()
                sys.exit(0)
            self._process_event(event)
```

**Implementation phase:** Scheduler/runner module

**Source confidence:** MEDIUM - Standard containerization practice.

---

## Prevention Strategies Summary

| Pitfall | Primary Prevention | Secondary Prevention | Priority |
|---------|-------------------|----------------------|----------|
| Rule explosion | Rule composition, categorization | Quarterly review process | P0 |
| Cloudflare rate limits | Caching, rate limiter decorator | Graceful degradation | P0 |
| UniFi rate limits | Conservative polling, request spacing | Backoff on failures | P0 |
| Tight integration coupling | Adapter pattern, interfaces | Null provider fallback | P0 |
| Missing circuit breaker | pybreaker library | Short timeouts | P0 |
| False positive explosion | Shadow mode for new rules | Configurable thresholds | P1 |
| Import failures | Lazy imports, extras in pyproject | Feature detection at startup | P1 |
| Cybersecure version | Feature detection | Clear documentation | P1 |
| Category overlap | Event type ownership table | Registry validation | P1 |
| Credentials in logs | Scrub processor | Mask in config display | P1 |
| Stale fixtures | Metadata with refresh date | CI warning | P2 |
| Ungraceful shutdown | Signal handling | Partial state saves | P2 |

---

## Phase-Specific Implementation Recommendations

| Phase Topic | Likely Pitfalls | Mitigation |
|-------------|-----------------|------------|
| Rule architecture design | #1 Rule explosion, #9 Category overlap | Design event ownership table and rule composition patterns before coding |
| Cloudflare integration | #2 Rate limits, #4 Tight coupling, #5 Circuit breaker | Build adapter pattern with rate limiter and circuit breaker from day one |
| Cybersecure integration | #3 UniFi rate limits, #8 Version compatibility | Feature detection and conservative polling |
| New rule implementation | #6 False positives | Shadow mode rollout, baseline period |
| Package/config updates | #7 Import failures, #10 Credential logging | Lazy imports, log scrubbing |

---

## Implementation Checklist

Before merging integration/rule expansion:

**Rule Architecture:**
- [ ] Event type ownership documented (which category owns which events)
- [ ] Rule composition helpers for common patterns
- [ ] No duplicate event_type coverage across categories
- [ ] Shadow mode support for new rules

**API Integrations:**
- [ ] Adapter interface defined (ThreatIntelProvider or similar)
- [ ] Null/no-op provider for disabled integrations
- [ ] Circuit breaker on all external API calls
- [ ] Rate limiter with caching
- [ ] Short timeouts (5s) for enrichment calls

**Configuration:**
- [ ] Optional dependencies in `[project.optional-dependencies]`
- [ ] Lazy imports for optional packages
- [ ] Feature detection at startup with clear logging
- [ ] Credential scrubbing in log processors

**Testing:**
- [ ] Test no rule conflicts (same event, different severities)
- [ ] Test circuit breaker opens after failures
- [ ] Test graceful degradation when integration unavailable
- [ ] Test lazy import doesn't crash without optional package

---

## Sources

**API Rate Limits:**
- [Cloudflare API rate limits](https://developers.cloudflare.com/fundamentals/api/reference/limits/) - 1,200 requests per 5 minutes
- [UniFi API rate limiting (community)](https://github.com/Art-of-WiFi/UniFi-API-client/issues/194) - Undocumented limits
- [UniFi CyberSecure requirements](https://help.ui.com/hc/en-us/articles/30426718447639-UniFi-CyberSecure) - Network 9.3+

**Rule Engine Patterns:**
- [Rules engine design patterns](https://www.nected.ai/us/blog-us/rules-engine-design-pattern) - Scalability and maintenance
- [SIEM alert tuning best practices](https://www.redlegg.com/blog/siem-alert) - False positive reduction
- [Eliminating SIEM false positives](https://www.connectwise.com/blog/9-ways-to-eliminate-siem-false-positives) - Baseline establishment

**Integration Patterns:**
- [Circuit breaker in Python (pybreaker)](https://github.com/danielfm/pybreaker) - Failure handling
- [Resilient APIs patterns](https://medium.com/@fahimad/resilient-apis-retry-logic-circuit-breakers-and-fallback-mechanisms-cfd37f523f43) - Circuit breakers and fallbacks
- [Adapter pattern for optional dependencies](https://medium.com/@hieutrantrung.it/designing-modular-python-packages-with-adapters-and-optional-dependencies-63efd8b07715) - Clean architecture
- [Python optional dependencies](https://pydevtools.com/handbook/explanation/what-are-optional-dependencies-and-dependency-groups/) - Package structure

**Feature Flags:**
- [Feature flags in Python](https://www.statsig.com/perspectives/feature-flagging-python-best-practices) - Shadow mode patterns
- [Feature flag best practices](https://posthog.com/docs/feature-flags/best-practices) - Rollout strategies

---

**Research confidence:** HIGH
**Verification:** Cross-referenced with Cloudflare official documentation, existing codebase patterns (`analysis/rules/`, `api/client.py`), and community reports of UniFi API behavior.
