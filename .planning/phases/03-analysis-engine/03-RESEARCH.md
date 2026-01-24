# Phase 3: Analysis Engine - Research

**Researched:** 2026-01-24
**Domain:** Log analysis, rules engine, event categorization, deduplication
**Confidence:** MEDIUM

## Summary

This research investigates how to build an analysis engine that transforms raw UniFi LogEntry objects into categorized Findings with plain English explanations and remediation guidance. The phase involves four key technical domains: rules engine architecture for pattern matching, UniFi event type mapping, time-based deduplication, and template-based explanation generation.

The standard approach for this type of analysis engine in Python is to use a **dictionary dispatch pattern** combined with **structural pattern matching** (Python 3.10+) rather than heavy external rules engine libraries. This keeps the codebase simple, testable, and maintainable while providing the flexibility needed for log analysis rules. For deduplication, a simple time-window grouping algorithm (1-hour clusters per the user decision) can be implemented without ML libraries.

**Primary recommendation:** Build a lightweight, custom rules engine using dictionary dispatch with dataclass-based rule definitions. Avoid external rules engine libraries as they add complexity without proportional benefit for this use case.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.10+ | Pattern matching, dataclasses | Native match/case syntax, no dependencies |
| Pydantic | 2.x | Rule and Finding validation | Already in codebase, excellent for data models |
| datetime | stdlib | Time clustering | Native timezone-aware datetime handling |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Jinja2 | 3.x | Explanation templates | Phase 4 integration, but can use for explanation generation |
| collections.defaultdict | stdlib | Dictionary dispatch defaults | Handling unknown event types gracefully |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom rules engine | rule-engine library | Adds dependency, DSL learning curve, overkill for ~50 rules |
| Custom rules engine | durable-rules | Heavy, designed for complex CEP, not simple log matching |
| Simple time clustering | tslearn/scikit-learn | ML libraries overkill for 1-hour time windows |
| Dictionary dispatch | Python match/case only | Dictionary dispatch handles unknown cases more gracefully |

**Installation:**
```bash
# No new dependencies needed - uses existing Pydantic
pip install pydantic  # Already installed
```

## Architecture Patterns

### Recommended Project Structure
```
src/unifi_scanner/
├── analysis/
│   ├── __init__.py
│   ├── engine.py           # Main AnalysisEngine class
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── base.py         # Rule protocol/base class
│   │   ├── security.py     # Security category rules
│   │   ├── connectivity.py # Connectivity category rules
│   │   ├── performance.py  # Performance category rules
│   │   └── system.py       # System category rules
│   ├── store.py            # FindingStore with deduplication
│   └── templates/
│       ├── __init__.py
│       ├── explanations.py # Plain English templates
│       └── remediation.py  # Remediation step templates
└── models/
    ├── finding.py          # Already exists
    └── enums.py            # Already has Severity, Category
```

### Pattern 1: Dictionary Dispatch for Rules
**What:** Map event_type strings to handler functions using a dictionary
**When to use:** When you have many event types mapping to different handlers
**Example:**
```python
# Source: https://martinheinz.dev/blog/90
from collections import defaultdict
from typing import Callable, Optional
from unifi_scanner.models.log_entry import LogEntry
from unifi_scanner.models.finding import Finding

class RuleRegistry:
    """Registry of event_type -> handler mappings."""

    def __init__(self):
        self._handlers: dict[str, Callable[[LogEntry], Optional[Finding]]] = {}
        self._default_handler: Callable[[LogEntry], Optional[Finding]] = self._handle_unknown

    def register(self, event_type: str):
        """Decorator to register a handler for an event type."""
        def decorator(func: Callable[[LogEntry], Optional[Finding]]):
            self._handlers[event_type] = func
            return func
        return decorator

    def handle(self, log_entry: LogEntry) -> Optional[Finding]:
        """Dispatch to appropriate handler based on event_type."""
        handler = self._handlers.get(log_entry.event_type, self._default_handler)
        return handler(log_entry)

    def _handle_unknown(self, log_entry: LogEntry) -> Optional[Finding]:
        """Handle unknown event types - put in Uncategorized bucket."""
        # Per user decision: unknown patterns go to separate bucket
        return None  # Or create an Uncategorized finding
```

