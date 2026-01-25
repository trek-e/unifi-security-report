---
phase: 08-enhanced-security
plan: 01
subsystem: analysis
tags: [ips, ids, suricata, et-signatures, pydantic, security]

# Dependency graph
requires:
  - phase: 03-analysis-engine
    provides: Rule-based analysis infrastructure
provides:
  - IPSEvent pydantic model with from_api_event factory
  - ET signature parser with 24 category mappings
  - Action classification for blocked/detected events
  - Module exports for IPS analysis foundation
affects: [08-02, 08-03, 08-04]

# Tech tracking
tech-stack:
  added: []  # Uses existing pydantic
  patterns:
    - ET_SIGNATURE_PATTERN regex for Suricata parsing
    - from_api_event factory pattern for API normalization
    - Nested vs flat API structure handling

key-files:
  created:
    - src/unifi_scanner/analysis/ips/signature_parser.py
  modified:
    - src/unifi_scanner/analysis/ips/models.py
    - src/unifi_scanner/analysis/ips/__init__.py
    - tests/test_ips_models.py

key-decisions:
  - "Pydantic BaseModel instead of dataclass for API validation"
  - "24 ET category mappings from Emerging Threats documentation"
  - "Millisecond timestamp detection via > 1 trillion threshold"
  - "Unknown actions default to detected (not blocked) for safety"

patterns-established:
  - "parse_signature_category returns (raw, friendly, description) tuple"
  - "from_api_event handles both inner_alert nested and flat structures"
  - "is_action_blocked uses lowercase set membership"

# Metrics
duration: 6min
completed: 2026-01-25
---

# Phase 08 Plan 01: IPS Models and Signature Parser Summary

**Pydantic IPSEvent model with ET signature parser extracting 24 categories and blocked/detected action classification**

## Performance

- **Duration:** 6 min
- **Started:** 2026-01-25T05:19:10Z
- **Completed:** 2026-01-25T05:25:10Z
- **Tasks:** 2 (TDD RED-GREEN cycle)
- **Files modified:** 4

## Accomplishments

- Created IPSEvent pydantic model with from_api_event factory for UniFi API normalization
- Implemented ET signature parser supporting 24 Suricata categories with friendly names
- Built action classification distinguishing blocked (blocked/drop/reject) from detected (allowed/alert/pass)
- Added comprehensive test suite with 31 tests covering all parsing and model scenarios

## Task Commits

Each task was committed atomically:

1. **TDD RED: Failing tests** - `4baf74a` (test)
2. **TDD GREEN: Implementation** - `b3a6c12` (feat)

_TDD plan: No refactor needed - code followed project patterns_

## Files Created/Modified

- `src/unifi_scanner/analysis/ips/signature_parser.py` - ET signature parser with category extraction
- `src/unifi_scanner/analysis/ips/models.py` - IPSEvent pydantic model with from_api_event
- `src/unifi_scanner/analysis/ips/__init__.py` - Module exports for public API
- `tests/test_ips_models.py` - 31 tests (354 lines) for parser and model

## Decisions Made

1. **Pydantic over dataclass:** Existing IPSEvent dataclass was incomplete. Replaced with pydantic BaseModel for validation, consistent with LogEntry and Finding models.

2. **24 category mappings:** Comprehensive ET category list from RESEARCH.md covers SCAN, MALWARE, POLICY, TROJAN, EXPLOIT, DOS, COINMINING, PHISHING, TOR, P2P, and 14 more.

3. **Timestamp handling:** UniFi API uses milliseconds. Detection via `> 1 trillion` threshold distinguishes from seconds-based timestamps.

4. **Safe defaults:** Unknown actions default to `is_blocked=False` to avoid false positives on threat blocking claims.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- IPSEvent model ready for IPSAnalyzer in 08-02
- Signature parser available for threat categorization
- Action classification supports blocked/detected separation

---
*Phase: 08-enhanced-security*
*Completed: 2026-01-25*
