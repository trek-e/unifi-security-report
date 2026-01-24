---
phase: 02-log-collection-parsing
verified: 2026-01-24T19:23:00Z
status: passed
score: 4/4 must-haves verified
---

# Phase 2: Log Collection & Parsing Verification Report

**Phase Goal:** Service can fetch logs from any UniFi device and normalize them into structured LogEntry objects

**Verified:** 2026-01-24T19:23:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Service retrieves events and alarms from UniFi API | ✓ VERIFIED | `UnifiClient.get_events()` and `get_alarms()` methods exist, call correct endpoints, return parsed data. Tests pass. |
| 2 | Service parses multiple log formats (syslog, JSON) into normalized LogEntry objects | ✓ VERIFIED | `LogParser` handles JSON API events and syslog lines. `LogEntry.from_unifi_event()` and `from_syslog()` factory methods work. UTC normalization confirmed. |
| 3 | Service falls back to SSH when API log access is insufficient | ✓ VERIFIED | `LogCollector` orchestrates API-first, SSH fallback chain. `SSHLogCollector` connects via paramiko, reads device-specific log files. Tests verify fallback trigger on insufficient entries. |
| 4 | All timestamps are normalized to UTC regardless of source format | ✓ VERIFIED | `normalize_timestamp()` handles milliseconds, seconds, ISO strings. Field validator on `LogEntry.timestamp` ensures all timestamps are UTC-aware. Tested with multiple formats. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/unifi_scanner/api/client.py` | get_events() and get_alarms() methods | ✓ VERIFIED | Lines 247-365: Both methods exist, call correct endpoints, handle pagination, detect truncation |
| `src/unifi_scanner/api/endpoints.py` | events and alarms endpoint definitions | ✓ VERIFIED | Lines 33-34, 45-46, 57-58: Endpoints defined for both UDM and self-hosted |
| `src/unifi_scanner/utils/timestamps.py` | UTC timestamp normalization | ✓ VERIFIED | 62 lines, exports `normalize_timestamp()`, handles ms/s/string/datetime, tested |
| `src/unifi_scanner/models/log_entry.py` | Enhanced LogEntry with defensive parsing | ✓ VERIFIED | 193 lines, field validators for timestamp/MAC/event_type, factory methods for API and syslog |
| `src/unifi_scanner/logs/parser.py` | Multi-format log parsing | ✓ VERIFIED | 113 lines, `LogParser` class with `parse_api_events()`, `parse_syslog_lines()`, `detect_and_parse()` |
| `src/unifi_scanner/logs/ssh_collector.py` | SSH-based log collection | ✓ VERIFIED | 268 lines, `SSHLogCollector` with paramiko, device-specific log paths, timeout handling |
| `src/unifi_scanner/logs/api_collector.py` | API-based log collection | ✓ VERIFIED | 128 lines, `APILogCollector` wraps UnifiClient methods, parses to LogEntry |
| `src/unifi_scanner/logs/collector.py` | Orchestrating collector with fallback | ✓ VERIFIED | 216 lines, `LogCollector` implements fallback chain, deduplication, configurable threshold |
| `src/unifi_scanner/config/settings.py` | SSH settings (username, password, timeout, enabled) | ✓ VERIFIED | Lines 125-139: ssh_username, ssh_password, ssh_timeout (30s default), ssh_enabled (True default) |

**All artifacts substantive and wired.**

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `api_collector.py` | `client.py` | `client.get_events()` and `get_alarms()` | ✓ WIRED | Lines 94, 107: Calls client methods with site and history_hours params |
| `log_entry.py` | `timestamps.py` | `normalize_timestamp` in field_validator | ✓ WIRED | Lines 11, 64: Import and usage in validator |
| `parser.py` | `log_entry.py` | `LogEntry.from_unifi_event()` and `from_syslog()` | ✓ WIRED | Lines 39, 67: Factory methods called to create LogEntry instances |
| `collector.py` | `api_collector.py` | `APILogCollector` as primary source | ✓ WIRED | Lines 15, 104-109: Import and instantiation in collect() |
| `collector.py` | `ssh_collector.py` | `SSHLogCollector` as fallback | ✓ WIRED | Lines 16, 207-214: Import and instantiation in _collect_via_ssh() |
| `ssh_collector.py` | `parser.py` | `LogParser.parse_syslog_lines()` | ✓ WIRED | Lines 14, 126: Import and usage to parse SSH log output |

**All key links verified as wired and functional.**

### Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| COLL-04: Service falls back to SSH when API is insufficient | ✓ SATISFIED | LogCollector implements fallback chain: API first (min_entries threshold), SSH on failure or insufficient data. SSHLogCollector reads device-specific log files via paramiko. Tests verify behavior. |

**1/1 requirements satisfied.**

### Anti-Patterns Found

No blocking anti-patterns found.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `__main__.py` | 208 | TODO: Phase 5 scheduling | ℹ️ Info | Expected - deferred to Phase 5 |

**0 blockers, 0 warnings, 1 informational.**

### Test Coverage

**Test suites:** 3 files, 47 tests, **all passing**

1. **tests/test_timestamps.py**: 13 tests
   - Millisecond/second timestamp conversion
   - ISO string parsing with timezone awareness
   - Naive datetime handling (assume_utc flag)
   - Invalid input error handling
   - UniFi typical timestamps (1705084800000 ms format)

2. **tests/test_log_parser.py**: 23 tests
   - API event parsing with various MAC address fields
   - Syslog parsing with hostname, program, PID extraction
   - Auto-format detection (JSON vs syslog)
   - Graceful handling of unparseable entries
   - Source field correctly set (API vs SYSLOG)
   - UTC timestamp verification

3. **tests/test_collectors.py**: 11 tests
   - APILogCollector events/alarms collection
   - LogCollector fallback chain behavior
   - SSH fallback on insufficient API results (<10 entries)
   - SSH fallback disabled when ssh_enabled=False
   - Both sources fail raises LogCollectionError
   - Partial results returned on SSH failure
   - Force SSH mode skips API

**Coverage verification:**
```bash
$ python3 -m pytest tests/test_timestamps.py tests/test_log_parser.py tests/test_collectors.py -v
======================= 47 passed, 11 warnings in 0.47s =======================
```

### Manual Verification Performed

**Runtime verification:**

1. ✓ Imports work: All collector classes import successfully
2. ✓ UnifiClient has methods: `get_events()` and `get_alarms()` exist
3. ✓ Timestamp normalization: Milliseconds and ISO strings convert to UTC
4. ✓ LogEntry parsing: Both API events and syslog lines parse correctly
5. ✓ Settings include SSH config: ssh_username, ssh_password, ssh_timeout, ssh_enabled fields present
6. ✓ LogCollector instantiates: Can be created with UnifiClient and settings

**Code inspection verification:**

1. ✓ `get_events()`: Lines 247-318 in client.py - POST to events endpoint, handles pagination, detects truncation via meta.count
2. ✓ `get_alarms()`: Lines 320-365 in client.py - GET to alarms endpoint, optional archived filter
3. ✓ Endpoint definitions: Lines 33-34 (events, alarms) in Endpoints dataclass, both UDM and self-hosted paths
4. ✓ UTC normalization: normalize_timestamp() detects milliseconds (>1e12), converts to UTC, handles strings with dateutil
5. ✓ Defensive parsing: LogEntry validators handle None timestamps (default to now()), invalid MACs (return original), empty event_type (default "UNKNOWN")
6. ✓ Syslog parsing: Regex pattern matches "Jan 24 10:30:15 hostname program[pid]: message" format
7. ✓ SSH fallback chain: LogCollector tries API first, checks min_entries threshold (default 10), falls back to SSH if configured
8. ✓ SSH log paths: Device-specific paths defined (UDM: /var/log/messages, /mnt/data/log/daemon.log; Self-hosted: /var/log/unifi/server.log, /var/log/unifi/mongod.log)
9. ✓ SSH timeout: Channel timeout set (default 30s) prevents hanging on large log files
10. ✓ Error handling: All collectors raise specific exceptions (APICollectionError, SSHCollectionError, LogCollectionError) with context

## Phase Goal Achievement: VERIFIED

**All success criteria met:**

1. ✓ Service retrieves events and alarms from UniFi API
   - `UnifiClient.get_events()` and `get_alarms()` implemented and tested
   - Pagination supported (start, limit parameters)
   - Truncation detection logs warnings
   - Both UDM and self-hosted endpoints supported

2. ✓ Service parses multiple log formats into normalized LogEntry objects
   - JSON API events parsed via `LogEntry.from_unifi_event()`
   - Syslog format parsed via `LogEntry.from_syslog()`
   - `LogParser` auto-detects format
   - All fields normalized (timestamp, MAC address, event_type)

3. ✓ Service falls back to SSH when API is insufficient
   - `LogCollector` orchestrates API-first, SSH fallback strategy
   - Fallback triggers on API failure or <10 entries (configurable)
   - `SSHLogCollector` reads device-specific log files via paramiko
   - SSH credentials configurable (ssh_username, ssh_password) with API creds fallback
   - SSH operations have configurable timeout (default 30s)
   - Tests verify all fallback scenarios

4. ✓ All timestamps normalized to UTC
   - `normalize_timestamp()` utility handles milliseconds, seconds, ISO strings, datetime objects
   - Auto-detects milliseconds vs seconds by magnitude (>1e12 = milliseconds)
   - Field validator on `LogEntry.timestamp` ensures all timestamps UTC-aware
   - Defensive fallback to now(UTC) on parse failure
   - Tested with multiple formats

**Requirement COLL-04 satisfied:** SSH fallback implemented with paramiko, device-specific log paths, timeout handling, graceful degradation when SSH unavailable.

**Phase 2 complete. Ready for Phase 3 (Analysis Engine).**

---

_Verified: 2026-01-24T19:23:00Z_
_Verifier: Claude (gsd-verifier)_