### Pattern 2: Rule Definition with Dataclasses
**What:** Define rules as dataclasses for clarity and type safety
**When to use:** When rules need configuration (severity, category, templates)
**Example:**
```python
from dataclasses import dataclass
from typing import Callable, Optional, Pattern
import re

@dataclass
class Rule:
    """Definition of a single analysis rule."""
    event_types: list[str]              # Event types this rule handles
    category: Category                   # Security, Connectivity, etc.
    severity: Severity                   # Low, Medium, Severe
    title_template: str                  # e.g., "Failed login from {ip}"
    description_template: str            # Plain English explanation
    remediation_template: Optional[str]  # Step-by-step fix (SEVERE/MEDIUM only)
    pattern: Optional[Pattern] = None    # Optional regex for message matching

    def matches(self, log_entry: LogEntry) -> bool:
        """Check if this rule applies to the log entry."""
        if log_entry.event_type not in self.event_types:
            return False
        if self.pattern and not self.pattern.search(log_entry.message):
            return False
        return True
```

### Pattern 3: Time-Window Deduplication
**What:** Group events by (event_type, device_mac) within 1-hour windows
**When to use:** When deduplicating repeated events per user decision
**Example:**
```python
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

class FindingStore:
    """Store findings with time-based deduplication."""

    CLUSTER_WINDOW = timedelta(hours=1)  # User decision: 1-hour clustering
    RECURRING_THRESHOLD = 5              # Claude's discretion: threshold for "recurring"

    def __init__(self):
        self._findings: dict[UUID, Finding] = {}
        # Key: (event_type, device_mac) -> most recent finding for dedup
        self._dedup_index: dict[tuple[str, Optional[str]], Finding] = {}

    def add_or_merge(self, log_entry: LogEntry, finding_template: Finding) -> Finding:
        """Add new finding or merge into existing if within time window."""
        dedup_key = (log_entry.event_type, log_entry.device_mac)

        existing = self._dedup_index.get(dedup_key)
        if existing and self._within_window(existing.last_seen, log_entry.timestamp):
            # Merge into existing finding
            existing.add_occurrence(log_entry.id, log_entry.timestamp)
            return existing

        # Create new finding
        new_finding = finding_template.model_copy()
        new_finding.source_log_ids = [log_entry.id]
        new_finding.first_seen = log_entry.timestamp
        new_finding.last_seen = log_entry.timestamp

        self._findings[new_finding.id] = new_finding
        self._dedup_index[dedup_key] = new_finding
        return new_finding

    def _within_window(self, last_seen: datetime, new_time: datetime) -> bool:
        """Check if new event is within clustering window of last seen."""
        return (new_time - last_seen) <= self.CLUSTER_WINDOW
```

### Anti-Patterns to Avoid
- **Hardcoding messages in rules:** Use templates with placeholders instead of string concatenation
- **Regex for everything:** Use exact event_type matching when possible; regex only for message content
- **Mutating Finding objects directly:** Use the `add_occurrence()` method for proper deduplication
- **Ignoring timezone:** All timestamps should be UTC internally (already handled by LogEntry)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| String templating | Custom format() logic | str.format() or f-strings | Edge cases with escaping, missing keys |
| Timestamp parsing | Custom parsers | datetime.fromisoformat() + normalize_timestamp() | Already exists in codebase |
| UUID generation | Custom IDs | uuid4() | Collision probability, already standardized |
| Pydantic validation | Manual checks | Field validators | Already using Pydantic, leverage it |
| Time comparison | Manual subtraction | timedelta | Edge cases with timezone, DST |

**Key insight:** The existing codebase already has robust models with Pydantic validation. Build on this foundation rather than creating parallel validation logic.

## Common Pitfalls

### Pitfall 1: Over-Engineering the Rules Engine
**What goes wrong:** Teams often reach for complex rules engine libraries (Drools-like, CEP engines) when simple pattern matching suffices
**Why it happens:** Assumption that "rules engine" = external library
**How to avoid:** Start with dictionary dispatch + dataclasses. Only add complexity if you hit limitations.
**Warning signs:** Evaluating libraries that support "complex event processing," "forward chaining," or "working memory"

### Pitfall 2: Forgetting Unknown Event Types
**What goes wrong:** New UniFi firmware introduces new event types, causing KeyError or unhandled exceptions
**Why it happens:** Only testing with known event types
**How to avoid:** Always have a default handler that logs unknown types gracefully. User decision: put in "Uncategorized" bucket.
**Warning signs:** No tests for unknown event types, no default case in dispatch

