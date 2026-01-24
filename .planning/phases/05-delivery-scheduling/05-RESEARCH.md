# Phase 5: Delivery & Scheduling - Research

**Researched:** 2026-01-24
**Domain:** Email delivery, scheduling, Docker containerization
**Confidence:** HIGH

## Summary

Phase 5 implements the delivery and scheduling layer for UniFi Scanner, enabling automated report generation and delivery. The phase covers four key areas: SMTP email delivery with HTML+plaintext multipart messages, file-based report output with retention management, APScheduler-based job scheduling with timezone support, and Docker container packaging.

The standard approach uses Python's built-in `email` and `smtplib` modules for email delivery (no external dependencies needed), APScheduler 3.x for scheduling (mature, production-ready), and multi-stage Docker builds with `python:3.12-slim-bookworm` as the base image. The existing codebase already has structlog configured for JSON logging, pydantic-settings for configuration, and Jinja2 templates for report generation.

**Primary recommendation:** Use APScheduler 3.11.x with BlockingScheduler for the service loop, Python standard library for email delivery, and a multi-stage Dockerfile that keeps the image under 200MB.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APScheduler | 3.11.x | Job scheduling with cron/interval triggers | Production-stable, timezone support, active maintenance |
| smtplib | stdlib | SMTP client for email delivery | Built-in, no dependencies, full SMTP support |
| email | stdlib | MIME message construction | Built-in, handles multipart/alternative correctly |
| pathlib | stdlib | File path operations and cleanup | Modern, cross-platform file handling |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytz | 2024.x | IANA timezone database | Already in project via python-dateutil |
| ssl | stdlib | TLS/SSL context creation | SMTP_SSL and STARTTLS connections |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| smtplib | aiosmtplib | Only if async needed; adds dependency |
| APScheduler | schedule | Simpler API but no cron syntax, no timezone |
| pathlib | os.path | pathlib is more Pythonic for Python 3.9+ |

**Installation:**
```bash
# Add to pyproject.toml dependencies
pip install "APScheduler>=3.10,<4.0"
# Note: smtplib, email, pathlib, ssl are stdlib - no install needed
```

## Architecture Patterns

### Recommended Project Structure
```
src/unifi_scanner/
├── delivery/           # NEW: Delivery subsystem
│   ├── __init__.py
│   ├── email.py        # EmailDelivery class - SMTP sending
│   ├── file.py         # FileDelivery class - file output + retention
│   └── manager.py      # DeliveryManager - orchestrates both
├── scheduler/          # NEW: Scheduling subsystem
│   ├── __init__.py
│   ├── runner.py       # ScheduledRunner - APScheduler integration
│   └── presets.py      # Schedule presets (daily_8am, weekly_monday)
├── config/
│   └── settings.py     # EXTEND: Add delivery/schedule settings
└── __main__.py         # MODIFY: Integrate scheduler loop
```

### Pattern 1: Multipart Email with BCC Recipients
**What:** Send HTML+plaintext emails with all recipients hidden in BCC
**When to use:** All email delivery (per CONTEXT.md decision)
**Example:**
```python
# Source: Python docs - email.examples
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate

def send_report_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_addr: str,
    bcc_recipients: list[str],
    subject: str,
    html_content: str,
    text_content: str,
    use_tls: bool = True,
) -> None:
    """Send multipart email with BCC-only recipients."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["Date"] = formatdate(localtime=True)
    # NOTE: No To/Cc headers - all recipients via BCC (hidden)

    # Set plaintext first, then add HTML alternative
    msg.set_content(text_content)
    msg.add_alternative(html_content, subtype="html")

    # Create secure SSL context
    context = ssl.create_default_context()

    if use_tls and smtp_port == 465:
        # Implicit TLS (SMTPS)
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(from_addr, bcc_recipients, msg.as_string())
    else:
        # Explicit TLS (STARTTLS) - port 587 typically
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.sendmail(from_addr, bcc_recipients, msg.as_string())
```

