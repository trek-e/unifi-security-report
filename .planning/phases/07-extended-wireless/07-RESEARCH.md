# Phase 7: Extended Wireless Analysis - Research

**Researched:** 2026-01-24
**Domain:** UniFi wireless event analysis (roaming, channel changes, DFS, signal quality)
**Confidence:** HIGH

## Summary

This research documents the exact UniFi event types, payload structures, and implementation patterns needed for extended wireless analysis rules. The phase adds 6 new wireless rules covering client roaming (WIFI-01), band switching (WIFI-02), channel changes (WIFI-03), DFS radar detection (WIFI-04), RSSI-to-quality translation (WIFI-05), and excessive roaming detection (WIFI-06).

The implementation follows the existing rules engine pattern established in phases 1-3. All wireless events use the standard `EVT_*` format and are available through the existing `stat/event` API endpoint. No new API calls or dependencies are required. The primary work is creating a new `wireless_rules.py` file with rules that match on event types and extract data from event payloads.

**Key finding:** UniFi wireless events contain rich payload data including `ap_from`/`ap_to`, `channel_from`/`channel_to`, and `radio_from`/`radio_to` fields. This enables detailed roaming analysis without additional API calls.

**Primary recommendation:** Create a new WIRELESS category in enums.py and wireless_rules.py with 6 rules. Use the existing Rule class with pattern matching for DFS radar detection (message-based) and aggregation logic for flapping detection.

## Standard Stack

No new dependencies required. All wireless analysis uses existing infrastructure.

### Core (Existing)
| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| Rule class | `analysis/rules/base.py` | Rule definition with event_types, pattern matching | EXISTS |
| RuleRegistry | `analysis/rules/base.py` | O(1) event type lookup | EXISTS |
| Category enum | `models/enums.py` | Finding categories | EXTEND (add WIRELESS) |
| LogEntry | `models/log_entry.py` | Event data with raw_data access | EXISTS |
| AnalysisEngine | `analysis/engine.py` | Processes entries through rules | EXISTS |

### New Files to Create
| File | Purpose |
|------|---------|
| `analysis/rules/wireless.py` | WIRELESS_RULES list with 6 rules |

### Installation
No additional packages required.

## Architecture Patterns

### Recommended Project Structure
```
src/unifi_scanner/analysis/rules/
    __init__.py          # Add WIRELESS_RULES import
    base.py              # Existing Rule, RuleRegistry
    connectivity.py      # Existing
    performance.py       # Existing
    security.py          # Existing
    system.py            # Existing
    wireless.py          # NEW: WIRELESS_RULES list
```

### Pattern 1: Simple Event Type Matching
**What:** Rule matches on event_type(s), extracts data from raw_data
**When to use:** Roaming events (EVT_WU_Roam), channel changes (EVT_WU_RoamRadio)
**Example:**
```python
# Source: Existing codebase pattern (connectivity.py)
Rule(
    name="client_roaming",
    event_types=["EVT_WU_Roam", "EVT_WG_Roam"],
    category=Category.WIRELESS,
    severity=Severity.LOW,
    title_template="[Wireless] Client roamed from {ap_from_name} to {ap_to_name}",
    description_template=(
        "Client {client_name} roamed from access point {ap_from_name} "
        "to {ap_to_name} (EVT_WU_Roam). This is normal mobility behavior as "
        "you move around your space."
    ),
    remediation_template=None,  # LOW severity
)
```

### Pattern 2: Message Pattern Matching for DFS
**What:** Rule matches event_type AND message pattern (regex)
**When to use:** DFS radar detection where event type is generic but message is specific
**Example:**
```python
# Source: Existing codebase pattern (base.py supports pattern field)
Rule(
    name="dfs_radar_detected",
    event_types=["EVT_AP_Interference", "EVT_AP_RADAR_DETECTED", "EVT_AP_ChannelChange"],
    category=Category.WIRELESS,
    severity=Severity.MEDIUM,
    title_template="[Wireless] DFS radar detected on {device_name}",
    description_template=(
        "Access point {device_name} detected radar interference on channel {channel} "
        "(DFS: Radar detected). Per FCC regulations, the AP must vacate this channel "
        "for 30 minutes. Clients may experience a brief disconnection."
    ),
    remediation_template=(
        "1. This is automated regulatory compliance - no immediate action needed\\n"
        "2. The AP will automatically select a new channel\\n"
        "3. If this happens frequently, consider using non-DFS channels (36-48)\\n"
        "4. Check for actual radar sources nearby (airports, weather stations)\\n"
        "5. Enable WiFi AI to automatically avoid problematic DFS channels"
    ),
    pattern=r"[Rr]adar\s+(detected|detected on)",  # Match "Radar detected" variations
)
```

