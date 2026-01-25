# Phase 12: Cybersecure Integration - Research

**Researched:** 2026-01-25
**Domain:** UniFi Cybersecure subscription detection, Proofpoint enhanced IPS signatures, badge attribution
**Confidence:** MEDIUM

## Summary

This phase implements Cybersecure integration so users with active subscriptions see enhanced threat intelligence badged in their reports. Research focused on three requirements: (1) detecting Cybersecure subscription status on the gateway, (2) identifying which IPS findings originate from enhanced Proofpoint signatures, and (3) displaying attribution badges in reports.

The key technical finding is that **Proofpoint ET PRO signatures use SID range 2800000-2899999**, which distinguishes them from free ET Open signatures (2000000-2099999). This allows badge attribution without requiring subscription detection at the API level - simply checking if an IPS event's `signature_id` falls within the ET PRO range indicates Cybersecure-powered detection. However, subscription status detection via API remains partially documented and may require validation on a real controller.

The integration follows Phase 10 infrastructure: implements the `Integration` Protocol, registers with `IntegrationRegistry`, and uses the existing `IntegrationRunner` with circuit breakers. Unlike Cloudflare (external API), Cybersecure enriches existing UniFi IPS data rather than collecting new data - it's a "decorator" integration that augments IPS findings with attribution metadata.

**Primary recommendation:** Detect Cybersecure signatures by checking if `signature_id` is in range 2800000-2899999 (ET PRO). Add `is_cybersecure` flag to `IPSEvent` and `ThreatSummary` models. Subscription detection via site settings API is secondary (validation needed). Badge display via template conditional.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Existing codebase | - | All required components exist | IPSEvent, IPSAnalyzer, UnifiClient already implemented |
| pydantic | 2.11+ | Model extension for Cybersecure metadata | Already used for IPSEvent |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.27+ | UniFi API calls (already in project) | Site settings query for subscription detection |
| structlog | 25.5+ | Structured logging (already in project) | Integration status logging |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SID range detection | Site settings API only | SID range is definitive for badge; API for overall subscription status |
| Separate Cybersecure collector | IPSAnalyzer enhancement | Cybersecure enriches existing IPS data, doesn't collect new data |

**Installation:**
```bash
# No new dependencies required - uses existing codebase
```

## Architecture Patterns

### Recommended Project Structure
```
src/unifi_scanner/
├── integrations/
│   ├── cybersecure/           # Cybersecure integration module
│   │   ├── __init__.py        # Public exports, register with registry
│   │   ├── integration.py     # CybersecureIntegration class (Protocol impl)
│   │   ├── detector.py        # Subscription detection logic
│   │   └── signature.py       # ET PRO signature range detection
├── analysis/
│   └── ips/
│       ├── models.py          # Extend IPSEvent with is_cybersecure flag
│       └── analyzer.py        # Extend ThreatSummary with cybersecure metadata
```

### Pattern 1: SID Range Detection for Cybersecure Attribution
**What:** Detect Proofpoint-powered signatures by checking signature ID range
**When to use:** Attributing individual IPS findings to Cybersecure subscription
**Example:**
```python
# Source: Emerging Threats SID Allocation (doc.emergingthreats.net/bin/view/Main/SidAllocation)
# ET OPEN: 2000000-2099999
# ET PRO: 2800000-2899999

def is_cybersecure_signature(signature_id: int) -> bool:
    """Check if signature is from Cybersecure (Proofpoint ET PRO ruleset).

    ET PRO signatures use SID range 2800000-2899999.
    This is the definitive way to identify Proofpoint-powered detections.

    Args:
        signature_id: The signature ID from the IPS event

    Returns:
        True if signature is from ET PRO (Cybersecure subscription)
    """
    return 2800000 <= signature_id <= 2899999


def get_signature_source(signature_id: int) -> str:
    """Get the source label for a signature ID.

    Args:
        signature_id: The signature ID from the IPS event

    Returns:
        "cybersecure" for ET PRO, "standard" for ET Open, "custom" otherwise
    """
    if 2800000 <= signature_id <= 2899999:
        return "cybersecure"  # Proofpoint ET PRO
    elif 2000000 <= signature_id <= 2099999:
        return "standard"  # ET Open (free)
    else:
        return "custom"  # User-defined or other source
```

