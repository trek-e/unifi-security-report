# Roadmap: UniFi Scanner

## Milestones

- **v0.2-alpha** -- Phases 1-5 (shipped 2026-01-24) -- Production-ready containerized service
- **v0.3-alpha** -- Phase 6 (shipped 2026-01-24) -- State persistence to prevent duplicate events
- **v0.3.1-alpha** -- Phase 7 (planned) -- Extended wireless analysis
- **v0.3.2-alpha** -- Phase 8 (planned) -- Enhanced security analysis
- **v0.3.3-alpha** -- Phase 9 (planned) -- Device health monitoring
- **v0.3.4-alpha** -- Phase 10 (planned) -- Integration infrastructure
- **v0.3.15-alpha** -- Phase 13 (planned) -- WebSocket support for UniFi Network 10.x events
- **v0.3.5-alpha** -- Phase 11 (planned) -- Cloudflare integration
- **v0.4-alpha** -- Phase 12 (planned) -- Cybersecure integration

See `.planning/MILESTONES.md` for detailed milestone history.
See `.planning/milestones/` for archived roadmap and requirements per milestone.

## Phases

<details>
<summary>v0.2-alpha Production Ready (Phases 1-5) -- SHIPPED 2026-01-24</summary>

- [x] Phase 1: Foundation & API Connection (4/4 plans) -- completed 2026-01-24
- [x] Phase 2: Log Collection & Parsing (3/3 plans) -- completed 2026-01-24
- [x] Phase 3: Analysis Engine (4/4 plans) -- completed 2026-01-24
- [x] Phase 4: Report Generation (3/3 plans) -- completed 2026-01-24
- [x] Phase 5: Delivery & Scheduling (5/5 plans) -- completed 2026-01-24

</details>

<details>
<summary>v0.3-alpha No Duplicate Reports (Phase 6) -- SHIPPED 2026-01-24</summary>

- [x] Phase 6: State Persistence (2/2 plans) -- completed 2026-01-24

</details>

<details>
<summary>v0.3.1-alpha Extended Wireless Analysis (Phase 7) -- SHIPPED 2026-01-25</summary>

- [x] Phase 7: Extended Wireless Analysis (3/3 plans) -- completed 2026-01-25

</details>

### v0.3.2-alpha Enhanced Security Analysis (Planned)

- [ ] **Phase 8: Enhanced Security Analysis** - Suricata signature parsing, threat categorization, source IP summaries

### v0.3.3-alpha Device Health Monitoring (Planned)

- [ ] **Phase 9: Device Health Monitoring** - Temperature monitoring, PoE events, uptime tracking, resource alerts

### v0.3.4-alpha Integration Infrastructure (Planned)

- [ ] **Phase 10: Integration Infrastructure** - Optional integration framework, failure isolation, circuit breakers

### v0.3.15-alpha WebSocket Support (Planned)

- [ ] **Phase 13: WebSocket Support** - Real-time event streaming for UniFi Network 10.x compatibility

### v0.3.5-alpha Cloudflare Integration (Planned)

- [ ] **Phase 11: Cloudflare Integration** - WAF events, DNS analytics, tunnel status monitoring

### v0.4-alpha Cybersecure Integration (Planned)

- [ ] **Phase 12: Cybersecure Integration** - Subscription detection, enhanced signatures, threat badging

## Phase Details

### Phase 7: Extended Wireless Analysis
**Goal**: Users gain visibility into wireless client behavior and AP radio changes
**Depends on**: Phase 6 (existing rules engine foundation)
**Requirements**: WIFI-01, WIFI-02, WIFI-03, WIFI-04, WIFI-05, WIFI-06
**Success Criteria** (what must be TRUE):
  1. Report shows client roaming events between APs with source/destination AP names
  2. Report shows band switching events (2.4GHz to 5GHz and vice versa)
  3. Report shows AP channel changes with explanation of why channel changed
  4. Report flags DFS radar events as warnings requiring attention
  5. Report translates RSSI values to human-readable signal quality (Excellent/Good/Fair/Poor)
**Plans**: 3 plans

Plans:
- [x] 07-01-PLAN.md — WIRELESS category and rules for roaming, band switch, channel change, DFS radar (WIFI-01 through WIFI-04)
- [x] 07-02-PLAN.md — RSSI quality translation and flapping detection (WIFI-05, WIFI-06)
- [x] 07-03-PLAN.md — Gap closure: Update templates to use context variables (template output fixes)

### Phase 8: Enhanced Security Analysis
**Goal**: Users understand IDS/IPS alerts in plain English with actionable context
**Depends on**: Phase 7 (extends existing security rules)
**Requirements**: SECR-01, SECR-02, SECR-03, SECR-04, SECR-05
**Success Criteria** (what must be TRUE):
  1. Report shows Suricata signature categories (ET SCAN, ET MALWARE, etc.) in plain English
  2. Report clearly distinguishes blocked threats from detected-only threats
  3. Report summarizes top threat source IPs with count of events per IP
  4. Report provides category-specific remediation guidance for security findings
**Plans**: TBD

Plans:
- [ ] 08-01: TBD
- [ ] 08-02: TBD

