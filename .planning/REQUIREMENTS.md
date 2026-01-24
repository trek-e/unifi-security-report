# Requirements: UniFi Scanner

**Defined:** 2026-01-24
**Core Value:** Translate cryptic UniFi logs into understandable findings with actionable remediation steps for serious issues

## v0.3-alpha Requirements

Requirements for duplicate report prevention milestone.

### State Tracking

- [ ] **STATE-01**: Service tracks timestamp of last successful report delivery
- [ ] **STATE-02**: Service only processes events that occurred after last report time
- [ ] **STATE-03**: State persists in reports directory as `.last_run.json`
- [ ] **STATE-04**: State file uses atomic writes to prevent corruption
- [ ] **STATE-05**: Missing state file treated as first run (24h lookback)
- [ ] **STATE-06**: Corrupted state file treated as first run with warning log
- [ ] **STATE-07**: Clock skew tolerance of 5 minutes for late-arriving events

### Configuration

- [ ] **CONF-01**: First-run lookback window configurable via `UNIFI_INITIAL_LOOKBACK_HOURS` (default: 24)
- [ ] **CONF-02**: Empty report sends confirmation message "No new security events since last report"

## Validated Requirements (v0.2-alpha)

These requirements shipped and are working.

### Log Collection
- [x] **COLL-01**: Service connects to UniFi Controller via API
- [x] **COLL-02**: Service auto-detects device type (UDM Pro, UCG Ultra, self-hosted)
- [x] **COLL-03**: Service handles session expiration with automatic re-authentication
- [x] **COLL-04**: Service falls back to SSH when API is insufficient

### Analysis
- [x] **ANLZ-01**: Service categorizes issues by severity (low, medium, severe)
- [x] **ANLZ-02**: Service generates plain English explanations for log events
- [x] **ANLZ-03**: Service provides step-by-step remediation for severe issues
- [x] **ANLZ-04**: Service deduplicates repeated events and shows occurrence counts

### Reports
- [x] **REPT-01**: Service generates HTML formatted reports
- [x] **REPT-02**: Service generates plain text reports
- [x] **REPT-03**: Service delivers reports via SMTP email
- [x] **REPT-04**: Service saves reports to configurable directory

### Deployment
- [x] **DEPL-01**: Service runs as Docker container
- [x] **DEPL-02**: Service configurable via environment variables
- [x] **DEPL-03**: Service supports YAML configuration file
- [x] **DEPL-04**: Service runs on configurable schedule (daily/weekly)

## Future Requirements

Deferred to later milestones. Tracked but not in current roadmap.

### Dashboard (v2+)
- **DASH-01**: Integration with Grafana for visualization
- **DASH-02**: Real-time metrics display
- **DASH-03**: Historical trend analysis

### Advanced Features (v2+)
- **ADVN-01**: Multi-gateway support
- **ADVN-02**: Custom rule creation
- **ADVN-03**: Real-time alerting (push notifications)
- **ADVN-04**: Network health scoring

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Automatic remediation | Risk of breaking network; recommendations only |
| Dashboard UI in v1 | Scope creep; reports are faster to ship |
| Mobile app | Web/email reports sufficient for v1 |
| Real-time streaming | Batch polling fits use case; adds complexity |
| Multi-network support | Architectural change; v1 is single gateway |
| Raw log display | Defeats purpose of plain English translation |
| Event ID tracking | UniFi API may not provide stable IDs; timestamp sufficient |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| STATE-01 | Phase 6 | Pending |
| STATE-02 | Phase 6 | Pending |
| STATE-03 | Phase 6 | Pending |
| STATE-04 | Phase 6 | Pending |
| STATE-05 | Phase 6 | Pending |
| STATE-06 | Phase 6 | Pending |
| STATE-07 | Phase 6 | Pending |
| CONF-01 | Phase 6 | Pending |
| CONF-02 | Phase 6 | Pending |

**Coverage:**
- v0.3-alpha requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-24 (v0.1/v0.2)*
*Last updated: 2026-01-24 after v0.3-alpha milestone start*