### Pattern 2: IPSEvent Model Extension
**What:** Add Cybersecure attribution metadata to IPS event model
**When to use:** Processing IPS events from UniFi API
**Example:**
```python
# Source: Existing IPSEvent pattern in analysis/ips/models.py
from pydantic import BaseModel, Field, computed_field
from typing import Optional

class IPSEvent(BaseModel):
    """Normalized IPS/IDS event with Cybersecure attribution."""

    # ... existing fields ...
    signature_id: int = Field(..., description="Numeric signature ID")

    # Cybersecure attribution (computed from signature_id)
    @computed_field
    @property
    def is_cybersecure(self) -> bool:
        """Whether this detection is powered by Cybersecure subscription."""
        return 2800000 <= self.signature_id <= 2899999

    @computed_field
    @property
    def signature_source(self) -> str:
        """Source of the signature: 'cybersecure', 'standard', or 'custom'."""
        if self.is_cybersecure:
            return "cybersecure"
        elif 2000000 <= self.signature_id <= 2099999:
            return "standard"
        return "custom"
```

### Pattern 3: ThreatSummary Enhancement
**What:** Propagate Cybersecure attribution to threat analysis results
**When to use:** Building threat summaries for report
**Example:**
```python
# Source: Existing ThreatSummary pattern in analysis/ips/analyzer.py
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ThreatSummary:
    """Summary of a threat type with Cybersecure attribution."""

    category_friendly: str
    description: str
    count: int
    severity: Severity
    sample_signature: str
    source_ips: List[str] = field(default_factory=list)
    remediation: Optional[str] = None

    # Cybersecure attribution
    is_cybersecure: bool = False  # True if ANY event in this summary is Cybersecure
    cybersecure_count: int = 0    # How many events are Cybersecure-detected
```

### Pattern 4: Subscription Detection via Site Settings (LOW confidence)
**What:** Detect Cybersecure subscription status from site settings API
**When to use:** Displaying subscription status in report header
**Example:**
```python
# Source: UniFi API community documentation (ubntwiki.com)
# WARNING: API structure is partially documented, needs validation

async def detect_cybersecure_subscription(
    client: "UnifiClient",
    site: str,
) -> dict:
    """Detect Cybersecure subscription status from site settings.

    Queries the site settings API and looks for Cybersecure-related fields.

    Note: This API structure is not fully documented. Field names may
    vary by UniFi Network version. Validated behavior is needed.

    Args:
        client: Authenticated UniFi client
        site: Site name to check

    Returns:
        Dict with subscription info:
        {
            "detected": bool,  # Whether detection succeeded
            "active": bool,    # Whether Cybersecure is active
            "tier": str,       # "standard", "enterprise", or "none"
            "signature_count": int,  # Number of signatures loaded
        }
    """
    # Endpoint: /api/s/{site}/rest/setting
    # Look for IPS-related settings that indicate Cybersecure status

    # Potential field names (need validation):
    # - ips_cybersecure_enabled
    # - cybersecure_subscription_active
    # - ips_ruleset_type: "proofpoint" vs "standard"

    settings = await client.get_site_settings(site)

    # Strategy 1: Look for explicit Cybersecure flag
    cybersecure_enabled = settings.get("ips_cybersecure_enabled", False)

    # Strategy 2: Look for ruleset type
    ruleset_type = settings.get("ips_ruleset_type", "standard")

    # Strategy 3: Check signature count (55k+ indicates Cybersecure)
    # CyberSecure: 55,000+ signatures
    # CyberSecure Enterprise: 95,000+ signatures
    # Standard: ~35,000 signatures
    signature_count = settings.get("ips_signature_count", 0)

    if signature_count >= 90000:
        tier = "enterprise"
    elif signature_count >= 50000:
        tier = "standard"
    else:
        tier = "none"

    return {
        "detected": True,
        "active": cybersecure_enabled or ruleset_type == "proofpoint" or tier != "none",
        "tier": tier,
        "signature_count": signature_count,
    }
```

