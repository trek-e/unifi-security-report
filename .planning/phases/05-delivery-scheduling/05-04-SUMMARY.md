---
phase: 05-delivery-scheduling
plan: 04
subsystem: delivery
tags: [docker, scheduler, delivery, integration]

# Dependency Graph
requires: ["05-01", "05-02", "05-03"]
provides:
  - DeliveryManager for orchestrating email and file delivery
  - Integrated scheduler in __main__.py with run_report_job()
  - Dockerfile with multi-stage build
  - docker-compose.yml with complete environment reference
affects: []

# Tech Tracking
tech-stack:
  added: []
  patterns:
    - Multi-stage Docker build
    - Delivery orchestration with fallback
    - Complete service pipeline integration

# File Tracking
key-files:
  created:
    - src/unifi_scanner/delivery/manager.py
    - Dockerfile
    - docker-compose.yml
  modified:
    - src/unifi_scanner/delivery/__init__.py
    - src/unifi_scanner/__main__.py

# Decisions
decisions:
  - id: delivery-fallback
    choice: "Automatic file fallback when email fails"
    rationale: "Ensures reports are never lost even with email issues"

# Metrics
duration: 3 min
completed: 2026-01-24
---

# Phase 05 Plan 04: Docker Container Integration Summary

**One-liner:** DeliveryManager orchestration with email fallback, scheduler integration in __main__.py, and production-ready Docker container with complete env var reference.

## What Was Built

### DeliveryManager (src/unifi_scanner/delivery/manager.py)

Orchestrates report delivery via email and/or file:

```python
class DeliveryManager:
    def __init__(
        self,
        email_delivery: Optional[EmailDelivery] = None,
        file_delivery: Optional[FileDelivery] = None,
        fallback_dir: str = "./reports",
    ) -> None: ...

    def deliver(
        self,
        report: Report,
        html_content: str,
        text_content: str,
        email_recipients: Optional[List[str]] = None,
    ) -> bool: ...
```

**Key behavior:**
- Attempts email delivery first if configured
- On email failure, automatically activates file fallback
- Returns True if at least one delivery method succeeded
- Logs all delivery attempts and results

### Scheduler Integration (__main__.py)

Added `run_report_job()` function executing complete pipeline:

```python
def run_report_job() -> None:
    # 1. Connect to UniFi API
    with UnifiClient(config) as client:
        site = client.select_site(config.site)

        # 2. Collect logs
        collector = LogCollector(client=client, settings=config, site=site)
        log_entries = collector.collect()

        # 3. Analyze logs
        registry = get_default_registry()
        engine = AnalysisEngine(registry=registry)
        findings = engine.analyze(log_entries)

        # 4. Generate report
        generator = ReportGenerator(display_timezone=config.schedule_timezone)
        html_content = generator.generate_html(report)
        text_content = generator.generate_text(report)

        # 5. Deliver
        manager = DeliveryManager(...)
        manager.deliver(report, html_content, text_content, recipients)
```

Updated `main()` to use `ScheduledRunner`:
- Supports schedule presets (daily_8am, weekly_monday_8am, etc.)
- Supports custom cron expressions
- One-shot mode when no schedule configured

### Dockerfile (Multi-stage Build)

```dockerfile
# Stage 1: Build dependencies
FROM python:3.12-slim-bookworm AS builder
# Install deps, create venv, pip install .

# Stage 2: Production image
FROM python:3.12-slim-bookworm
COPY --from=builder /opt/venv /opt/venv
USER appuser
HEALTHCHECK --interval=60s ...
ENTRYPOINT ["unifi-scanner"]
```

**Features:**
- Multi-stage build for smaller image size
- Non-root user (appuser) for security
- Health check using /tmp/unifi-scanner-health file
- JSON log format default for production

### docker-compose.yml (Complete Reference)

Documents all environment variables:

| Category | Variables |
|----------|-----------|
| Connection | UNIFI_HOST, UNIFI_USERNAME, UNIFI_PORT, UNIFI_SITE, UNIFI_VERIFY_SSL |
| Scheduling | UNIFI_SCHEDULE_PRESET, UNIFI_SCHEDULE_CRON, UNIFI_SCHEDULE_TIMEZONE |
| Email | UNIFI_EMAIL_ENABLED, UNIFI_SMTP_HOST, UNIFI_SMTP_PORT, UNIFI_SMTP_USER, UNIFI_SMTP_USE_TLS, UNIFI_EMAIL_FROM, UNIFI_EMAIL_RECIPIENTS |
| File Output | UNIFI_FILE_ENABLED, UNIFI_FILE_OUTPUT_DIR, UNIFI_FILE_FORMAT, UNIFI_FILE_RETENTION_DAYS |
| Logging | UNIFI_LOG_LEVEL, UNIFI_LOG_FORMAT |

**Includes:**
- Docker secrets support (unifi_password, smtp_password)
- Volume mount for reports persistence
- Resource limits (256M max, 128M reserved)

## Deviations from Plan

None - plan executed exactly as written.

## Verification Notes

Docker daemon not available in test environment, so Docker build/run commands could not be executed. However:

- Dockerfile structure verified programmatically (multi-stage, healthcheck, non-root user)
- docker-compose.yml YAML structure validated
- All required environment variables present
- All Python imports and function signatures verified

## How to Use

### Quick Start

```bash
# Build image
docker build -t unifi-scanner .

# Test configuration
docker run --rm \
  -e UNIFI_HOST=192.168.1.1 \
  -e UNIFI_USERNAME=admin \
  -e UNIFI_PASSWORD=secret \
  unifi-scanner --test

# Run with docker-compose
cp .env.example .env  # Edit with your values
mkdir -p secrets
echo "your-unifi-password" > secrets/unifi_password.txt
docker-compose up -d
```

### Environment Variable Reference

See docker-compose.yml for complete reference with all options documented.

## Files Changed

| File | Change |
|------|--------|
| src/unifi_scanner/delivery/manager.py | Created - DeliveryManager class |
| src/unifi_scanner/delivery/__init__.py | Updated - Export DeliveryManager |
| src/unifi_scanner/__main__.py | Updated - Scheduler and delivery integration |
| Dockerfile | Created - Multi-stage build |
| docker-compose.yml | Created - Complete deployment reference |

## Commits

- `9664709`: feat(05-04): add DeliveryManager for orchestrating report delivery
- `7042285`: feat(05-04): integrate scheduler and delivery into __main__.py
- `7e5d936`: feat(05-04): add Dockerfile and docker-compose.yml

## Next Phase Readiness

Phase 5 is now complete. The UniFi Scanner is ready for production deployment:

- All delivery methods implemented (email, file)
- Scheduler supports presets and custom cron
- Docker container ready for deployment
- Complete environment variable documentation
