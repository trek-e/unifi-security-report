# Architecture Patterns

**Domain:** Network log analysis and reporting service
**Researched:** 2026-01-24
**Confidence:** MEDIUM (architecture patterns verified through multiple sources; UniFi-specific integration details based on community libraries)

## Executive Summary

The UniFi Scanner service follows a classic **ETL pipeline architecture** with five distinct stages: Collection, Parsing, Analysis, Report Generation, and Delivery. This architecture separates concerns cleanly, allows independent testing of each stage, and follows established patterns for log analysis systems.

The recommended approach uses a **scheduled batch processing model** (not real-time streaming) appropriate for the v1 periodic reporting use case. Components communicate through in-memory data structures during a single run, with optional persistence for historical analysis.

## Recommended Architecture

```
+------------------+     +------------------+     +------------------+
|                  |     |                  |     |                  |
|   Log Collector  +---->+   Log Parser     +---->+   Analyzer       |
|   (UniFi API/SSH)|     |   (Normalizer)   |     |   (Rule Engine)  |
|                  |     |                  |     |                  |
+------------------+     +------------------+     +--------+---------+
                                                          |
                                                          v
+------------------+     +------------------+     +------------------+
|                  |     |                  |     |                  |
|   Delivery       +<----+   Report Gen     +<----+   Finding Store  |
|   (Email/File)   |     |   (Templates)    |     |   (In-Memory)    |
|                  |     |                  |     |                  |
+------------------+     +------------------+     +------------------+
```

### Component Boundaries

| Component | Responsibility | Input | Output | Communicates With |
|-----------|---------------|-------|--------|-------------------|
| **Scheduler** | Triggers collection runs on configured intervals | Cron config | Run trigger | Log Collector |
| **Log Collector** | Fetches raw logs from UniFi gateway/controller | API credentials, SSH config | Raw log entries | Log Parser |
| **Log Parser** | Normalizes diverse log formats into structured data | Raw log strings | Normalized LogEntry objects | Analyzer |
| **Analyzer** | Applies rules to detect issues, assigns severity | Normalized entries | Finding objects with severity | Finding Store |
| **Finding Store** | Accumulates findings for report generation | Finding objects | Grouped/sorted findings | Report Generator |
| **Report Generator** | Creates human-readable reports from findings | Findings, templates | Report content (HTML/text) | Delivery |
| **Delivery** | Sends reports via configured channels | Report content, config | Email sent, file written | External systems |
| **Config Manager** | Loads and validates configuration | Config file, env vars | Typed config objects | All components |

### Data Flow

**Collection Phase:**
```
UniFi Gateway/Controller
    |
    | (HTTPS API or SSH)
    v
Raw Log Entries (strings)
    |
    | (list of raw log lines with metadata)
    v
Log Parser
```

**Processing Phase:**
```
Raw Log Entry
    |
    | (regex parsing, field extraction)
    v
Normalized LogEntry {
    timestamp: datetime
    source: str (device ID/name)
    facility: str (hostapd, kernel, etc.)
    severity: int (syslog level 0-7)
    message: str
    raw: str
    metadata: dict
}
    |
    | (rule matching)
    v
Finding {
    id: str
    category: str (security, connectivity, performance, etc.)
    severity: enum (low, medium, severe)
    title: str
    explanation: str (plain English)
    remediation: Optional[str] (for severe only)
    source_entries: List[LogEntry]
    detected_at: datetime
}
```

**Output Phase:**
```
List[Finding]
    |
    | (grouping, sorting by severity)
    v
Report {
    generated_at: datetime
    period: (start, end)
    summary: dict (counts by severity)
    findings_severe: List[Finding]
    findings_medium: List[Finding]
    findings_low: List[Finding]
}
    |
    | (template rendering)
    v
Report Content (HTML and/or plain text)
    |
    | (SMTP or filesystem)
    v
Email / File Output
```

## Component Details

### 1. Scheduler

**Purpose:** Trigger log collection and analysis runs at configured intervals.

**Approaches (ranked by recommendation):**

1. **Built-in Python scheduler (APScheduler)** - Recommended for v1
   - Runs within the container process
   - No external dependencies
   - Supports cron-like expressions
   - Handles missed runs gracefully

2. **Container-native cron (Ofelia/Supercronic)** - Alternative
   - Separate scheduler container triggers main container
   - More complex deployment but cleaner separation
   - Better for multi-container orchestration

3. **Kubernetes CronJob** - For K8s deployments
   - Native K8s scheduling
   - Out of scope for v1 Docker focus

