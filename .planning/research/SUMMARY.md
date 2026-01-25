# Project Research Summary

**Project:** UniFi Scanner - v0.3-alpha State Persistence
**Domain:** Network log analysis and monitoring service
**Researched:** 2026-01-24
**Confidence:** HIGH

## Executive Summary

The v0.3-alpha milestone adds state persistence to track the last successful report timestamp, preventing duplicate event reporting (Issue #1). This is a focused enhancement to an existing containerized Python service that polls UniFi gateways hourly, analyzes logs, and delivers reports via email/file.

Research confirms that **no additional dependencies are required**. Python's standard library (`json`, `tempfile`, `shutil`, `pathlib`) provides everything needed for crash-safe state management. The critical success factors are: (1) atomic file writes using the write-to-temp-then-rename pattern already present in the codebase (`FileDelivery._atomic_write`), (2) integrating state read/write into the existing pipeline at the correct points (read before collection, write after delivery success), and (3) avoiding common containerized state pitfalls through proper volume mounting and concurrency controls.

The primary risk is state file corruption or permission issues in the Docker environment. Prevention requires atomic writes (already implemented as a pattern), UTC-only timestamps, named Docker volumes (avoid bind mount permission mismatches), and scheduler-level concurrency protection (APScheduler `max_instances=1` or Ofelia `no-overlap=true`). These are well-documented patterns with HIGH confidence.

## Key Findings

### Recommended Stack

**No new dependencies required.** The existing Python 3.12+ runtime with standard library modules provides all necessary functionality for state persistence. The project already has the atomic write pattern in place (`FileDelivery._atomic_write` at lines 61-80 uses `tempfile.mkstemp` + `shutil.move`), which can be reused for state file writes.

**Core components for state management:**
- `json` (stdlib): Simple timestamp state, no performance requirements justify external libraries
- `tempfile` + `shutil.move` (stdlib): Atomic write pattern for crash safety
- `pathlib.Path` (stdlib): Consistent with existing codebase style
- APScheduler (existing dependency): Already configured, just needs `max_instances: 1` to prevent overlapping runs

**File locking explicitly NOT required:**
- Single Docker container architecture (docker-compose.yml shows one instance)
- APScheduler `max_instances: 1` prevents overlapping job execution
- No multi-process or distributed deployment scenarios
- Atomic write pattern provides crash safety without explicit locking

**Source confidence:** HIGH - Analysis of existing codebase shows pattern already exists, no external dependencies needed. Atomic write pattern verified in `src/unifi_scanner/delivery/file.py` lines 61-80.

### Expected Features

The v0.3-alpha milestone implements a single focused feature with clear success criteria.

**Must have (table stakes):**
- Read last successful report timestamp before log collection
- Filter out events already reported (since last success)
- Write state only after successful delivery (idempotent retry behavior)
- Handle missing state file gracefully (first run defaults to 24h lookback)
- Atomic writes to prevent corruption during crashes
- UTC timestamps to avoid timezone confusion

**Should have (quality):**
- Backup state file with automatic recovery (`.last_run.json.bak`)
- Startup validation that state path is in mounted volume
- Clear logging of state transitions (first run, state updated, recovery from backup)
- Graceful degradation on state file corruption (log warning, use default lookback)

**Defer (v2+):**
- Per-device state tracking (not needed for initial scope)
- State migration/versioning (schema_version exists but not used yet)
- Health metrics based on state file age
- Multi-site state management

### Architecture Approach

State persistence integrates into the existing `run_report_job()` pipeline using the **checkpoint-after-delivery** pattern from stream processing systems (Apache Flink, Kafka Streams). State commits occur only after all downstream operations succeed, ensuring idempotent retries.

**Integration points:**
1. **State Read (before log collection):** Load `.last_run.json` to determine timestamp cutoff, pass to `LogCollector` as `since_timestamp` parameter
2. **State Write (after successful delivery):** Update state file only if `DeliveryManager.deliver()` returns `True`
3. **State Skip (on delivery failure):** Do NOT update state if delivery fails, ensuring next run retries same events

**Major components:**
1. **StateManager** (new) - Read/write state file with atomic operations, backup recovery, UTC enforcement
2. **LogCollector** (modified) - Accept `since_timestamp` parameter to filter API events
3. **run_report_job** (modified) - Orchestrate state read → collect → analyze → deliver → state write flow

**Data flow:**
```
StateManager.read_last_run() → timestamp (or None for first run)
    ↓
LogCollector.collect(since=timestamp) → filtered events
    ↓
AnalysisEngine.analyze() → findings
    ↓
Report → ReportGenerator → DeliveryManager
    ↓
If delivery success: StateManager.write_last_run(report.generated_at)
If delivery fails: Skip state update (retry next run)
```

**State file location:** `{REPORTS_DIR}/.last_run.json` (same volume as reports, ensuring persistence across container restarts)

**State file schema:**
```json
{
  "last_successful_run": "2026-01-24T14:30:00Z",
  "last_report_count": 3,
  "schema_version": "1.0"
}
```

**Confidence: HIGH** — Pipeline integration points clearly defined, checkpoint-after-delivery pattern well-documented in stream processing literature (Apache Flink, Kafka Streams, Airbyte).

### Critical Pitfalls

Research identified 8 pitfalls specific to file-based state in containerized services. The top 5 require prevention measures:

1. **Partial writes during crashes** - Power failure mid-write corrupts JSON, service loses state and re-processes all events. **Prevention:** Atomic write pattern (write to temp file, fsync, rename). Already exists in codebase at `FileDelivery._atomic_write()`, reuse for state.

2. **Permission mismatches on volume mounts** - Container runs as non-root user (UID 1000), bind mount owned by different user causes `PermissionError`. **Prevention:** Use Docker named volumes (not bind mounts) which handle permissions automatically. Document bind mount ownership requirements if users choose that route.

3. **Concurrent container instances** - Manual trigger during scheduled run causes race condition, duplicate reports, state corruption. **Prevention:** APScheduler `max_instances=1` (prevents overlapping jobs) or Ofelia `no-overlap=true` (scheduler-level protection).

4. **Container ephemeral filesystem confusion** - State file stored in container writable layer (not volume) disappears on restart. **Prevention:** Startup validation that `STATE_FILE_PATH` is in mounted volume, fail fast if not writable.

5. **Timezone confusion in state timestamps** - Mixing UTC and local time in comparisons causes events to be skipped or duplicated. **Prevention:** Always use `datetime.now(timezone.utc)`, store ISO 8601 UTC in state file, parse with timezone awareness.

**Additional moderate pitfalls:**
- Missing state file treated as error (should be normal first-run behavior)
- State file in `.gitignore` breakage (overly broad patterns)
- No state file backup/recovery (corruption has no fallback)

**Source confidence:** HIGH - Pitfalls verified through official Docker docs, production experience articles (DEV Community crash-safe JSON), and analysis of existing codebase patterns.

## Implications for Roadmap

This is a single-phase milestone with clear implementation scope and high confidence.

### Phase 1: State Persistence Implementation

**Rationale:** All research confirms this is a straightforward enhancement with well-established patterns. The atomic write mechanism already exists in the codebase, concurrency control is trivial (one-line config), and no new dependencies are required. High confidence allows single-phase delivery.

**Delivers:**
- StateManager module with read/write/backup operations
- Modified LogCollector accepting `since_timestamp` parameter
- Modified run_report_job orchestrating state lifecycle
- Tests for first run, corruption recovery, concurrent protection
- Documentation for Docker volume requirements

**Addresses:**
- Issue #1: Don't send previous logs
- Table stakes: Idempotent retry behavior
- Quality: Graceful degradation, backup recovery

**Avoids:**
- Pitfall #1: Atomic writes prevent corruption
- Pitfall #2: Documentation covers volume permissions
- Pitfall #3: APScheduler config prevents concurrency
- Pitfall #4: Startup validation ensures volume mount
- Pitfall #5: UTC enforcement prevents timezone bugs

**Implementation order:**
1. Create `StateManager` module (reuse atomic write pattern from FileDelivery)
2. Add `since_timestamp` parameter to LogCollector
3. Modify `run_report_job()` to integrate state read/write
4. Add startup validation for volume writability
5. Configure APScheduler `max_instances=1`
6. Write tests (first run, corruption, concurrency)
7. Update documentation (volume requirements, first-run behavior)

### Phase Ordering Rationale

**Single phase is appropriate because:**
- Scope is tightly focused (one feature: state persistence)
- No new dependencies means no integration risk
- Pattern already exists in codebase (atomic writes)
- Architecture integration point is clear and non-invasive
- All research areas have HIGH confidence

**No phase dependencies exist:**
- Feature is orthogonal to existing functionality
- Log collection API doesn't change externally
- Delivery system unchanged
- Report generation unchanged

**This avoids over-planning:**
- Breaking into smaller phases would create artificial milestones
- All components must be delivered together for feature to work
- Testing requires complete state lifecycle

### Research Flags

**Standard patterns (skip additional research):**
- **State file I/O:** Atomic writes, JSON serialization, backup recovery all have official documentation and production examples
- **Docker volumes:** Permission handling, named vs bind mounts well-documented in Docker official guides
- **Concurrency control:** APScheduler configuration is straightforward, documented in existing codebase
- **Timezone handling:** UTC enforcement pattern consistent with existing `utils/timestamps.py`

**No phases need deeper research:**
- All technical decisions validated with official sources (Python docs, Docker docs, APScheduler docs)
- Patterns verified in existing codebase (atomic writes, timezone handling)
- Pitfalls cross-referenced with production experience articles (DEV Community, Medium)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new dependencies required, stdlib sufficient. Existing codebase already has atomic write pattern. |
| Features | HIGH | Clear scope from Issue #1, well-defined success criteria, no feature ambiguity. |
| Architecture | HIGH | Integration points identified in existing pipeline, checkpoint-after-delivery pattern well-documented. |
| Pitfalls | HIGH | 8 pitfalls identified from official Docker docs, production experience articles, existing codebase analysis. |

**Overall confidence:** HIGH

### Gaps to Address

**Minor validation needed during implementation:**

- **UniFi Events API timestamp filtering:** Assumption that API supports `start` parameter for timestamp filtering needs verification. If not supported, fallback to client-side filtering (slightly less efficient but functionally equivalent).
  - **Resolution:** Test with actual UniFi controller during development, document if client-side filtering required.

- **State file size growth:** Assumption that state file remains ~200 bytes. If additional metadata added in future (per-device tracking, error history), may need size monitoring.
  - **Resolution:** Keep schema_version in state for future migrations, defer size concerns until actual need emerges.

- **Startup validation strictness:** Decision needed whether missing volume mount should fail fast (raise exception) or warn and continue (graceful degradation).
  - **Resolution:** Fail fast on non-writable state path (configuration error), warn on missing state file (expected first run).

**No blocking gaps exist.** All identified gaps have clear resolution strategies and do not prevent implementation.

## Sources

### Primary (HIGH confidence)
- **Python Official Docs**: `json`, `tempfile`, `shutil`, `pathlib` standard library documentation
- **Docker Official Docs**: [Persisting container data](https://docs.docker.com/get-started/workshop/05_persisting_data/), volume mount permissions
- **APScheduler Docs**: Job configuration, max_instances parameter
- **Existing Codebase**: `FileDelivery._atomic_write()` (lines 61-80), `utils/timestamps.py`, `docker-compose.yml`

### Secondary (MEDIUM confidence)
- **[DEV Community: Crash-safe JSON at scale](https://dev.to/constanta/crash-safe-json-at-scale-atomic-writes-recovery-without-a-db-3aic)**: Atomic write patterns, backup recovery strategies
- **[Airbyte: Idempotency in Data Pipelines](https://airbyte.com/data-engineering-resources/idempotency-in-data-pipelines)**: Checkpoint-after-delivery pattern
- **[Dagster: Data Pipeline Architecture](https://dagster.io/guides/data-pipeline-architecture-5-design-patterns-with-examples)**: State management best practices
- **[LabEx: Docker Volume Permissions](https://labex.io/tutorials/docker-how-to-resolve-permission-denied-error-when-mounting-volume-in-docker-417724)**: Permission mismatch solutions
- **[Apache Flink Checkpointing](https://medium.com/@akash.d.goel/apache-flink-series-part-6-4ef9ad38e051)**: Watermark and checkpoint patterns

### Tertiary (LOW confidence - not applicable)
- **[OneUpTime: Docker Cron Jobs](https://oneuptime.com/blog/post/2026-01-06-docker-cron-jobs/view)**: Ofelia no-overlap configuration (not applicable if using APScheduler)
- **[Baeldung: File Locking in Linux](https://www.baeldung.com/linux/file-locking)**: Advisory locks (determined unnecessary for single-instance architecture)

---
**Research completed:** 2026-01-24
**Ready for roadmap:** Yes
**Implementation confidence:** HIGH - All technical decisions validated, no new dependencies, pattern exists in codebase
