# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-24)

**Core value:** Translate cryptic UniFi logs into understandable findings with actionable remediation steps for serious issues
**Current focus:** v0.3-alpha COMPLETE - State persistence to prevent duplicate event reporting

## Current Position

Phase: Phase 6 - State Persistence (COMPLETE)
Plan: 2 of 2 complete
Status: Phase complete
Last activity: 2026-01-24 - Completed 06-02-PLAN.md (State Integration)

Progress: [██████████] 100% (2/2 plans in phase 6)

## Performance Metrics

**Velocity:**
- Total plans completed: 21
- Average duration: 4 min
- Total execution time: 79 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 4 | 22 min | 6 min |
| 02-log-collection | 3 | 10 min | 3 min |
| 03-analysis-engine | 4 | 19 min | 5 min |
| 04-report-generation | 3 | 10 min | 3 min |
| 05-delivery-scheduling | 5 | 10 min | 2 min |
| 06-state-persistence | 2 | 8 min | 4 min |

**Recent Trend:**
- Last 5 plans: 05-02 (2 min), 05-03 (3 min), 05-04 (3 min), 06-01 (4 min), 06-02 (4 min)
- Trend: Stable at 2-4 min per plan

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Python 3.9+ compatibility (uses Optional[] syntax instead of X | None)
- Custom YamlConfigSettingsSource for proper env > yaml > defaults precedence
- Severity constrained to three levels: low, medium, severe
- All models include metadata field for extensibility
- Finding.source_log_ids links to LogEntry UUIDs
- Device detection probes /status on ports 443, 8443, 11443 in order
- Password never logged at any level, username at DEBUG only
- Tenacity handles retry logic (not hand-rolled) for reliability
- Health file at /tmp/unifi-scanner-health for Docker HEALTHCHECK
- --test mode verifies both config AND connection, not just config
- Events endpoint uses POST with JSON body for query parameters
- 3000 event limit enforced client-side (API maximum)
- Truncation logged as warning when meta.count exceeds data length
- python-dateutil for flexible timestamp parsing
- Millisecond auto-detection: timestamps > 1e12 are milliseconds
- Defensive fallbacks: invalid timestamp -> now(UTC), missing event_type -> UNKNOWN
- Syslog event_type format: SYSLOG_{PROGRAM} in uppercase
- SSH credentials default to API credentials if not set
- Channel timeout via paramiko settimeout() prevents SSH hangs
- Fallback triggers when API returns < min_entries (default 10)
- Unknown event types tracked in Dict[str, int] with counts for debugging
- Template rendering uses SafeDict pattern - missing keys replaced with 'Unknown'
- Remediation only rendered for SEVERE and MEDIUM severity findings
- Device display name falls back: device_name -> device_mac -> 'Unknown device'
- RECURRING_THRESHOLD as module-level constant (Pydantic v2 compatibility)
- Deduplication key is (event_type, device_mac) tuple
- None device_mac is valid deduplication key for system events
- Time-window deduplication default: 1 hour (per user decision)
- Event type variants in rules (EVT_AP_Lost_Contact, EVT_AP_DISCONNECTED)
- Client connect/disconnect events are LOW (too frequent for MEDIUM)
- Unexpected restarts are MEDIUM (warrants investigation)
- Category prefix in all titles: [Security], [Connectivity], [Performance], [System]
- {event_type} placeholder in all descriptions for searchability/Googling
- SEVERE remediation has numbered steps (1., 2., 3.)
- MEDIUM remediation has high-level guidance
- zoneinfo for timezone handling (stdlib Python 3.9+)
- Absolute timestamps with timezone abbreviation (e.g., "Jan 24, 2026 at 9:30 AM EST")
- FindingFormatter for display-ready output conversion
- Jinja2 for HTML/text templating with PackageLoader
- Inline CSS mandatory for email compatibility (email clients strip `<style>` tags)
- Table-based layouts (no flexbox/grid for email)
- UniFi brand colors: #2282FF blue, severity badges (red/orange/gray)
- Tiered detail: SEVERE=full, MEDIUM=summary, LOW=one-liner
- Collapsible LOW section using checkbox/:checked CSS pattern
- PackageLoader for Jinja2 template loading from installed package
- Autoescape enabled for HTML/XML files (security default)
- ReportGenerator composes with FindingFormatter (reuse, not reimplement)
- Text report tiered detail: SEVERE=full, MEDIUM=summary, LOW=one-liner
- Text template hides empty severity sections with {% if %}
- No HTML escaping for .txt files (autoescape only for html/xml)
- BCC-only recipients for email (privacy - recipients cannot see each other)
- Severity-aware subject line: [N SEVERE] prefix when severe_count > 0
- Dual TLS support: port 587 (STARTTLS) and 465 (implicit TLS)
- Email delivery fails gracefully (returns bool, never crashes)
- Atomic file writes via temp file in same directory, then rename
- Retention cleanup runs after each successful save
- Filename format: unifi-report-YYYY-MM-DD-HHMM.ext
- APScheduler 3.x (not 4.0 alpha) for stable blocking scheduler
- CronTrigger.from_crontab() requires explicit timezone parameter
- Misfire grace time 3600s with coalesce=True for missed runs
- One-shot mode: schedule 1s in future with auto-shutdown listener
- DeliveryManager orchestrates email + file with automatic file fallback
- Multi-stage Docker build with python:3.12-slim-bookworm
- Non-root user (appuser) in container for security

**v0.3-alpha context:**
- Skip already-reported events (simple timestamp cutoff, not recurring counts)
- State file in reports dir (simple, uses existing volume mount)
- Reuse FileDelivery._atomic_write() pattern for state persistence
- No new dependencies needed (stdlib json/pathlib/tempfile sufficient)

**Phase 6 decisions:**
- Atomic write via tempfile.mkstemp + shutil.move (same pattern as FileDelivery)
- State file .last_run.json in configurable directory
- Schema version 1.0 in state file for future migration support
- Timezone-naive timestamps rejected (must be UTC-aware)
- Corrupted/invalid state returns None with warning (graceful degradation)
- Client-side timestamp filtering (UniFi API lacks timestamp filter support)
- 5-minute clock skew tolerance for time drift between scanner and controller
- Empty reports still delivered (user confirmation + state update prevents repeats)

### Pending Todos

- ~~Issue #1: Don't Send Previous Logs (v0.3-alpha scope - Phase 6)~~ RESOLVED

### Blockers/Concerns

- Pydantic deprecation warning for json_encoders (future migration needed)
- System Python is 3.9.6, may want to consider pyenv/venv for newer Python
- 2 pre-existing test failures in test_models.py (timezone-aware vs naive datetime assertions)

## Session Continuity

Last session: 2026-01-24
Stopped at: Completed 06-02-PLAN.md (State Integration) - Phase 6 COMPLETE
Resume file: None (v0.3-alpha feature complete)

## v0.3-alpha Release Status

All Phase 6 plans complete. v0.3-alpha feature (state persistence) is ready:

- [x] 06-01: StateManager module with atomic writes
- [x] 06-02: State integration in pipeline with timestamp filtering

**Key deliverables:**
- Service reads last run timestamp before collecting logs
- Service only processes events newer than last successful run
- First run with no state processes events from initial_lookback_hours
- State is only updated after successful delivery
- Empty report (no new events) sends confirmation message