### Pattern 2: APScheduler with BlockingScheduler
**What:** Main service loop using APScheduler's blocking scheduler
**When to use:** Service entry point when scheduler is the main loop
**Example:**
```python
# Source: APScheduler 3.x docs
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

def create_scheduler(timezone: str = "UTC") -> BlockingScheduler:
    """Create configured scheduler with sensible defaults."""
    job_defaults = {
        "coalesce": True,  # Combine missed runs into one
        "misfire_grace_time": 3600,  # 1 hour grace period
        "max_instances": 1,  # Prevent concurrent runs
    }
    return BlockingScheduler(
        timezone=timezone,
        job_defaults=job_defaults,
    )

def add_cron_job(
    scheduler: BlockingScheduler,
    func: callable,
    cron_expr: str,
    timezone: str,
) -> None:
    """Add job with cron expression (5-field format)."""
    trigger = CronTrigger.from_crontab(cron_expr, timezone=timezone)
    scheduler.add_job(func, trigger, id="report_job")

def add_preset_job(
    scheduler: BlockingScheduler,
    func: callable,
    preset: str,
    timezone: str,
) -> None:
    """Add job using preset schedule."""
    presets = {
        "daily_8am": {"hour": 8, "minute": 0},
        "daily_6pm": {"hour": 18, "minute": 0},
        "weekly_monday_8am": {"day_of_week": "mon", "hour": 8, "minute": 0},
        "weekly_friday_5pm": {"day_of_week": "fri", "hour": 17, "minute": 0},
    }
    if preset not in presets:
        raise ValueError(f"Unknown preset: {preset}")

    scheduler.add_job(
        func,
        "cron",
        timezone=timezone,
        **presets[preset],
        id="report_job",
    )
```

### Pattern 3: File Retention Cleanup
**What:** Delete old report files beyond retention period
**When to use:** After saving new report files
**Example:**
```python
# Source: Python pathlib + os.stat patterns
from datetime import datetime, timedelta
from pathlib import Path
import structlog

log = structlog.get_logger()

def cleanup_old_reports(
    output_dir: Path,
    retention_days: int,
    pattern: str = "unifi-report-*.html",
) -> int:
    """Delete report files older than retention_days.

    Returns count of files deleted.
    """
    if not output_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted_count = 0

    for file_path in output_dir.glob(pattern):
        try:
            # Use modification time for age calculation
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime < cutoff:
                file_path.unlink()
                deleted_count += 1
                log.debug("deleted_old_report", path=str(file_path), age_days=(datetime.now() - mtime).days)
        except (OSError, PermissionError) as e:
            log.warning("cleanup_failed", path=str(file_path), error=str(e))

    if deleted_count > 0:
        log.info("cleanup_complete", deleted=deleted_count, retention_days=retention_days)

    return deleted_count
```

### Pattern 4: Severity-Aware Email Subject
**What:** Build subject line with severity count prefix
**When to use:** Constructing email subject
**Example:**
```python
from datetime import datetime
from unifi_scanner.models.report import Report

def build_subject(report: Report, timezone: str = "UTC") -> str:
    """Build email subject with severity indicator.

    Format: "[N SEVERE] UniFi Report - Jan 24, 2026"
    or:     "UniFi Report - Jan 24, 2026" (if no severe findings)
    """
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone)
    date_str = report.generated_at.astimezone(tz).strftime("%b %d, %Y")

    if report.severe_count > 0:
        return f"[{report.severe_count} SEVERE] UniFi Report - {date_str}"
    return f"UniFi Report - {date_str}"
```

### Anti-Patterns to Avoid
- **Setting msg['Bcc'] header:** Exposes BCC recipients - pass them only to sendmail()
- **Hardcoding SMTP credentials:** Always use environment variables or Docker secrets
- **Using APScheduler 4.x:** Still in alpha; stick with stable 3.11.x
- **Logging to files in Docker:** Log to stdout; let Docker handle aggregation
- **Forgetting timezone on CronTrigger.from_crontab():** Defaults to system TZ, not scheduler TZ

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MIME multipart email | String concatenation | `email.message.EmailMessage` | RFC compliance, encoding, boundaries |
| Cron expression parsing | Regex parser | `CronTrigger.from_crontab()` | Handles all edge cases, DST |
| TLS certificate validation | Manual cert handling | `ssl.create_default_context()` | Loads system CAs, proper validation |
| Timezone conversions | Manual offset math | `zoneinfo.ZoneInfo` | DST handling, IANA database |
| Docker secret reading | Custom file reader | Extend existing `resolve_file_secrets()` | Already handles _FILE pattern |

