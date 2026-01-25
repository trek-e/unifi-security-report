# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-24)

**Core value:** Translate cryptic UniFi logs into understandable findings with actionable remediation steps for serious issues
**Current focus:** v0.3.2-alpha — Enhanced Security Analysis

## Current Position

Phase: 8 of 13 (Enhanced Security Analysis)
Plan: 5 of 5 in current phase
Status: Phase Complete (Verified)
Last activity: 2026-01-25 — Completed 08-05-PLAN.md (Remediation Wiring Gap Closure)

Progress: [##################..] 90% (9/13 phases complete, Phase 8 VERIFIED)

## Milestones

| Version | Name | Phases | Status |
|---------|------|--------|--------|
| v0.2-alpha | Production Ready | 1-5 | SHIPPED 2026-01-24 |
| v0.3-alpha | No Duplicate Reports | 6 | SHIPPED 2026-01-24 |
| v0.3.1-alpha | Extended Wireless Analysis | 7 | SHIPPED 2026-01-25 |
| v0.3.2-alpha | Enhanced Security Analysis | 8 | SHIPPED 2026-01-25 |
| v0.3.3-alpha | Device Health Monitoring | 9 | Planned |
| v0.3.4-alpha | Integration Infrastructure | 10 | Planned |
| v0.3.15-alpha | WebSocket Support | 13 | SHIPPED 2026-01-25 |
| v0.3.5-alpha | Cloudflare Integration | 11 | Planned |
| v0.4-alpha | Cybersecure Integration | 12 | Planned |

See `.planning/MILESTONES.md` for full milestone history.

## Performance Metrics

**Velocity:**
- Total plans completed: 34
- Average duration: 4 min
- Total execution time: 134 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 4 | 22 min | 6 min |
| 02-log-collection | 3 | 10 min | 3 min |
| 03-analysis-engine | 4 | 19 min | 5 min |
| 04-report-generation | 3 | 10 min | 3 min |
| 05-delivery-scheduling | 5 | 10 min | 2 min |
| 06-state-persistence | 2 | 8 min | 4 min |
| 07-extended-wireless | 3 | 10 min | 3 min |
| 13-websocket-support | 6 | 29 min | 5 min |
| 08-enhanced-security | 5 | 24 min | 5 min |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v0.3-alpha]: Atomic state writes with tempfile.mkstemp + shutil.move
- [v0.3-alpha]: Client-side timestamp filtering (UniFi API lacks filter support)
- [v0.3-alpha]: 5-minute clock skew tolerance for time drift
- [v0.3.1-alpha]: DFS radar uses pattern matching (EVT_AP_Interference is generic)
- [v0.3.1-alpha]: RSSI thresholds: -50 Excellent, -60 Good, -70 Fair, -80 Poor
- [v0.3.1-alpha]: Flapping threshold: 5+ roams per client per analysis window
- [v0.3.1-alpha]: Template context variables used by rule templates (07-03 gap closure)
- [v0.3.15-alpha]: WebSocket max_size parameter uses underscore for consistency
- [v0.3.15-alpha]: WebSocket endpoint strips trailing slashes to prevent double slashes
- [v0.3.15-alpha]: WebSocketManager uses daemon thread with isolated event loop
- [v0.3.15-alpha]: WSLogCollector uses same 5-minute clock skew as APILogCollector
- [v0.3.15-alpha]: Cookie extraction filters None values for type safety
- [v0.3.15-alpha]: WS events merge with REST events using (timestamp, message) deduplication
- [v0.3.15-alpha]: WebSocket enabled by default (True) to support UniFi 10.x+ out of box
- [v0.3.15-alpha]: WebSocket manager persists across report cycles at module level
- [v0.3.2-alpha]: Pydantic IPSEvent over dataclass for validation consistency
- [v0.3.2-alpha]: 24 ET category mappings from Emerging Threats documentation
- [v0.3.2-alpha]: Unknown actions default to detected (not blocked) for safety
- [v0.3.2-alpha]: Deduplication by signature only (not signature+source_ip) - one threat entry with multiple source IPs
- [v0.3.2-alpha]: Detection mode note appears only when ALL events are detected-only
- [v0.3.2-alpha]: Int severity (1,2,3) from pydantic model converted to Severity enum for output
- [v0.3.2-alpha]: SafeDict returns [key] placeholder for missing template variables
- [v0.3.2-alpha]: Remediation templates cover 20+ ET categories with severity-adjusted detail
- [v0.3.2-alpha]: False positive notes only for categories with common benign triggers
- [v0.3.2-alpha]: IPS analysis is optional - failures don't prevent report generation
- [v0.3.2-alpha]: Raw IPS events fetched separately for dedicated IPSAnalyzer processing
- [v0.3.2-alpha]: Remediation uses first source IP from grouped threats as context
- [v0.3.2-alpha]: Remediation shown only for detected threats in templates (blocked threats stopped)

### Pending Todos

None yet.

### Blockers/Concerns

- UniFi Network 10.x deprecated `/stat/event` REST endpoint; WiFi events now require WebSocket connection (Phase 13)

### Roadmap Evolution

- Phase 13 added: WebSocket support for UniFi Network 10.x events

## Git Workflow

**Branch Strategy:** Keep alpha branches separate until v0.5 release
- Each version gets its own branch: `alpha-0.3.2`, `alpha-0.4`, `alpha-0.5`
- Do NOT merge to `main` until user approves at v0.5
- Create PRs for visibility but keep open until release

**Current branches:**
- `main` - contains v0.3.1a1 (merged during troubleshooting session 2026-01-25)
- `alpha-0.3.1` - Phase 7 work
- Future: `alpha-0.3.2` for Phase 8, etc.

## Session Continuity

Last session: 2026-01-25
Stopped at: Completed 08-05-PLAN.md (Remediation Wiring Gap Closure)
Resume file: None (Phase 8 fully complete with gap closure)

## Next Steps

Phase 8 (Enhanced Security Analysis) fully complete with remediation gap closed. Ready for Phase 9 (Device Health Monitoring) or version bump to v0.3.2-alpha.