### Pitfall 3: Time Zone Confusion in Deduplication
**What goes wrong:** Events 1 hour apart in UTC might look like same incident if timestamps are compared in different zones
**Why it happens:** Mixing timezone-aware and naive datetimes
**How to avoid:** LogEntry already normalizes to UTC. Keep all internal comparisons in UTC.
**Warning signs:** datetime objects without tzinfo, mixing local and UTC times

### Pitfall 4: Template Variable Mismatch
**What goes wrong:** Template expects {ip} but log entry only has {device_mac}
**Why it happens:** Not validating template variables against available data
**How to avoid:** Use defaultdict or .get() with fallbacks in template rendering
**Warning signs:** KeyError in production, templates with many variables

### Pitfall 5: Memory Growth in FindingStore
**What goes wrong:** Long-running analysis accumulates findings without cleanup
**Why it happens:** Not implementing TTL or size limits
**How to avoid:** Either process in batches or implement periodic cleanup of old dedup_index entries
**Warning signs:** Memory usage grows linearly with uptime

## Code Examples

Verified patterns from official sources:

### Plain English Explanation Template
```python
# Based on user decisions from CONTEXT.md
EXPLANATION_TEMPLATES = {
    "EVT_AD_Login": {
        "title": "[Security] Admin login from {ip}",
        "description": (
            "An administrator logged into your UniFi controller from {ip} "
            "(EVT_AD_Login). This is normal if you or a known admin initiated it. "
            "Check if you recognize this activity."
        ),
        "severity": Severity.LOW,  # Informational - normal operations
    },
    "EVT_AD_LOGIN_FAILED": {
        "title": "[Security] Failed login attempt from {ip}",
        "description": (
            "Someone attempted to log into your UniFi controller from {ip} but "
            "failed authentication (EVT_AD_LOGIN_FAILED). This could indicate "
            "someone trying to guess your password."
        ),
        "severity": Severity.SEVERE,  # Security threat requiring action
        "remediation": (
            "1. Check if you recognize the IP address {ip}\n"
            "2. If unfamiliar, consider blocking it in your firewall\n"
            "3. Ensure your admin password is strong and unique\n"
            "4. Enable two-factor authentication if available"
        ),
    },
    "EVT_AP_Lost_Contact": {
        "title": "[Connectivity] Lost contact with {device_name}",
        "description": (
            "Your access point {device_name} ({device_mac}) stopped responding "
            "to the controller (EVT_AP_Lost_Contact). Devices connected to this "
            "AP may have lost WiFi connectivity."
        ),
        "severity": Severity.SEVERE,  # Requires admin action
        "remediation": (
            "1. Check if the access point has power (LED should be lit)\n"
            "2. Verify the ethernet cable is connected at both ends\n"
            "3. Try power cycling the AP by unplugging for 10 seconds\n"
            "4. Check your switch port for errors or PoE budget issues"
        ),
    },
}
```

### Occurrence Display Format
```python
# Per user decision: "Occurred 5 times (first: 2:00 PM, last: 4:30 PM)"
def format_occurrence_summary(finding: Finding, timezone: str = "UTC") -> str:
    """Format occurrence count and time range for display."""
    if finding.occurrence_count == 1:
        return f"Occurred at {finding.first_seen.strftime('%I:%M %p')}"

    return (
        f"Occurred {finding.occurrence_count} times "
        f"(first: {finding.first_seen.strftime('%I:%M %p')}, "
        f"last: {finding.last_seen.strftime('%I:%M %p')})"
    )
```

### Recurring Issue Detection
```python
# Claude's discretion: threshold for "recurring" flag
RECURRING_THRESHOLD = 5  # Configurable

def is_recurring(finding: Finding) -> bool:
    """Determine if finding should be flagged as recurring."""
    return finding.occurrence_count >= RECURRING_THRESHOLD

def get_recurring_label(finding: Finding) -> str:
    """Get display label for recurring issues."""
    if is_recurring(finding):
        return " [Recurring Issue]"
    return ""
```

## UniFi Event Types Reference

Mapping of common UniFi event types to categories and severities based on user decisions:

### Security Events (SEVERE unless noted)
| Event Type | Category | Severity | Notes |
|------------|----------|----------|-------|
| EVT_AD_LOGIN_FAILED | SECURITY | SEVERE | Failed admin login |
| EVT_AP_DetectRogueAP | SECURITY | SEVERE | Unauthorized AP detected |
| EVT_IPS_* | SECURITY | SEVERE | Intrusion detection alerts |

