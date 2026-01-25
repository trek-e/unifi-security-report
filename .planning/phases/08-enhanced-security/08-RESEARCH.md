# Phase 8: Enhanced Security Analysis - Research

**Researched:** 2026-01-25
**Domain:** IDS/IPS Event Processing, Suricata Signature Parsing, Security Report Generation
**Confidence:** HIGH

## Summary

This phase extends the existing analysis engine to provide enhanced IDS/IPS alert processing. The project already collects IPS events via the `/stat/ips/event` API endpoint and has a working rule-based analysis system. The enhancement focuses on:

1. **Parsing Suricata signatures** to extract ET categories (e.g., "ET SCAN Nmap" -> "Reconnaissance")
2. **Distinguishing blocked vs detected threats** based on IPS action field
3. **Aggregating source IPs** with threshold-based highlighting (10+ events)
4. **Providing category-specific remediation** with severity-adjusted detail levels

The existing architecture (Rule, RuleRegistry, AnalysisEngine, FindingStore) supports this directly. UniFi uses Suricata with Emerging Threats rulesets, so signature parsing follows well-documented ET naming conventions.

**Primary recommendation:** Create a dedicated IPS analyzer module that processes IPS events separately from standard rules, with signature category extraction, IP aggregation, and enhanced report sections for threats.

## Standard Stack

### Core (Already in Project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.x | Data models for IPS events | Already used for Finding, LogEntry |
| structlog | latest | Structured logging | Already used project-wide |
| jinja2 | 3.x | Report templates | Already used for HTML/text reports |

### Supporting (New Dependencies)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ipaddress | stdlib | IP address parsing/validation | Built-in, no install needed |

### Optional (User Discretion - Geographic Info)
| Library | Version | Purpose | Tradeoff |
|---------|---------|---------|----------|
| geoip2 | 5.2.0 | IP geolocation | Requires MaxMind GeoLite2 database download (free); adds ~60MB database file |

**Note on Geographic Info:** The CONTEXT.md marks this as Claude's discretion. **Recommendation:** Skip geographic enrichment for Phase 8 MVP. Reasons:
1. UniFi API already provides `srcipCountry`, `dstipCountry` fields when available
2. GeoLite2 requires user to register and download database separately
3. Adds complexity without core value for home network users
4. Can be added as enhancement in future phase if requested

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom signature parser | Existing rule pattern matching | New parser needed for ET category extraction |
| Inline IP aggregation | Pandas groupby | Overkill for simple count+groupby; stdlib collections.Counter sufficient |

**No new installations required for core functionality.**

## Architecture Patterns

### Recommended Project Structure
```
src/unifi_scanner/analysis/
├── engine.py                    # Existing - add IPS processing method
├── rules/
│   ├── security.py              # Existing - keep basic IPS rule
│   └── ips_categories.py        # NEW: ET category mappings and parsers
├── templates/
│   ├── explanations.py          # Existing - add IPS explanations
│   └── ips_remediation.py       # NEW: Category-specific remediation templates
├── ips/                         # NEW: IPS-specific analysis
│   ├── __init__.py
│   ├── analyzer.py              # IPSAnalyzer class
│   ├── models.py                # IPSEvent, ThreatSummary, SourceIPSummary
│   └── signature_parser.py      # ET signature category extraction
├── formatter.py                 # Existing - extend for IPS sections
└── store.py                     # Existing - may need IPS-specific dedup
```

### Pattern 1: Dedicated IPS Analyzer
**What:** Separate IPS processing from generic rule-based analysis
**When to use:** IPS events have different data structure than standard events (different fields, action semantics)
**Why:** IPS events from `/stat/ips/event` have signature info, action, src/dest IPs which don't map cleanly to LogEntry.from_unifi_event()

```python
# Source: Project codebase analysis
class IPSAnalyzer:
    """Dedicated analyzer for IPS/IDS events.

    Processes raw IPS events from get_ips_events() API,
    extracting signature categories, aggregating source IPs,
    and generating threat summaries.
    """

    def __init__(self, event_threshold: int = 10):
        self.event_threshold = event_threshold
        self._events: List[IPSEvent] = []

    def process_events(self, raw_events: List[Dict]) -> ThreatAnalysisResult:
        """Process raw IPS events into structured analysis."""
        pass

    def aggregate_by_source_ip(self) -> List[SourceIPSummary]:
        """Group events by source IP, filter by threshold."""
        pass

    def separate_blocked_detected(self) -> Tuple[List[IPSEvent], List[IPSEvent]]:
        """Separate events into blocked and detected-only."""
        pass
```

