# Technology Stack

**Project:** UniFi Log Analysis Service
**Researched:** 2026-01-24
**Overall Confidence:** MEDIUM-HIGH

## Executive Summary

This document recommends a Python-based containerized service stack for analyzing UniFi gateway logs and generating human-readable reports. The stack prioritizes:

1. **Stability over novelty** - Production-ready libraries with active maintenance
2. **Sync-first architecture** - Polling-based service doesn't require async complexity
3. **Minimal dependencies** - Reduce attack surface and maintenance burden
4. **Container-native design** - Built for Docker from day one

---

## Recommended Stack

### Runtime Environment

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| Python | 3.12+ | Core runtime | HIGH |
| Docker | - | Containerization | HIGH |
| python:3.12-slim-bookworm | - | Base image | HIGH |

**Why Python 3.12+:**
- Latest stable release with performance improvements
- Full type hint support for modern syntax (`list[str]` vs `typing.List[str]`)
- All recommended libraries support 3.12+
- EOL not until 2028

**Why slim-bookworm over Alpine:**
- Better compatibility with compiled packages (cryptography, etc.)
- Paramiko and other SSH libraries work without musl issues
- Only ~100MB larger than Alpine but avoids wheel compilation problems
- Debian-based = glibc compatibility

**Source:** [Docker Best Practices 2025](https://collabnix.com/10-essential-docker-best-practices-for-python-developers-in-2025/)

---

### UniFi API Integration

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| unifi-controller-api | 0.3.2 | UniFi Controller API client | MEDIUM |
| requests | 2.32.5 | HTTP client (dependency) | HIGH |

**Why unifi-controller-api:**
- Most actively maintained Python UniFi library (released Dec 2025)
- Typed data models (`UnifiDevice`, `UnifiSite`, `UnifiClient`)
- Supports both UDM Pro/SE and legacy controllers
- Minimal dependencies (only `requests`)

**Caveats (MEDIUM confidence):**
- Under active development, API may change
- Only 11 GitHub stars, small community
- Undocumented UniFi API may break between controller versions
- May need custom extensions for log-specific endpoints

**Alternative Considered:**
| Library | Why Not |
|---------|---------|
| unificontrol | Archived, substantially outdated API support |
| unifi-python-api | Less feature-rich, basic functionality only |

**Source:** [PyPI unifi-controller-api](https://pypi.org/project/unifi-controller-api/) (verified Dec 27, 2025)

---

### SSH Fallback

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| paramiko | 4.0.0 | SSH client for direct log access | HIGH |

**Why Paramiko over AsyncSSH:**
- LGPL license (more permissive than EPL)
- Synchronous API matches our polling architecture
- Production-stable, used by Ansible
- No async complexity overhead for simple SSH commands

**When to use SSH fallback:**
- API doesn't expose needed log data
- Need raw syslog files from `/var/log/`
- Direct device access when controller unavailable

**Alternative Considered:**
| Library | Why Not |
|---------|---------|
| asyncssh | EPL license incompatible with some projects; async overhead unnecessary |
| fabric | Higher-level abstraction than needed; adds dependencies |

**Source:** [PyPI paramiko](https://pypi.org/project/paramiko/) (verified Aug 4, 2025)

---

### Log Parsing & Analysis

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| Python re (stdlib) | - | Regex parsing | HIGH |
| pydantic | 2.x (latest) | Log event data models & validation | HIGH |

**Why stdlib regex + Pydantic (not log parsing library):**
- UniFi logs are non-standard format requiring custom parsing
- CEF format only available via SIEM integration (Network App 9.3.43+)
- Direct syslog from UDM is plain text, not CEF
- No existing library handles UniFi-specific log patterns

**Parsing Strategy:**
1. Define regex patterns for known UniFi log formats
2. Parse into Pydantic models for type safety
3. Categorize by severity using domain-specific rules

**Why Pydantic:**
- Rust-powered validation (fast)
- Type hints with runtime enforcement
- Excellent for structured log event models
- Used by FastAPI, LangChain, 466k+ repos

**What NOT to use:**
| Library | Why Not |
|---------|---------|
| logparser (logpai) | ML-based, overkill for known log formats |
| pylogsparser | XML config files, unnecessary complexity |
| logdissect | Generic tool, doesn't handle UniFi patterns |

**Source:** [UniFi SIEM Integration](https://help.ui.com/hc/en-us/articles/33349041044119-UniFi-System-Logs-SIEM-Integration), [Pydantic Docs](https://docs.pydantic.dev/latest/)

---

### Scheduling

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| APScheduler | 3.11.2 | Job scheduling | HIGH |

**Why APScheduler:**
- Production-stable, MIT licensed
- Cron-style, interval, and one-off scheduling
- Works in Docker containers without external dependencies
- Memory, SQLite, or Redis job stores
- No need for external cron daemon

**Configuration:**
```python
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BlockingScheduler()
scheduler.add_job(poll_logs, CronTrigger(hour="*/1"))  # Hourly
scheduler.start()
```

**Alternative Considered:**
| Approach | Why Not |
|----------|---------|
| System cron | Requires container modifications, less portable |
| Celery | Massive overkill for single-service polling |
| asyncio loop | APScheduler handles edge cases (missed jobs, persistence) |

**Source:** [PyPI APScheduler](https://pypi.org/project/APScheduler/) (verified Dec 22, 2025)

---

### Report Generation

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| Jinja2 | 3.1.6 | HTML/text templating | HIGH |
| WeasyPrint | latest | HTML to PDF conversion | MEDIUM |

**Why Jinja2:**
- Industry standard (Flask, Ansible, Sphinx)
- Template inheritance for consistent report structure
- Autoescaping for security
- Async support if needed later

**Why WeasyPrint (for PDF):**
- Pure Python, CSS-based layout
- No external binaries (unlike wkhtmltopdf/pdfkit)
- Standards-compliant PDF output
- Supports flexbox, grid, media queries

**Report Format Strategy:**
1. **Primary:** Plain text/Markdown (simplest, email-friendly)
2. **Secondary:** HTML (richer formatting, web viewing)
3. **Optional:** PDF via WeasyPrint (formal reports)

**Alternative Considered:**
| Library | Why Not |
|---------|---------|
| pdfkit | Requires wkhtmltopdf binary installation |
| ReportLab | Lower-level API, more complex |
| fpdf | Less CSS/HTML support |

**Source:** [PyPI Jinja2](https://pypi.org/project/Jinja2/) (verified Mar 5, 2025)

---

### Email Delivery

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| smtplib (stdlib) | - | SMTP email sending | HIGH |
| email (stdlib) | - | Email message construction | HIGH |

**Why stdlib over third-party:**
- No external dependencies
- Sufficient for transactional emails
- Full MIME support for attachments
- Works with any SMTP server

**Configuration approach:**
- Environment variables for SMTP credentials
- Support for TLS/STARTTLS
- Optional: Gmail app passwords, SendGrid, etc.

**What NOT to use for MVP:**
| Library | Why Not |
|---------|---------|
| yagmail | Gmail-specific, adds dependency |
| redmail | Unnecessary abstraction for simple use case |
| SendGrid/Mailgun SDKs | External service dependency |

**Future consideration:** If email deliverability becomes an issue, migrate to ESP API.

---

### Logging & Observability

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| structlog | 25.5.0 | Structured logging | HIGH |

**Why structlog:**
- JSON output for production (machine-parseable)
- Pretty output for development (human-readable)
- Context binding (request ID, device ID across log lines)
- Integrates with stdlib logging
- Type hints included

**Configuration:**
```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()  # Production
        # structlog.dev.ConsoleRenderer()    # Development
    ]
)

log = structlog.get_logger()
log.info("log_parsed", device="UDM-Pro", events=42)
```

**Alternative Considered:**
| Library | Why Not |
|---------|---------|
| loguru | Less structured output, pretty-printing focus |
| stdlib logging | Verbose configuration, no built-in JSON |

**Source:** [PyPI structlog](https://pypi.org/project/structlog/) (verified Oct 27, 2025)

---

### Data Validation & Configuration

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| pydantic | 2.x | Data models, config validation | HIGH |
| pydantic-settings | 2.x | Environment variable parsing | HIGH |

**Why Pydantic for configuration:**
- Type-safe environment variable parsing
- Validation with clear error messages
- Supports `.env` files
- Same library as log event models (consistency)

**Example:**
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    unifi_host: str
    unifi_username: str
    unifi_password: str
    poll_interval_minutes: int = 60
    smtp_host: str | None = None

    class Config:
        env_file = ".env"
```

---

### Testing

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| pytest | 9.0.2 | Test framework | HIGH |
| pytest-cov | latest | Coverage reporting | HIGH |
| responses | latest | Mock HTTP requests | HIGH |

**Why pytest:**
- De facto standard for Python testing
- Rich plugin ecosystem (1300+ plugins)
- Fixtures for test setup
- Parameterized tests for log parsing variations

**Source:** [PyPI pytest](https://pypi.org/project/pytest/) (verified Dec 6, 2025)

---

### Type Checking & Code Quality

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| mypy | latest | Static type checking | HIGH |
| ruff | latest | Linting and formatting | HIGH |

**Why Ruff over Black + isort + flake8:**
- Single tool replaces multiple linters
- 10-100x faster (Rust-based)
- Compatible with Black formatting
- Active development, modern defaults

---

## Complete Dependency List

### Runtime Dependencies

```
# requirements.txt
unifi-controller-api>=0.3.2
paramiko>=4.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
APScheduler>=3.11.0
Jinja2>=3.1.0
structlog>=25.0.0
requests>=2.32.0
```

### Optional Dependencies

```
# requirements-optional.txt
WeasyPrint>=60.0  # PDF generation
```

### Development Dependencies

```
# requirements-dev.txt
pytest>=9.0.0
pytest-cov>=4.0.0
responses>=0.25.0
mypy>=1.0.0
ruff>=0.1.0
```

---

## Docker Configuration

### Dockerfile

```dockerfile
FROM python:3.12-slim-bookworm

# Security: non-root user
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app

# Install dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=app:app . .

USER app

CMD ["python", "-m", "unifi_scanner"]
```

### Environment Variables

```bash
# Required
UNIFI_HOST=192.168.1.1
UNIFI_USERNAME=admin
UNIFI_PASSWORD=secret
UNIFI_IS_UDM=true

# Optional
POLL_INTERVAL_MINUTES=60
LOG_LEVEL=INFO
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=user
SMTP_PASSWORD=secret
REPORT_EMAIL_TO=admin@example.com
```

---

## What NOT to Use

| Category | Avoid | Reason |
|----------|-------|--------|
| Base image | Alpine | musl libc compatibility issues with paramiko/cryptography |
| HTTP client | aiohttp | Async complexity unnecessary for polling service |
| UniFi API | unificontrol | Archived, outdated API |
| Scheduler | Celery | Massive overkill, requires Redis/RabbitMQ |
| PDF | pdfkit | Requires wkhtmltopdf binary |
| Email | yagmail | Gmail-specific dependency |
| Logging | print statements | No structure, no levels, unprofessional |

---

## Risk Assessment

### High Risk: UniFi API Instability

**Issue:** UniFi API is undocumented and may change between versions.

**Mitigation:**
1. Abstract API calls behind interface
2. Version-pin UniFi controller in testing
3. Implement graceful degradation to SSH fallback
4. Monitor unifi-controller-api releases

### Medium Risk: Log Format Changes

**Issue:** UniFi log formats vary by device type and firmware version.

**Mitigation:**
1. Regex patterns per device/version
2. Unknown log line handling (don't crash)
3. Configurable pattern files

### Low Risk: Library Maintenance

**Issue:** unifi-controller-api has small community.

**Mitigation:**
1. Minimal API surface used
2. Could fork/maintain if abandoned
3. Underlying requests library is stable

---

## Sources

### HIGH Confidence (Official/Verified)
- [PyPI unifi-controller-api](https://pypi.org/project/unifi-controller-api/) - v0.3.2, Dec 27, 2025
- [PyPI paramiko](https://pypi.org/project/paramiko/) - v4.0.0, Aug 4, 2025
- [PyPI APScheduler](https://pypi.org/project/APScheduler/) - v3.11.2, Dec 22, 2025
- [PyPI Jinja2](https://pypi.org/project/Jinja2/) - v3.1.6, Mar 5, 2025
- [PyPI structlog](https://pypi.org/project/structlog/) - v25.5.0, Oct 27, 2025
- [PyPI pytest](https://pypi.org/project/pytest/) - v9.0.2, Dec 6, 2025
- [PyPI requests](https://pypi.org/project/requests/) - v2.32.5, Aug 18, 2025
- [Pydantic Documentation](https://docs.pydantic.dev/latest/)
- [UniFi SIEM Integration](https://help.ui.com/hc/en-us/articles/33349041044119-UniFi-System-Logs-SIEM-Integration)

### MEDIUM Confidence (WebSearch Verified)
- [Docker Best Practices 2025](https://collabnix.com/10-essential-docker-best-practices-for-python-developers-in-2025/)
- [Python Docker Images](https://pythonspeed.com/articles/base-image-python-docker-images/)
- [structlog Best Practices](https://www.structlog.org/en/stable/logging-best-practices.html)
- [Paramiko vs AsyncSSH Comparison](https://elegantnetwork.github.io/posts/comparing-ssh/)

### LOW Confidence (Needs Validation)
- WeasyPrint version (PyPI fetch failed, verify during implementation)
- Pydantic v3 status (mentioned in search results, may still be v2)
