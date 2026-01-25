# Features Research: Event Deduplication

**Domain:** Log monitoring event deduplication / "don't re-report" patterns
**Researched:** 2026-01-24
**Confidence:** HIGH (verified across multiple log monitoring tools and stream processing systems)

## Executive Summary

Event deduplication in log monitoring follows well-established patterns from tools like Fluentd, Filebeat, logwatch, and stream processing systems (Apache Flink, Kafka). The core pattern is **checkpoint-based state tracking**: persist the last successfully processed position (timestamp, event ID, or file offset), then resume from that position on next run.

The UniFi Scanner use case is straightforward: **"only report events that occurred since last report."** This maps directly to timestamp-based watermarking with stateful persistence.

**Key insight:** This is NOT traditional deduplication (removing duplicate log entries). This is **incremental processing** (only process new data since last run). The research confirms this is a table stakes feature for any log monitoring tool.

---

## Table Stakes

What must work for this feature to be considered functional.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Persist last run timestamp** | Without state, tool can't know where it left off | Low | Write timestamp to state file after successful report |
| **Resume from last timestamp** | Core functionality; "only show new events" | Low | Query events WHERE timestamp > last_run |
| **Survive service restarts** | State must persist across container restarts | Low | File-based state in volume mount |
| **Handle first run gracefully** | No previous state exists; don't crash | Low | If no state file, use configurable lookback window (e.g., 24h) |
| **Update state on success only** | Don't advance watermark if report generation fails | Medium | Atomic write: report succeeds → update state file |
| **Handle empty results** | No new events since last run is valid | Low | Generate "no new events" report or skip report entirely (configurable) |

### Implementation Pattern (from Fluentd/Filebeat)

Both Fluentd and Filebeat use **position files** to track state:

- **Fluentd**: `pos_file` parameter records last read position and inode number. If td-agent restarts, it resumes from last position. Handles multiple files in one position file.
- **Filebeat**: `db` property creates SQLite database to track file offsets. Service restart continues from last checkpoint.
- **Pattern**: Write checkpoint AFTER successful processing, never before.

**For UniFi Scanner:** Timestamp-based checkpoint is simpler than file offset because we're querying an API, not tailing a file. State file should contain:
```json
{
  "last_successful_run": "2026-01-24T18:30:00Z",
  "last_event_processed": "evt_12345",  // optional: event ID for deduplication
  "report_generated": true
}
```

---

## Expected Behavior

How users expect this to work, based on established patterns.

### 1. First Run Behavior (Bootstrap)

**User expectation:** Tool should be usable immediately without manual configuration.

**Standard patterns from research:**
- **Backfill option:** Google Cloud Datastream offers "Backfill historical data" checkbox. If checked, processes all existing data. If unchecked, processes only new changes.
- **Lookback window:** Default to reasonable window (e.g., 24 hours) on first run to avoid overwhelming users with years of historical logs.
- **No-backfill mode:** Start from "now" and only process future events.

**Recommended for UniFi Scanner:**
```
Option 1 (Recommended): Configurable lookback window
- First run: Process last 24 hours by default
- Environment variable: INITIAL_LOOKBACK_HOURS=24

Option 2: No backfill
- First run: Process events from "now" onwards
- User gets empty report initially

Option 3: Full backfill
- First run: Process ALL historical events
- High risk of overwhelming report
```

**Best practice from research:** Option 1 with sensible default (24h). LogScale tags backfill events with `humioBackfill` tag to distinguish them.

### 2. Incremental Processing

**User expectation:** Each report shows only NEW events since last report.

**Implementation:**
```python
# Pseudocode
if state_file_exists():
    last_run = read_state_file()
    events = query_events(since=last_run.timestamp)
else:
    # First run
    events = query_events(since=now() - INITIAL_LOOKBACK_HOURS)

if events:
    report = generate_report(events)
    send_report(report)
    write_state_file(timestamp=now())
else:
    # No new events
    if config.report_on_empty:
        send_report("No new events since last run")
    write_state_file(timestamp=now())  # Still update timestamp
```