### Pattern 5: Integration Protocol Implementation
**What:** Implement Integration Protocol for registry compatibility
**When to use:** Integrating with Phase 10 infrastructure
**Example:**
```python
# Source: Phase 10 Integration Protocol pattern
from typing import Optional
from unifi_scanner.integrations.base import Integration, IntegrationResult
from unifi_scanner.integrations.registry import IntegrationRegistry

class CybersecureIntegration:
    """Cybersecure integration for enhanced threat attribution.

    Unlike other integrations (Cloudflare), Cybersecure doesn't collect
    new data - it enriches existing IPS analysis with attribution metadata.

    This integration:
    1. Detects Cybersecure subscription status (optional, LOW confidence)
    2. Provides signature detection utilities for IPSAnalyzer
    3. Returns metadata for report badge display
    """

    def __init__(self, settings) -> None:
        self._settings = settings
        self._client = None  # Set during fetch

    @property
    def name(self) -> str:
        return "cybersecure"

    def is_configured(self) -> bool:
        """Cybersecure uses UniFi credentials, always configured if UniFi is.

        No additional credentials needed - Cybersecure is a UniFi feature.
        """
        return bool(getattr(self._settings, 'host', None))

    def validate_config(self) -> Optional[str]:
        """No additional validation needed."""
        return None

    async def fetch(self) -> IntegrationResult:
        """Detect Cybersecure status and return metadata.

        This doesn't fetch IPS events (that's done by UnifiClient.get_ips_events).
        It returns subscription metadata for report display.
        """
        try:
            # Detect subscription status
            status = await self._detect_subscription()

            return IntegrationResult(
                name=self.name,
                success=True,
                data={
                    "subscription_active": status.get("active", False),
                    "tier": status.get("tier", "none"),
                    "signature_count": status.get("signature_count", 0),
                },
            )
        except Exception as e:
            return IntegrationResult(
                name=self.name,
                success=False,
                error=str(e),
            )

# Register at module import time
IntegrationRegistry.register(CybersecureIntegration)
```

### Pattern 6: Report Template Badge Display
**What:** Display Cybersecure badge on enhanced findings
**When to use:** Rendering IPS findings in HTML/text reports
**Example:**
```html
{# Source: Existing report template patterns #}
{% for threat in blocked_threats %}
<div class="threat-item severity-{{ threat.severity.value|lower }}">
    <h4>
        {{ threat.category_friendly }}
        {% if threat.is_cybersecure %}
        <span class="badge badge-cybersecure" title="Detected by CyberSecure enhanced signatures">
            CyberSecure
        </span>
        {% endif %}
    </h4>
    <p>{{ threat.description }}</p>
    <p class="stats">
        {{ threat.count }} events
        {% if threat.cybersecure_count > 0 %}
        ({{ threat.cybersecure_count }} via CyberSecure)
        {% endif %}
    </p>
</div>
{% endfor %}
```

### Anti-Patterns to Avoid
- **Separate Cybersecure collector:** Cybersecure enriches IPS data, doesn't replace it
- **Requiring subscription for badge:** Badge based on signature SID, not API detection
- **Blocking on subscription detection:** Use SID range as primary, API as secondary
- **Hardcoding signature count thresholds:** May change with updates

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IPS event collection | Separate Cybersecure collector | Existing UnifiClient.get_ips_events | Same API endpoint |
| Signature parsing | Custom parser for Cybersecure | Existing signature_parser.py | Already handles categories |
| Threat aggregation | Cybersecure-specific analyzer | Existing IPSAnalyzer with extension | Same analysis logic |
| Integration registry | Custom registration | Phase 10 IntegrationRegistry | Standard pattern |

**Key insight:** Cybersecure is an enrichment, not a separate data source. The integration adds metadata to existing IPS analysis rather than collecting new data. This is fundamentally different from Cloudflare integration which queries external APIs.

## Common Pitfalls

### Pitfall 1: Assuming API Documents Subscription Status
**What goes wrong:** Site settings API may not expose Cybersecure subscription status
**Why it happens:** API is partially documented, subscription managed via cloud portal
**How to avoid:** Use SID range detection as primary method (definitive); API detection as secondary (optional)
**Warning signs:** Missing fields in site settings response, inconsistent behavior

### Pitfall 2: Wrong SID Range Detection
**What goes wrong:** Badge applied to wrong signatures or missed on correct ones
**Why it happens:** Hardcoded wrong range, off-by-one errors
**How to avoid:** Use exact range 2800000-2899999 (inclusive), validate with real events
**Warning signs:** Badges on events that shouldn't have them, missing badges

### Pitfall 3: Blocking Report on Subscription Detection Failure
**What goes wrong:** Report fails or shows error when API detection fails
**Why it happens:** Treating subscription detection as required
**How to avoid:** SID-based badges work without subscription detection; API is informational only
**Warning signs:** Reports failing for users with Cybersecure active

