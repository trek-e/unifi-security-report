# Project Research Summary

**Project:** UniFi Scanner v0.4-alpha - Extended Analysis & Integrations
**Domain:** Network monitoring and log analysis service
**Researched:** 2026-01-24
**Confidence:** MEDIUM-HIGH

## Executive Summary

The v0.4-alpha milestone extends the existing UniFi Scanner with comprehensive wireless/security/device health rules and optional Cybersecure/Cloudflare integrations. Research confirms the **existing stack requires minimal changes**—the current Python-based sync architecture with Pydantic, httpx, and the established rules engine handles all new requirements cleanly. No new core dependencies needed for extended analysis rules; only optional Cloudflare SDK for users who want that integration.

The recommended approach is **incremental expansion** of the proven rules engine pattern with strict categorization and adapter-based optional integrations. Extended analysis rules (wireless roaming, IDS signature parsing, device health) leverage existing event collection APIs—no architectural changes. Optional integrations (Cybersecure, Cloudflare) should be **parallel collectors** that fail independently without blocking core UniFi analysis. This preserves the existing reliability while adding value for advanced users.

**Key risks are preventable:** (1) Rule explosion creating maintenance burden—mitigate with rule composition patterns and categorization by domain. (2) Cloudflare API rate limits (1,200 req/5min)—mitigate with caching, circuit breakers, and graceful degradation. (3) Tight coupling of optional features—mitigate with adapter pattern and lazy imports. All three have proven mitigation patterns ready to implement.

## Key Findings

### Recommended Stack

The existing stack (Python 3.12+, httpx, Pydantic, structlog, APScheduler) is well-suited for all v0.4 requirements. **No new core dependencies needed** for extended analysis rules—the existing rules engine pattern handles new categories cleanly.

**Core technologies (existing, keep):**
- **httpx 0.27+**: HTTP client for API calls — already handles UniFi API perfectly
- **Pydantic 2.11+**: Data validation and models — used for log events, extends naturally to new event types
- **structlog 25.5.0**: Structured logging — production-ready JSON output, context binding
- **APScheduler 3.10+**: Job scheduling — proven in production, no changes needed

**Optional additions (Cloudflare integration only):**
- **cloudflare 4.3.1+**: Official SDK with typed models — only if user wants Cloudflare integration; add as `[cloudflare]` extra in pyproject.toml

**NOT needed:**
- No separate Cybersecure API—threat data flows through existing UniFi endpoints (`/stat/event`, `/stat/alarm`)
- No log parsing libraries—UniFi events are already structured, use existing Pydantic models
- No async complexity—sync polling architecture remains optimal

### Expected Features

Extended analysis rules build on existing categories (SECURITY, CONNECTIVITY, PERFORMANCE, SYSTEM) with two new categories: WIRELESS and DEVICE_HEALTH.

**Must have (table stakes):**
- **Wireless roaming events** (EVT_WU_Roam, EVT_WU_RoamRadio) — users expect visibility into client roaming behavior
- **Enhanced IDS/IPS context** — parse Suricata signature categories (ET SCAN, ET MALWARE, etc.) into plain English
- **Device health alerts** — temperature warnings, PoE failures prevent device outages
- **DFS radar detection** — channel changes due to radar affect all connected clients, users need awareness

**Should have (competitive):**
- **Roaming quality assessment** — "Client roamed 15 times in 1 hour" indicates coverage gaps
- **Signal strength context** — translate RSSI to quality labels (excellent/good/fair/poor)
- **IDS source/destination mapping** — "This threat came FROM your device [name]" vs "came TO your device"
- **Temperature trend warnings** — "Device temperature increased 10C over last week"

**Optional (premium features, clearly marked):**
- **Cybersecure threat intelligence** — enhanced signatures with Proofpoint categories (requires $99/year subscription, UniFi Network 9.3+)
- **Cloudflare WAF analytics** — blocked threats, DNS analytics (requires Cloudflare Zero Trust account)
- **Content filtering events** — blocked domains by category (requires CyberSecure subscription)

**Defer (v2+):**
- Real-time alerting (current: scheduled reports only)
- Historical trending beyond 7 days
- Custom rule creation UI

### Architecture Approach

Optional integrations follow the existing **Collector + Rules + Report** pipeline with parallel data collection and adapter-based isolation. Cybersecure and Cloudflare are **additional data sources** that produce LogEntry objects, processed by the same AnalysisEngine with source-specific rules.

