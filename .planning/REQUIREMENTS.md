# Requirements: UniFi Scanner

**Defined:** 2026-01-24
**Core Value:** Translate cryptic UniFi logs into understandable findings with actionable remediation steps for serious issues

## v0.4-alpha Requirements

Requirements for extended analysis rules and optional integrations milestone.

### Wireless Analysis

- [x] **WIFI-01**: Service detects client roaming events between APs
- [x] **WIFI-02**: Service detects radio band switching (2.4GHz to 5GHz and vice versa)
- [x] **WIFI-03**: Service detects AP channel changes with reason
- [x] **WIFI-04**: Service detects DFS radar events requiring channel evacuation
- [x] **WIFI-05**: Service translates RSSI values to signal quality (Excellent/Good/Fair/Poor)
- [x] **WIFI-06**: Service detects excessive client roaming (flapping) as warning

### Security Analysis (IDS/IPS)

- [x] **SECR-01**: Service parses Suricata signature categories from IPS alerts
- [x] **SECR-02**: Service provides plain English explanations for threat categories
- [x] **SECR-03**: Service distinguishes between blocked and detected threats
- [x] **SECR-04**: Service summarizes top threat source IPs in report
- [x] **SECR-05**: Service provides category-specific remediation guidance

### Device Health

- [x] **HLTH-01**: Service monitors device temperatures via stat/device polling
- [x] **HLTH-02**: Service detects PoE disconnect events
- [x] **HLTH-03**: Service detects PoE overload/power budget exceeded events
- [x] **HLTH-04**: Service tracks and reports device uptime
- [x] **HLTH-05**: Service alerts on high CPU/memory utilization

### Integration Infrastructure

- [ ] **INTG-01**: Service supports optional integrations that gracefully skip if not configured
- [ ] **INTG-02**: Service isolates integration failures (one failing doesn't break others)
- [ ] **INTG-03**: Service implements circuit breakers for external API calls

### Cybersecure Integration (Optional)

- [ ] **CYBS-01**: Service detects if Cybersecure subscription is active
- [ ] **CYBS-02**: Service marks findings with enhanced signature coverage when Cybersecure active
- [ ] **CYBS-03**: Service shows Cybersecure badge on threat findings when applicable

### Cloudflare Integration (Optional)

- [ ] **CLDF-01**: Service connects to Cloudflare API when credentials configured
- [ ] **CLDF-02**: Service retrieves WAF block events from Cloudflare
- [ ] **CLDF-03**: Service retrieves DNS analytics (blocked queries) from Cloudflare
- [ ] **CLDF-04**: Service monitors Cloudflare tunnel status if tunnels exist

### WebSocket Support

- [ ] **WS-01**: Service connects to UniFi WebSocket endpoint after REST API authentication
- [ ] **WS-02**: Service receives WiFi events (roaming, connections, disconnections) via WebSocket
- [ ] **WS-03**: Service buffers WebSocket events and processes on report generation schedule
- [ ] **WS-04**: Service gracefully falls back to REST API when WebSocket unavailable

## Future Requirements

Deferred to later milestones.

### Advanced Wireless (v0.5+)
- **WIFI-07**: Interference pattern detection
- **WIFI-08**: Wireless survey recommendations

### Advanced Security (v0.5+)
- **SECR-06**: Threat intelligence enrichment (IP reputation lookup)
- **SECR-07**: Anomaly detection for unusual traffic patterns

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Real-time alerting | v1 is periodic reports only |
| Automatic remediation | Recommendations only, no auto-fix |
| Multi-gateway support | v1 is single gateway |
| Custom rule creation UI | Users edit code if needed |
| Historical trend graphs | Reports are point-in-time; dashboard is v2 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| WIFI-01 | Phase 7 | Complete |
| WIFI-02 | Phase 7 | Complete |
| WIFI-03 | Phase 7 | Complete |
| WIFI-04 | Phase 7 | Complete |
| WIFI-05 | Phase 7 | Complete |
| WIFI-06 | Phase 7 | Complete |
| SECR-01 | Phase 8 | Complete |
| SECR-02 | Phase 8 | Complete |
| SECR-03 | Phase 8 | Complete |
| SECR-04 | Phase 8 | Complete |
| SECR-05 | Phase 8 | Complete |
| HLTH-01 | Phase 9 | Complete |
| HLTH-02 | Phase 9 | Complete |
| HLTH-03 | Phase 9 | Complete |
| HLTH-04 | Phase 9 | Complete |
| HLTH-05 | Phase 9 | Complete |
| INTG-01 | Phase 10 | Pending |
| INTG-02 | Phase 10 | Pending |
| INTG-03 | Phase 10 | Pending |
| CLDF-01 | Phase 11 | Pending |
| CLDF-02 | Phase 11 | Pending |
| CLDF-03 | Phase 11 | Pending |
| CLDF-04 | Phase 11 | Pending |
| CYBS-01 | Phase 12 | Pending |
| CYBS-02 | Phase 12 | Pending |
| CYBS-03 | Phase 12 | Pending |
| WS-01 | Phase 13 | Pending |
| WS-02 | Phase 13 | Pending |
| WS-03 | Phase 13 | Pending |
| WS-04 | Phase 13 | Pending |

**Coverage:**
- v0.5-alpha requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0

---
*Requirements defined: 2026-01-24*
*Last updated: 2026-01-25 after Phase 9 completion*