### Pitfall 4: Duplicate Badge Counting
**What goes wrong:** Same event counted multiple times for Cybersecure attribution
**Why it happens:** Checking at multiple levels (event, summary, report)
**How to avoid:** Single source of truth: is_cybersecure on IPSEvent, propagate to summary
**Warning signs:** cybersecure_count > total count

### Pitfall 5: Missing Badge on Aggregated Threats
**What goes wrong:** ThreatSummary doesn't show badge even though events are Cybersecure
**Why it happens:** Badge flag not propagated from events to summary
**How to avoid:** Set is_cybersecure=True if ANY event in summary has Cybersecure signature
**Warning signs:** Individual events show badge, summary doesn't

### Pitfall 6: Incompatible UniFi Version
**What goes wrong:** Cybersecure features unavailable on older UniFi versions
**Why it happens:** Cybersecure requires UniFi Network 9.3+ and firmware 4.1.3+
**How to avoid:** Document requirements clearly; degrade gracefully (show standard badges)
**Warning signs:** No ET PRO signatures despite subscription

## Code Examples

Verified patterns from official sources and existing codebase:

### SID Range Constants
```python
# Source: Emerging Threats SID Allocation (doc.emergingthreats.net)
# Verified via Proofpoint documentation

# Emerging Threats Open Rulesets (free)
ET_OPEN_SID_MIN = 2000000
ET_OPEN_SID_MAX = 2099999

# Emerging Threats Pro Full Coverage (Cybersecure/Proofpoint)
ET_PRO_SID_MIN = 2800000
ET_PRO_SID_MAX = 2899999

# Additional ranges for reference
ET_FORKED_SNORT_MIN = 2100000  # Forked Snort GPL signatures
ET_FORKED_SNORT_MAX = 2103999
```

### Complete IPSEvent Extension
```python
# Source: Existing models.py pattern + Cybersecure attribution
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field

# SID range constants
ET_PRO_SID_MIN = 2800000
ET_PRO_SID_MAX = 2899999

class IPSEvent(BaseModel):
    """Normalized IPS/IDS event from UniFi API with Cybersecure attribution."""

    model_config = ConfigDict(from_attributes=True)

    # Core identifiers
    id: str = Field(..., description="Unique identifier from UniFi API")
    timestamp: datetime = Field(..., description="When the event occurred")

    # Network details
    src_ip: str = Field(..., description="Source IP address")
    src_port: Optional[int] = Field(default=None)
    dest_ip: str = Field(..., description="Destination IP address")
    dest_port: Optional[int] = Field(default=None)
    proto: str = Field(..., description="Protocol (TCP, UDP, ICMP)")

    # Signature details
    signature: str = Field(..., description="Full signature string")
    signature_id: int = Field(..., description="Numeric signature ID")
    category_raw: str = Field(..., description="Raw category from API")
    severity: int = Field(..., description="Severity level (1=high, 3=low)")
    action: str = Field(..., description="Action taken (blocked, allowed)")

    # Computed fields
    category_friendly: str = Field(default="")
    is_blocked: bool = Field(default=False)

    @computed_field
    @property
    def is_cybersecure(self) -> bool:
        """True if detected by Cybersecure (Proofpoint ET PRO) signature."""
        return ET_PRO_SID_MIN <= self.signature_id <= ET_PRO_SID_MAX

    @computed_field
    @property
    def signature_source(self) -> str:
        """Source of the signature ruleset."""
        if self.is_cybersecure:
            return "cybersecure"
        return "standard"
```

### ThreatSummary with Cybersecure Metadata
```python
# Source: Existing analyzer.py pattern + Cybersecure attribution
from dataclasses import dataclass, field
from typing import List, Optional
from unifi_scanner.models.enums import Severity

@dataclass
class ThreatSummary:
    """Summary of a threat type with Cybersecure attribution."""

    category_friendly: str
    description: str
    count: int
    severity: Severity
    sample_signature: str
    source_ips: List[str] = field(default_factory=list)
    remediation: Optional[str] = None

    # Cybersecure attribution
    is_cybersecure: bool = False
    """True if ANY event in this summary was detected by Cybersecure."""

    cybersecure_count: int = 0
    """Number of events detected by Cybersecure signatures."""

    @property
    def cybersecure_percentage(self) -> float:
        """Percentage of events detected by Cybersecure."""
        if self.count == 0:
            return 0.0
        return (self.cybersecure_count / self.count) * 100
```

