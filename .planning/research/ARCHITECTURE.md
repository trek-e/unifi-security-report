# Architecture Research: State Integration

**Project:** UniFi Scanner - v0.3-alpha State Persistence
**Researched:** 2026-01-24
**Confidence:** HIGH

## Executive Summary

State persistence for duplicate event filtering must integrate cleanly into the existing `run_report_job()` pipeline without disrupting the established orchestration flow. Based on analysis of the current architecture and industry patterns for idempotent data pipelines, state should be:

1. **Read BEFORE log collection** to establish the filter cutoff timestamp
2. **Written AFTER successful delivery** using an idempotent commit pattern
3. **NOT updated on failure** to prevent data loss and ensure re-processing on retry

This follows the **checkpoint-after-delivery** pattern used in stream processing systems, where state commits occur only after all downstream operations succeed.

## Current Pipeline Architecture

### Existing Flow (from `__main__.py::run_report_job()`)

```
1. Connect to UniFi API
2. Select site
3. Collect logs (LogCollector)
   └─> collector.collect() returns List[LogEntry]
4. Analyze logs (AnalysisEngine)
   └─> engine.analyze(log_entries) returns List[Finding]
5. Build report (Report)
   └─> Report(period_start, period_end, findings, ...)
6. Generate content (ReportGenerator)
   └─> generator.generate_html(report)
   └─> generator.generate_text(report)
7. Deliver (DeliveryManager)
   └─> manager.deliver(report, html, text, recipients)
   └─> Returns bool (success/failure)
8. Update health status based on delivery success
```

**Current characteristics:**
- Pipeline is **linear and synchronous** (no parallelization)
- **Error handling via exceptions** (caught at job level)
- **Delivery is the final success indicator** (bool return)
- **No existing state persistence** mechanism

## Integration Points

### Integration Point 1: State Read (Before Log Collection)

**Location:** Between step 2 (select site) and step 3 (collect logs)

**Purpose:** Determine the timestamp cutoff for filtering logs

**Implementation pattern:**
```python
# After site selection, before log collection
state_manager = StateManager(state_file_path)
last_successful_run = state_manager.read_last_run()

# Pass to collector for filtering
collector = LogCollector(
    client=client,
    settings=config,
    site=site,
    since_timestamp=last_successful_run,  # NEW parameter
)
log_entries = collector.collect()
```

**Rationale:**
- State read must happen **before collection** to inform what to fetch
- Placing it immediately before `LogCollector` construction keeps related operations adjacent
- If state file doesn't exist (first run), use default lookback period (e.g., 24 hours)

**Failure handling:**
- Missing state file: Use default lookback period (safe default for first run)
- Corrupted state file: Log warning, use default lookback period, continue
- State file permissions error: Raise exception (configuration problem, should halt)

### Integration Point 2: State Write (After Successful Delivery)

**Location:** After step 7 (deliver) returns `True`, before step 8 (health status update)

**Purpose:** Record successful run timestamp to prevent duplicate reporting

**Implementation pattern:**
```python
success = manager.deliver(
    report=report,
    html_content=html_content,
    text_content=text_content,
    email_recipients=recipients,
)

if success:
    # COMMIT PATTERN: Update state only after successful delivery
    try:
        state_manager.write_last_run(report.generated_at)
        log.info("state_updated", timestamp=report.generated_at)
    except Exception as e:
        # State update failure is non-fatal (delivery already succeeded)
        log.error("state_update_failed", error=str(e))
        # Continue to health status update

    log.info("job_complete", status="success")
    update_health_status(HealthStatus.HEALTHY, {"last_run": "success"})
else:
    # CRITICAL: Do NOT update state on delivery failure
    log.warning("job_complete", status="delivery_failed")
    update_health_status(HealthStatus.UNHEALTHY, {"last_run": "delivery_failed"})
```

**Rationale:**
- State update **after delivery success** ensures idempotent retry behavior
- If delivery fails but state updates, subsequent runs would skip those events permanently
- State update failure is logged but non-fatal (delivery already succeeded, state will lag but not lose data)

## Data Flow with State Integration

### Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ run_report_job()                                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Connect to UniFi API                                        │
│  2. Select site                                                 │
│                                                                 │
│  ┌───────────────────────────────────────┐                     │
│  │ STATE READ                            │                     │
│  │ - Load .last_run.json                 │                     │
│  │ - Extract timestamp                   │                     │
│  │ - Default to NOW - 24h if missing     │                     │
│  └───────────────────────────────────────┘                     │
│         │                                                        │
│         ▼                                                        │
│  3. Collect logs (with timestamp filter)                        │
│     - API request: events since <timestamp>                     │
│     - Filter out older events                                   │
│                                                                 │
│  4. Analyze logs → Findings                                     │
│  5. Build Report                                                │
│  6. Generate HTML/Text                                          │
│  7. Deliver                                                     │
│         │                                                        │
│         ├─ SUCCESS ─────────┐                                   │
│         │                   ▼                                   │
│         │            ┌───────────────────────────────────┐      │
│         │            │ STATE WRITE (COMMIT)              │      │
│         │            │ - Update .last_run.json           │      │
│         │            │ - Write report.generated_at       │      │
│         │            │ - Atomic write (temp + rename)    │      │
│         │            └───────────────────────────────────┘      │
│         │                   │                                   │
│         │                   ▼                                   │
│         │            8. Health: HEALTHY                         │
│         │                                                        │
│         └─ FAILURE ────> 8. Health: UNHEALTHY                   │
│                          (DO NOT UPDATE STATE)                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### State File Format

