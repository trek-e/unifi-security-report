---
phase: 03-analysis-engine
plan: 02
subsystem: analysis
tags: [rules, security, connectivity, performance, system, remediation]

# Dependency graph
requires:
  - phase: 03-01
    provides: Rule/RuleRegistry dataclass and dictionary dispatch architecture
provides:
  - 23 category-specific rules for common UniFi events
  - Security rules (4): failed login, rogue AP, IPS, login success
  - Connectivity rules (7): device offline, WAN down, isolation, client events
  - Performance rules (5): interference, CPU, memory, speed, channel utilization
  - System rules (7): firmware, restarts, adoption, config, backup, updates
  - ALL_RULES aggregation list
  - get_default_registry() helper function
affects: [04-output, 05-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Category rules in separate modules (security.py, connectivity.py, etc.)"
    - "ALL_RULES aggregation in rules/__init__.py"
    - "get_default_registry() factory for pre-populated registry"
    - "Remediation policy: SEVERE/MEDIUM have templates, LOW does not"
    - "Title format: [Category] description"
    - "Description includes event_type for searchability"

key-files:
  created:
    - src/unifi_scanner/analysis/rules/security.py
    - src/unifi_scanner/analysis/rules/connectivity.py
    - src/unifi_scanner/analysis/rules/performance.py
    - src/unifi_scanner/analysis/rules/system.py
    - tests/test_rules.py
  modified:
    - src/unifi_scanner/analysis/rules/__init__.py

key-decisions:
  - "Event types include variants (EVT_AP_Lost_Contact, EVT_AP_DISCONNECTED)"
  - "Remediation steps are numbered 1-5 actionable items"
  - "Descriptions explain impact in plain English"
  - "Client connect/disconnect events are LOW (too frequent for MEDIUM)"

patterns-established:
  - "Rule modules export *_RULES list (SECURITY_RULES, etc.)"
  - "ALL_RULES concatenates all category lists"
  - "Test parametrization across all rules for policy enforcement"

# Metrics
duration: 3min
completed: 2026-01-24
---

# Phase 03 Plan 02: Initial Rule Set Summary

**23 rules across 4 categories with plain English descriptions, event types for searchability, and remediation guidance for SEVERE/MEDIUM severity**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-24T17:10:41Z
- **Completed:** 2026-01-24T17:13:50Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Created 23 rules covering common UniFi events across all categories
- Enforced remediation policy: SEVERE/MEDIUM have step-by-step fixes, LOW informational only
- All descriptions include event_type in parentheses for Google searchability
- All titles prefixed with [Category] for clear categorization
- 225 tests verify rule structure, policy compliance, and engine integration

## Task Commits

Each task was committed atomically:

1. **Task 1: Create security category rules** - `5646744` (feat)
2. **Task 2: Create connectivity and performance category rules** - `6421c2a` (feat)
3. **Task 3: Create system category rules, aggregate exports, and tests** - `a039e65` (feat)

## Files Created/Modified
- `src/unifi_scanner/analysis/rules/security.py` - 4 security rules (failed login, rogue AP, IPS, login success)
- `src/unifi_scanner/analysis/rules/connectivity.py` - 7 connectivity rules (AP/switch offline, WAN down, isolation, client events)
- `src/unifi_scanner/analysis/rules/performance.py` - 5 performance rules (interference, CPU, memory, speed, channel)
- `src/unifi_scanner/analysis/rules/system.py` - 7 system rules (firmware, restarts, adoption, config, backup, updates)
- `src/unifi_scanner/analysis/rules/__init__.py` - ALL_RULES aggregation, get_default_registry() helper
- `tests/test_rules.py` - 225 tests covering all rules and policies

## Decisions Made

1. **Event type variants** - Rules handle multiple event type names (EVT_AP_Lost_Contact, EVT_AP_DISCONNECTED) since UniFi controller versions may emit different names
2. **Client events are LOW** - connect/disconnect events happen frequently; MEDIUM would create noise
3. **Unexpected restarts are MEDIUM** - Distinguished from planned restarts; warrants investigation but not SEVERE
4. **Configuration changes are LOW** - Normal administrative activity; logged for awareness/audit

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 23 rules ready for use with AnalysisEngine
- get_default_registry() provides one-line engine initialization
- Ready for Phase 4: Output formatting (findings to human-readable reports)
- Comprehensive test coverage ensures rules meet all formatting policies

---
*Phase: 03-analysis-engine*
*Completed: 2026-01-24*