### 3. State Update Timing

**User expectation:** If report generation fails, don't lose events.

**Critical pattern from stream processing:**
- Apache Flink: Checkpoint barriers flow through pipeline. State committed AFTER successful processing.
- Kafka: Consumer commits offset AFTER message processing succeeds.
- **Anti-pattern:** Update state before processing completes → events lost if processing fails.

**For UniFi Scanner:**
```
CORRECT:
1. Query new events
2. Generate report
3. Send/write report
4. IF all succeeded → update state file
5. ELSE → leave state file unchanged

INCORRECT:
1. Query new events
2. Update state file  ← TOO EARLY
3. Generate report (might fail)
4. Send report (might fail)
```

### 4. State File Corruption/Loss Recovery

**User expectation:** Tool recovers gracefully, doesn't lose all history or crash.

**Research findings:**
- Terraform state: "Never manually edit state files." Corrupted state → infrastructure drift.
- Best practice: Treat missing/corrupted state same as first run.

**For UniFi Scanner:**
```python
def load_state():
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
            validate_state(state)  # Check required fields
            return state
    except (FileNotFoundError, json.JSONDecodeError, ValidationError):
        log.warning("State file missing/corrupted, treating as first run")
        return None  # Falls back to first-run behavior
```

**Optional enhancement:** Write state to two files (current + backup). If current corrupted, try backup.

### 5. Empty Report Handling

**User expectation:** Don't spam me when nothing happened.

**Options:**
1. **Skip report entirely** (recommended for quiet periods)
2. **Send summary report** ("No new events since last run — network healthy")
3. **Configurable threshold** (only send if >N events)

**Research pattern:** LogicMonitor recommends reducing alert volume by 60-80% through intelligent filtering. Sending "nothing happened" reports contributes to alert fatigue.

**Recommendation:**
- Default: Skip report if zero events
- Config option: `SEND_EMPTY_REPORTS=false`
- Special case: If >7 days since last report, send "still monitoring, no events" confirmation

---

## Edge Cases

Scenarios that break naive implementations.

### 1. Clock Skew / Time Drift

**Problem:** Server clock drifts backward. Events with "future" timestamps get missed.

**Research findings:**
- Modern cloud VPCs: assume 1-50ms drift within region, 100-500ms across regions
- Time series databases: accept writes up to 6-24 hour late arrival window
- Chat apps avoid timestamp-based ordering due to drift issues

**Impact on UniFi Scanner:**
- UniFi gateway clock drifts 30 seconds slow
- Last run timestamp: 2026-01-24 18:00:00
- Event occurs at: 2026-01-24 18:00:15 (gateway time)
- Next run queries: WHERE timestamp > '2026-01-24 18:00:00'
- Event MISSED because gateway timestamp appears in past

**Mitigation strategies:**
1. **Tolerance window:** Query `WHERE timestamp > (last_run - 5 minutes)` to catch late arrivals
2. **Event ID tracking:** Use event unique ID instead of timestamp for exact-once processing
3. **Overlap window:** Accept some duplication to avoid missing events

**Recommended approach:**
```python
# Add 5-minute tolerance for clock skew
query_start = last_run_timestamp - timedelta(minutes=5)
events = query_events(since=query_start)

# Deduplicate by event ID if available
if last_processed_event_id:
    events = [e for e in events if e.id > last_processed_event_id]
```

### 2. Event Timestamp vs Processing Timestamp

**Problem:** Should we track when event OCCURRED or when we PROCESSED it?

**Research pattern (Apache Flink):**
- **Event time:** When event occurred in real world
- **Processing time:** When system processed event
- **Watermark:** Tracks progress of event time