**Key insight:** Email RFC compliance and timezone/DST handling are deceptively complex. The stdlib solutions handle edge cases that would take weeks to discover through bugs.

## Common Pitfalls

### Pitfall 1: BCC Exposed in Headers
**What goes wrong:** Setting `msg['Bcc']` header exposes recipients to all
**Why it happens:** Intuitive but incorrect - BCC works at SMTP level
**How to avoid:** Never set Bcc header; pass recipients only to `sendmail()`
**Warning signs:** Recipients can see other addresses in email client

### Pitfall 2: CronTrigger Timezone Default
**What goes wrong:** Jobs run at wrong times after deployment
**Why it happens:** `CronTrigger.from_crontab()` ignores scheduler timezone
**How to avoid:** Always pass `timezone=` explicitly to from_crontab()
**Warning signs:** Logs show job running at unexpected UTC offset

### Pitfall 3: Missing TLS Context
**What goes wrong:** Connection fails or is insecure
**Why it happens:** Not using `ssl.create_default_context()`
**How to avoid:** Always create context for SMTP_SSL and starttls()
**Warning signs:** SSL errors, certificate warnings

### Pitfall 4: File Cleanup Race Condition
**What goes wrong:** Deleting file currently being written
**Why it happens:** Cleanup runs while report save is in progress
**How to avoid:** Use atomic file writes (write to temp, then rename)
**Warning signs:** Truncated or corrupt report files