### Pattern 2: Signature Category Extraction
**What:** Parse ET signature names to extract category
**When to use:** Every IPS event with signature field

```python
# Source: Emerging Threats category documentation
import re

# ET signature format: "ET <CATEGORY> <description>"
ET_SIGNATURE_PATTERN = re.compile(r"^ET\s+(\w+)\s+(.+)$", re.IGNORECASE)

# Category mapping to user-friendly names (per CONTEXT.md decisions)
ET_CATEGORY_FRIENDLY_NAMES = {
    "SCAN": "Reconnaissance",
    "MALWARE": "Malware Activity",
    "POLICY": "Policy Violation",
    "TROJAN": "Trojan Activity",       # Legacy, maps to Malware in Suricata 5+
    "EXPLOIT": "Exploit Attempt",
    "DOS": "Denial of Service",
    "ATTACK_RESPONSE": "Attack Response",
    "COINMINING": "Cryptocurrency Mining",
    "USER_AGENTS": "Suspicious User Agent",
    "DNS": "DNS Anomaly",
    "WEB_CLIENT": "Web Client Attack",
    "WEB_SERVER": "Web Server Attack",
    "BOTCC": "Botnet Command & Control",
    "COMPROMISED": "Compromised Host",
    "DROP": "Blocked by Reputation",
    "DSHIELD": "Known Attacker",
    "HUNTING": "Threat Hunting Match",
    "CURRENT_EVENTS": "Active Campaign",
    "PHISHING": "Phishing Attempt",
    "MOBILE_MALWARE": "Mobile Malware",
    "TOR": "TOR Network Traffic",
    "INFO": "Informational",
    "P2P": "Peer-to-Peer Traffic",
    "GAMES": "Gaming Traffic",
    "CHAT": "Chat Application",
    # Default fallback
    "UNKNOWN": "Security Event",
}

def parse_signature_category(signature: str) -> Tuple[str, str, str]:
    """Extract category from ET signature.

    Args:
        signature: Full signature string, e.g., "ET SCAN Nmap Scripting Engine"

    Returns:
        Tuple of (raw_category, friendly_name, description)
        e.g., ("SCAN", "Reconnaissance", "Nmap Scripting Engine")
    """
    match = ET_SIGNATURE_PATTERN.match(signature)
    if match:
        category = match.group(1).upper()
        description = match.group(2)
        friendly = ET_CATEGORY_FRIENDLY_NAMES.get(category, "Security Event")
        return (category, friendly, description)

    # Non-ET signature (Suricata built-in, etc.)
    return ("UNKNOWN", "Security Event", signature)
```

### Pattern 3: Action-Based Threat Classification
**What:** Distinguish blocked vs detected based on action field
**When to use:** Every IPS event

```python
# Source: UniFi API documentation and community research
IPS_ACTION_BLOCKED = {"blocked", "drop", "reject"}
IPS_ACTION_DETECTED = {"allowed", "alert", "pass"}

def is_threat_blocked(action: str) -> bool:
    """Determine if threat was blocked or just detected.

    UniFi IPS action field values:
    - "blocked"/"drop"/"reject" = IPS blocked the traffic
    - "allowed"/"alert"/"pass" = IDS detected only (detection mode)
    """
    return action.lower() in IPS_ACTION_BLOCKED
```

### Pattern 4: Threshold-Based IP Aggregation
**What:** Only highlight IPs with 10+ events (per CONTEXT.md)
**When to use:** Generating source IP summary section

```python
from collections import Counter, defaultdict
from typing import Dict, List, NamedTuple

class SourceIPSummary(NamedTuple):
    ip: str
    total_events: int
    category_breakdown: Dict[str, int]  # category -> count
    is_internal: bool
    sample_signatures: List[str]  # First 3 unique signatures

def aggregate_source_ips(
    events: List[IPSEvent],
    threshold: int = 10
) -> List[SourceIPSummary]:
    """Aggregate events by source IP, filter by threshold.

    Returns IPs with >= threshold events, sorted by count descending.
    Separates internal vs external based on RFC1918 ranges.
    """
    ip_events: Dict[str, List[IPSEvent]] = defaultdict(list)
    for event in events:
        ip_events[event.src_ip].append(event)

    summaries = []
    for ip, ip_event_list in ip_events.items():
        if len(ip_event_list) >= threshold:
            category_counts = Counter(e.category_friendly for e in ip_event_list)
            signatures = list(set(e.signature for e in ip_event_list[:10]))[:3]

            summaries.append(SourceIPSummary(
                ip=ip,
                total_events=len(ip_event_list),
                category_breakdown=dict(category_counts),
                is_internal=is_private_ip(ip),
                sample_signatures=signatures,
            ))

    return sorted(summaries, key=lambda s: s.total_events, reverse=True)
```