**For log monitoring:**
- Events arrive out of order (5 events occur, API returns them in random order)
- If we track "last processed time," we might skip events with earlier timestamps

**Example:**
```
API call at 18:00 returns events:
- Event A: timestamp 17:58
- Event B: timestamp 17:59
- Event C: timestamp 17:57  ← Out of order

If we set last_run = 17:59 after processing, Event C gets missed in next run.
```

**Solution:** Track **maximum event timestamp seen**, not processing time:
```python
events = query_events(since=last_run)
if events:
    max_event_time = max(e.timestamp for e in events)
    write_state(last_run=max_event_time)
```

### 3. API Pagination and State

**Problem:** Query returns 1000 events, but API paginates at 100/page. Crash on page 7.

**Risk:** Process pages 1-6, crash, restart → reprocess pages 1-6 again.

**Pattern from distributed systems:**
- Checkpoint per batch, not per entire operation
- Accept "at least once" delivery (some duplicates) vs risking "at most once" (losing data)

**Trade-off for UniFi Scanner:**
- **Option A (simpler):** Update state only after ALL pages processed
  - Risk: Reprocess all events if crash mid-pagination
  - Benefit: Simpler code, guaranteed consistency
- **Option B (robust):** Update state after each page
  - Risk: State file thrashing
  - Benefit: Never reprocess more than 1 page of events

**Recommendation:** Option A for v1 (simpler). Pagination crash is rare, reprocessing is safe (just generates duplicate report).

### 4. Concurrent Runs

**Problem:** Cron triggers run at 18:00. Previous run still processing. Both runs execute.

**Research pattern:**
- Fluentd: File position tracking prevents concurrent writes
- Best practice: Lock file or "is_running" flag

**For UniFi Scanner:**
```python
LOCK_FILE = "/reports/.running"

def run():
    if os.path.exists(LOCK_FILE):
        log.warning("Previous run still in progress, skipping")
        return

    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

    try:
        execute_report_generation()
    finally:
        os.remove(LOCK_FILE)
```

**Alternative:** Use flock() for atomic locking.

### 5. State File Location and Permissions

**Problem:** State file written to read-only filesystem or wrong volume.

**Research pattern:**
- Fluentd: `pos_file` specified in config, must be writable
- Filebeat: Database file must be unique per plugin instance

**For UniFi Scanner (Docker context):**
- Reports written to `/reports` volume mount
- State file should be in same volume for persistence
- Path: `/reports/.last_run.json` (hidden file)
- Permissions: Container user must have write access

**Validation on startup:**
```python
def validate_state_file_writable():
    try:
        with open(STATE_FILE, 'a') as f:
            pass  # Touch file
        return True
    except IOError as e:
        log.error(f"State file not writable: {e}")
        sys.exit(1)
```

### 6. UniFi API Event ID Availability

**Problem:** UniFi API might not return stable event IDs.

**Research needed:** Does UniFi API provide:
- Unique event ID per log entry?
- Monotonically increasing ID?
- Or just timestamp?

**Fallback strategy if no event ID:**
- Use timestamp + hash of event content
- Accept small risk of duplicates rather than missing events

```python
def get_event_fingerprint(event):
    """Generate unique fingerprint for deduplication."""
    if hasattr(event, 'id'):
        return event.id
    else:
        # Fallback: timestamp + content hash
        content = f"{event.timestamp}{event.message}{event.device}"
        return hashlib.md5(content.encode()).hexdigest()
```

---

## Configuration Options

What might be configurable based on research patterns.

