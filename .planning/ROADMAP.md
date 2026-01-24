# Roadmap: UniFi Scanner

## Overview

UniFi Scanner transforms from empty repository to production-ready containerized service. v0.2-alpha delivered core functionality across five phases: UniFi API integration, log parsing, analysis engine, report generation, and scheduled delivery. v0.3-alpha adds state persistence to prevent duplicate event reporting across runs.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

### v0.2-alpha (Complete)
- [x] **Phase 1: Foundation & API Connection** - Establish reliable UniFi integration with config, models, and authentication
- [x] **Phase 2: Log Collection & Parsing** - Fetch and normalize logs via API and SSH fallback
- [x] **Phase 3: Analysis Engine** - Detect issues, assign severity, generate explanations and remediation
- [x] **Phase 4: Report Generation** - Create human-readable HTML and text reports from findings
- [x] **Phase 5: Delivery & Scheduling** - Email reports, save files, run on schedule in Docker

### v0.3-alpha (Current)
- [ ] **Phase 6: State Persistence** - Track last report timestamp to prevent duplicate event reporting

## Phase Details

### Phase 1: Foundation & API Connection
**Goal**: Service can authenticate with UniFi Controller and maintain a stable connection across sessions
**Depends on**: Nothing (first phase)
**Requirements**: COLL-01, COLL-02, COLL-03, DEPL-02, DEPL-03
**Success Criteria** (what must be TRUE):
  1. Service connects to UniFi Controller using local admin credentials
  2. Service auto-detects device type (UDM Pro, UCG Ultra, self-hosted) and uses correct API endpoints
  3. Service automatically re-authenticates when session expires (no manual intervention)
  4. Service is configurable via environment variables and YAML config file
  5. Core data models exist for LogEntry, Finding, and Report
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffolding and configuration system
- [x] 01-02-PLAN.md — Core data models with Pydantic validation
- [x] 01-03-PLAN.md — UniFi API client with device detection
- [x] 01-04-PLAN.md — Session management and auto re-authentication

### Phase 2: Log Collection & Parsing
**Goal**: Service can fetch logs from any UniFi device and normalize them into structured LogEntry objects
**Depends on**: Phase 1
**Requirements**: COLL-04
**Success Criteria** (what must be TRUE):
  1. Service retrieves events and alarms from UniFi API
  2. Service parses multiple log formats (syslog, JSON) into normalized LogEntry objects
  3. Service falls back to SSH when API log access is insufficient
  4. All timestamps are normalized to UTC regardless of source format
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — API-based log collection (events, alarms endpoints)
- [x] 02-02-PLAN.md — Multi-format parser with UTC normalization and defensive parsing
- [x] 02-03-PLAN.md — SSH fallback collector with orchestration

### Phase 3: Analysis Engine
**Goal**: Service can analyze logs, detect issues, categorize by severity, and generate human-readable explanations
**Depends on**: Phase 2
**Requirements**: ANLZ-01, ANLZ-02, ANLZ-03, ANLZ-04
**Success Criteria** (what must be TRUE):
  1. Service categorizes detected issues as low, medium, or severe
  2. Service generates plain English explanations for all detected issues (no jargon)
  3. Service provides step-by-step remediation guidance for severe issues
  4. Service deduplicates repeated events and displays occurrence counts
  5. Unknown log patterns are captured gracefully without crashing
**Plans**: 4 plans

Plans:
- [x] 03-01-PLAN.md — Rules engine architecture with pattern matching and dictionary dispatch
- [x] 03-02-PLAN.md — Initial rule set for security, connectivity, performance, and system categories
- [x] 03-03-PLAN.md — Finding store with 1-hour time-window deduplication
- [x] 03-04-PLAN.md — Plain English explanation and remediation templates with FindingFormatter

### Phase 4: Report Generation
**Goal**: Service can transform findings into professionally formatted, human-readable reports
**Depends on**: Phase 3
**Requirements**: REPT-01, REPT-02
**Success Criteria** (what must be TRUE):
  1. Service generates HTML formatted reports with severity-based sections
  2. Service generates plain text reports for email fallback
  3. Reports present severe issues first with remediation steps, then medium, then low
  4. Reports include summary section with issue counts by severity
**Plans**: 3 plans

Plans:
- [x] 04-01-PLAN.md — Jinja2 template system setup with ReportGenerator foundation
- [x] 04-02-PLAN.md — HTML report templates with UniFi styling and email compatibility
- [x] 04-03-PLAN.md — Plain text report template with tiered detail levels

### Phase 5: Delivery & Scheduling
**Goal**: Service runs as a scheduled Docker container that delivers reports via email and file
**Depends on**: Phase 4
**Requirements**: REPT-03, REPT-04, DEPL-01, DEPL-04
**Success Criteria** (what must be TRUE):
  1. Service sends reports via SMTP email (HTML with plaintext fallback)
  2. Service saves reports to configurable directory
  3. Service runs as Docker container with all dependencies bundled
  4. Service executes on configurable schedule (daily/weekly) without manual intervention
  5. Service handles delivery failures gracefully with file fallback
**Plans**: 5 plans

Plans:
- [x] 05-01-PLAN.md — SMTP email delivery with BCC recipients and severity-aware subjects
- [x] 05-02-PLAN.md — File output with datetime naming and retention cleanup
- [x] 05-03-PLAN.md — APScheduler integration with cron expressions and presets
- [x] 05-04-PLAN.md — Docker container build and service integration
- [x] 05-05-PLAN.md — End-to-end integration testing with human verification

### Phase 6: State Persistence
**Goal**: Service tracks last successful report and only processes new events to prevent duplicate reporting
**Depends on**: Phase 5
**Requirements**: STATE-01, STATE-02, STATE-03, STATE-04, STATE-05, STATE-06, STATE-07, CONF-01, CONF-02
**Success Criteria** (what must be TRUE):
  1. Service remembers when the last successful report was delivered and uses it as the timestamp cutoff for the next run
  2. User sees no duplicate events across multiple scheduled runs (same event never appears in two reports)
  3. First-time service startup processes events from the last 24 hours (or configurable initial lookback)
  4. If state file is corrupted or missing, service logs a warning and falls back to default lookback (no crash)
**Plans**: 2 plans

Plans:
- [ ] 06-01-PLAN.md — StateManager module with atomic writes and configuration
- [ ] 06-02-PLAN.md — Log collector integration and pipeline state lifecycle

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & API Connection | 4/4 | Complete | 2026-01-24 |
| 2. Log Collection & Parsing | 3/3 | Complete | 2026-01-24 |
| 3. Analysis Engine | 4/4 | Complete | 2026-01-24 |
| 4. Report Generation | 3/3 | Complete | 2026-01-24 |
| 5. Delivery & Scheduling | 5/5 | Complete | 2026-01-24 |
| 6. State Persistence | 0/2 | Planned | — |

---
*Roadmap created: 2026-01-24 (v0.2-alpha)*
*Phase 1 planned: 2026-01-24*
*Phase 1 complete: 2026-01-24*
*Phase 2 planned: 2026-01-24*
*Phase 2 complete: 2026-01-24*
*Phase 3 planned: 2026-01-24*
*Phase 3 complete: 2026-01-24*
*Phase 4 planned: 2026-01-24*
*Phase 4 complete: 2026-01-24*
*Phase 5 planned: 2026-01-24*
*Phase 5 complete: 2026-01-24*
*v0.3-alpha Phase 6 added: 2026-01-24*
*Phase 6 planned: 2026-01-24*
*Depth: comprehensive*
*Total requirements: 25 (16 v0.2 + 9 v0.3) | Total phases: 6 | Total plans: 21*