**Location:** `{file_output_dir}/.last_run.json` (same directory as reports)

**Format:**
```json
{
  "last_successful_run": "2026-01-24T14:30:00Z",
  "last_report_count": 3,
  "schema_version": "1.0"
}
```

**Fields:**
- `last_successful_run`: ISO 8601 timestamp in UTC (required)
- `last_report_count`: Number of findings in last report (informational, optional)
- `schema_version`: Format version for future migrations (required)

**Rationale:**
- Atomic writes prevent partial state corruption
- Schema version supports future enhancements
- Stored in reports directory reuses existing volume mount

## Failure Handling

### When NOT to Update State

Critical scenarios where state must NOT be updated:

| Failure Scenario | State Action | Rationale |
|------------------|--------------|-----------|
| **Delivery fails** | DO NOT UPDATE | Events not delivered; must retry with same events |
| **Email fails, file fallback succeeds** | UPDATE | Fallback delivery counts as success |
| **Report generation throws exception** | DO NOT UPDATE | Job aborted before delivery |
| **Log collection fails** | DO NOT UPDATE | No events processed |
| **Analysis throws exception** | DO NOT UPDATE | Processing incomplete |

### When TO Update State

| Success Scenario | State Action | Timestamp Value |
|------------------|--------------|-----------------|
| **Both email and file succeed** | UPDATE | `report.generated_at` |
| **Email succeeds, file disabled** | UPDATE | `report.generated_at` |
| **Email fails, file fallback succeeds** | UPDATE | `report.generated_at` |
| **File succeeds, email disabled** | UPDATE | `report.generated_at` |

### State Update Failure Handling

If state update fails AFTER successful delivery:

```python
if success:
    try:
        state_manager.write_last_run(report.generated_at)
    except PermissionError as e:
        # CRITICAL: Cannot write state file
        log.error("state_write_permission_denied", path=state_file, error=str(e))
        # Alert admin via health status
        update_health_status(HealthStatus.DEGRADED, {
            "last_run": "success_but_state_write_failed",
            "error": str(e)
        })
    except Exception as e:
        # Other errors: log but don't fail the job
        log.error("state_update_failed", error=str(e))
```

**Recovery approach:**
- Delivery succeeded, so job is successful
- State lag means next run will have some duplicate events
- Better to have duplicate reports than missing events
- Health status reflects degraded state for admin awareness

### State Read Failure Handling

If state read fails BEFORE collection:

```python
try:
    last_run = state_manager.read_last_run()
except FileNotFoundError:
    # First run - use default lookback
    last_run = datetime.now(timezone.utc) - timedelta(hours=24)
    log.info("first_run_detected", using_default_lookback="24h")
except PermissionError as e:
    # Cannot read state - critical config issue
    log.error("state_read_permission_denied", path=state_file, error=str(e))
    raise  # Halt job - admin must fix permissions
except json.JSONDecodeError as e:
    # Corrupted state file - recoverable
    log.warning("state_file_corrupted", error=str(e), using_default_lookback="24h")
    last_run = datetime.now(timezone.utc) - timedelta(hours=24)
```

## Architectural Patterns Referenced

### 1. Checkpoint-After-Delivery Pattern

**Pattern:** State commits occur only after all downstream operations complete successfully.

**Source:** Apache Flink, Kafka Streams
- Watermark progress is checkpointed after processing completes
- Unaligned checkpoints generate watermarks after restoring in-flight data

**Application to UniFi Scanner:**
- State file is the "checkpoint"
- Delivery success is the "commit barrier"
- Failed delivery means checkpoint is not advanced

### 2. Idempotent Consumer Pattern

**Pattern:** Track delivered event identifiers to prevent re-processing even if re-consumed.

**Source:** Airbyte, Kafka exactly-once semantics
- Log of delivered event identifiers maintained separately from data
- Transaction flow: check log → deliver → record identifier → commit offset

**Application to UniFi Scanner:**
- Timestamp cutoff acts as the "delivered events log"
- Events before cutoff are filtered (not re-processed)
- State update only after delivery ensures idempotency

### 3. Delete-Write Pattern for Idempotency

**Pattern:** Atomic state replacement instead of incremental updates.

**Source:** Modern ETL systems
- Delete existing data before writing new data
- Makes pipelines idempotent even with retries