**Major components:**

1. **IntegrationManager** — orchestrates parallel collection from optional sources, ensures failures are isolated (one integration failing doesn't block others)

2. **Integration collectors** (new) — CybersecureCollector, CloudflareCollector implement IntegrationCollector protocol; return `List[LogEntry]` with source metadata; gracefully degrade when unconfigured/unavailable

3. **Extended rules engine** (existing, expand) — add wireless_rules.py, device_health_rules.py with dedicated event type ownership; maintain existing registry validation

4. **Adapter pattern for optional dependencies** — ThreatIntelProvider interface with NullProvider fallback; CloudflareThreatIntel implementation only loaded if package installed and configured

**Data flow:**
```
run_report_job()
  |
  +---> UnifiLogCollector.collect()         [existing]
  +---> CybersecureCollector.collect()      [new, if enabled]
  +---> CloudflareCollector.collect()       [new, if enabled]
  |
  v
all_entries merged by source
  |
  v
AnalysisEngine.analyze(all_entries)
  |-- UniFi rules (existing)
  |-- Wireless rules (new)
  |-- Device health rules (new)
  |-- Cybersecure rules (new, if data present)
  |-- Cloudflare rules (new, if data present)
  |
  v
Report with mixed-source findings
```

**Key principle:** Integrations are isolated modules. Core scanner works without them. No integration can crash the pipeline.

### Critical Pitfalls

1. **Rule explosion and maintenance burden** — Starting with 15 rules, expanding to 50+ creates unpredictable behavior and testing burden. **Avoid with:** Rule categorization by domain (wireless_rules.py, device_health_rules.py), rule composition helpers for common patterns, quarterly review process, event type ownership table to prevent category overlap.

2. **Cloudflare API rate limits (1,200 req/5min)** — Per-event API calls exceed global rate limit, causing 5-minute service outage. **Avoid with:** Aggressive caching (1-hour TTL for threat data), rate limiter decorator (4 req/sec sustainable), circuit breaker to fail fast on repeated errors, graceful degradation returning None when rate limited.

3. **Tight coupling of optional integrations** — Direct Cloudflare calls in core business logic make testing fragile and feature addition complex. **Avoid with:** Adapter pattern (ThreatIntelProvider interface), Null provider for disabled integrations, lazy imports (don't crash if optional package missing), factory function selects provider at startup.

4. **UniFi API rate limiting (undocumented)** — Aggressive polling triggers silent data loss or auth failures. **Avoid with:** Conservative 5-minute minimum poll interval, request spacing (500ms between different API calls), exponential backoff on 403 errors, detection logic for zero events despite history request.

5. **False positive explosion** — New rules tested with synthetic data generate 40% false positive rate in production. **Avoid with:** Shadow mode for new rules (logged but not reported), 2-week baseline period before alerting, configurable thresholds per environment, false positive feedback mechanism in remediation templates.

## Implications for Roadmap

Based on research, v0.4-alpha should be structured as three sequential phases with optional integration phases at the end. This ordering prioritizes high-impact user-facing features first while establishing infrastructure for later extensibility.

### Phase 1: Extended Wireless Analysis

**Rationale:** High user impact, low implementation complexity. Wireless events use standard EVT_ format with existing collection APIs. No new dependencies. Builds on proven rules engine.

**Delivers:**
- Roaming visibility (EVT_WU_Roam, EVT_WG_Roam, EVT_WU_RoamRadio)
- Channel change alerts (EVT_AP_ChannelChange)
- DFS radar detection (pattern matching on existing events)
- Signal strength context (RSSI translation to quality labels)

**Addresses features:** All "Must have" wireless events from research, "Should have" roaming quality assessment

**Avoids pitfalls:** Rule categorization established (wireless_rules.py), event type ownership documented before adding rules, shadow mode support implemented for new wireless rules

**Research flag:** LOW—wireless events well-documented in community projects, standard EVT_ patterns

### Phase 2: Enhanced Security Context (IDS/IPS)

**Rationale:** Builds on existing security rules. Parses Suricata signatures already present in EVT_IPS_Alert events. High security value with no API changes needed.

**Delivers:**
- Signature category mapping (ET SCAN → "Network scanning activity")
- Severity translation (Suricata 1-4 → LOW/MEDIUM/SEVERE)
- Blocked vs detected distinction (IPS vs IDS mode)
- Source/destination device identification (cross-reference with client list)

**Uses:** Existing httpx for API calls, Pydantic for signature models, regex for message parsing

**Implements:** Security rules expansion in existing security_rules.py with signature category mappings

**Avoids pitfalls:** Clear category ownership (all EVT_IPS_* events stay in SECURITY category), false positive mitigation with signature-specific severity overrides

**Research flag:** MEDIUM—Suricata categories standard, but UniFi implementation details less documented; may need real-world testing

### Phase 3: Device Health Monitoring

**Rationale:** Preventive maintenance value. Requires device polling (stat/device) in addition to events, establishing pattern for future non-event data sources.

**Delivers:**
- Temperature monitoring (poll general_temperature field)
- PoE failure alerts (EVT_SW_PoeDisconnect, overload patterns)
- Port status tracking (up/down events)
- Uptime monitoring (identify long-running devices needing restart)

**Addresses features:** "Must have" device health alerts, "Should have" temperature trend warnings

**Implements:** New device_health_rules.py category, device polling in collector (extends existing pattern)

**Avoids pitfalls:** Rule composition for temperature thresholds by device type, configurable threshold overrides to reduce false positives

**Research flag:** MEDIUM—Device polling adds new collection pattern; temperature thresholds vary by hardware model

### Phase 4: Optional Integrations Infrastructure (if desired)

**Rationale:** Establishes adapter pattern for all future integrations. No user-facing features yet—pure infrastructure to avoid technical debt.

**Delivers:**
- IntegrationCollector protocol
- IntegrationManager for parallel collection
- ThreatIntelProvider adapter interface
- Null provider implementations
- Lazy import handling
- Circuit breaker pattern

**Addresses:** Pitfall #3 (tight coupling), #4 (missing circuit breaker), #7 (import failures)

**Uses:** pybreaker for circuit breaker, existing structlog for health tracking

**Research flag:** LOW—standard patterns, well-documented in architecture research

### Phase 5: Cloudflare Integration (optional)

**Rationale:** Most requested optional integration. Official SDK with good docs. Independent from Cybersecure (different API).

**Delivers:**
- WAF event collection (GraphQL firewall events)
- DNS analytics (query volume, blocked domains)
- Threat intelligence enrichment (IP reputation lookups)

**Uses:** cloudflare 4.3.1+ SDK (as optional dependency), existing adapter infrastructure from Phase 4

**Implements:** CloudflareCollector, CloudflareThreatIntel adapter, cloudflare_rules.py

**Avoids pitfalls:** Rate limiter (4 req/sec), caching (1-hour TTL), circuit breaker, graceful degradation on rate limit

**Research flag:** LOW—official SDK well-documented, GraphQL API examples available

### Phase 6: Cybersecure Integration (optional)

**Rationale:** Uses existing UniFi API, no new dependencies. Premium feature requiring subscription detection.

**Delivers:**
- Enhanced signature detection (identifies Proofpoint-powered signatures)
- Cybersecure badge in reports for subscription-enabled findings
- Content filtering events (if available via syslog)

**Uses:** Existing UniFi client with feature detection

**Implements:** CybersecureCollector (wraps existing API calls), cybersecure_rules.py for subscription-specific patterns

**Avoids pitfalls:** Version detection (UniFi Network 9.3+ required), feature availability check before enabling, clear documentation of subscription requirements

**Research flag:** MEDIUM—Cybersecure API poorly documented; may require real controller testing to validate event format

### Phase Ordering Rationale

- **Wireless first:** Highest user impact, lowest risk, establishes extended rule patterns
- **Security second:** Builds on existing security foundation, adds immediate value to existing IPS users
- **Device health third:** Introduces device polling pattern, more complex than events-only phases
- **Infrastructure fourth:** Must come before any integration to avoid technical debt
- **Cloudflare before Cybersecure:** Better documentation, official SDK, more predictable implementation

**Dependency chain:**
- Phases 1-3 are independent (can be reordered if priorities change)
- Phase 4 blocks Phases 5-6 (integrations need adapter infrastructure)
- Phases 5-6 are independent of each other (parallel implementation possible)

**Risk reduction:**
- Each phase delivers user value independently
- Phases 1-3 have no external dependencies (can't be blocked by vendor issues)
- Phases 5-6 are optional (can be skipped if not needed by users)

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 2 (IDS/IPS):** MEDIUM confidence on signature format parsing; recommend capturing real IPS events from multiple UniFi versions to validate regex patterns
- **Phase 3 (Device Health):** MEDIUM confidence on device-specific temperature thresholds; need hardware model matrix for safe operating ranges
- **Phase 6 (Cybersecure):** LOW confidence on event differentiation from base IPS; may need subscription access for testing

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Wireless):** Well-documented event types, multiple community projects confirm format
- **Phase 4 (Infrastructure):** Standard adapter and circuit breaker patterns from architecture research
- **Phase 5 (Cloudflare):** Official SDK with comprehensive documentation and examples

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Existing stack verified sufficient; Cloudflare SDK vetted |
| Features | MEDIUM | Wireless/security events documented; Cybersecure events less clear |
| Architecture | HIGH | Adapter pattern proven in existing codebase (delivery channels) |
| Pitfalls | HIGH | Rate limits documented (Cloudflare official), mitigation patterns verified |

**Overall confidence:** MEDIUM-HIGH

Research is solid on technical approach and architecture. Medium confidence areas are operational details (signature formats, temperature thresholds, Cybersecure event structure) that require validation during implementation but won't change the overall architecture.

### Gaps to Address

**During Phase 1 planning:**
- Validate RSSI threshold ranges across different AP models (UniFi 6, WiFi 7, etc.)
- Establish roaming frequency baseline ("too much roaming" threshold varies by environment)

**During Phase 2 planning:**
- Capture real IPS events from UniFi controllers running different firmware versions to validate signature parsing regex
- Build test fixture library from production UniFi logs (with sensitive data scrubbed)

**During Phase 3 planning:**
- Research device-specific temperature thresholds (UDM Pro vs UCG Max vs USW switches)
- Determine safe uptime limits (some devices handle 365-day uptime, others should restart quarterly)

**During Phase 6 planning:**
- Validate Cybersecure subscription detection method (feature flag in controller API?)
- Confirm content filtering events surface in UniFi API vs requiring syslog integration

**Configuration management:**
- Design configurable threshold system before Phase 1 (prevents false positive explosion)
- Implement shadow mode infrastructure before Phase 1 (safe rollout of new rules)

## Sources

### Primary (HIGH confidence)
- [PyPI cloudflare](https://pypi.org/project/cloudflare/) — v4.3.1 SDK verification
- [Cloudflare API rate limits](https://developers.cloudflare.com/fundamentals/api/reference/limits/) — 1,200 requests per 5 minutes
- [UniFi CyberSecure requirements](https://help.ui.com/hc/en-us/articles/30426718447639-UniFi-CyberSecure) — Network 9.3+, subscription details
- [UniFi IDS/IPS documentation](https://help.ui.com/hc/en-us/articles/360006893234-UniFi-Gateway-Intrusion-Detection-and-Prevention-IDS-IPS) — Suricata integration
- [Cloudflare GraphQL Analytics API](https://developers.cloudflare.com/analytics/graphql-api/) — Event collection endpoints
- Existing codebase analysis — Rules engine patterns, delivery adapter pattern

### Secondary (MEDIUM confidence)
- [oznu/unifi-events](https://github.com/oznu/unifi-events) — Event type enumeration
- [dim13/unifi](https://github.com/dim13/unifi) — Event struct definitions
- [Ubiquiti Community Wiki API](https://ubntwiki.com/products/software/unifi-controller/api) — Community API documentation
- [UniFi SIEM Integration](https://help.ui.com/hc/en-us/articles/33349041044119-UniFi-System-Logs-SIEM-Integration) — CEF format for security events
- [pybreaker](https://github.com/danielfm/pybreaker) — Circuit breaker implementation
- [Adapter pattern for optional dependencies](https://medium.com/@hieutrantrung.it/designing-modular-python-packages-with-adapters-and-optional-dependencies-63efd8b07715)

### Tertiary (LOW confidence, needs validation)
- UniFi API rate limiting — Undocumented, based on community reports; needs production testing
- Cybersecure event format differentiation — Inferred from description; needs subscription access to validate
- Temperature thresholds by device model — Needs hardware-specific research

---
*Research completed: 2026-01-24*
*Ready for roadmap: yes*