### Phase 9: Device Health Monitoring
**Goal**: Users receive proactive alerts about device health before failures occur
**Depends on**: Phase 8 (parallel data collection pattern)
**Requirements**: HLTH-01, HLTH-02, HLTH-03, HLTH-04, HLTH-05
**Success Criteria** (what must be TRUE):
  1. Report shows device temperatures with warnings when exceeding safe thresholds
  2. Report shows PoE disconnect and overload events with affected port identification
  3. Report shows device uptime with flags for devices needing restart
  4. Report alerts on high CPU/memory utilization before performance degrades
**Plans**: TBD

Plans:
- [ ] 09-01: TBD
- [ ] 09-02: TBD

### Phase 10: Integration Infrastructure
**Goal**: Framework for optional integrations that fail gracefully without affecting core functionality
**Depends on**: Phase 9 (prepares for external integrations)
**Requirements**: INTG-01, INTG-02, INTG-03
**Success Criteria** (what must be TRUE):
  1. Integrations that are not configured are silently skipped (no errors in logs)
  2. One integration failing does not prevent other integrations from running
  3. External API failures trigger circuit breakers that fail fast and recover automatically
**Plans**: TBD

Plans:
- [ ] 10-01: TBD

### Phase 11: Cloudflare Integration
**Goal**: Users with Cloudflare see WAF and DNS events in their UniFi security report
**Depends on**: Phase 10 (requires integration infrastructure)
**Requirements**: CLDF-01, CLDF-02, CLDF-03, CLDF-04
**Success Criteria** (what must be TRUE):
  1. When Cloudflare credentials are configured, service connects and authenticates successfully
  2. Report shows WAF block events from Cloudflare with threat details
  3. Report shows DNS analytics including blocked query counts
  4. Report shows Cloudflare tunnel status (up/down) when tunnels exist
**Plans**: TBD

Plans:
- [ ] 11-01: TBD
- [ ] 11-02: TBD

### Phase 12: Cybersecure Integration
**Goal**: Users with Cybersecure subscription see enhanced threat intelligence in reports
**Depends on**: Phase 10 (requires integration infrastructure)
**Requirements**: CYBS-01, CYBS-02, CYBS-03
**Success Criteria** (what must be TRUE):
  1. Service detects whether Cybersecure subscription is active on the gateway
  2. Findings from enhanced Cybersecure signatures are marked as such in report
  3. Cybersecure-powered findings display a badge indicating premium threat intelligence
**Plans**: TBD

Plans:
- [ ] 12-01: TBD

### Phase 13: WebSocket Support
**Goal**: Users running UniFi Network 10.x+ receive WiFi events via WebSocket API
**Depends on**: Phase 8 (core analysis engine must handle new event source)
**Requirements**: WS-01, WS-02, WS-03, WS-04
**Success Criteria** (what must be TRUE):
  1. Service connects to UniFi WebSocket endpoint after REST API authentication
  2. WiFi events (roaming, connections, disconnections) stream in real-time
  3. Events are buffered and processed on report generation schedule
  4. Graceful fallback to REST API for controllers that don't support WebSocket
**Plans**: 6 plans

Plans:
- [x] 13-01-PLAN.md — Core WebSocket client with cookie auth and event buffer
- [x] 13-02-PLAN.md — TDD: Event parsing and buffer tests
- [ ] 13-03-PLAN.md — WebSocket manager and WS log collector
- [ ] 13-04-PLAN.md — Collector fallback chain integration (WS -> REST -> SSH)
- [ ] 13-05-PLAN.md — Service lifecycle and configuration
- [ ] 13-06-PLAN.md — Integration tests and verification

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation & API Connection | v0.2-alpha | 4/4 | Complete | 2026-01-24 |
| 2. Log Collection & Parsing | v0.2-alpha | 3/3 | Complete | 2026-01-24 |
| 3. Analysis Engine | v0.2-alpha | 4/4 | Complete | 2026-01-24 |
| 4. Report Generation | v0.2-alpha | 3/3 | Complete | 2026-01-24 |
| 5. Delivery & Scheduling | v0.2-alpha | 5/5 | Complete | 2026-01-24 |
| 6. State Persistence | v0.3-alpha | 2/2 | Complete | 2026-01-24 |
| 7. Extended Wireless Analysis | v0.3.1-alpha | 3/3 | Complete | 2026-01-25 |
| 8. Enhanced Security Analysis | v0.3.2-alpha | 0/TBD | Not started | - |
| 9. Device Health Monitoring | v0.3.3-alpha | 0/TBD | Not started | - |
| 10. Integration Infrastructure | v0.3.4-alpha | 0/TBD | Not started | - |
| 11. Cloudflare Integration | v0.3.5-alpha | 0/TBD | Not started | - |
| 12. Cybersecure Integration | v0.4-alpha | 0/TBD | Not started | - |
| 13. WebSocket Support | v0.3.15-alpha | 2/6 | In progress | - |

**Summary:** 13 phases total -- 7 complete, 6 planned across v0.3.2 through v0.4

---
*Roadmap created: 2026-01-24*
*v0.2-alpha complete: 2026-01-24*
*v0.3-alpha complete: 2026-01-24*
*v0.3.1 through v0.4 roadmap created: 2026-01-24*
*Phase 13 planned: 2026-01-25*
