# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-24)

**Core value:** Translate cryptic UniFi logs into understandable findings with actionable remediation steps for serious issues
**Current focus:** Phase 4 - Reporting (Phase 3 complete)

## Current Position

Phase: 3 of 5 (Analysis Engine) - COMPLETE
Plan: 4 of 4 in current phase (all complete)
Status: Phase complete
Last activity: 2026-01-24 - Completed 03-04-PLAN.md (Templates and Formatter)

Progress: [██████████] 100% (Phase 3 complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 12
- Average duration: 4 min
- Total execution time: 51 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 4 | 22 min | 6 min |
| 02-log-collection | 3 | 10 min | 3 min |
| 03-analysis-engine | 4 | 19 min | 5 min |

**Recent Trend:**
- Last 5 plans: 03-01 (3 min), 03-02 (4 min), 03-03 (4 min), 03-02 (3 min), 03-04 (5 min)
- Trend: Stable

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

### Pending Todos

None yet.

### Blockers/Concerns

- Pydantic deprecation warning for json_encoders (future migration needed)
- System Python is 3.9.6, may want to consider pyenv/venv for newer Python

## Session Continuity

Last session: 2026-01-24T17:16:01Z
Stopped at: Completed 03-04-PLAN.md (Templates and Formatter) - Phase 3 complete
Resume file: None