### Pattern 3: Aggregation for Flapping Detection (WIFI-06)
**What:** Count roaming events per client within time window
**When to use:** Detecting excessive roaming (flapping)
**Implementation approach:** Post-processing in AnalysisEngine or dedicated FlappingDetector

**Note:** The current Rule class handles individual events. Flapping detection requires counting events over time. Options:
1. **Recommended:** Add aggregation logic in AnalysisEngine.analyze() after individual rule processing
2. **Alternative:** Create FlappingRule subclass with count/window parameters
3. **Simple:** Post-process findings to detect patterns (multiple roam findings for same client)

```python
# Aggregation approach (in analysis engine or post-processor)
def detect_flapping(entries: List[LogEntry], window_minutes: int = 60, threshold: int = 5):
    """Detect clients with excessive roaming within time window."""
    roam_events = [e for e in entries if e.event_type in ["EVT_WU_Roam", "EVT_WG_Roam"]]

    # Group by client MAC
    by_client = defaultdict(list)
    for event in roam_events:
        client_mac = event.raw_data.get("user")  # user field contains client MAC
        by_client[client_mac].append(event)

    # Find clients exceeding threshold
    flapping_clients = []
    for client_mac, events in by_client.items():
        if len(events) >= threshold:
            flapping_clients.append({
                "client": client_mac,
                "roam_count": len(events),
                "events": events,
            })

    return flapping_clients
```

### Anti-Patterns to Avoid
- **Duplicating existing rules:** EVT_AP_Interference already has a rule in performance.py - the DFS rule should use pattern matching to differentiate radar-specific events
- **Creating WIRELESS category overlap:** Channel utilization (EVT_AP_CHANNEL_UTIL_HIGH) stays in PERFORMANCE - only roaming/band events go in WIRELESS
- **Hardcoding AP names:** Always use template variables ({ap_from_name}, {device_name}) for dynamic formatting

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RSSI thresholds | Custom threshold logic | Standard thresholds table | Industry-standard values, well-documented |
| MAC normalization | Custom MAC parser | Existing LogEntry validator | Already handles colons, dashes, case |
| Timestamp parsing | Custom date parser | Existing normalize_timestamp | Handles UniFi milliseconds format |
| Event routing | If/else chains | RuleRegistry.get_rules() | O(1) lookup, existing pattern |

**Key insight:** The existing rules infrastructure handles all wireless events without modification. Focus on rule definitions, not infrastructure changes.

## Common Pitfalls

### Pitfall 1: Confusing Radio Band Indicators
**What goes wrong:** Misinterpreting `radio_from`/`radio_to` values
**Why it happens:** UniFi uses cryptic abbreviations for radio bands
**How to avoid:** Use this mapping:
- `"na"` = 5GHz (802.11n/ac/ax)
- `"ng"` = 2.4GHz (802.11n/g)
- `"6e"` = 6GHz (WiFi 6E, newer devices only)

**Warning signs:** Descriptions showing "na" instead of "5GHz" in user-facing text

### Pitfall 2: Missing AP Name Resolution
**What goes wrong:** Showing MAC addresses instead of friendly AP names
**Why it happens:** Roaming events have `ap_from`/`ap_to` as MACs, not names
**How to avoid:** Cross-reference with device list or use LogEntry.from_unifi_event() which extracts ap_name. For roaming, may need separate lookup.
**Warning signs:** Report showing "aa:bb:cc:dd:ee:ff" instead of "Office-AP"

### Pitfall 3: DFS False Positives
**What goes wrong:** Flagging all interference events as DFS radar
**Why it happens:** EVT_AP_Interference covers multiple interference types
**How to avoid:** Use pattern matching to specifically identify radar messages
**Warning signs:** Non-radar interference flagged as DFS events

### Pitfall 4: Aggressive Flapping Thresholds
**What goes wrong:** Normal mobility flagged as flapping
**Why it happens:** Setting threshold too low for active environments
**How to avoid:** Start with conservative threshold (10 roams/hour), make configurable
**Warning signs:** Mobile users (phones, laptops) constantly flagged