### Pitfall 5: Docker Secrets Not Found
**What goes wrong:** App crashes with "file not found" on secrets
**Why it happens:** Secret not properly mounted in docker-compose.yml
**How to avoid:** Always define secret at top-level AND reference in service
**Warning signs:** FileNotFoundError for /run/secrets/* paths

### Pitfall 6: APScheduler Missed Run Confusion
**What goes wrong:** Job never runs after container restart
**Why it happens:** Default `misfire_grace_time=1` second is too short
**How to avoid:** Set `misfire_grace_time` to reasonable value (1 hour)
**Warning signs:** "Missed execution" warnings in logs

## Code Examples

Verified patterns from official sources:

### Docker Secrets Loading (extend existing)
```python
# Source: Existing loader.py pattern + Docker docs
# Extend to support both /run/secrets/ files AND _FILE env vars
def read_docker_secret(secret_name: str, default: str | None = None) -> str | None:
    """Read secret from Docker secrets path or environment.

    Checks in order:
    1. /run/secrets/{secret_name}
    2. UNIFI_{SECRET_NAME}_FILE environment variable pointing to file
    3. UNIFI_{SECRET_NAME} environment variable
    4. default value
    """
    from pathlib import Path
    import os

    # Check Docker secrets mount
    secret_path = Path(f"/run/secrets/{secret_name}")
    if secret_path.exists():
        return secret_path.read_text().strip()

    # Check _FILE pattern (handled by existing resolve_file_secrets)
    file_env = f"UNIFI_{secret_name.upper()}_FILE"
    if file_env in os.environ:
        file_path = Path(os.environ[file_env])
        if file_path.exists():
            return file_path.read_text().strip()

    # Check direct environment variable
    env_key = f"UNIFI_{secret_name.upper()}"
    if env_key in os.environ:
        return os.environ[env_key]

    return default
```

### One-Shot Mode (No Schedule)
```python
# Source: APScheduler DateTrigger docs
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler

def run_once_and_exit(func: callable) -> None:
    """Execute function once immediately, then exit.

    Used when no schedule is configured (one-shot mode).
    """
    scheduler = BlockingScheduler()

    # Schedule for 1 second from now, then shutdown
    run_time = datetime.now() + timedelta(seconds=1)
    scheduler.add_job(
        func,
        "date",
        run_date=run_time,
        id="oneshot_job",
    )

    # Add listener to shutdown after job completes
    def shutdown_after_job(event):
        scheduler.shutdown(wait=False)

    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    scheduler.add_listener(shutdown_after_job, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    scheduler.start()
```

### Delivery Failure with File Fallback
```python
# Source: CONTEXT.md decision - no retry loop, save to file on failure
import structlog
from pathlib import Path
from datetime import datetime

log = structlog.get_logger()

def deliver_report(
    report: Report,
    html_content: str,
    text_content: str,
    email_config: dict | None,
    file_config: dict | None,
) -> bool:
    """Deliver report via configured channels.

    Email delivery failure triggers file fallback (per CONTEXT.md).
    Returns True if any delivery succeeded.
    """
    email_success = False
    file_success = False

    # Attempt email delivery
    if email_config and email_config.get("enabled"):
        try:
            send_report_email(
                html_content=html_content,
                text_content=text_content,
                **email_config,
            )
            email_success = True
            log.info("email_delivered", recipients_count=len(email_config["recipients"]))
        except Exception as e:
            log.error("email_delivery_failed", error=str(e))
            # Fallback: save to file even if file output wasn't configured
            if not file_config or not file_config.get("enabled"):
                log.warning("activating_file_fallback", reason="email_failed")
                file_config = {"enabled": True, "output_dir": "./reports", "format": "both"}

    # File delivery (explicit or fallback)
    if file_config and file_config.get("enabled"):
        try:
            save_report_files(
                html_content=html_content,
                text_content=text_content,
                **file_config,
            )
            file_success = True
        except Exception as e:
            log.error("file_delivery_failed", error=str(e))

    return email_success or file_success
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `email.mime.*` classes | `email.message.EmailMessage` | Python 3.6 | Simpler API, add_alternative() |
| `pytz` for timezones | `zoneinfo.ZoneInfo` | Python 3.9 | stdlib, no external dependency |
| Port 465 deprecated | Port 465 re-standardized | RFC 8314 (2018) | SMTP_SSL on 465 is valid again |
| APScheduler 3.x | Still current (4.x alpha) | 2025 | Stay on 3.11.x for production |
| python:3.9-slim | python:3.12-slim | 2024 | Better performance, zoneinfo builtin |

**Deprecated/outdated:**
- APScheduler 2.x: Missing modern features, no longer maintained
- `email.MIMEText` for multipart: Use `EmailMessage` with `add_alternative()`
- Port 587 as only option: Port 465 (implicit TLS) is standard again

## Open Questions

Things that couldn't be fully resolved:

1. **Missed Run Catch-Up Behavior**
   - What we know: APScheduler `coalesce=True` combines missed runs into one
   - What's unclear: Is "catch up immediately" or "wait for next scheduled time" preferred?
   - Recommendation: Use `coalesce=True` and `misfire_grace_time=3600` (1 hour)

2. **Email Retry Timing Before Fallback**
   - What we know: CONTEXT.md says "no retry loop" but mentions "retry timing"
   - What's unclear: Should there be a single retry with timeout?
   - Recommendation: No retries - fail immediately to file fallback per decision

3. **Alpine vs Slim Base Image**
   - What we know: Alpine is smaller (~50MB vs ~150MB) but has musl issues
   - What's unclear: Any project dependencies that require glibc?
   - Recommendation: Use `python:3.12-slim-bookworm` for compatibility

## Sources

### Primary (HIGH confidence)
- [APScheduler 3.x User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) - Scheduler patterns, triggers, configuration
- [Python email.examples](https://docs.python.org/3/library/email.examples.html) - Multipart email construction
- [Python smtplib](https://docs.python.org/3/library/smtplib.html) - SMTP client, TLS options
- [Docker Compose Secrets](https://docs.docker.com/compose/how-tos/use-secrets/) - Secret mounting, access patterns
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) - Version 3.11.2 current, 4.x alpha

### Secondary (MEDIUM confidence)
- [Docker Python Best Practices - TestDriven.io](https://testdriven.io/blog/docker-best-practices/) - Multi-stage build patterns
- [Python SMTP Security - Real Python](https://realpython.com/python-send-email/) - TLS/SSL configuration
- [structlog Logging Best Practices](https://www.structlog.org/en/stable/logging-best-practices.html) - stdout logging for containers
- [Pybites BCC Pattern](https://pybit.es/articles/python-mime-bcc/) - BCC recipient handling

### Tertiary (LOW confidence)
- WebSearch results for community patterns - cross-verified with official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All based on official documentation and stdlib
- Architecture: HIGH - Patterns from APScheduler docs and existing codebase
- Pitfalls: MEDIUM - Mix of official docs and community knowledge
- Docker patterns: MEDIUM - Best practices evolve; verified against 2024/2025 sources

**Research date:** 2026-01-24
**Valid until:** 2026-02-24 (30 days - stable domain, no breaking changes expected)

---

## Dockerfile Reference

Complete multi-stage Dockerfile for Phase 5:

```dockerfile
# Stage 1: Build dependencies
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Stage 2: Production image
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY src/ ./src/

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UNIFI_LOG_FORMAT=json

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check (no HTTP endpoint, check process)
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD pgrep -f "unifi-scanner" || exit 1

ENTRYPOINT ["unifi-scanner"]
```

## Docker Compose Reference

Complete docker-compose.yml with all options:

```yaml
services:
  unifi-scanner:
    build: .
    image: unifi-scanner:latest
    container_name: unifi-scanner
    restart: unless-stopped

    environment:
      # Connection (required)
      UNIFI_HOST: ${UNIFI_HOST:?UNIFI_HOST is required}
      UNIFI_USERNAME: ${UNIFI_USERNAME:?UNIFI_USERNAME is required}
      # UNIFI_PASSWORD: Set via secret below, not env var

      # Connection (optional)
      UNIFI_PORT: ${UNIFI_PORT:-}
      UNIFI_SITE: ${UNIFI_SITE:-}
      UNIFI_VERIFY_SSL: ${UNIFI_VERIFY_SSL:-true}

      # Scheduling
      UNIFI_SCHEDULE_PRESET: ${UNIFI_SCHEDULE_PRESET:-daily_8am}
      # Or use cron: UNIFI_SCHEDULE_CRON: "0 8 * * *"
      UNIFI_SCHEDULE_TIMEZONE: ${UNIFI_SCHEDULE_TIMEZONE:-UTC}

      # Email delivery
      UNIFI_EMAIL_ENABLED: ${UNIFI_EMAIL_ENABLED:-false}
      UNIFI_SMTP_HOST: ${UNIFI_SMTP_HOST:-}
      UNIFI_SMTP_PORT: ${UNIFI_SMTP_PORT:-587}
      UNIFI_SMTP_USER: ${UNIFI_SMTP_USER:-}
      # UNIFI_SMTP_PASSWORD: Set via secret below
      UNIFI_EMAIL_FROM: ${UNIFI_EMAIL_FROM:-unifi-scanner@localhost}
      UNIFI_EMAIL_RECIPIENTS: ${UNIFI_EMAIL_RECIPIENTS:-}  # Comma-separated

      # File output
      UNIFI_FILE_ENABLED: ${UNIFI_FILE_ENABLED:-false}
      UNIFI_FILE_FORMAT: ${UNIFI_FILE_FORMAT:-both}  # html, text, or both
      UNIFI_FILE_RETENTION_DAYS: ${UNIFI_FILE_RETENTION_DAYS:-30}

      # Logging
      UNIFI_LOG_LEVEL: ${UNIFI_LOG_LEVEL:-INFO}
      UNIFI_LOG_FORMAT: json

    secrets:
      - unifi_password
      - smtp_password

    volumes:
      # Optional: persist reports
      - ./reports:/app/reports:rw
      # Optional: custom config file
      - ./config.yaml:/app/config.yaml:ro

    # Resource limits (adjust as needed)
    deploy:
      resources:
        limits:
          memory: 256M
        reservations:
          memory: 128M

secrets:
  unifi_password:
    file: ./secrets/unifi_password.txt
  smtp_password:
    file: ./secrets/smtp_password.txt
```