**Confidence:** MEDIUM - Based on [Ofelia](https://github.com/mcuadros/ofelia) and general containerization patterns.

### 2. Log Collector

**Purpose:** Retrieve logs from UniFi infrastructure.

**Primary Method: UniFi Controller API**
- Uses unofficial but well-documented community APIs
- Python libraries available: `unifi-controller-api`, `unificontrol`, `pyunifi`
- Provides `get_events()` and `get_alarms()` methods
- Returns structured JSON with timestamps and metadata

**Fallback Method: SSH Direct Access**
- Connect directly to UniFi gateway via SSH
- Read syslog files (`/var/log/messages`, device-specific logs)
- Requires paramiko or asyncssh for Python
- More complex parsing required

**SIEM Integration Method (Alternative):**
- Configure UniFi to forward logs via syslog (UDP)
- Service listens on UDP port for incoming logs
- Uses Common Event Format (CEF) standardized format
- More complex infrastructure but real-time capable

**Recommendation for v1:** API-first with SSH fallback, per PROJECT.md decision.

**Data Models:**

```python
@dataclass
class RawLogBatch:
    source: str  # "api" or "ssh"
    device_id: str
    device_name: str
    collected_at: datetime
    entries: List[str]  # Raw log lines
    metadata: dict  # API response metadata
```

**Confidence:** HIGH for API method - verified via [unifi-controller-api](https://github.com/tnware/unifi-controller-api) and [unificontrol](https://unificontrol.readthedocs.io/en/latest/introduction.html).

### 3. Log Parser

**Purpose:** Convert raw log strings into structured, normalized data.

**Challenges:**
- UniFi logs come in multiple formats (syslog, JSON, custom)
- Format varies by device type and firmware version
- Multi-line log entries for stack traces

**Pattern Approach:**
1. **Format detection** - Identify log format (syslog, JSON, custom)
2. **Field extraction** - Parse timestamp, facility, severity, message
3. **Normalization** - Convert to common LogEntry structure
4. **Enrichment** - Add device context, parse known message patterns

**Libraries:**
- `python-dateutil` for flexible timestamp parsing
- `regex` (not just `re`) for advanced pattern matching
- Custom parsers for known UniFi message types

**Data Models:**

```python
@dataclass
class LogEntry:
    id: str  # Unique identifier
    timestamp: datetime
    source_device: str
    facility: str  # hostapd, kernel, dhcpd, etc.
    severity: int  # Syslog 0-7
    message: str
    raw: str  # Original unparsed line
    parsed_fields: dict  # Extracted structured data

    @property
    def severity_name(self) -> str:
        return ["EMERG", "ALERT", "CRIT", "ERR",
                "WARN", "NOTICE", "INFO", "DEBUG"][self.severity]
```

**Confidence:** MEDIUM - Patterns verified via [NXLog UniFi docs](https://docs.nxlog.co/integrate/unifi.html) and syslog standards.

### 4. Analyzer (Rule Engine)

**Purpose:** Detect issues in normalized log entries and assign severity.

**Architecture Pattern: Rules Engine**

Use a lightweight rules engine pattern where rules are:
- Declarative (can be defined in YAML/JSON or code)
- Composable (combine simple conditions)
- Extensible (easy to add new rules)

**Rule Structure:**

```python
@dataclass
class Rule:
    id: str
    name: str
    description: str
    category: str  # security, connectivity, performance, hardware
    output_severity: Severity  # low, medium, severe

    # Matching criteria
    facility_match: Optional[str]  # regex
    message_match: Optional[str]  # regex
    severity_min: Optional[int]  # syslog level threshold
    time_window: Optional[timedelta]  # for correlation
    count_threshold: Optional[int]  # for frequency-based rules

    # Output templates
    explanation_template: str
    remediation_template: Optional[str]  # for severe only
```

**Rule Categories:**

| Category | Example Issues | Typical Severity |
|----------|---------------|------------------|
| Security | Failed auth attempts, unauthorized access, firewall blocks | Medium-Severe |
| Connectivity | Client disconnects, AP failures, DHCP issues | Low-Medium |
| Performance | High latency, channel congestion, interference | Low-Medium |
| Hardware | Overheating, high CPU, memory pressure | Medium-Severe |
| Configuration | Invalid settings, deprecated features | Low |

**Severity Assignment Logic:**

| Severity | Criteria | Action |
|----------|----------|--------|
| **Severe** | Security breach indicators, hardware failure, service outage | Include remediation steps |
| **Medium** | Recurring issues, degraded performance, warning patterns | Flag for attention |
| **Low** | Informational, one-off events, normal churn | Report only |

**Libraries:**
- `rule-engine` PyPI package for expression evaluation
- Or custom implementation using strategy pattern

**Confidence:** HIGH - Rules engine pattern is well-established; see [Rules Engine Design Pattern](https://tenmilesquare.com/resources/software-development/basic-rules-engine-design-pattern/).

### 5. Finding Store

**Purpose:** Accumulate and organize findings for reporting.

**Design:** In-memory for v1 (single-run batch processing).

```python
@dataclass
class Finding:
    id: str
    rule_id: str
    category: str
    severity: Severity
    title: str
    explanation: str  # Plain English
    remediation: Optional[str]  # For severe only
    source_entries: List[LogEntry]
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int
```

**Aggregation Logic:**
- Group duplicate findings by rule_id
- Track first/last occurrence and count
- Sort by severity (severe first), then by recency

**Future Enhancement (v2):**
- SQLite for historical tracking
- Trend analysis (is this issue getting worse?)
- Deduplication across runs

**Confidence:** HIGH - Standard pattern.

### 6. Report Generator

**Purpose:** Create human-readable reports from findings.

**Template Engine:** Jinja2
- Industry standard for Python templating
- Supports HTML and plain text
- Separation of content from presentation
- Easy to customize report format

**Report Structure:**

```
# Network Health Report
Generated: 2026-01-24 08:00:00
Period: Last 24 hours

## Summary
- Severe Issues: 1
- Medium Issues: 3
- Low Issues: 12

## Severe Issues (Action Required)

### [Security] Multiple Failed Admin Login Attempts
**What happened:** 47 failed login attempts to the UniFi Controller
from IP 192.168.1.105 between 02:15 and 02:45.

**Why this matters:** This pattern indicates a potential brute-force
attack on your network administration interface.

**What to do:**
1. Check if you recognize IP 192.168.1.105
2. If unknown, block this IP in your firewall
3. Enable two-factor authentication on your UniFi account
4. Consider changing your admin password

---

## Medium Issues

### [Connectivity] Frequent Client Disconnections on AP-Living-Room
...

## Low Issues (Informational)
...
```

**Templates:**
- `report.html.j2` - HTML email version
- `report.txt.j2` - Plain text version
- `report_summary.txt.j2` - Short summary for subject lines

**Confidence:** HIGH - Jinja2 is standard; see [Better Stack Jinja Guide](https://betterstack.com/community/guides/scaling-python/jinja-templating/).

### 7. Delivery

**Purpose:** Send reports via configured channels.

**Channels:**

1. **Email (SMTP)**
   - Use `smtplib` + `email` stdlib
   - Support TLS/SSL (port 587/465)
   - HTML with plain text fallback
   - Credentials via environment variables

2. **File Output**
   - Write to configurable directory
   - Filename pattern: `unifi-report-{datetime}.{format}`
   - Support HTML, plain text, JSON

**Email Configuration:**

```python
@dataclass
class EmailConfig:
    enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str  # From env var
    use_tls: bool
    from_address: str
    to_addresses: List[str]
    subject_template: str
```

**Confidence:** HIGH - Standard Python patterns; see [Python smtplib docs](https://docs.python.org/3/library/smtplib.html).

### 8. Config Manager

**Purpose:** Load, validate, and provide typed configuration.

**Configuration Sources (priority order):**
1. Environment variables (for secrets, container config)
2. Config file (YAML or TOML)
3. Defaults

**Configuration Schema:**

```yaml
# unifi-scanner.yaml
unifi:
  controller_url: "https://192.168.1.1"
  username: "${UNIFI_USERNAME}"  # Env var substitution
  password: "${UNIFI_PASSWORD}"
  site: "default"
  verify_ssl: false

  ssh_fallback:
    enabled: true
    host: "192.168.1.1"
    username: "root"
    key_file: "/config/ssh/id_rsa"

schedule:
  cron: "0 8 * * *"  # Daily at 8 AM
  timezone: "America/New_York"

analysis:
  lookback_hours: 24
  rules_file: "/config/rules.yaml"  # Optional custom rules

output:
  file:
    enabled: true
    directory: "/reports"
    format: "html"  # html, txt, json

  email:
    enabled: true
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    use_tls: true
    from: "unifi-scanner@example.com"
    to:
      - "admin@example.com"
    subject: "UniFi Report: {severe_count} severe, {medium_count} medium issues"

logging:
  level: "INFO"
  format: "json"  # json or text
```

**Libraries:**
- `pydantic` for config validation and typing
- `python-dotenv` for env var loading
- `pyyaml` for YAML parsing

**Confidence:** HIGH - Standard patterns.

## Patterns to Follow

### Pattern 1: Pipeline Processor

**What:** Each processing stage is an independent function/class that takes input and produces output, with no side effects outside its domain.

**When:** All main processing stages (collect, parse, analyze, generate, deliver).

**Example:**
```python
class LogParser:
    def __init__(self, config: ParserConfig):
        self.config = config
        self.patterns = self._compile_patterns()

    def parse(self, raw_batch: RawLogBatch) -> List[LogEntry]:
        """Pure function: raw logs in, structured entries out."""
        entries = []
        for line in raw_batch.entries:
            if entry := self._parse_line(line, raw_batch):
                entries.append(entry)
        return entries
```

### Pattern 2: Dependency Injection for Testability

**What:** Components receive their dependencies through constructor, not hardcoded.

**When:** Any component that depends on external systems (UniFi API, SMTP, filesystem).

**Example:**
```python
class LogCollector:
    def __init__(self, api_client: UnifiApiClient, ssh_client: Optional[SSHClient] = None):
        self.api = api_client
        self.ssh = ssh_client

    def collect(self, lookback: timedelta) -> RawLogBatch:
        try:
            return self._collect_via_api(lookback)
        except ApiError:
            if self.ssh:
                return self._collect_via_ssh(lookback)
            raise
```

### Pattern 3: Configuration-Driven Rules

**What:** Analysis rules defined in data (YAML) rather than code where possible.

**When:** Rule definitions that non-developers might customize.

**Example:**
```yaml
# rules.yaml
rules:
  - id: auth_failure_brute_force
    name: "Brute Force Login Attempt"
    category: security
    severity: severe
    match:
      facility: "authpriv"
      message_pattern: "authentication failure.*rhost=(?P<ip>[\\d.]+)"
      count_threshold: 10
      time_window_minutes: 30
    explanation: >
      {count} failed login attempts from IP {ip} in {window} minutes.
      This pattern suggests a brute-force attack.
    remediation: |
      1. Verify if {ip} is a known device on your network
      2. If unknown, block this IP in your firewall rules
      3. Enable two-factor authentication
      4. Consider changing admin credentials
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Monolithic Run Function

**What:** Single function that does collection, parsing, analysis, and delivery inline.

**Why bad:**
- Impossible to test stages independently
- Cannot reuse components
- Difficult to modify one stage without affecting others

**Instead:** Separate pipeline stages with clear interfaces.

### Anti-Pattern 2: Hardcoded Credentials

**What:** Putting UniFi passwords, SMTP credentials in config files or code.

**Why bad:**
- Security vulnerability
- Difficult to manage across environments
- Commits secrets to version control

**Instead:** Use environment variables for secrets, config files for non-sensitive settings.

### Anti-Pattern 3: Regex-Only Log Parsing

**What:** Relying solely on regex patterns without format detection.

**Why bad:**
- Brittle against format changes
- Poor error handling for malformed logs
- No fallback for unknown formats

**Instead:** Format detection first, then format-specific parsers, with fallback to raw capture.

### Anti-Pattern 4: Blocking Email Delivery

**What:** Synchronously sending email in the main processing pipeline.

**Why bad:**
- SMTP timeouts block entire run
- Retry logic complicates main flow
- Single failure prevents file output

**Instead:** Deliver to file first (always succeeds), then attempt email delivery separately with retries.

## Build Order (Phase Implications)

Based on component dependencies, recommended build order:

```
Phase 1: Foundation
├── Config Manager (needed by everything)
├── Data Models (LogEntry, Finding, Report)
└── Basic container structure

Phase 2: Collection
├── Log Collector (API method)
├── Log Parser (syslog format)
└── Integration test: collect + parse

Phase 3: Analysis
├── Rule Engine core
├── Initial rule set (10-20 common issues)
├── Finding Store
└── Integration test: full pipeline to findings

Phase 4: Output
├── Report Generator (Jinja2 templates)
├── File Delivery
└── Integration test: end-to-end to file

Phase 5: Delivery
├── Email Delivery
├── Scheduler integration
└── Production container

Phase 6: Hardening
├── SSH fallback for collection
├── Extended rule set
├── Error handling + logging
└── Retry logic
```

**Rationale:**
1. Config and models are dependencies for everything else
2. Collection must work before parsing can be tested
3. Analysis requires normalized log data
4. Report generation requires findings
5. Email is optional and can fail without blocking file output
6. SSH fallback and hardening can be deferred

## Scalability Considerations

| Concern | v1 (Single Gateway) | Future (Multi-Gateway) |
|---------|---------------------|------------------------|
| Log Volume | ~1000s entries/day, in-memory OK | Consider SQLite or file-based buffering |
| Collection | Single API call per run | Parallel collection, rate limiting |
| Analysis | Sequential rule evaluation | Batch processing, possibly parallel |
| Reports | Single report | Per-gateway reports, aggregate summary |
| Storage | No persistence | Historical database for trending |

**v1 Design Decision:** Optimize for simplicity. In-memory processing is sufficient for single-gateway volumes. Add persistence layer in v2 if needed.

## Container Architecture

```
unifi-scanner/
├── Dockerfile
├── docker-compose.yml
├── config/
│   ├── unifi-scanner.yaml
│   └── rules.yaml
├── src/
│   └── unifi_scanner/
│       ├── __init__.py
│       ├── main.py           # Entry point
│       ├── config.py         # Config Manager
│       ├── collector/
│       │   ├── api.py        # UniFi API client
│       │   └── ssh.py        # SSH fallback
│       ├── parser/
│       │   └── syslog.py     # Log parser
│       ├── analyzer/
│       │   ├── engine.py     # Rule engine
│       │   └── rules.py      # Built-in rules
│       ├── reporter/
│       │   ├── generator.py  # Report generator
│       │   └── templates/    # Jinja2 templates
│       └── delivery/
│           ├── email.py      # SMTP delivery
│           └── file.py       # File output
├── templates/
│   ├── report.html.j2
│   └── report.txt.j2
└── tests/
```

**Docker Compose Example:**

```yaml
version: "3.8"
services:
  unifi-scanner:
    build: .
    environment:
      - UNIFI_USERNAME=${UNIFI_USERNAME}
      - UNIFI_PASSWORD=${UNIFI_PASSWORD}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
    volumes:
      - ./config:/config:ro
      - ./reports:/reports
    restart: unless-stopped
```

## Sources

### UniFi Integration
- [unifi-controller-api GitHub](https://github.com/tnware/unifi-controller-api) - Python API client (HIGH confidence)
- [unificontrol documentation](https://unificontrol.readthedocs.io/en/latest/introduction.html) - Alternative Python client (HIGH confidence)
- [NXLog UniFi Integration](https://docs.nxlog.co/integrate/unifi.html) - Syslog collection patterns (MEDIUM confidence)
- [Ubiquiti Community - API Discussion](https://community.ui.com/questions/Ubiquiti-unifi-logs-collection-using-API/e30fb551-40e9-4172-80e4-8c729e8eb14c) - Community patterns (LOW confidence)

### Architecture Patterns
- [GeeksforGeeks - Centralized Logging Systems](https://www.geeksforgeeks.org/system-design/centralized-logging-systems-system-design/) - System design patterns (MEDIUM confidence)
- [Rules Engine Design Pattern](https://tenmilesquare.com/resources/software-development/basic-rules-engine-design-pattern/) - Rules architecture (HIGH confidence)
- [Microservices Log Aggregation Pattern](https://microservices.io/patterns/observability/application-logging.html) - Logging patterns (HIGH confidence)

### Containerization
- [Ofelia Docker Scheduler](https://github.com/mcuadros/ofelia) - Container job scheduling (HIGH confidence)
- [Running Python Tasks in Docker](https://nschdr.medium.com/running-scheduled-python-tasks-in-a-docker-container-bf9ea2e8a66c) - Docker Python patterns (MEDIUM confidence)

### Report Generation
- [Better Stack - Jinja Templating](https://betterstack.com/community/guides/scaling-python/jinja-templating/) - Template patterns (HIGH confidence)
- [Real Python - Jinja Primer](https://realpython.com/primer-on-jinja-templating/) - Jinja2 usage (HIGH confidence)

### Email Delivery
- [Python smtplib Documentation](https://docs.python.org/3/library/smtplib.html) - Official Python docs (HIGH confidence)
- [Mailtrap - Python Send Email](https://mailtrap.io/blog/python-send-email/) - SMTP best practices (MEDIUM confidence)

### Log Classification
- [Better Stack - Log Levels Explained](https://betterstack.com/community/guides/logging/log-levels-explained/) - Severity classification (HIGH confidence)
- [Datadog - How to Categorize Logs](https://www.datadoghq.com/blog/how-to-categorize-logs/) - Categorization patterns (MEDIUM confidence)