### Connectivity Events
| Event Type | Category | Severity | Notes |
|------------|----------|----------|-------|
| EVT_AP_Lost_Contact | CONNECTIVITY | SEVERE | AP offline |
| EVT_SW_Lost_Contact | CONNECTIVITY | SEVERE | Switch offline |
| EVT_WU_Disconnected | CONNECTIVITY | LOW | Client disconnect (normal) |
| EVT_WU_Connected | CONNECTIVITY | LOW | Client connect (normal) |
| EVT_AP_Isolated | CONNECTIVITY | SEVERE | AP isolated from network |

### Performance Events
| Event Type | Category | Severity | Notes |
|------------|----------|----------|-------|
| EVT_AP_PossibleInterference | PERFORMANCE | MEDIUM | Wireless interference |
| High CPU (threshold alert) | PERFORMANCE | MEDIUM | CPU > 90% |
| High Memory (threshold alert) | PERFORMANCE | MEDIUM | Memory > 90% |

### System Events
| Event Type | Category | Severity | Notes |
|------------|----------|----------|-------|
| EVT_AP_Upgraded | SYSTEM | LOW | Firmware updated successfully |
| EVT_AP_Restarted | SYSTEM | LOW | Admin-initiated restart |
| EVT_AP_RestartedUnknown | SYSTEM | MEDIUM | Unexpected restart |
| EVT_AP_Adopted | SYSTEM | LOW | New device adopted |
| EVT_AD_Login | SYSTEM | LOW | Successful admin login |

**Source:** [dim13/unifi event.go](https://github.com/dim13/unifi/blob/master/event.go), [oznu/unifi-events](https://github.com/oznu/unifi-events)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| If/elif chains | Dictionary dispatch + match/case | Python 3.10 (2021) | Cleaner code, easier to extend |
| External DSL rules | Native Python rules | N/A | Simpler debugging, no learning curve |
| ML-based clustering | Simple time windows | N/A | Appropriate for known patterns |

**Deprecated/outdated:**
- Heavy rules engines (Drools, Clips): Overkill for log analysis with <100 rules
- Complex event processing (CEP): Designed for real-time streaming, not batch analysis

## Open Questions

Things that couldn't be fully resolved:

1. **Complete UniFi Event Type List**
   - What we know: Common event types documented in community projects (dim13/unifi, oznu/unifi-events)
   - What's unclear: Ubiquiti doesn't publish official documentation; eventStrings.json URL returns 404
   - Recommendation: Build initial rules for known types, add logging for unknown types to discover new patterns

2. **Exact Remediation Wording**
   - What we know: User wants step-by-step for SEVERE, high-level for MEDIUM
   - What's unclear: Exact technical depth users can handle
   - Recommendation: Start with clear, actionable steps; iterate based on feedback

3. **Time Zone Display**
   - What we know: User wants "controller's timezone" for display
   - What's unclear: How to determine controller's timezone from API
   - Recommendation: Store in UTC, make display timezone configurable

## Sources

### Primary (HIGH confidence)
- Existing codebase: `/Users/trekkie/projects/unifi_scanner/src/unifi_scanner/models/` - LogEntry, Finding, enums already defined
- PEP 636: https://peps.python.org/pep-0636/ - Pattern matching syntax
- Pydantic docs: https://docs.pydantic.dev/latest/concepts/models/ - Model validation patterns

### Secondary (MEDIUM confidence)
- Dictionary dispatch pattern: https://martinheinz.dev/blog/90 - Code examples verified
- UniFi event types: https://github.com/dim13/unifi/blob/master/event.go - Community-maintained Go implementation
- UniFi events Node.js: https://github.com/oznu/unifi-events - Event structure reference
- UniFi API best practices: https://github.com/uchkunrakhimow/unifi-best-practices - API endpoint reference

### Tertiary (LOW confidence)
- rule-engine library: https://pypi.org/project/rule-engine/ - Evaluated but not recommended
- UniFi official help: https://help.ui.com - Troubleshooting guides (403 errors on some pages)
- UniFi eventStrings.json: https://ui.com/manage/locales/en/eventStrings.json - Returns 404

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using existing Pydantic + stdlib, well-documented patterns
- Architecture: MEDIUM - Dictionary dispatch is established pattern, but our specific implementation is custom
- Pitfalls: MEDIUM - Based on general rules engine experience, some UniFi-specific gaps

**Research date:** 2026-01-24
**Valid until:** 30 days (stable patterns, UniFi API rarely changes)