| Option | Purpose | Default | Notes |
|--------|---------|---------|-------|
| **INITIAL_LOOKBACK_HOURS** | How far back on first run | 24 | Databricks: configurable backfill window |
| **ENABLE_BACKFILL** | Process all historical data on first run | false | Google Datastream: checkbox option |
| **STATE_FILE_PATH** | Where to store checkpoint | /reports/.last_run.json | Fluentd: configurable pos_file |
| **SEND_EMPTY_REPORTS** | Send report when no new events | false | Alert fatigue prevention |
| **CLOCK_SKEW_TOLERANCE_MINUTES** | Lookback buffer for time drift | 5 | Time series DB: 6-24h late arrival window |
| **ENABLE_EVENT_ID_DEDUP** | Use event ID for exact deduplication | true (if available) | Elasticsearch: custom document IDs |
| **STATE_UPDATE_MODE** | When to update state: after_report or after_send | after_send | Kafka: commit after processing |
| **ENABLE_CONCURRENT_RUN_LOCK** | Prevent overlapping executions | true | Distributed systems: standard pattern |

### Advanced Options (Post-v1)

| Option | Purpose | Default | Notes |
|--------|---------|---------|-------|
| **STATE_BACKUP_ENABLED** | Write backup state file | false | Terraform: versioned state files |
| **EVENT_DEDUP_CACHE_SIZE** | In-memory cache of recent event IDs | 10000 | Vector dedupe: configurable cache size |
| **EVENT_DEDUP_CACHE_TTL_HOURS** | How long to cache event IDs | 24 | Vector: configurable max age |
| **BATCH_CHECKPOINT_ENABLED** | Update state per batch vs per run | false | Distributed systems: micro-batching |

---

## Comparison: Deduplication vs Incremental Processing

Research revealed two distinct patterns often conflated:

### Pattern 1: Event Deduplication (Within Single Run)

**Problem:** Same event appears multiple times in log stream
**Example:** Router goes down → 50 alerts for same root cause
**Solution:** Hash-based deduplication, group by signature
**Tools:** Elasticsearch (custom document IDs), Vector (dedupe transform), syslog-ng (grouping-by)

**Key features:**
- Cache of recently seen event IDs/hashes
- Time window (e.g., dedupe within 10 seconds)
- Group similar events, report count

**UniFi Scanner already has this:** Line 32 of existing FEATURES.md mentions "Issue deduplication — Group by signature/pattern, report count"

### Pattern 2: Incremental Processing (Across Runs)

**Problem:** Don't reprocess events from previous runs
**Example:** Daily report shouldn't re-report yesterday's events
**Solution:** Checkpoint/watermark tracking
**Tools:** Fluentd (pos_file), Filebeat (state DB), Kafka (consumer offsets)

**Key features:**
- Persistent state file
- Timestamp or offset tracking
- Resume from last position

**UniFi Scanner needs this:** Current milestone objective

### UniFi Scanner Needs BOTH

1. **Within-run deduplication:** If 100 identical "port scan" alerts occur in 1 hour, show as "Port scan detected (100 occurrences)"
2. **Cross-run incremental processing:** Don't re-report the same 100 alerts in tomorrow's report

**Implementation:**
```python
# Cross-run: Only query new events
events = query_events(since=last_run_timestamp)

# Within-run: Deduplicate by signature
deduplicated = group_by_signature(events)

# Report
for signature, occurrences in deduplicated:
    report.add(f"{signature.description} ({len(occurrences)} occurrences)")
```

---

## Research Confidence

| Area | Confidence | Source |
|------|------------|--------|
| Checkpoint pattern | HIGH | Fluentd/Filebeat official docs, Apache Flink docs |
| First run behavior | HIGH | Google Datastream docs, Databricks backfill docs |
| Clock skew handling | HIGH | Distributed systems research, time series DB patterns |
| State update timing | HIGH | Kafka consumer patterns, stream processing best practices |
| Configuration options | MEDIUM | Inferred from multiple tools; specific defaults need validation |
| UniFi API event IDs | LOW | Needs direct API investigation |

---

## Implementation Checklist

Based on research findings, UniFi Scanner should:

