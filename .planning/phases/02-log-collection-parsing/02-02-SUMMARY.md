---
phase: 02-log-collection-parsing
plan: 02
subsystem: parsing
tags: [timestamps, syslog, json, pydantic, dateutil, utc]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: LogEntry model, LogSource enum, base project structure
provides:
  - UTC timestamp normalization via normalize_timestamp()
  - Defensive parsing with Pydantic validators
  - Multi-format log parsing (JSON API + syslog)
  - LogParser class with auto-format detection
affects: [03-analysis-engine, 04-reporting]

# Tech tracking
tech-stack:
  added: [python-dateutil]
  patterns: [field_validator for defensive parsing, factory classmethods for parsing]

key-files:
  created:
    - src/unifi_scanner/utils/__init__.py
    - src/unifi_scanner/utils/timestamps.py
    - src/unifi_scanner/logs/__init__.py
    - src/unifi_scanner/logs/parser.py
    - tests/test_timestamps.py
    - tests/test_log_parser.py
  modified:
    - src/unifi_scanner/models/log_entry.py
    - pyproject.toml

key-decisions:
  - "Use python-dateutil for flexible timestamp parsing"
  - "Auto-detect milliseconds vs seconds by magnitude (>1e12 = ms)"
  - "Defensive fallbacks: invalid timestamp defaults to now(), missing event_type defaults to UNKNOWN"
  - "Syslog event_type format: SYSLOG_{PROGRAM} in uppercase"

patterns-established:
  - "normalize_timestamp(): central utility for all timestamp normalization"
  - "field_validator with mode='before' for input normalization"
  - "Factory classmethods (from_unifi_event, from_syslog) for parsing"
  - "Graceful error handling: log warning, skip bad entries, continue processing"

# Metrics
duration: 4min
completed: 2026-01-24
---

# Phase 02 Plan 02: Timestamp Normalization & Log Parsing Summary

**UTC timestamp normalization with python-dateutil, defensive Pydantic validators for malformed data, and multi-format LogParser supporting JSON API and syslog formats**

## Performance

- **Duration:** 4 min
- **Started:** 2026-01-24T16:13:32Z
- **Completed:** 2026-01-24T16:17:08Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Created normalize_timestamp() that handles milliseconds, seconds, ISO strings, and datetime objects
- Added defensive field validators to LogEntry (timestamp, MAC address, event_type)
- Implemented from_syslog() classmethod for parsing syslog format logs
- Built LogParser with auto-detection of JSON vs syslog formats
- Comprehensive test suite with 36 passing tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Create timestamp normalization utility** - `9183ccc` (feat)
2. **Task 2: Enhance LogEntry with defensive parsing validators** - `a2718df` (feat)
3. **Task 3: Create LogParser for multi-format parsing** - `9ac9b75` (feat)

## Files Created/Modified

- `src/unifi_scanner/utils/__init__.py` - Exports normalize_timestamp
- `src/unifi_scanner/utils/timestamps.py` - UTC timestamp conversion utility
- `src/unifi_scanner/models/log_entry.py` - Enhanced with validators and from_syslog()
- `src/unifi_scanner/logs/__init__.py` - Exports LogParser
- `src/unifi_scanner/logs/parser.py` - Multi-format parser with auto-detection
- `tests/test_timestamps.py` - 13 tests for timestamp normalization
- `tests/test_log_parser.py` - 23 tests for log parsing
- `pyproject.toml` - Added python-dateutil dependency

## Decisions Made

- **python-dateutil for parsing:** Provides flexible ISO string parsing that handles various formats
- **Millisecond auto-detection:** Timestamps > 1e12 are milliseconds (year 2001+ threshold)
- **Defensive defaults:** Missing timestamps default to now(UTC), missing event_type defaults to "UNKNOWN"
- **MAC normalization:** Lowercase with colons (aa:bb:cc:dd:ee:ff format)
- **Syslog event_type:** Format as SYSLOG_{PROGRAM} for easy filtering

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Initial test assertions used incorrect timestamp values (expected 20:00 for epoch 1705084800 but actual is 18:40) - fixed test assertions to match actual values

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Timestamp normalization ready for use across all log sources
- LogEntry validators ensure robust handling of malformed API data
- LogParser ready to process both API responses and SSH syslog output
- Test coverage provides confidence for future changes

---
*Phase: 02-log-collection-parsing*
*Completed: 2026-01-24*
