# Project Milestones: UniFi Scanner

## v0.4-alpha Cybersecure Integration (Shipped: 2026-01-25)

**Delivered:** Proofpoint ET PRO (Cybersecure) signature detection with visual badge in threat reports

**Phases completed:** 12 (3 plans total)

**Key accomplishments:**
- ET PRO signature detection via SID range 2800000-2899999
- is_cybersecure computed field on IPSEvent with automatic JSON serialization
- ThreatSummary Cybersecure attribution tracking (is_cybersecure flag + count)
- Purple CYBERSECURE badge in threat report templates (detected + blocked sections)
- Full TDD test coverage (13 tests) for boundary cases and aggregation scenarios

**Stats:**
- 5 files modified
- 335 lines added (models + analyzer + template + tests)
- 1 phase, 3 plans, 5 tasks
- 1 day (2026-01-24 → 2026-01-25)

**Git range:** `e399a9b` (phase plan) → `5fbc0df` (milestone audit)

**What's next:** All v0.4 phases complete — ready for v0.5 planning

---

## v0.3-alpha No Duplicate Reports (Shipped: 2026-01-24)

**Delivered:** State persistence to prevent duplicate event reporting across scheduled runs

**Phases completed:** 6 (2 plans total)

**Key accomplishments:**
- StateManager module with atomic writes (crash-safe persistence)
- Timestamp filtering in API and SSH log collectors
- Checkpoint-after-delivery pattern ensures no duplicates
- 5-minute clock skew tolerance for time drift
- Configurable initial lookback (UNIFI_INITIAL_LOOKBACK_HOURS)
- Empty report handling with confirmation message

**Stats:**
- 20 files modified
- 413 lines of Python added (state module + tests)
- 1 phase, 2 plans, 6 tasks
- <1 day (single session)

**Git range:** `165aada` (milestone start) → `8b6ee27` (phase complete)

**What's next:** TBD - user testing and feedback

---

## v0.2-alpha Production Ready (Shipped: 2026-01-24)

**Delivered:** Production-ready containerized UniFi log analysis service with email and file delivery

**Phases completed:** 1-5 (19 plans total)

**Key accomplishments:**
- UniFi API client with auto-detection (UDM Pro, UCG Ultra, self-hosted)
- Multi-format log parsing (events, alarms, syslog)
- Rules engine with severity categorization
- Plain English explanations and remediation guidance
- HTML/text report generation with UniFi styling
- Email delivery (BCC recipients, severity-aware subjects)
- File output with retention cleanup
- Docker container with scheduled execution

**Stats:**
- 47 files created
- 2,400+ lines of Python
- 5 phases, 19 plans
- Single day from start to ship

**Git range:** `feat(01-01)` → `feat(05-05)`

**What's next:** v0.3-alpha state persistence (Issue #1)

---
