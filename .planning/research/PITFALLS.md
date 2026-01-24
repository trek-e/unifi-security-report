# Pitfalls Research: State Persistence in Containerized Services

**Domain:** File-based state persistence for Docker-scheduled log monitoring
**Researched:** 2026-01-24
**Confidence:** HIGH (verified with official sources and production experience)

## Executive Summary

Adding `.last_run.json` to a containerized service presents 8 critical pitfalls that can cause data loss, corruption, or incorrect behavior. The three most dangerous are: (1) partial writes during power failure, (2) permission mismatches between container and host, and (3) concurrent container instances racing for the same file. All are preventable with atomic writes, proper volume ownership, and instance locking.

---

## Critical Pitfalls

### Pitfall 1: Partial Writes During Crashes

**What goes wrong:**
Power outage or container crash during JSON write leaves `.last_run.json` corrupted with partial content. Next run reads malformed JSON, crashes, and loses track of last processed timestamp. Service re-processes all historical events.

**Why it happens:**
Python's `json.dump()` and `f.write()` are not atomic. If interrupted mid-write, the file contains incomplete JSON like `{"last_run_at": "2026-01-` (no closing brace, truncated timestamp).

**Consequences:**
- **Data loss:** State file unreadable, treated as "never run before"
- **Duplicate reports:** All events re-processed and re-reported
- **Service crash:** JSON parser exception on corrupted file

**Detection:**
- JSON decode errors in logs (`json.JSONDecodeError: Expecting ',' delimiter`)
- State file exists but empty or truncated
- Reports contain events that should have been filtered

**Prevention:**
```python
# WRONG: Direct write (not atomic)
with open('.last_run.json', 'w') as f:
    json.dump(state, f)

# RIGHT: Atomic write (write-to-temp-then-rename)
import tempfile
import shutil

temp_fd, temp_path = tempfile.mkstemp(
    dir=output_dir,      # Same filesystem as target
    prefix='.tmp-state-',
    suffix='.json'
)
try:
    with open(temp_fd, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())  # Force OS to write to disk
    shutil.move(temp_path, '.last_run.json')  # Atomic on POSIX
except Exception:
    Path(temp_path).unlink(missing_ok=True)
    raise
```

**Implementation phase:** State file writer (core module)