### Anti-Patterns to Avoid
- **Processing IPS events as standard LogEntry:** IPS events have different field structure (signature, action, src_ip/dest_ip) - use dedicated model
- **One finding per IPS event:** Would flood reports - aggregate by signature+source IP combination
- **Hardcoding severity from ET category:** UniFi provides severity field; use that, only enhance with category context
- **Ignoring IPS mode detection:** Must note when IPS is in detection-only mode (no blocked events)

## Don't Hand-Roll

Problems with existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IP address validation | Custom regex | `ipaddress` stdlib | Handles IPv4/IPv6, edge cases |
| Private IP detection | Manual range checks | `ipaddress.ip_address().is_private` | Handles all RFC1918, RFC4193 ranges |
| Signature parsing | Complex parser | Simple regex with fallback | ET format is consistent |
| Timezone handling | Manual offset math | `zoneinfo.ZoneInfo` | Already used in project |
| Deduplication | Custom logic | Extend existing `FindingStore` | Proven pattern, same time-window approach |

**Key insight:** The existing analysis infrastructure (Rule, AnalysisEngine, FindingStore, Formatter) provides solid patterns. Extend rather than replace.

## Common Pitfalls

### Pitfall 1: Treating All IPS Events as Equal Severity
**What goes wrong:** Showing all IPS alerts as "SEVERE" causes alert fatigue
**Why it happens:** IPS events look scary; temptation to treat all as critical
**How to avoid:** Use UniFi's severity field (`InnerAlertSeverity`) and adjust display:
- Severity 1 (High) -> SEVERE
- Severity 2 (Medium) -> MEDIUM
- Severity 3+ (Low/Info) -> LOW
**Warning signs:** Users ignoring all IPS alerts; every report shows same severity

### Pitfall 2: Not Handling Detection-Only Mode
**What goes wrong:** Report says "0 Threats Blocked" without explanation
**Why it happens:** IPS can run in detection-only (IDS) mode where nothing is blocked
**How to avoid:** Detect when all events have action=allowed and add note:
  "Note: IPS is in detection mode. Threats are logged but not blocked."
**Warning signs:** User confusion about why nothing is blocked

### Pitfall 3: Over-Aggregating Signature Types
**What goes wrong:** "47 security events detected" - meaningless without context
**Why it happens:** Aggregating all events into one finding
**How to avoid:** Group by signature category AND source IP, show breakdown:
  "Port scan from 192.168.1.50 (seen 47 times)"
**Warning signs:** Single-line IPS summary regardless of threat variety

### Pitfall 4: Missing Common False Positives
**What goes wrong:** User panics over benign alerts (streaming services, gaming)
**Why it happens:** Not documenting known false positive patterns
**How to avoid:** Add false positive notes to remediation for common categories:
- POLICY violations from streaming services (Netflix, YouTube)
- P2P alerts from legitimate game launchers (Steam, Epic)
- USER_AGENTS from mobile apps with non-standard agents
**Warning signs:** User questions about "attacks" from Google/Netflix IPs

### Pitfall 5: IPS Event Timestamp Format
**What goes wrong:** Timestamps display incorrectly or cause parsing errors
**Why it happens:** IPS events use `timestamp` field (int) vs standard events using `time` field
**How to avoid:** Handle both field names in LogEntry.from_unifi_event() or use dedicated IPSEvent model
**Warning signs:** "Unknown" timestamps in IPS findings

## Code Examples