### IPSAnalyzer Enhancement
```python
# Source: Existing analyzer.py + Cybersecure propagation
def _create_threat_summaries(self, events: List[IPSEvent]) -> List[ThreatSummary]:
    """Create deduplicated threat summaries with Cybersecure attribution."""

    # ... existing grouping logic ...

    for signature, data in signature_data.items():
        event_list = data["events"]

        # Count Cybersecure detections
        cybersecure_events = [e for e in event_list if e.is_cybersecure]
        cybersecure_count = len(cybersecure_events)

        summary = ThreatSummary(
            category_friendly=friendly_name,
            description=description,
            count=len(event_list),
            severity=max_severity,
            sample_signature=signature,
            source_ips=list(data["source_ips"]),
            remediation=remediation_text,
            # Cybersecure attribution
            is_cybersecure=cybersecure_count > 0,
            cybersecure_count=cybersecure_count,
        )
        summaries.append(summary)

    return summaries
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ET Open only | ET PRO via Cybersecure | UniFi 9.0 (2024) | 55k+ signatures vs 35k |
| Single IPS ruleset | Tiered subscriptions | UniFi 9.0 (2024) | Standard vs Enterprise tiers |
| Unknown signature source | SID range identification | Always available | Badge attribution possible |
| Manual subscription check | API-based detection | UniFi 9.3+ (needs validation) | Automated status display |

**Deprecated/outdated:**
- **Direct Suricata config editing**: Managed via UniFi UI/subscription now
- **Manual rule downloads**: Cybersecure handles updates automatically

## Open Questions

Things that couldn't be fully resolved:

1. **Site Settings API Field Names**
   - What we know: /api/s/{site}/rest/setting endpoint exists
   - What's unclear: Exact field names for Cybersecure subscription status
   - Recommendation: Use SID range as primary; API detection as bonus feature, needs validation on real controller

2. **Signature Count Thresholds**
   - What we know: CyberSecure ~55k, Enterprise ~95k, Standard ~35k
   - What's unclear: Whether these counts are stable or updated frequently
   - Recommendation: Use ranges (50k-89k = Standard, 90k+ = Enterprise) not exact values

3. **Memory Optimized Mode Impact**
   - What we know: Cybersecure has "Memory Optimized Mode" for smaller gateways
   - What's unclear: Whether this reduces signature count below detection threshold
   - Recommendation: Document this case, may show as Cybersecure active but lower count

4. **Content Filtering Events**
   - What we know: Cybersecure includes Cloudflare-powered content filtering
   - What's unclear: Whether these events surface in standard IPS API or need syslog
   - Recommendation: Defer content filtering to future phase; focus on IPS badges for now

## Sources

### Primary (HIGH confidence)
- [Emerging Threats SID Allocation](https://doc.emergingthreats.net/bin/view/Main/SidAllocation) - Definitive SID range documentation
- [Proofpoint ET Pro Ruleset](https://www.proofpoint.com/us/threat-insight/et-pro-ruleset) - ET PRO feature description
- [UniFi CyberSecure Overview](https://help.ui.com/hc/en-us/articles/30426718447639-UniFi-CyberSecure) - Subscription tiers and requirements
- Existing codebase - IPSEvent, IPSAnalyzer, Integration Protocol patterns

### Secondary (MEDIUM confidence)
- [UniFi CyberSecure by Proofpoint](https://help.ui.com/hc/en-us/articles/25930305913751-UniFi-CyberSecure-Enhanced-by-Proofpoint-and-Cloudflare) - Enhanced IPS features
- [UniFi IDS/IPS Documentation](https://help.ui.com/hc/en-us/articles/360006893234-UniFi-Gateway-Intrusion-Detection-and-Prevention-IDS-IPS) - IPS configuration
- [UniFi Network 9.3 Release](https://blog.ui.com/article/introducing-network-9-3) - Content filtering requirements
- [UniFi Community Wiki API](https://ubntwiki.com/products/software/unifi-controller/api) - Site settings endpoints

### Tertiary (LOW confidence)
- Site settings API field names - Needs validation on real controller
- Subscription detection via API - Partially documented, implementation details unclear

## Metadata

**Confidence breakdown:**
- SID range detection: HIGH - Definitively documented by Emerging Threats
- Model extensions: HIGH - Follows existing codebase patterns
- API subscription detection: LOW - Needs validation on real controller
- Report badges: MEDIUM - Implementation straightforward, UX needs validation

**Research date:** 2026-01-25
**Valid until:** 2026-02-10 (15 days - Cybersecure API poorly documented, may need iteration)
