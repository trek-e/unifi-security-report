# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-24)

**Core value:** Translate cryptic UniFi logs into understandable findings with actionable remediation steps for serious issues
**Current focus:** v0.4-alpha — Cybersecure Integration

## Current Position

Phase: 12 of 13 (Cybersecure Integration)
Plan: 3 of 3 in current phase
Status: Phase complete
Last activity: 2026-01-25 — Completed 12-03-PLAN.md

Progress: [####################] 100% (13/13 phases complete)

## Milestones

| Version | Name | Phases | Status |
|---------|------|--------|--------|
| v0.2-alpha | Production Ready | 1-5 | SHIPPED 2026-01-24 |
| v0.3-alpha | No Duplicate Reports | 6 | SHIPPED 2026-01-24 |
| v0.3.1-alpha | Extended Wireless Analysis | 7 | SHIPPED 2026-01-25 |
| v0.3.2-alpha | Enhanced Security Analysis | 8 | SHIPPED 2026-01-25 |
| v0.3.3-alpha | Device Health Monitoring | 9 | SHIPPED 2026-01-25 |
| v0.3.4-alpha | Integration Infrastructure | 10 | SHIPPED 2026-01-25 |
| v0.3.15-alpha | WebSocket Support | 13 | SHIPPED 2026-01-25 |
| v0.3.5-alpha | Cloudflare Integration | 11 | SHIPPED 2026-01-25 |
| v0.4-alpha | Cybersecure Integration | 12 | SHIPPED 2026-01-25 |

See `.planning/MILESTONES.md` for full milestone history.

## Performance Metrics

**Velocity:**
- Total plans completed: 48
- Average duration: 4 min
- Total execution time: 191 min

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
| 09-device-health | 4 | 17 min | 4 min |
| 10-integration-infrastructure | 3 | 15 min | 5 min |
| 11-cloudflare-integration | 4 | 22 min | 6 min |
| 12-cybersecure-integration | 3 | 3 min | 1 min |

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
- [v0.3.2-alpha]: Shared auth session between WebSocket and REST to avoid 429 rate limits
- [v0.3.3-alpha]: PoE disconnect is MEDIUM severity (power loss impacts device function)
- [v0.3.3-alpha]: PoE overload is SEVERE severity requiring immediate attention
- [v0.3.3-alpha]: HEALTH_RULES use Category.SYSTEM (device-level concern)
- [v0.3.3-alpha]: DeviceStats uses pydantic for validation consistency with IPSEvent
- [v0.3.3-alpha]: Temperature parsing prefers general_temperature over temps dict
- [v0.3.3-alpha]: has_temperature flag tracks whether device reports temperature data
- [v0.3.3-alpha]: Thresholds use > comparison (80C means warning at 80.1C, not 80.0C)
- [v0.3.3-alpha]: Critical findings checked before warnings to avoid dual findings per category
- [v0.3.3-alpha]: Remediation templates are category+severity specific (warning vs critical)
- [v0.3.3-alpha]: Health section follows threat_section.html pattern for consistency
- [v0.3.3-alpha]: Health analysis is optional - failures logged as warnings, don't block reports
- [v0.3.4-alpha]: Use typing.Protocol for Integration interface (duck typing with static type checking)
- [v0.3.4-alpha]: IntegrationRegistry uses hardcoded class list (not dynamic plugin discovery)
- [v0.3.4-alpha]: Partial config logs warning, missing config silently skipped
- [v0.3.4-alpha]: Use capsys for structlog output capture in tests (not caplog)
- [v0.3.4-alpha]: Circuit breaker uses calling() context manager for async (not @breaker decorator)
- [v0.3.5-alpha]: GraphQL for WAF/DNS analytics (richer filtering), REST for tunnels (SDK simplicity)
- [v0.3.5-alpha]: Account ID auto-discovered from zones if not provided
- [v0.3.5-alpha]: Lazy HTTP client initialization for resource efficiency
- [v0.3.5-alpha]: Helper methods on CloudflareData for common analysis patterns
- [v0.3.5-alpha]: API token only for is_configured() (account_id auto-discovered)
- [v0.3.5-alpha]: Silent skip via IntegrationRegistry.get_configured() filtering (no cleanup needed)
- [v0.3.5-alpha]: Template uses CloudflareData helper methods directly (no pre-processing)
- [v0.3.5-alpha]: Integration sections use integrations.get_section(name) pattern
- [v0.3.5-alpha]: Async report generation for integration runner await
- [v0.4-alpha]: Pydantic computed_field for derived boolean properties (is_cybersecure)
- [v0.4-alpha]: ET PRO SID range 2800000-2899999 identifies Cybersecure signatures
- [v0.4-alpha]: ThreatSummary.is_cybersecure = True if ANY event in group is Cybersecure
- [v0.4-alpha]: ThreatSummary.cybersecure_count tracks exact count of ET PRO events
- [v0.4-alpha]: Purple (#6f42c1) badge differentiates Cybersecure from severity badges
- [v0.4-alpha]: Cybersecure badge tooltip explains "Detected by CyberSecure enhanced signatures"

### Pending Todos

None yet.

### Blockers/Concerns

- UniFi Network 10.x deprecated `/stat/event` REST endpoint; WiFi events now require WebSocket connection (Phase 13)
- Pre-existing test failures in test_models.py (datetime timezone) and test_rules.py (rule count, category prefix) - technical debt to address

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
Stopped at: Completed 12-03-PLAN.md (Cybersecure badge display)
Resume file: None

## Next Steps

1. v0.4-alpha SHIPPED - All 13 phases complete
2. All milestones complete - ready for v0.5 planning or release