### IPS Event Model
```python
# Source: UniFi API research (unifi-poller project)
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class IPSEvent(BaseModel):
    """Normalized IPS/IDS event from UniFi API."""

    id: str = Field(..., alias="_id")
    timestamp: datetime

    # Network details
    src_ip: str
    src_port: Optional[int] = None
    dest_ip: str
    dest_port: Optional[int] = None
    proto: str  # TCP, UDP, ICMP

    # Signature details
    signature: str = Field(..., alias="inner_alert_signature")
    signature_id: int = Field(..., alias="inner_alert_signature_id")
    category_raw: str = Field(..., alias="inner_alert_category")
    severity: int = Field(..., alias="inner_alert_severity")
    action: str = Field(..., alias="inner_alert_action")

    # Parsed fields (computed)
    category_friendly: str = ""
    is_blocked: bool = False

    @classmethod
    def from_api_event(cls, event: dict) -> "IPSEvent":
        """Factory from raw API response."""
        # Handle nested alert structure
        alert = event.get("inner_alert", event)

        instance = cls(
            _id=event.get("_id", ""),
            timestamp=event.get("timestamp", 0),
            src_ip=event.get("src_ip", ""),
            src_port=event.get("src_port"),
            dest_ip=event.get("dest_ip", ""),
            dest_port=event.get("dest_port"),
            proto=event.get("proto", ""),
            inner_alert_signature=alert.get("signature", ""),
            inner_alert_signature_id=alert.get("signature_id", 0),
            inner_alert_category=alert.get("category", ""),
            inner_alert_severity=alert.get("severity", 3),
            inner_alert_action=alert.get("action", "allowed"),
        )

        # Parse signature category
        _, friendly, _ = parse_signature_category(instance.signature)
        instance.category_friendly = friendly
        instance.is_blocked = instance.action.lower() in IPS_ACTION_BLOCKED

        return instance
```

### Remediation Template Example
```python
# Source: Project pattern from templates/remediation.py
IPS_REMEDIATION_TEMPLATES = {
    # Severe: Step-by-step remediation
    "SCAN": {
        "severe": (
            "1. Identify the source IP {src_ip} - check if it's internal or external\n"
            "2. If external, this may be routine internet scanning - monitor for follow-up attacks\n"
            "3. If internal, check the device for malware or unauthorized scanning tools\n"
            "4. Review firewall logs for other probes from this source\n"
            "5. Consider blocking persistent scanners at the firewall level"
        ),
        "medium": (
            "Port scans from {src_ip} were detected. This is often routine internet "
            "background noise, but verify the source isn't an internal compromised device."
        ),
    },
    "MALWARE": {
        "severe": (
            "1. IMMEDIATELY isolate the affected device ({src_ip}) from the network\n"
            "2. Run a full malware scan on the device using updated antivirus\n"
            "3. Check for data exfiltration - review outbound traffic logs\n"
            "4. Change passwords for any accounts accessed from this device\n"
            "5. If confirmed infected, consider reimaging the device\n"
            "6. Monitor other devices for similar signatures"
        ),
        "medium": (
            "Potential malware communication detected from {src_ip}. Run a malware "
            "scan on the device and verify it's not a false positive from legitimate software."
        ),
    },
    "POLICY": {
        "severe": (
            "1. Review what triggered the policy violation - signature: {signature}\n"
            "2. Determine if this is legitimate traffic that needs a policy exception\n"
            "3. If unauthorized, investigate the user/device for policy compliance\n"
            "4. Update network policies if the traffic should be permitted"
        ),
        "medium": (
            "Policy violation detected. This often indicates traffic that violates "
            "organizational policy (streaming, P2P, etc.). Verify if this is expected behavior."
        ),
        "false_positive_note": (
            "Note: POLICY violations from streaming services (Netflix, YouTube, etc.) "
            "are common false positives and typically don't require action."
        ),
    },
    # ... additional categories
}
```

