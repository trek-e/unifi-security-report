---
phase: 05-delivery-scheduling
plan: 03
subsystem: scheduler
tags: [apscheduler, cron, scheduling, automation]

dependency_graph:
  requires: []
  provides: [schedule-management, cron-support, preset-schedules, one-shot-mode]
  affects: [05-04]

tech_stack:
  added: [APScheduler>=3.10,<4.0]
  patterns: [BlockingScheduler, CronTrigger, event-driven-shutdown]

key_files:
  created:
    - src/unifi_scanner/scheduler/__init__.py
    - src/unifi_scanner/scheduler/presets.py
    - src/unifi_scanner/scheduler/runner.py
  modified:
    - pyproject.toml
    - src/unifi_scanner/config/settings.py

decisions:
  - id: apscheduler-3x
    choice: APScheduler 3.x (not 4.0 alpha)
    reason: Stable API, blocking scheduler pattern, production-ready
  - id: explicit-timezone
    choice: CronTrigger.from_crontab() with explicit timezone param
    reason: Does not inherit from scheduler timezone, must be explicit
  - id: misfire-grace-time
    choice: 3600 seconds (1 hour) with coalesce=True
    reason: Combine missed runs into single execution, handle brief outages
  - id: one-shot-mode
    choice: Schedule 1 second in future with auto-shutdown listener
    reason: Clean exit after single execution when no schedule configured

metrics:
  duration: 3 min
  completed: 2026-01-24
---

# Phase 5 Plan 03: APScheduler Integration Summary

APScheduler-based scheduling with cron expressions, presets, timezone support, and one-shot mode.

## What Was Built

### Schedule Presets (presets.py)
Four predefined schedules for common use cases:
- `daily_8am`: Run every day at 8:00 AM
- `daily_6pm`: Run every day at 6:00 PM
- `weekly_monday_8am`: Run Mondays at 8:00 AM
- `weekly_friday_5pm`: Run Fridays at 5:00 PM

### ScheduledRunner (runner.py)
APScheduler wrapper that provides:
- **Cron expression support**: 5-field format via CronTrigger.from_crontab()
- **Preset schedules**: Named presets for common patterns
- **One-shot mode**: Run once and exit when no schedule configured
- **Timezone support**: Explicit timezone for all schedule types
- **Graceful missed run handling**: 3600s grace time with coalesce

### Configuration Settings
Added to UnifiSettings:
- `schedule_preset`: Named preset (validated against known presets)
- `schedule_cron`: Custom cron expression (5-field format)
- `schedule_timezone`: IANA timezone (default: UTC)

## Technical Decisions

### CronTrigger Timezone
Critical: `CronTrigger.from_crontab()` requires explicit timezone parameter:
```python
# WRONG - timezone not inherited from scheduler
trigger = CronTrigger.from_crontab("0 8 * * *")

# CORRECT - explicit timezone
trigger = CronTrigger.from_crontab("0 8 * * *", timezone=self.timezone)
```

### One-Shot Mode Implementation
When neither cron nor preset is configured:
1. Schedule job for 1 second in the future
2. Register listener for EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
3. Listener calls scheduler.shutdown(wait=False)
4. Clean exit after single run

### Misfire Handling
Configuration for missed job handling:
```python
job_defaults = {
    "coalesce": True,  # Combine missed runs into one
    "misfire_grace_time": 3600,  # 1 hour grace period
    "max_instances": 1,  # Prevent concurrent runs
}
```

## Files Created

| File | Purpose |
|------|---------|
| `scheduler/__init__.py` | Public API exports |
| `scheduler/presets.py` | SCHEDULE_PRESETS dict, get_preset(), list_presets() |
| `scheduler/runner.py` | ScheduledRunner class, SchedulerError |

## Files Modified

| File | Changes |
|------|---------|
| `pyproject.toml` | Added APScheduler>=3.10,<4.0 dependency |
| `config/settings.py` | Added schedule_preset, schedule_cron, schedule_timezone fields |

## Usage Example

```python
from unifi_scanner.scheduler import ScheduledRunner

def generate_report():
    print("Generating report...")

# Option 1: Preset schedule
runner = ScheduledRunner(timezone="America/New_York")
runner.run(generate_report, preset="daily_8am")

# Option 2: Cron expression
runner = ScheduledRunner(timezone="America/New_York")
runner.run(generate_report, cron_expr="0 8 * * *")

# Option 3: One-shot mode (no schedule)
runner = ScheduledRunner()
runner.run(generate_report)  # Runs once and exits
```

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Hash | Message |
|------|---------|
| a743706 | feat(05-03): add APScheduler dependency and schedule settings |
| 678dd65 | feat(05-03): create scheduler module with presets and runner |

## Next Phase Readiness

Ready for 05-04 (Service Entry Point):
- ScheduledRunner available for main service loop
- Settings contain schedule configuration
- One-shot mode enables --once flag implementation
