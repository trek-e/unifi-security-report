---
phase: 02-log-collection-parsing
plan: 03
subsystem: logs
tags: [ssh, paramiko, fallback, collectors]

dependency-graph:
  requires: ["02-01", "02-02"]
  provides: ["log-collectors", "ssh-fallback"]
  affects: ["03-analysis"]

tech-stack:
  added: ["paramiko>=3.4"]
  patterns: ["fallback-chain", "multi-source-collection"]

key-files:
  created:
    - src/unifi_scanner/logs/ssh_collector.py
    - src/unifi_scanner/logs/api_collector.py
    - src/unifi_scanner/logs/collector.py
    - tests/test_collectors.py
  modified:
    - pyproject.toml
    - src/unifi_scanner/config/settings.py
    - src/unifi_scanner/logs/__init__.py

decisions:
  - key: ssh-credentials-fallback
    choice: "SSH uses ssh_username/password if set, otherwise falls back to API credentials"
    rationale: "Simplifies config when same credentials work for both"
  - key: channel-timeout
    choice: "Use paramiko channel.settimeout() for command execution"
    rationale: "Prevents SSH commands from hanging indefinitely"
  - key: min-entries-threshold
    choice: "Configurable min_entries (default 10) triggers SSH fallback"
    rationale: "API may return partial data; SSH provides fuller picture"

metrics:
  duration: "3 min"
  completed: "2026-01-24"
---

# Phase 02 Plan 03: SSH Fallback and Log Collectors Summary

SSH fallback collector with paramiko for direct device access; API collector wrapping UnifiClient; orchestrating LogCollector with automatic fallback chain.

## What Was Built

### 1. SSH Settings (pyproject.toml, settings.py)
- Added `paramiko>=3.4` dependency
- Added `ssh_username`, `ssh_password` (optional, defaults to API creds)
- Added `ssh_timeout` (5-300 sec, default 30)
- Added `ssh_enabled` toggle for fallback feature

### 2. SSHLogCollector (ssh_collector.py)
- Connects to UniFi devices via SSH
- Device-specific log paths:
  - UDM Pro: `/var/log/messages`, `/mnt/data/log/daemon.log`
  - Self-hosted: `/var/log/unifi/server.log`, `/var/log/unifi/mongod.log`
- Uses `tail -n {max_lines}` to read logs efficiently
- Channel timeout prevents command hanging
- SSHCollectionError with host and cause for debugging

### 3. APILogCollector (api_collector.py)
- Wraps `UnifiClient.get_events()` and `get_alarms()`
- Parses results into LogEntry objects via LogParser
- Configurable history_hours (default 720 = 30 days)
- APICollectionError for error handling

### 4. LogCollector (collector.py)
- Orchestrates collection from multiple sources
- Fallback chain:
  1. Try API first (non-invasive)
  2. Fall back to SSH if API fails or returns < min_entries
  3. Raise LogCollectionError if all sources fail
- Deduplicates entries when merging API + SSH results
- Supports `force_ssh=True` to skip API

### 5. Tests (test_collectors.py)
- 11 tests covering:
  - APILogCollector events/alarms collection
  - LogCollector fallback behavior
  - SSH disabled handling
  - Partial results on fallback failure

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Python 3.9 type syntax**
- **Found during:** Task 3 verification
- **Issue:** Used `Exception | None` which requires Python 3.10+
- **Fix:** Changed to `Optional[Exception]` for 3.9 compatibility
- **Files modified:** api_collector.py
- **Commit:** 5e60527

## Key Patterns Established

1. **Fallback Chain Pattern**: API first, SSH fallback, configurable thresholds
2. **Channel Timeout**: Paramiko channel.settimeout() for command timeouts
3. **Credential Inheritance**: SSH creds default to API creds if not specified
4. **Error Chaining**: Exception classes capture root cause for debugging

## Verification Results

```bash
$ python -c "from unifi_scanner.config import UnifiSettings; s = UnifiSettings(host='x', username='u', password='p'); print(s.ssh_timeout, s.ssh_enabled)"
30.0 True

$ python -c "from unifi_scanner.logs import SSHLogCollector; print('SSHLogCollector imported')"
SSHLogCollector imported

$ pytest tests/test_collectors.py -v
11 passed
```

## Next Phase Readiness

Phase 02 (Log Collection & Parsing) is now complete:
- 02-01: UnifiClient with events/alarms endpoints
- 02-02: Timestamp normalization and LogParser
- 02-03: SSH fallback and orchestrating collectors

Ready for Phase 03 (Analysis Engine):
- LogEntry objects ready for pattern matching
- Multiple collection sources available
- Robust error handling in place