### Report Section Template
```jinja2
{# Source: Project pattern from report.html #}
{% if ips_analysis %}
<!-- Threat Detection Summary -->
<div style="margin-top: 30px;">
    <h2 style="color: #333;">Security Threat Summary</h2>

    {% if ips_analysis.detection_mode_note %}
    <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 12px;">
        <p style="margin: 0; color: #856404;">
            {{ ips_analysis.detection_mode_note }}
        </p>
    </div>
    {% endif %}

    <!-- Threats Detected Section -->
    {% if ips_analysis.detected_threats %}
    <h3>Threats Detected</h3>
    {% for category, threats in ips_analysis.detected_threats_by_category.items() %}
    <div class="threat-category">
        <h4>{{ category }} ({{ threats|length }} events)</h4>
        {% for threat in threats[:5] %}
        <p>{{ threat.description }} (seen {{ threat.count }} times)</p>
        {% endfor %}
    </div>
    {% endfor %}
    {% endif %}

    <!-- Threats Blocked Section -->
    {% if ips_analysis.blocked_threats %}
    <h3>Threats Blocked</h3>
    <!-- Similar structure -->
    {% endif %}

    <!-- Top Threat Sources -->
    {% if ips_analysis.top_source_ips %}
    <h3>Top Threat Sources</h3>
    <h4>External Threats</h4>
    {% for ip_summary in ips_analysis.external_sources %}
    <p>{{ ip_summary.ip }}: {{ ip_summary.total_events }} events
       ({{ ip_summary.category_breakdown|join(', ') }})</p>
    {% endfor %}

    <h4>Internal Concerns</h4>
    {% for ip_summary in ips_analysis.internal_sources %}
    <p>{{ ip_summary.ip }}: {{ ip_summary.total_events }} events
       ({{ ip_summary.category_breakdown|join(', ') }})</p>
    {% endfor %}
    {% endif %}
</div>
{% endif %}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ET TROJAN category | ET MALWARE category | Suricata 5.0 (2020) | Map TROJAN->MALWARE for compatibility |
| Snort rule format only | Suricata native rules | Suricata 5+ | Both formats supported, prefer Suricata |
| GeoIP Legacy API | GeoIP2 API | MaxMind 2022 | Legacy deprecated, use geoip2 if needed |

**Deprecated/outdated:**
- `python-geoip` legacy library: Use `geoip2` instead
- ET category `TROJAN`: Now mapped to `MALWARE` in Suricata 5.0+
- Snort-only rule formats: Suricata uses own format, compatible with Snort

## Open Questions

1. **IPS Event Field Naming Consistency**
   - What we know: API returns nested `inner_alert` structure with signature details
   - What's unclear: Exact field names may vary between UniFi versions (10.x vs older)
   - Recommendation: Parse defensively with `.get()` and fallbacks; test with real data

2. **Severity Mapping from UniFi**
   - What we know: UniFi uses numeric severity (1=high, 2=medium, 3=low)
   - What's unclear: Exact boundary for "informational" vs "low"
   - Recommendation: Map 1->SEVERE, 2->MEDIUM, 3+->LOW initially; tune based on feedback

3. **IPS Detection Mode Detection**
   - What we know: Need to note when IPS is detection-only (all events have action=allowed)
   - What's unclear: Is there an API field that indicates IPS mode directly?
   - Recommendation: Infer from events (if 100% allowed actions, likely detection mode)

## Sources

### Primary (HIGH confidence)
- Project codebase: `/src/unifi_scanner/analysis/` - existing patterns
- Project codebase: `/src/unifi_scanner/api/client.py` - IPS API method
- [Emerging Threats Wiki - Rule Categories](https://community.emergingthreats.net/t/suricata-5-6-7-rule-categories/94) - Complete ET category list
- [unifi-poller GitHub Issue #68](https://github.com/unifi-poller/unifi-poller/issues/68) - IPS event JSON structure

### Secondary (MEDIUM confidence)
- [Ubiquiti Help Center - IDS/IPS](https://help.ui.com/hc/en-us/articles/360006893234-UniFi-Gateway-Intrusion-Prevention-and-Detections-IPS-IDS) - UniFi IPS documentation
- [Suricata Documentation - EVE JSON Format](https://docs.suricata.io/en/latest/output/eve/eve-json-format.html) - Alert field structure
- [geoip2 PyPI](https://pypi.org/project/geoip2/) - IP geolocation library (if geographic info added)

### Tertiary (LOW confidence)
- [Netgate Forum - Suricata False Positives](https://forum.netgate.com/topic/179096/suricata-ids-ips-false-positives) - Community experience with false positives
- [Stamus Networks - Suricata Myths](https://www.stamus-networks.com/blog/suricata-myths-alerts-and-nsm) - Best practices

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies required; uses existing project patterns
- Architecture: HIGH - Extends proven patterns from existing analysis engine
- ET Categories: HIGH - Official Emerging Threats documentation
- IPS Event Fields: MEDIUM - Based on third-party research (unifi-poller), needs validation with real data
- False Positives: MEDIUM - Community knowledge, may need tuning

**Research date:** 2026-01-25
**Valid until:** 90 days (Suricata/ET rulesets update frequently but categories stable)