### Pitfall 5: Missing Guest Network Events
**What goes wrong:** Only monitoring EVT_WU_* events, missing EVT_WG_* guest events
**Why it happens:** Forgetting guest network has parallel event types
**How to avoid:** Always pair WU and WG event types in rules
**Warning signs:** Guest network roaming invisible in reports

## Code Examples

### UniFi Roaming Event Payload
```json
// Source: GitHub dim13/unifi, community documentation
{
  "_id": "5eac130853afdc04bb92ba8c",
  "key": "EVT_WU_Roam",
  "user": "aa:bb:cc:dd:ee:ff",       // Client MAC
  "ap_from": "11:22:33:44:55:66",    // Source AP MAC
  "ap_to": "77:88:99:aa:bb:cc",      // Destination AP MAC
  "radio_from": "ng",                 // 2.4GHz
  "radio_to": "na",                   // 5GHz
  "channel_from": "6",
  "channel_to": "36",
  "channel": "36",                    // Current channel
  "ssid": "MyNetwork",
  "datetime": "2026-01-24T10:30:00Z",
  "time": 1737715800000,
  "msg": "User[aa:bb:cc:dd:ee:ff] roamed from ap[Living-Room] to ap[Office]",
  "subsystem": "wlan"
}
```

### RSSI to Quality Translation
```python
# Source: Industry standards, Ubiquiti documentation, community consensus
RSSI_THRESHOLDS = {
    "Excellent": -50,   # >= -50 dBm: Very strong, close to AP
    "Good": -60,        # -50 to -60 dBm: Strong signal, good performance
    "Fair": -70,        # -60 to -70 dBm: Moderate, may have occasional issues
    "Poor": -80,        # -70 to -80 dBm: Weak, slower speeds expected
    "Very Poor": -90,   # < -80 dBm: Very weak, unreliable connection
}

def rssi_to_quality(rssi: int) -> str:
    """Convert RSSI (dBm) to human-readable quality label."""
    if rssi >= -50:
        return "Excellent"
    elif rssi >= -60:
        return "Good"
    elif rssi >= -70:
        return "Fair"
    elif rssi >= -80:
        return "Poor"
    else:
        return "Very Poor"
```

### Radio Band Translation
```python
# Source: UniFi event payloads, community documentation
RADIO_BANDS = {
    "ng": "2.4GHz",
    "na": "5GHz",
    "6e": "6GHz",
}

def format_radio_band(radio_code: str) -> str:
    """Convert UniFi radio code to human-readable band."""
    return RADIO_BANDS.get(radio_code, radio_code)
```

### Complete Wireless Rule Example
```python
# Source: Adapted from existing rules pattern
from typing import List
from unifi_scanner.analysis.rules.base import Rule
from unifi_scanner.models.enums import Category, Severity

WIRELESS_RULES: List[Rule] = [
    # WIFI-01: Client roaming between APs
    Rule(
        name="client_roaming",
        event_types=["EVT_WU_Roam", "EVT_WG_Roam"],
        category=Category.WIRELESS,
        severity=Severity.LOW,
        title_template="[Wireless] Client roamed to {device_name}",
        description_template=(
            "A wireless client roamed from one access point to another "
            "(EVT_WU_Roam). This is normal behavior as devices move around "
            "your space and find better signal strength."
        ),
        remediation_template=None,
    ),

    # WIFI-02: Band switching (2.4GHz <-> 5GHz)
    Rule(
        name="band_switch",
        event_types=["EVT_WU_RoamRadio", "EVT_WG_RoamRadio"],
        category=Category.WIRELESS,
        severity=Severity.LOW,
        title_template="[Wireless] Client switched bands on {device_name}",
        description_template=(
            "A wireless client switched frequency bands on the same access point "
            "(EVT_WU_RoamRadio). This typically happens due to band steering or "
            "signal quality changes. Frequent switches may indicate interference."
        ),
        remediation_template=None,
    ),

    # WIFI-03: AP channel change
    Rule(
        name="ap_channel_change",
        event_types=["EVT_AP_ChannelChange"],
        category=Category.WIRELESS,
        severity=Severity.MEDIUM,
        title_template="[Wireless] AP {device_name} changed channel",
        description_template=(
            "Access point {device_name} changed its wireless channel "
            "(EVT_AP_ChannelChange). This may briefly affect connected clients. "
            "Channel changes happen automatically to avoid interference or due to "
            "DFS radar detection."
        ),
        remediation_template=(
            "1. This is usually automatic optimization - no action needed\n"
            "2. Check if WiFi AI is enabled and working correctly\n"
            "3. If frequent, check for interference sources nearby\n"
            "4. Consider manually assigning channels if auto-selection is unstable"
        ),
    ),

    # WIFI-04: DFS radar detection
    Rule(
        name="dfs_radar_detected",
        event_types=["EVT_AP_RADAR_DETECTED", "EVT_AP_Interference", "EVT_AP_ChannelChange"],
        category=Category.WIRELESS,
        severity=Severity.MEDIUM,
        title_template="[Wireless] DFS radar detected on {device_name}",
        description_template=(
            "Access point {device_name} detected radar interference and must vacate "
            "its current channel (DFS: Radar detected). Per FCC regulations, the AP "
            "cannot use this channel for 30 minutes. Clients may briefly disconnect "
            "while the AP switches to a new channel."
        ),
        remediation_template=(
            "1. This is automated regulatory compliance - the AP handles it automatically\n"
            "2. Clients will reconnect after the channel change (usually seconds)\n"
            "3. If this happens frequently, consider using non-DFS channels (36-48, 149-165)\n"
            "4. Check for nearby radar sources (airports, weather stations, military)\n"
            "5. Enable WiFi AI to automatically avoid problematic DFS channels"
        ),
        pattern=r"[Rr]adar.*(detected|hit)",  # Match radar-specific messages
    ),
]
```

