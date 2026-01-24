---
phase: 03-analysis-engine
plan: 03
subsystem: analysis
tags: [deduplication, time-window, occurrence-tracking, recurring-detection]

# Dependency graph
requires:
  - phase: 03-01
    provides: Finding model with occurrence_count and source_log_ids
provides:
  - FindingStore class with time-window deduplication
  - RECURRING_THRESHOLD constant (5 occurrences)
  - is_recurring property on Finding model
  - format_occurrence_summary() method for display
  - Filtering by severity, category, and recurring status
affects: [03-04-enrichment, reporting, output-formatting]

# Tech tracking
tech-stack:
  added: []
  patterns: [time-window-deduplication, key-based-merging]

key-files:
  created:
    - src/unifi_scanner/analysis/store.py
    - tests/test_finding_store.py
  modified:
    - src/unifi_scanner/models/finding.py
    - src/unifi_scanner/models/__init__.py
    - src/unifi_scanner/analysis/__init__.py

key-decisions:
  - "RECURRING_THRESHOLD as module-level constant for Pydantic v2 compatibility"
  - "Deduplication key is (event_type, device_mac) tuple"
  - "None device_mac is valid deduplication key for system events"
  - "Recurring flag shown in occurrence summary without severity escalation"

patterns-established:
  - "Time-window deduplication: merge findings within configurable window"
  - "Key-based merging: (event_type, device_mac) as unique identifier"
  - "Occurrence tracking: count + first/last seen timestamps"

# Metrics
duration: 4min
completed: 2026-01-24
---

# Phase 3 Plan 3: Finding Store Summary

**FindingStore with 1-hour time-window deduplication, occurrence tracking, and recurring detection (5+ occurrences)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-01-24T17:03:30Z
- **Completed:** 2026-01-24T17:07:35Z
- **Tasks:** 3
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- FindingStore class with configurable time-window deduplication (default 1 hour)
- is_recurring property and format_occurrence_summary() method on Finding model
- Comprehensive test suite with 22 tests covering all deduplication scenarios
- Filtering methods: by_severity, by_category, recurring_only

## Task Commits

Each task was committed atomically:

1. **Task 1: Add is_recurring property and format_occurrence_summary** - `3bff8d6` (feat)
2. **Task 2: Create FindingStore with time-window deduplication** - `c5a08d4` (feat)
3. **Task 3: Create comprehensive tests for FindingStore** - `dc20283` (test)
4. **Fix: Move RECURRING_THRESHOLD to module level** - `1e66d49` (fix)

## Files Created/Modified
- `src/unifi_scanner/analysis/store.py` - FindingStore with add_or_merge deduplication
- `src/unifi_scanner/models/finding.py` - Added is_recurring, format_occurrence_summary()
- `src/unifi_scanner/models/__init__.py` - Export RECURRING_THRESHOLD constant
- `src/unifi_scanner/analysis/__init__.py` - Export FindingStore
- `tests/test_finding_store.py` - 22 tests for deduplication scenarios

## Decisions Made
- **RECURRING_THRESHOLD at module level:** Pydantic v2 doesn't support class attributes the same way as v1, so the constant was moved to module level and exported from the models package
- **Tuple key for deduplication:** (event_type, device_mac) provides unique identification for merging
- **None device_mac valid:** System-level events without device association can still be deduplicated
- **[Recurring] tag in summary:** Visual indicator without severity escalation per user decision

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Moved RECURRING_THRESHOLD to module level**
- **Found during:** Verification after Task 1
- **Issue:** Pydantic v2 BaseModel doesn't allow class-level attribute access via `Finding.RECURRING_THRESHOLD`
- **Fix:** Moved constant to module level in finding.py, exported from models/__init__.py
- **Files modified:** src/unifi_scanner/models/finding.py, src/unifi_scanner/models/__init__.py
- **Verification:** `from unifi_scanner.models import RECURRING_THRESHOLD` works
- **Committed in:** 1e66d49

---

**Total deviations:** 1 auto-fixed (blocking)
**Impact on plan:** Minor implementation detail for Pydantic v2 compatibility. No scope change.

## Issues Encountered
- Pre-existing test failures in test_models.py::TestLogEntry (timezone handling) - unrelated to this plan's changes

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- FindingStore ready for integration with AnalysisEngine
- Deduplication logic can receive findings from rule-based analysis
- Plan 03-04 can implement enrichment layer on top of deduplicated findings

---
*Phase: 03-analysis-engine*
*Completed: 2026-01-24*