**Application to UniFi Scanner:**
- Atomic file write (temp file + rename) implements this
- Each state update completely replaces previous state
- Retries don't create duplicate state entries

## Component Boundaries

### Existing Components (No Changes Required)

| Component | Responsibility | Why No Change |
|-----------|---------------|---------------|
| `LogCollector` | Orchestrate log collection from API/SSH | Filtering logic added internally, API unchanged |
| `AnalysisEngine` | Transform logs → findings | Operates on filtered logs, oblivious to state |
| `ReportGenerator` | Transform findings → HTML/text | Operates on findings, oblivious to state |
| `DeliveryManager` | Orchestrate delivery via email/file | Already returns success bool for state decision |

### New Component

| Component | Responsibility | Interfaces |
|-----------|---------------|------------|
| `StateManager` | Read/write last run timestamp | `read_last_run() -> datetime`, `write_last_run(timestamp: datetime)` |

**Placement:** `src/unifi_scanner/state/manager.py`

**Rationale:**
- Single responsibility: state file management
- Isolated from pipeline orchestration (testable independently)
- Reusable across multiple state tracking needs (future: per-device state)

## Performance Considerations

### State File I/O Impact

**Read operation:**
- Frequency: Once per job execution
- Size: ~200 bytes JSON file
- Impact: Negligible (<1ms on modern systems)

**Write operation:**
- Frequency: Once per successful delivery
- Size: ~200 bytes JSON file
- Impact: Negligible (<5ms with atomic write)

**Conclusion:** State I/O overhead is trivial compared to API calls (100-500ms) and report generation (50-200ms).

### Log Collection Filtering

**API filtering approach:**
- UniFi Events API supports `start` parameter (epoch timestamp)
- Filter at source reduces data transfer and parsing overhead
- Typical reduction: 95-99% fewer events processed on subsequent runs

**Example:**
- First run: 10,000 events over 24 hours
- Subsequent hourly runs: 100-500 events per run
- State tracking reduces processing by ~20-100x

## Migration Strategy

### Transition from Current Behavior

**Current behavior:** Every run processes all events from last 24 hours (API default or configured lookback)

**New behavior:** Every run processes events since last successful run

**Migration path:**
1. First run with new code: No state file exists → use 24-hour lookback (same as current)
2. State file created after first successful delivery
3. Subsequent runs use state file timestamp
4. Gradual transition, no manual migration needed

### Backward Compatibility

**State file is optional:**
- Missing state file is NOT an error
- System falls back to default lookback period
- Enables rollback to old version by deleting state file

## Sources

Industry patterns and architecture references:

### Pipeline Architecture
- [Data Pipeline Architecture: 5 Design Patterns with Examples | Dagster](https://dagster.io/guides/data-pipeline-architecture-5-design-patterns-with-examples)
- [Data Pipeline Architecture: 9 Patterns & Best Practices | Alation](https://www.alation.com/blog/data-pipeline-architecture-patterns/)
- [Data Engineering Design Patterns 2026 | AWS in Plain English](https://aws.plainenglish.io/data-engineering-design-patterns-you-must-learn-in-2026-c25b7bd0b9a7)

### State Management & Filtering
- [ETL Pipeline State Management Guide 2026 | Estuary](https://estuary.dev/blog/what-is-an-etl-pipeline/)
- [ETL Pipeline Best Practices | dbt Labs](https://www.getdbt.com/blog/etl-pipeline-best-practices)

### Idempotency Patterns
- [Understanding Idempotency in Data Pipelines | Airbyte](https://airbyte.com/data-engineering-resources/idempotency-in-data-pipelines)
- [Importance of Idempotent Data Pipelines | Prefect](https://www.prefect.io/blog/the-importance-of-idempotent-data-pipelines-for-resilience)
- [How to Make Data Pipelines Idempotent | Start Data Engineering](https://www.startdataengineering.com/post/why-how-idempotent-data-pipeline/)
- [Exactly Once Semantics Using Idempotent Consumer Pattern | Medium](https://medium.com/@zdb.dashti/exactly-once-semantics-using-the-idempotent-consumer-pattern-927b2595f231)
- [Building Idempotent Data Pipelines: Practical Guide | Medium](https://medium.com/towards-data-engineering/building-idempotent-data-pipelines-a-practical-guide-to-reliability-at-scale-2afc1dcb7251)

### Checkpointing & Failure Handling
- [How Watermarking Works in Spark Streaming](https://www.sparkcodehub.com/spark/streaming/watermarking)
- [Apache Flink Checkpointing and Savepoints | Medium](https://medium.com/@akash.d.goel/apache-flink-series-part-6-4ef9ad38e051)
- [What Does Checkpointing Mean | Dagster Glossary](https://dagster.io/glossary/checkpointing)
- [Pipeline Failure and Error Handling | Azure Data Factory](https://learn.microsoft.com/en-us/azure/data-factory/tutorial-pipeline-failure-error-handling)
