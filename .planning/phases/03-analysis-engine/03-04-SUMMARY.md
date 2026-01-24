---
phase: 03-analysis-engine
plan: 04
subsystem: analysis
tags: [templates, formatting, explanations, remediation, timezone]

# Dependency graph
requires:
  - phase: 03-01
    provides: Rules engine with Rule dataclass and RuleRegistry
  - phase: 03-03
    provides: Finding model with occurrence tracking and deduplication
provides:
  - EXPLANATION_TEMPLATES with 23 event types across 4 categories
  - REMEDIATION_TEMPLATES with severity-specific guidance (16 rules)
  - render_explanation() for template rendering with SafeDict fallback
  - render_remediation() with severity-aware output (None for LOW)
  - FindingFormatter for display-ready output with timezone conversion
  - Plain text report generation with severity grouping
affects: [04-reporting, 05-cli]

# Tech tracking
tech-stack:
  added: [zoneinfo]
  patterns: [SafeDict for template fallback, severity-grouped output]

key-files:
  created:
    - src/unifi_scanner/analysis/templates/__init__.py
    - src/unifi_scanner/analysis/templates/explanations.py
    - src/unifi_scanner/analysis/templates/remediation.py
    - src/unifi_scanner/analysis/formatter.py
    - tests/test_templates.py
  modified:
    - src/unifi_scanner/analysis/__init__.py

key-decisions:
  - "Category prefix in all titles: [Security], [Connectivity], [Performance], [System], [Uncategorized]"
  - "{event_type} placeholder in all descriptions for searchability/Googling"
  - "SEVERE remediation has numbered steps (1., 2., 3., etc.)"
  - "MEDIUM remediation has high-level guidance without strict numbering"
  - "LOW severity returns None for remediation (informational only)"
  - "SafeDict pattern for missing template keys - replaced with 'Unknown'"
  - "zoneinfo for timezone handling (stdlib in Python 3.9+)"
  - "Absolute timestamps with timezone abbreviation (e.g., 'Jan 24, 2026 at 9:30 AM EST')"
  - "[Recurring Issue] prefix for 5+ occurrences"
  - "Device display fallback: device_name -> device_mac -> 'Unknown device'"

patterns-established:
  - "Template structure: dict with 'title' and 'description' keys"
  - "Remediation by severity: 'severe' and 'medium' keys in template dict"
  - "SafeDict for graceful handling of missing template placeholders"
  - "FindingFormatter for display-ready output conversion"

# Metrics
duration: 5min
completed: 2026-01-24
---

# Phase 03 Plan 04: Templates and Formatter Summary

**Plain English explanation and remediation template system with FindingFormatter for display-ready output including timezone-aware timestamps**

## Performance

- **Duration:** 5 min
- **Started:** 2026-01-24T17:10:49Z
- **Completed:** 2026-01-24T17:16:01Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Created 23 explanation templates across Security, Connectivity, Performance, and System categories
- Created 16 remediation templates with severity-appropriate detail (numbered steps for SEVERE, guidance for MEDIUM)
- Built FindingFormatter with timezone conversion, occurrence summaries, severity grouping, and text report generation
- Added 45 comprehensive tests verifying all user style decisions from CONTEXT.md

## Task Commits

Each task was committed atomically:

1. **Task 1: Create explanation and remediation template modules** - `f0e3e40` (feat)
2. **Task 2: Create FindingFormatter for display-ready output** - `a039e65` (feat)
3. **Task 3: Create comprehensive template and formatter tests** - `f687558` (test)

Note: Task 2 files were included in commit a039e65 which was labeled as 03-02 due to branch state but contains the formatter.py and __init__.py changes for this plan.

## Files Created/Modified

- `src/unifi_scanner/analysis/templates/__init__.py` - Template module exports
- `src/unifi_scanner/analysis/templates/explanations.py` - 23 explanation templates with render_explanation()
- `src/unifi_scanner/analysis/templates/remediation.py` - 16 remediation templates with render_remediation()
- `src/unifi_scanner/analysis/formatter.py` - FindingFormatter class for display-ready output
- `src/unifi_scanner/analysis/__init__.py` - Added FindingFormatter export
- `tests/test_templates.py` - 45 tests for templates and formatter

## Decisions Made

1. **SafeDict pattern** - Missing template keys replaced with 'Unknown' rather than raising errors
2. **zoneinfo over pytz** - Using stdlib zoneinfo available in Python 3.9+
3. **Absolute timestamp format** - "Jan 24, 2026 at 9:30 AM EST" (not relative like "2 hours ago")
4. **Recurring flag** - "[Recurring Issue]" prefix in occurrence summary, not title
5. **Text report structure** - SEVERE/MEDIUM/LOW sections, remediation only shown for SEVERE/MEDIUM

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing test failures in test_models.py (2 tests) related to timestamp timezone awareness. These are not related to this plan and existed before execution. All 45 new tests pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Template system complete and tested
- FindingFormatter ready for use by CLI and reporting phases
- All CONTEXT.md style decisions implemented and verified
- Phase 3 (Analysis Engine) now complete

---
*Phase: 03-analysis-engine*
*Completed: 2026-01-24*
