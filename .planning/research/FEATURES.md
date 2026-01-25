# Feature Landscape: Extended Analysis Rules for UniFi Scanner

**Domain:** Extended event analysis for wireless, security, device health, and optional services
**Researched:** 2026-01-24
**Confidence:** MEDIUM (UniFi API is undocumented; findings based on community projects and official help articles)

## Executive Summary

This research documents UniFi event types and features needed to extend the existing analysis rules beyond the basic connectivity, security, and system events already implemented. The focus areas are:

1. **Wireless-specific events** - Roaming, channel changes, interference, signal quality
2. **Security events** - IDS/IPS alerts with Suricata signatures, threat categories
3. **Device health** - Temperature, CPU, memory, PoE, port status
4. **CyberSecure** - Premium threat intelligence (Proofpoint) and content filtering (Cloudflare)
5. **Cloudflare tunnel** - VPN/tunnel connectivity status

**Key Finding:** UniFi does not publish official API documentation. Event types are derived from community projects ([oznu/unifi-events](https://github.com/oznu/unifi-events), [dim13/unifi](https://github.com/dim13/unifi)) and the controller's `eventStrings.json` file. Event availability varies by device type and firmware version.

**Recommendation:** Implement rules in priority order: Wireless (high user impact) > IDS/IPS (actionable security) > Device Health (preventive maintenance) > CyberSecure/Cloudflare (optional features).

---

## Already Implemented (Existing Rules)

These rules exist in the current codebase and should NOT be duplicated:

### Connectivity Rules (connectivity.py)
| Event Type | Severity | Status |
|------------|----------|--------|
| EVT_AP_Lost_Contact, EVT_AP_DISCONNECTED | SEVERE | Implemented |
| EVT_SW_Lost_Contact, EVT_SW_DISCONNECTED | SEVERE | Implemented |
| EVT_GW_WAN_DISCONNECTED, EVT_WAN_FAILOVER | SEVERE | Implemented |
| EVT_AP_Isolated | SEVERE | Implemented |
| EVT_AP_Connected | LOW | Implemented |
| EVT_WU_Connected, EVT_WG_Connected, EVT_LU_Connected | LOW | Implemented |
| EVT_WU_Disconnected, EVT_WG_Disconnected, EVT_LU_Disconnected | LOW | Implemented |

### Security Rules (security.py)
| Event Type | Severity | Status |
|------------|----------|--------|
| EVT_AD_LOGIN_FAILED | SEVERE | Implemented |
| EVT_AP_RogueAPDetected | SEVERE | Implemented |
| EVT_IPS_Alert (generic) | SEVERE | Implemented |
| EVT_AD_Login | LOW | Implemented |

### System Rules (system.py)
| Event Type | Severity | Status |
|------------|----------|--------|
| EVT_*_Upgraded | LOW | Implemented |
| EVT_*_Restarted | LOW | Implemented |
| EVT_*_RestartedUnknown | MEDIUM | Implemented |
| EVT_*_Adopted | LOW | Implemented |
| EVT_CONFIG_CHANGED | LOW | Implemented |
| EVT_BACKUP_CREATED | LOW | Implemented |
| EVT_*_UPDATE_AVAILABLE | LOW | Implemented |

### Performance Rules (performance.py)
| Event Type | Severity | Status |
|------------|----------|--------|
| EVT_AP_Interference, EVT_AP_RADAR_DETECTED | MEDIUM | Implemented |
| EVT_*_HIGH_CPU | MEDIUM | Implemented |
| EVT_*_HIGH_MEMORY | MEDIUM | Implemented |
| EVT_SPEED_TEST_* | MEDIUM | Implemented |
| EVT_AP_CHANNEL_UTIL_HIGH | MEDIUM | Implemented |

---

## Table Stakes (Must Have)

Features users expect for comprehensive network monitoring. Missing = reports feel incomplete.

### Wireless Events

| Event Type | Category | Severity | Why Expected | API Source | User Explanation |
|------------|----------|----------|--------------|------------|------------------|
| **EVT_WU_Roam** | WIRELESS | LOW | Users want to see if devices are successfully roaming between APs | stat/event | "Your device [device] moved from [AP1] to [AP2]. This is normal behavior as you move around." |
| **EVT_WU_RoamRadio** | WIRELESS | LOW | Channel/band changes on same AP indicate potential issues if frequent | stat/event | "Your device [device] switched from [channel_from] to [channel_to] on the same AP. Frequent switches may indicate interference." |
| **EVT_WG_Roam** | WIRELESS | LOW | Guest network roaming visibility | stat/event | "A guest device moved between access points. Normal network behavior." |
| **EVT_AP_ChannelChange** | WIRELESS | MEDIUM | Unexpected channel changes affect connected clients | stat/event | "Access point [AP] changed from channel [from] to [to]. This may briefly interrupt connections." |
| **DFS Radar Detected** | WIRELESS | MEDIUM | Radar detection forces channel changes; users need awareness | stat/event, message pattern | "Radar was detected on channel [channel]. Your AP must vacate this channel for 30 minutes per FCC rules." |

**Complexity:** Low - These are standard EVT_ events available in stat/event API.

### Enhanced IDS/IPS Events

| Event Type | Category | Severity | Why Expected | API Source | User Explanation |
|------------|----------|----------|--------------|------------|------------------|
| **EVT_IPS_Alert (with signature details)** | SECURITY | SEVERE | Current implementation is generic; users need specific threat info | stat/event + message parsing | "Threat detected: [signature_name]. Risk level: [high/medium/low]. Source: [src_ip] to [dst_ip]." |
| **Signature Categories** | SECURITY | Varies | Map Suricata categories to plain English | Message parsing | See Threat Category Mapping below |
| **Blocked vs Detected** | SECURITY | SEVERE/MEDIUM | Users need to know if threat was blocked (IPS) or just detected (IDS) | Message parsing | "This threat was [blocked/detected]. [If blocked: No action needed. If detected: Consider enabling IPS.]" |

**Threat Category Mapping (Suricata/ET):**

| Suricata Category | Plain English | Suggested Severity |
|-------------------|---------------|-------------------|
| ET SCAN | "Network scanning activity - someone probing your network" | MEDIUM |
| ET TROJAN | "Potential malware communication detected" | SEVERE |
| ET MALWARE | "Known malicious software signature" | SEVERE |
| ET DOS | "Denial of service attempt" | SEVERE |
| ET EXPLOIT | "Attempt to exploit a vulnerability" | SEVERE |
| ET POLICY | "Policy violation (may be normal, e.g., P2P)" | LOW |
| ET INFO | "Informational - unusual but not necessarily malicious" | LOW |
| ET USER_AGENTS | "Suspicious browser/software identifier" | MEDIUM |
| ET CURRENT_EVENTS | "Matches current threat intelligence" | SEVERE |
| ET HUNTING | "Potentially suspicious behavior worth investigating" | MEDIUM |

**Complexity:** Medium - Requires parsing signature strings from IPS alerts.

### Device Health Events

| Event Type | Category | Severity | Why Expected | API Source | User Explanation |
|------------|----------|----------|--------------|------------|------------------|
| **Temperature alerts** | DEVICE_HEALTH | MEDIUM/SEVERE | Overheating can cause failures; users need early warning | stat/device (general_temperature field) | "Device [name] is running hot at [temp]C. Ensure adequate ventilation." |
| **EVT_SW_PoeDisconnect** | DEVICE_HEALTH | MEDIUM | PoE failures affect powered devices | stat/event | "Power over Ethernet disconnected on [switch] port [port]. Device on that port lost power." |
| **PoE Overload** | DEVICE_HEALTH | SEVERE | Budget exceeded means devices lose power | stat/event, message pattern | "PoE power budget exceeded on [switch]. Some devices may lose power. Consider a PoE injector or larger switch." |
| **Port Up/Down** | DEVICE_HEALTH | MEDIUM | Physical connectivity changes | stat/event | "Port [port] on [switch] [came up/went down]. Check physical connections if unexpected." |

**Note:** Temperature data requires polling `stat/device` endpoint rather than events. CPU temperature is available via `general_temperature` field on device objects.

**Complexity:** Medium - Temperature requires device polling; PoE events are standard EVT_ types.

---

## Differentiators (Should Have)

Features that make reports especially valuable compared to UniFi's native alerts.

### Enhanced Wireless Intelligence

| Feature | Value Proposition | Complexity | Implementation Notes |
|---------|-------------------|------------|---------------------|
| **Roaming quality assessment** | "Client [device] roamed 15 times in 1 hour - may indicate sticky client or coverage gap" | Medium | Track roaming frequency per client; threshold-based alerts |
| **Signal strength context** | Include RSSI values in disconnect explanations | Low | RSSI available in disconnect events; translate to quality (excellent/good/fair/poor) |
| **Min-RSSI kick explanation** | "Client was disconnected because signal dropped below threshold" | Low | Pattern match on disconnect reason |
| **Band steering events** | "Client was encouraged to move from 2.4GHz to 5GHz" | Low | EVT_AP events for steering |

**RSSI to Quality Mapping (for non-experts):**

| RSSI Range | Quality | User Explanation |
|------------|---------|------------------|
| > -50 dBm | Excellent | "Very strong signal, right next to the access point" |
| -50 to -60 dBm | Good | "Strong signal, good performance expected" |
| -60 to -70 dBm | Fair | "Moderate signal, may experience occasional issues" |
| -70 to -80 dBm | Poor | "Weak signal, expect slower speeds and possible disconnects" |
| < -80 dBm | Very Poor | "Very weak signal, connection unreliable" |

### IPS/IDS Context

| Feature | Value Proposition | Complexity | Implementation Notes |
|---------|-------------------|------------|---------------------|
| **Threat severity translation** | Map Suricata severity 1-4 to low/medium/severe | Low | Direct mapping from alert fields |
| **Source device identification** | "This threat came FROM your device [name]" vs "came TO your device" | Medium | Cross-reference src/dst IP with client list |
| **False positive likelihood** | "This is commonly a false positive when using [VPN/P2P/gaming]" | Medium | Maintain list of known FP signatures |
| **Remediation by category** | Different action steps for malware vs scanning vs policy | High | Category-specific remediation templates |

### Device Health Intelligence

| Feature | Value Proposition | Complexity | Implementation Notes |
|---------|-------------------|------------|---------------------|
| **Temperature trend warnings** | "Device temperature has increased 10C over last week" | Medium | Requires historical tracking |
| **Uptime monitoring** | "Device [name] has been running for 90 days - consider scheduled restart" | Low | Uptime available in stat/device |
| **Firmware age alerts** | "Device [name] is 3 versions behind current firmware" | Medium | Compare running vs available firmware |

---

## Optional Features (CyberSecure & Cloudflare)

These features require paid subscriptions or specific configurations. Mark clearly as optional in reports.

### CyberSecure by Proofpoint (Subscription Required)

**Prerequisite:** CyberSecure subscription ($99/year standard, $499/year enterprise)

| Feature | Category | Severity | Detection Method | User Explanation |
|---------|----------|----------|------------------|------------------|
| **Enhanced threat signatures** | SECURITY | Varies | Same IPS events, more signatures | "Your CyberSecure subscription detected [threat] using enterprise threat intelligence." |
| **Proofpoint category blocks** | SECURITY | MEDIUM | IPS events with Proofpoint signatures | "Blocked by Proofpoint threat intelligence: [category]" |
| **Weekly signature updates** | SECURITY | LOW | Informational | "CyberSecure updated with [X] new threat signatures this week." |

**Implementation Notes:**
- CyberSecure uses same IPS event format but with more signatures (55K+ standard, 95K+ enterprise)
- Signature categories expand to 50+ with CyberSecure vs ~20 without
- Detection: Check if signature ID falls in Proofpoint range or contains Proofpoint identifier
- No separate API endpoint - same stat/event with richer signatures

**Complexity:** Low - Same event format, just more signatures. Add "CyberSecure" badge to relevant alerts.

### Cloudflare Content Filtering (CyberSecure Required)

**Prerequisite:** CyberSecure subscription

| Feature | Category | Severity | Detection Method | User Explanation |
|---------|----------|----------|------------------|------------------|
| **Content category blocks** | CONTENT_FILTER | LOW | DNS query logs | "Access to [domain] was blocked. Category: [Adult Content/Malware/etc]" |
| **Ad blocking events** | CONTENT_FILTER | LOW | DNS query logs | "Advertisement blocked from [domain]" |
| **Policy violations** | CONTENT_FILTER | MEDIUM | DNS query logs | "Access attempt to blocked category: [category]" |

**Content Filtering Categories (100+ available with CyberSecure):**

| Category Group | Examples | Default Action |
|----------------|----------|----------------|
| Security Threats | Malware, Phishing, Spam | Block |
| Adult Content | Adult, Gambling | Block (optional) |
| Productivity | Social Media, Streaming, Gaming | Configurable |
| Communication | Email, Messaging, VoIP | Allow (default) |

**Implementation Notes:**
- Content filtering events may not appear in standard stat/event API
- Consider using SIEM/syslog integration if available (requires UniFi Network 8.5.1+)
- DNS-level filtering means events occur at gateway level
- Mark as "[CyberSecure]" in reports so users know this requires subscription

**Complexity:** Medium - May require syslog parsing rather than API events.

### Cloudflare Tunnel/Zero Trust Integration

**Prerequisite:** Cloudflare Zero Trust account + IPsec VPN configuration

| Feature | Category | Severity | Detection Method | User Explanation |
|---------|----------|----------|------------------|------------------|
| **Tunnel health** | VPN | SEVERE if down | Site-to-Site VPN status | "Cloudflare tunnel [name] is [connected/disconnected]." |
| **Tunnel latency** | VPN | MEDIUM if high | VPN metrics | "Cloudflare tunnel latency is [X]ms. [If high: May affect remote access performance.]" |

**Implementation Notes:**
- Cloudflare tunnels appear as Site-to-Site VPN connections in UniFi
- VPN status available via `rest/networkconf` or similar endpoint
- Tunnel health can be monitored via Cloudflare dashboard, not UniFi events
- Limited event visibility in UniFi - mainly connection/disconnection

**Complexity:** Medium - VPN status requires different API endpoints than events.

---

## Anti-Features (Explicitly NOT Include)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Every client connect/disconnect** | Creates noise; thousands of events per day | Already implemented as LOW severity; consider aggregation |
| **Raw signature IDs** | Non-experts can't interpret "sid:2024897" | Always translate to plain English category + explanation |
| **Network flow details** | Technical: src:port -> dst:port is meaningless to users | Summarize as "Device [name] communicated with [service/domain]" |
| **Per-packet statistics** | Overwhelming data; not actionable | Report high-level trends only |
| **Configuration change details** | Too technical; changes are intentional | Report occurrence count, not content |
| **Certificate/SSL events** | Complex to explain; often false positives | Only report expired certs causing connection failures |

---

## Event Sources and API Endpoints

### Primary Event Source

| Endpoint | Description | Use For |
|----------|-------------|---------|
| `api/s/{site}/stat/event` | Event log, 3000 result limit, newest first | All EVT_* events |
| `api/s/{site}/stat/alarm` | Alarms, 3000 result limit | IPS/IDS alerts, high-priority issues |
| `api/s/{site}/stat/device` | Device status including health metrics | Temperature, CPU, memory, uptime |
| `api/s/{site}/stat/sta` | Connected clients | Client details for cross-referencing |

**Note:** For UDM Pro and UCG Max, prefix all endpoints with `/proxy/network`.

### SIEM Integration (UniFi 8.5.1+)

CEF-formatted logs via syslog contain richer security data:
- IDS/IPS events with full signature details
- Firewall rule matches
- Admin activity

**CEF fields available:** `act`, `cat`, `destinationDnsDomain`, `dhost`, `dpt`, `dst`, `duser`, `fname`, `msg`, `proto`, `shost`, `spt`, `src`, `suser`

---

## Implementation Priority

### Phase 1: Core Wireless (High Impact, Low Effort)

1. EVT_WU_Roam / EVT_WG_Roam - Roaming events
2. EVT_WU_RoamRadio - Channel/band changes
3. DFS radar detection (message pattern matching)
4. EVT_AP_ChannelChange

**Estimated rules:** 4-5 new rules
**Complexity:** Low

### Phase 2: Enhanced IDS/IPS (Security Value)

1. Parse Suricata signature categories from existing IPS events
2. Map categories to plain English
3. Add severity based on signature classification
4. Add blocked vs detected distinction

**Estimated rules:** 10-15 signature category mappings
**Complexity:** Medium (regex parsing)

### Phase 3: Device Health (Preventive)

1. Temperature monitoring (poll stat/device)
2. EVT_SW_PoeDisconnect
3. PoE overload events
4. Uptime tracking

**Estimated rules:** 3-4 new rules + device polling
**Complexity:** Medium (requires device polling)

### Phase 4: Optional Services (Premium)

1. CyberSecure badge for enhanced signatures
2. Cloudflare content filtering (if syslog available)
3. VPN tunnel status

**Estimated rules:** 3-5 rules
**Complexity:** Medium-High (may require syslog)

---

## Confidence Assessment

| Category | Confidence | Reasoning |
|----------|------------|-----------|
| Wireless events | HIGH | Documented in multiple community projects; standard EVT_ format |
| IDS/IPS categories | MEDIUM | Suricata categories are standard; UniFi implementation details less clear |
| Device health | MEDIUM | Temperature available in stat/device; PoE events documented |
| CyberSecure features | LOW | Subscription-only; limited public documentation |
| Cloudflare integration | LOW | Third-party integration; events may not surface in UniFi API |
| Event API structure | HIGH | Consistent across community projects and testing |

---

## Sources

### UniFi Event Types (MEDIUM confidence)
- [oznu/unifi-events](https://github.com/oznu/unifi-events) - Node.js event listener with event type documentation
- [dim13/unifi event.go](https://github.com/dim13/unifi/blob/master/event.go) - Go implementation with struct definitions
- [Ubiquiti Community Wiki API](https://ubntwiki.com/products/software/unifi-controller/api) - Community-maintained API documentation
- eventStrings.json (controller-local) - Complete event type definitions

### Security Features (MEDIUM confidence)
- [UniFi IDS/IPS Help](https://help.ui.com/hc/en-us/articles/360006893234-UniFi-Gateway-Intrusion-Detection-and-Prevention-IDS-IPS) - Official IDS/IPS documentation
- [UniFi CyberSecure](https://help.ui.com/hc/en-us/articles/25930305913751-UniFi-CyberSecure-Enhanced-by-Proofpoint-and-Cloudflare) - CyberSecure features
- [UniFi System Logs & SIEM](https://help.ui.com/hc/en-us/articles/33349041044119-UniFi-System-Logs-SIEM-Integration) - CEF format and SIEM integration

### Wireless Features (MEDIUM confidence)
- [UniFi WiFi SSID Settings](https://help.ui.com/hc/en-us/articles/32065480092951-UniFi-WiFi-SSID-and-AP-Settings-Overview) - Official wireless settings
- [Min-RSSI Documentation](https://help.ui.com/hc/en-us/articles/221321728-Understanding-and-Implementing-Minimum-RSSI) - RSSI and roaming
- [DFS Channels](https://help.ui.com/hc/en-us/articles/15510834696599-DFS-Channels) - DFS radar detection

### Content Filtering (MEDIUM confidence)
- [Content and Domain Filtering](https://help.ui.com/hc/en-us/articles/12568927589143-Content-and-Domain-Filtering-in-UniFi) - Cloudflare content filtering

### Cloudflare Integration (LOW confidence)
- [Cloudflare Ubiquiti Documentation](https://developers.cloudflare.com/cloudflare-one/networks/connectors/wan-tunnels/configuration/manually/third-party/ubiquiti/) - Official integration guide

---

## Open Questions

1. **Event availability across device types:** Do all UniFi devices emit all event types, or are some AP-only, gateway-only, etc.?

2. **CyberSecure event differentiation:** How to detect if an IPS alert came from CyberSecure vs base signatures?

3. **Temperature thresholds:** What temperatures are concerning for each device type? Need device-specific thresholds.

4. **Cloudflare event visibility:** Are Cloudflare content filtering blocks visible via UniFi API, or only via Cloudflare dashboard/syslog?

5. **Roaming event frequency:** What's the threshold for "too much roaming" that should generate a warning?
