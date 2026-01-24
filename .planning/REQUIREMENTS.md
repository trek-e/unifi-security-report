# Requirements: UniFi Scanner

**Defined:** 2026-01-24
**Core Value:** Translate cryptic UniFi logs into understandable findings with actionable remediation steps for serious issues

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Log Collection

- [x] **COLL-01**: Service connects to UniFi Controller via API
- [x] **COLL-02**: Service auto-detects device type (UDM Pro, UCG Ultra, self-hosted)
- [x] **COLL-03**: Service handles session expiration with automatic re-authentication
- [x] **COLL-04**: Service falls back to SSH when API is insufficient

### Analysis

- [ ] **ANLZ-01**: Service categorizes issues by severity (low, medium, severe)
- [ ] **ANLZ-02**: Service generates plain English explanations for log events
- [ ] **ANLZ-03**: Service provides step-by-step remediation for severe issues
- [ ] **ANLZ-04**: Service deduplicates repeated events and shows occurrence counts

### Reports

- [ ] **REPT-01**: Service generates HTML formatted reports
- [ ] **REPT-02**: Service generates plain text reports
- [ ] **REPT-03**: Service delivers reports via SMTP email
- [ ] **REPT-04**: Service saves reports to configurable directory

### Deployment

- [ ] **DEPL-01**: Service runs as Docker container
- [x] **DEPL-02**: Service configurable via environment variables
- [x] **DEPL-03**: Service supports YAML configuration file
- [ ] **DEPL-04**: Service runs on configurable schedule (daily/weekly)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Dashboard

- **DASH-01**: Integration with Grafana for visualization
- **DASH-02**: Real-time metrics display
- **DASH-03**: Historical trend analysis

### Advanced Features

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

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| COLL-01 | Phase 1 | Complete |
| COLL-02 | Phase 1 | Complete |
| COLL-03 | Phase 1 | Complete |
| COLL-04 | Phase 2 | Complete |
| ANLZ-01 | Phase 3 | Pending |
| ANLZ-02 | Phase 3 | Pending |
| ANLZ-03 | Phase 3 | Pending |
| ANLZ-04 | Phase 3 | Pending |
| REPT-01 | Phase 4 | Pending |
| REPT-02 | Phase 4 | Pending |
| REPT-03 | Phase 5 | Pending |
| REPT-04 | Phase 5 | Pending |
| DEPL-01 | Phase 5 | Pending |
| DEPL-02 | Phase 1 | Complete |
| DEPL-03 | Phase 1 | Complete |
| DEPL-04 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---
*Requirements defined: 2026-01-24*
*Last updated: 2026-01-24 after Phase 2 completion*