**Phase 1: Basic Incremental Processing**
- [ ] Create state file structure (.last_run.json)
- [ ] Write state file to /reports volume (persists across restarts)
- [ ] On first run, use 24h lookback window (configurable)
- [ ] Query events WHERE timestamp > last_run_timestamp
- [ ] Update state ONLY after successful report send
- [ ] Handle missing/corrupted state file gracefully (treat as first run)

**Phase 2: Edge Case Handling**
- [ ] Add 5-minute clock skew tolerance (query last_run - 5min)
- [ ] Track max event timestamp seen (not processing time)
- [ ] Add concurrent run lock file
- [ ] Validate state file writable on startup
- [ ] Handle empty results (skip report by default, configurable)

**Phase 3: Event ID Deduplication (if available)**
- [ ] Investigate UniFi API for event ID field
- [ ] If available, track last_processed_event_id
- [ ] Use event ID for exact-once processing
- [ ] Fallback to timestamp+hash if no ID

**Phase 4: Configuration & Polish**
- [ ] Environment variables for all config options
- [ ] Document state file format
- [ ] Add state file validation (schema check)
- [ ] Logging: "Processing N new events since TIMESTAMP"

---

## Sources

### State Tracking Patterns (HIGH confidence)
- [Fluentd tail input plugin](https://docs.fluentd.org/input/tail) - Position file tracking
- [Fluent Bit tail input](https://docs.fluentbit.io/manual/data-pipeline/inputs/tail) - SQLite database for state
- [Apache Flink Event Time and Watermarks](https://developer.confluent.io/courses/apache-flink/timely-stream-processing/) - Watermark concept
- [Apache Flink Checkpointing](https://medium.com/@akash.d.goel/apache-flink-series-part-6-4ef9ad38e051) - Checkpoint barriers

### Backfill and First Run (HIGH confidence)
- [Databricks Backfilling Historical Data](https://docs.databricks.com/aws/en/ldp/flows-backfill) - ONCE option for one-time backfill
- [Google Cloud Datastream Backfill](https://cloud.google.com/datastream/docs/manage-backfill-for-the-objects-of-a-stream) - Backfill checkbox option
- [LogScale Backfilling Data](https://library.humio.com/falcon-logscale-cloud/ingesting-data-backfilling.html) - humioBackfill tag for historical events

### Clock Skew and Time Drift (HIGH confidence)
- [Clock Offset vs Clock Skew](https://www.baeldung.com/cs/clock-offset-skew-difference) - Definitions and differences
- [When Logs Lie: Clock Drift](https://scalardynamic.com/resources/articles/21-when-logs-lie-how-clock-drift-skews-reality-and-breaks-systems) - Impact on log ordering
- [Out of Order Data in Time Series](https://www.systemoverflow.com/learn/database-design/time-series-databases/out-of-order-data-and-late-arrivals-handling-time-series-reality) - Late arrival windows

### Event Deduplication (HIGH confidence)
- [Elasticsearch Log Deduplication](https://www.elastic.co/blog/log-deduplication-with-elasticsearch) - Custom document IDs
- [Vector Dedupe Transform](https://vector.dev/docs/reference/configuration/transforms/dedupe/) - Cache-based deduplication
- [Syslog-ng Streaming Deduplication](https://syslog-ng-future.blog/streaming-deduplication-in-syslog-ng/) - grouping-by() parser

### Alert Fatigue and Best Practices (MEDIUM confidence)
- [Event Correlation Guide 2026](https://www.inoc.com/event-correlation) - 98.8% deduplication rates
- [Log Management Best Practices 2026](https://strongdm.com/blog/log-management-best-practices) - Filtering reduces volume 60-80%

### State File Recovery (MEDIUM confidence)
- [Terraform State Corruption Recovery](https://www.fosstechnix.com/terraform-state-file-corruption-recovery/) - Never manually edit state
- [File Integrity Monitoring Tools](https://eureka.patsnap.com/article/monitoring-file-system-corruption-and-data-recovery-strategies) - Tripwire, OSSEC