## UniFi Event Types for Wireless Analysis

### Event Types to Handle

| Requirement | Event Type(s) | Severity | Notes |
|-------------|---------------|----------|-------|
| WIFI-01: Roaming | EVT_WU_Roam, EVT_WG_Roam | LOW | Has ap_from, ap_to fields |
| WIFI-02: Band switch | EVT_WU_RoamRadio, EVT_WG_RoamRadio | LOW | Has radio_from, radio_to fields |
| WIFI-03: Channel change | EVT_AP_ChannelChange | MEDIUM | Has channel info |
| WIFI-04: DFS radar | EVT_AP_RADAR_DETECTED, EVT_AP_Interference (pattern) | MEDIUM | Use pattern match for "radar" |
| WIFI-05: RSSI quality | N/A - applies to disconnect events | N/A | Add to existing disconnect descriptions |
| WIFI-06: Flapping | Aggregation of EVT_WU_Roam | MEDIUM | Requires counting logic |

### Event Payload Fields

| Field | Event Types | Description |
|-------|-------------|-------------|
| user | WU_Roam, WU_RoamRadio | Client MAC address |
| ap_from | WU_Roam | Source AP MAC |
| ap_to | WU_Roam | Destination AP MAC |
| channel_from | WU_Roam, WU_RoamRadio | Previous channel number |
| channel_to | WU_Roam, WU_RoamRadio | New channel number |
| radio_from | WU_Roam, WU_RoamRadio | Previous band (ng=2.4GHz, na=5GHz) |
| radio_to | WU_Roam, WU_RoamRadio | New band |
| ssid | WU_* | Network name |
| msg | All events | Human-readable message (use for radar pattern) |

### DFS Channel Reference

| Channel Range | Type | Notes |
|---------------|------|-------|
| 36-48 | Non-DFS | Safe from radar detection |
| 52-64 | DFS (UNII-2) | Requires radar detection |
| 100-144 | DFS (UNII-2 Extended) | Requires radar detection |
| 149-165 | Non-DFS (UNII-3) | Safe from radar detection |

## RSSI Threshold Values

### Industry Standard Thresholds (HIGH confidence)

| Quality | RSSI Range | User Explanation |
|---------|------------|------------------|
| Excellent | >= -50 dBm | Very strong signal, right next to the access point |
| Good | -50 to -60 dBm | Strong signal, good performance expected |
| Fair | -60 to -70 dBm | Moderate signal, may experience occasional issues |
| Poor | -70 to -80 dBm | Weak signal, expect slower speeds and possible disconnects |
| Very Poor | < -80 dBm | Very weak signal, connection unreliable |

### Roaming Thresholds

