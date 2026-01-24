# Roadmap: UniFi Scanner

## Overview

UniFi Scanner transforms from empty repository to production-ready containerized service across five phases. The journey starts with reliable UniFi API integration (the hardest technical challenge), builds through log parsing and analysis (the core intelligence), and delivers through reports and scheduling (the user-facing value). Each phase delivers verifiable capability, culminating in a Docker container that polls UniFi logs and emails plain-English reports on schedule.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation & API Connection** - Establish reliable UniFi integration with config, models, and authentication
- [ ] **Phase 2: Log Collection & Parsing** - Fetch and normalize logs via API and SSH fallback
- [ ] **Phase 3: Analysis Engine** - Detect issues, assign severity, generate explanations and remediation
- [ ] **Phase 4: Report Generation** - Create human-readable HTML and text reports from findings
- [ ] **Phase 5: Delivery & Scheduling** - Email reports, save files, run on schedule in Docker

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
**Plans**: TBD

Plans:
- [ ] 01-01: Project scaffolding and configuration system
- [ ] 01-02: Core data models with Pydantic validation
- [ ] 01-03: UniFi API client with device detection
- [ ] 01-04: Session management and auto re-authentication

### Phase 2: Log Collection & Parsing
**Goal**: Service can fetch logs from any UniFi device and normalize them into structured LogEntry objects
**Depends on**: Phase 1
**Requirements**: COLL-04
**Success Criteria** (what must be TRUE):
  1. Service retrieves events and alarms from UniFi API
  2. Service parses multiple log formats (syslog, JSON) into normalized LogEntry objects
  3. Service falls back to SSH when API log access is insufficient
  4. All timestamps are normalized to UTC regardless of source format
**Plans**: TBD

Plans:
- [ ] 02-01: API-based log collection (events, alarms)
- [ ] 02-02: Multi-format log parser with defensive parsing
- [ ] 02-03: SSH fallback for direct log access

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
**Plans**: TBD

Plans:
- [ ] 03-01: Rules engine architecture with pattern matching
- [ ] 03-02: Initial rule set for common issues (security, connectivity, performance)
- [ ] 03-03: Finding store with deduplication
- [ ] 03-04: Plain English explanation and remediation templates

### Phase 4: Report Generation
**Goal**: Service can transform findings into professionally formatted, human-readable reports
**Depends on**: Phase 3
**Requirements**: REPT-01, REPT-02
**Success Criteria** (what must be TRUE):
  1. Service generates HTML formatted reports with severity-based sections
  2. Service generates plain text reports for email fallback
  3. Reports present severe issues first with remediation steps, then medium, then low
  4. Reports include summary section with issue counts by severity
**Plans**: TBD

Plans:
- [ ] 04-01: Jinja2 template system setup
- [ ] 04-02: HTML report template with styling
- [ ] 04-03: Plain text report template

### Phase 5: Delivery & Scheduling
**Goal**: Service runs as a scheduled Docker container that delivers reports via email and file
**Depends on**: Phase 4
**Requirements**: REPT-03, REPT-04, DEPL-01, DEPL-04
**Success Criteria** (what must be TRUE):
  1. Service sends reports via SMTP email (HTML with plaintext fallback)
  2. Service saves reports to configurable directory
  3. Service runs as Docker container with all dependencies bundled
  4. Service executes on configurable schedule (daily/weekly) without manual intervention
  5. Service handles delivery failures gracefully with retry logic
**Plans**: TBD

Plans:
- [ ] 05-01: SMTP email delivery system
- [ ] 05-02: File output with configurable paths
- [ ] 05-03: APScheduler integration for cron-style scheduling
- [ ] 05-04: Docker container build and deployment
- [ ] 05-05: End-to-end integration testing

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & API Connection | 0/4 | Not started | - |
| 2. Log Collection & Parsing | 0/3 | Not started | - |
| 3. Analysis Engine | 0/4 | Not started | - |
| 4. Report Generation | 0/3 | Not started | - |
| 5. Delivery & Scheduling | 0/5 | Not started | - |

---
*Roadmap created: 2026-01-24*
*Depth: comprehensive*
*Total requirements: 16 | Total phases: 5 | Total plans: 19*