**Source confidence:** HIGH - Production experience documented in [DEV Community crash-safe JSON article](https://dev.to/constanta/crash-safe-json-at-scale-atomic-writes-recovery-without-a-db-3aic), atomic writes pattern used in existing `FileDelivery._atomic_write()` at line 61-80.

---

### Pitfall 2: Permission Mismatches on Volume Mounts

**What goes wrong:**
Container runs as `appuser` (UID 1000), but host volume is owned by root or different UID. Container cannot create or write `.last_run.json`, fails silently or crashes with `PermissionError`.

**Why it happens:**
Docker bind mounts preserve host filesystem permissions. Container UID doesn't match host UID. The Dockerfile creates `appuser` with container-specific UID that may not map to host ownership of mounted `/app/reports`.

**Consequences:**
- **Silent failure:** State file never created, every run is "first run"
- **Crash on write:** `PermissionError: [Errno 13] Permission denied: '/app/reports/.last_run.json'`
- **Inconsistent behavior:** Works in dev (root user), fails in production (non-root user)

**Detection:**
- Permission denied errors in logs
- State file missing despite successful runs
- Different behavior between `docker run` (may run as root) and `docker-compose` (respects USER directive)
- `ls -la /app/reports` inside container shows ownership mismatch

**Prevention Strategy 1 - Named volumes (preferred):**
```yaml
# docker-compose.yml
volumes:
  - reports_volume:/app/reports  # Named volume, not bind mount
volumes:
  reports_volume:
```
Named volumes handle permissions automatically, created with correct ownership for container user.

**Prevention Strategy 2 - Fix bind mount ownership:**
```yaml
# docker-compose.yml
services:
  unifi-scanner:
    volumes:
      - ./reports:/app/reports
    user: "${UID:-1000}:${GID:-1000}"  # Match host user
```

**Prevention Strategy 3 - Entrypoint permission fix:**
```dockerfile
# Run as root initially to fix permissions, then drop to appuser
ENTRYPOINT ["/docker-entrypoint.sh"]

# docker-entrypoint.sh
#!/bin/bash
chown -R appuser:appuser /app/reports
exec gosu appuser unifi-scanner "$@"
```

**Implementation phase:** Docker configuration / deployment documentation

**Source confidence:** HIGH - [Docker official docs on volume permissions](https://labex.io/tutorials/docker-how-to-resolve-permission-denied-error-when-mounting-volume-in-docker-417724), [permission handling guide](https://denibertovic.com/posts/handling-permissions-with-docker-volumes/), existing Dockerfile shows non-root user at line 39-42.

---

### Pitfall 3: Concurrent Container Instances

**What goes wrong:**
Two container instances run simultaneously (manual trigger during scheduled run, or overlapping cron). Both read `.last_run.json`, both process same events, both write state. Last writer wins, timestamps may be inconsistent, duplicate reports sent.

**Why it happens:**
- Ofelia or cron scheduler has no overlap protection
- Docker Compose can launch multiple instances if misconfigured
- Manual `docker run` while scheduled container is running
- Previous run hasn't completed when next scheduled run starts

**Consequences:**
- **Duplicate reports:** Both instances process and report same events
- **State corruption:** Race condition where both write simultaneously produces corrupted JSON
- **Lost state updates:** Earlier completion overwrites later completion's timestamp
- **Resource contention:** Both containers hammering UniFi API simultaneously

**Detection:**
- Overlapping container logs (two instances running at same time)
- Multiple reports generated within seconds
- State file timestamp doesn't match last container completion time
- API rate limiting errors

**Prevention Strategy 1 - File locking (simple):**
```python
import fcntl

LOCK_FILE = output_dir / '.last_run.lock'

def acquire_lock():
    """Acquire exclusive lock or exit if already running."""
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        log.error("Another instance is already running")
        sys.exit(1)
```

**Prevention Strategy 2 - Ofelia no-overlap:**
```yaml
# docker-compose.yml with Ofelia scheduler
labels:
  ofelia.enabled: "true"
  ofelia.job-exec.unifi-scan.schedule: "@daily"
  ofelia.job-exec.unifi-scan.no-overlap: "true"  # Critical!
```

**Prevention Strategy 3 - APScheduler max_instances:**
```python
# If using APScheduler internally
scheduler.add_job(
    scan_and_report,
    'cron',
    hour=2,
    max_instances=1,  # Prevent concurrent runs
    coalesce=True     # Skip missed runs instead of queuing
)
```

**Implementation phase:** Scheduler configuration or state manager initialization

**Source confidence:** HIGH - [Ofelia documentation on no-overlap](https://github.com/mcuadros/ofelia), [APScheduler concurrency controls](https://oneuptime.com/blog/post/2026-01-06-docker-cron-jobs/view), [file locking fundamentals](https://www.baeldung.com/linux/file-locking).

---

### Pitfall 4: Container Ephemeral Filesystem Confusion

**What goes wrong:**
Developer stores `.last_run.json` in container's writable layer (not mounted volume). State persists between runs during development, disappears when container is removed. Production loses state on every container restart.

**Why it happens:**
Containers appear persistent during development (running container maintains writable layer). The illusion breaks when container is removed (e.g., `docker-compose down`). Developers test with `docker-compose stop/start` (preserves container) instead of `down/up` (removes container).

**Consequences:**
- **Works in dev, fails in prod:** Restarts erase state
- **Every run is "first run":** All events re-processed after container recreation
- **Silent data loss:** No error message, state just gone

**Detection:**
- State file exists inside running container but missing after restart
- `docker inspect` shows state file path not in mounted volumes
- Reports contain events that should have been filtered (every run after restart)

**Prevention:**
```python
# Enforce that state file MUST be in mounted volume
STATE_FILE_PATH = Path(os.getenv('REPORTS_DIR', '/app/reports')) / '.last_run.json'

# Verify at startup that path is on a volume
def verify_volume_mount():
    """Ensure reports directory is a mounted volume."""
    # Check if directory exists and is writable
    if not STATE_FILE_PATH.parent.is_dir():
        raise RuntimeError(f"{STATE_FILE_PATH.parent} is not a directory")

    # Try writing a test file to verify it's writable
    test_file = STATE_FILE_PATH.parent / '.write-test'
    try:
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        raise RuntimeError(f"Cannot write to {STATE_FILE_PATH.parent}: {e}")
```

**Implementation phase:** Configuration validation at startup

**Source confidence:** HIGH - [Docker persistence fundamentals](https://docs.docker.com/get-started/workshop/05_persisting_data/), [container storage architecture](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/architect-microservice-container-applications/docker-application-state-data).

---

## Moderate Pitfalls

### Pitfall 5: Timezone Confusion in State Timestamps

**What goes wrong:**
State file stores timestamp in local time, container runs in UTC, comparison logic breaks. Service either re-processes everything (timestamp in past) or skips events (timestamp in future).

**Why it happens:**
Python's `datetime.now()` uses local timezone (undefined in containers). UniFi API may return timestamps in gateway's timezone. Report generation uses `ZoneInfo(self.timezone)` but state file doesn't normalize.

**Consequences:**
- Events skipped or duplicated based on timezone offset
- Harder to debug (timestamps look correct in isolation)
- Behavior changes with daylight saving time

**Detection:**
- State file timestamp doesn't match logs (off by N hours)
- More events processed/skipped than expected
- Issues appear after DST transitions

**Prevention:**
```python
from datetime import datetime, timezone

# ALWAYS store UTC in state file
state = {
    'last_run_at': datetime.now(timezone.utc).isoformat(),
}

# ALWAYS parse as UTC when reading
def load_state():
    with open(STATE_FILE_PATH) as f:
        data = json.load(f)
    last_run = datetime.fromisoformat(data['last_run_at'])
    # Ensure timezone-aware UTC
    if last_run.tzinfo is None:
        last_run = last_run.replace(tzinfo=timezone.utc)
    return last_run
```

**Implementation phase:** State file read/write functions

**Source confidence:** MEDIUM - Based on existing timezone handling in `unifi_scanner/utils/timestamps.py` and `FileDelivery._generate_filename()` which uses `ZoneInfo`.

---

### Pitfall 6: Missing State File Treated as Error

**What goes wrong:**
First run (no state file) crashes or logs errors instead of gracefully treating missing file as "process all events."

**Why it happens:**
Code doesn't handle `FileNotFoundError` or treats missing state as exceptional rather than expected.

**Consequences:**
- Service cannot run until state file manually created
- Confusing error logs on first deployment
- Poor user experience

**Prevention:**
```python
def load_last_run_timestamp() -> Optional[datetime]:
    """Load last run timestamp from state file.

    Returns None if file doesn't exist (first run).
    """
    try:
        with open(STATE_FILE_PATH) as f:
            data = json.load(f)
        return datetime.fromisoformat(data['last_run_at'])
    except FileNotFoundError:
        log.info("No state file found, treating as first run")
        return None
    except json.JSONDecodeError as e:
        log.error("Corrupted state file, treating as first run", error=str(e))
        return None
    except Exception as e:
        log.warning("Unexpected error reading state", error=str(e))
        return None
```

**Implementation phase:** State file reader

**Source confidence:** HIGH - Standard defensive programming practice.

---

### Pitfall 7: State File in .gitignore Breakage

**What goes wrong:**
Developer adds `*.json` to `.gitignore`, state file excluded, but testing depends on committed example state file. Or opposite: state file committed with developer's local timestamp, breaks production.

**Why it happens:**
Overly broad `.gitignore` patterns or unclear distinction between test fixtures and runtime state.

**Prevention:**
```gitignore
# .gitignore
*.json
!tests/fixtures/*.json  # Keep test fixtures
!.planning/**/*.json    # Keep planning files

# Be explicit about state files
.last_run.json
```

**Documentation:**
```markdown
# README.md
## State File Location

Runtime state stored in: `$REPORTS_DIR/.last_run.json`

**DO NOT commit this file.** It is volume-mounted and runtime-generated.
```

**Implementation phase:** Repository setup / documentation

**Source confidence:** HIGH - Common git hygiene issue.

---

### Pitfall 8: No State File Backup/Recovery

**What goes wrong:**
State file corrupted or deleted (disk failure, accidental `rm`), no backup exists, no way to recover. Service re-processes months of historical events.

**Why it happens:**
State file treated as ephemeral rather than critical persistence.

**Consequences:**
- Manual intervention required to determine last successful run
- Duplicate reports for all historical events
- Lost audit trail

**Prevention:**
```python
def save_state_with_backup(state: dict) -> None:
    """Save state with rolling backup."""
    backup_path = STATE_FILE_PATH.with_suffix('.json.bak')

    # If current state exists, back it up first
    if STATE_FILE_PATH.exists():
        shutil.copy2(STATE_FILE_PATH, backup_path)

    # Atomic write new state
    atomic_write(STATE_FILE_PATH, json.dumps(state, indent=2))

    log.debug("State saved with backup",
              state_path=str(STATE_FILE_PATH),
              backup_path=str(backup_path))

def load_state_with_recovery() -> dict:
    """Load state with automatic backup recovery."""
    try:
        return load_state(STATE_FILE_PATH)
    except (json.JSONDecodeError, OSError):
        log.warning("Primary state file corrupted, attempting backup recovery")
        backup_path = STATE_FILE_PATH.with_suffix('.json.bak')
        if backup_path.exists():
            try:
                return load_state(backup_path)
            except Exception as e:
                log.error("Backup state also corrupted", error=str(e))
        return default_state()
```

**Implementation phase:** State manager module

**Source confidence:** HIGH - Pattern documented in [crash-safe JSON production experience](https://dev.to/constanta/crash-safe-json-at-scale-atomic-writes-recovery-without-a-db-3aic).

---

## Prevention Strategies Summary

| Pitfall | Primary Prevention | Secondary Prevention | Implementation Priority |
|---------|-------------------|----------------------|------------------------|
| Partial writes | Atomic write pattern | Backup file recovery | P0 (critical) |
| Permission mismatches | Named volumes | Entrypoint permission fix | P0 (critical) |
| Concurrent instances | Ofelia no-overlap | File locking | P0 (critical) |
| Ephemeral filesystem | Startup validation | Documentation | P1 (high) |
| Timezone confusion | Always use UTC | Explicit timezone conversion | P1 (high) |
| Missing file as error | Defensive FileNotFoundError handling | Default state factory | P2 (medium) |
| .gitignore issues | Explicit ignore rules | Documentation | P2 (medium) |
| No backup/recovery | Rolling backup on write | Recovery fallback on read | P2 (medium) |

---

## Implementation Checklist

Before merging state persistence PR:

**Code:**
- [ ] State writes use atomic pattern (temp file + rename)
- [ ] UTC timestamps enforced for all state file times
- [ ] Missing state file handled gracefully (not error)
- [ ] Corrupted state file falls back to backup or default
- [ ] Startup validation checks reports directory is writable
- [ ] File locking or scheduler no-overlap configured

**Configuration:**
- [ ] Docker Compose uses named volume or documents bind mount ownership
- [ ] STATE_FILE_PATH derived from REPORTS_DIR environment variable
- [ ] Scheduler configured with max_instances=1 or no-overlap=true

**Documentation:**
- [ ] State file location documented in README
- [ ] First-run behavior explained (no state file = process all)
- [ ] Recovery procedure documented for corrupted state
- [ ] Volume mount requirements specified

**Testing:**
- [ ] Test: First run with no state file succeeds
- [ ] Test: Corrupted state file recovered from backup or defaults
- [ ] Test: Container restart preserves state (volume-mounted)
- [ ] Test: Concurrent run blocked or prevented
- [ ] Test: Permission denied handled gracefully

---

## Warning Signs During Implementation

**High-risk indicators:**

1. **Direct file writes without atomic pattern**
   - ❌ `with open('.last_run.json', 'w') as f: json.dump(state, f)`
   - ✅ Use temp file + rename pattern

2. **Hardcoded state file paths**
   - ❌ `STATE_FILE = '/app/.last_run.json'`
   - ✅ `STATE_FILE = Path(os.getenv('REPORTS_DIR')) / '.last_run.json'`

3. **No concurrency protection**
   - ❌ Scheduler without `no-overlap` or `max_instances`
   - ✅ Ofelia `no-overlap: true` or APScheduler `max_instances=1`

4. **Naive timezone handling**
   - ❌ `datetime.now()` without timezone
   - ✅ `datetime.now(timezone.utc)`

5. **Exception on missing state**
   - ❌ `state = json.load(open('.last_run.json'))`
   - ✅ Try-except with `FileNotFoundError` → return None

---

## Sources

**Official Documentation:**
- [Docker: Persisting container data](https://docs.docker.com/get-started/workshop/05_persisting_data/)
- [Docker: Volume mount permissions resolution](https://labex.io/tutorials/docker-how-to-resolve-permission-denied-error-when-mounting-volume-in-docker-417724)
- [Python JSON documentation](https://docs.python.org/3/library/json.html)

**Production Experience & Best Practices:**
- [Crash-safe JSON at scale: atomic writes + recovery](https://dev.to/constanta/crash-safe-json-at-scale-atomic-writes-recovery-without-a-db-3aic)
- [Safe atomic file writes for JSON in Python](https://gist.github.com/therightstuff/cbdcbef4010c20acc70d2175a91a321f)
- [Handling Permissions with Docker Volumes](https://denibertovic.com/posts/handling-permissions-with-docker-volumes/)

**Container Scheduling & Concurrency:**
- [How to Run Cron Jobs Inside Docker Containers (The Right Way)](https://oneuptime.com/blog/post/2026-01-06-docker-cron-jobs/view)
- [Ofelia: Docker job scheduler](https://github.com/mcuadros/ofelia)
- [File locking introduction](https://www.baeldung.com/linux/file-locking)

**Known Issues & Vulnerabilities:**
- [Node.js fs.writeFile partial write corruption](https://github.com/nodejs/node/issues/1058)
- [ECS agent state file corruption on restart](https://github.com/aws/amazon-ecs-agent/issues/1301)
- [lowdb JSON corruption from concurrent writes](https://github.com/typicode/lowdb/issues/333)

---

**Research confidence:** HIGH
**Verification:** Cross-referenced with existing `FileDelivery` implementation (atomic writes present), Dockerfile (non-root user confirmed), and official Docker/Python documentation.