| Device Type | Roam Trigger | Notes |
|-------------|--------------|-------|
| Apple (iPhone/iPad) | -70 dBm | Built-in threshold |
| macOS | -75 dBm | Built-in threshold |
| Windows (default) | -80 dBm | Configurable via roaming aggressiveness |
| UniFi Min-RSSI | Configurable | Recommend -75 dBm as starting point |

## Flapping Detection Thresholds

### Recommended Thresholds (MEDIUM confidence)

Based on community best practices and network management standards:

| Environment | Threshold | Window | Rationale |
|-------------|-----------|--------|-----------|
| Office/Home | 5 roams | 60 min | Conservative - catches real issues |
| High-mobility | 10 roams | 60 min | Allows for normal movement |
| Warehouse/Campus | 15 roams | 60 min | High mobility expected |

**Recommendation:** Start with 5 roams per 60 minutes as default, make configurable.

### Implementation Notes

- Track roaming by client MAC (from `user` field in event)
- Consider excluding known mobile devices from alerts
- Provide context: "Client [name] roamed 12 times in the last hour"
- Include AP names in context to help identify coverage gaps

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Ignore roaming | Track roaming for visibility | Always best practice | Users see device mobility |
| Generic interference alerts | DFS-specific radar alerts | FCC requirements | Clearer user explanation |
| Raw RSSI values | Quality labels (Excellent/Poor) | Always best practice | Non-expert understanding |

**Current best practice:**
- Use 802.11k/v/r for fast roaming (client-side feature)
- Enable WiFi AI for automatic channel optimization
- Set Min-RSSI to encourage roaming when signal degrades

## Open Questions

1. **AP Name Resolution**
   - What we know: Roaming events contain AP MACs, not names
   - What's unclear: Best way to resolve MACs to names (device lookup vs event msg field)
   - Recommendation: Extract from `msg` field if present, otherwise use MAC

2. **RSSI in Events**
   - What we know: RSSI is tracked per-client, available in stat/sta endpoint
   - What's unclear: Whether RSSI is included in disconnect event payloads
   - Recommendation: Check disconnect events for RSSI field; if missing, note in description

3. **Flapping Severity**
   - What we know: Excessive roaming indicates network issues
   - What's unclear: Should flapping be MEDIUM or escalate to SEVERE?
   - Recommendation: Start with MEDIUM, let users configure

## Sources

### Primary (HIGH confidence)
- [dim13/unifi event.go](https://github.com/dim13/unifi/blob/master/event.go) - Event struct definitions with payload fields
- [oznu/unifi-events](https://github.com/oznu/unifi-events) - Event type enumeration and documentation
- Existing codebase analysis - Rules engine pattern, LogEntry model
- [Ubiquiti Community Wiki API](https://ubntwiki.com/products/software/unifi-controller/api) - API endpoint documentation

### Secondary (MEDIUM confidence)
- [UniFi Wireless LAN Roaming FAQ](https://community.ui.com/questions/Wireless-LAN-Roaming-FAQ/3044afc5-55ac-4c52-804d-2fbb91381e60) - Roaming behavior
- [Wi-Fi Signal Strength Explained](https://dongknows.com/wi-fi-signal-strength-dbm-explained/) - RSSI thresholds
- [Mist RSSI Roaming Documentation](https://www.juniper.net/documentation/us/en/software/mist/mist-wireless/topics/topic-map/rssi-fast-roaming.html) - Roaming thresholds
- [Cisco Client Roaming Documentation](https://documentation.meraki.com/MR/Wi-Fi_Basics_and_Best_Practices/Client_roaming_and_connectivity_decisions_explained) - Industry best practices
- [DFS Channels Help Article](https://help.ui.com/hc/en-us/articles/15510834696599-DFS-Channels) - DFS requirements

### Tertiary (LOW confidence - needs validation)
- Flapping threshold (5 roams/hour) - Community consensus, no official standard
- EVT_AP_ChannelChange existence - Inferred from naming convention, not directly verified

## Metadata

**Confidence breakdown:**
- Event types and payloads: HIGH - Verified from multiple Go/Node.js implementations
- RSSI thresholds: HIGH - Industry standard, multiple sources agree
- DFS behavior: HIGH - FCC-regulated, well-documented
- Flapping thresholds: MEDIUM - Community best practice, no official standard
- Category addition: HIGH - Follows existing codebase pattern

**Research date:** 2026-01-24
**Valid until:** 2026-03-24 (60 days - stable domain, event types rarely change)
