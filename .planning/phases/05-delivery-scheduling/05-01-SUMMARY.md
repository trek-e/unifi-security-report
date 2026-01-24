---
phase: 05-delivery-scheduling
plan: 01
subsystem: delivery
tags: [smtp, email, tls, multipart]

dependency-graph:
  requires: [04-report-generation]
  provides: [EmailDelivery, EmailDeliveryError, email-settings]
  affects: [05-03-orchestration]

tech-stack:
  added: []
  patterns:
    - "smtplib for SMTP protocol (stdlib)"
    - "email.message.EmailMessage for multipart MIME"
    - "BCC-only recipients (privacy)"
    - "Severity-aware subject lines"

key-files:
  created:
    - src/unifi_scanner/delivery/__init__.py
    - src/unifi_scanner/delivery/email.py
  modified:
    - src/unifi_scanner/config/settings.py

decisions:
  - key: bcc-only-recipients
    choice: "All recipients via BCC, no To/CC headers"
    reason: "Recipient privacy - recipients cannot see each other"
  - key: severity-subject
    choice: "[N SEVERE] prefix when severe_count > 0"
    reason: "Immediate visibility of critical issues in inbox"
  - key: dual-tls-support
    choice: "Support both port 587 (STARTTLS) and 465 (implicit TLS)"
    reason: "Compatibility with different SMTP server configurations"
  - key: graceful-failure
    choice: "deliver_report() returns bool, logs errors, never crashes"
    reason: "Report generation should not fail due to email issues"

metrics:
  duration: 2 min
  completed: 2026-01-24
---

# Phase 5 Plan 1: SMTP Email Delivery Summary

SMTP email delivery with BCC-only recipients, severity-aware subject lines, and dual TLS support

## What Was Built

### Email Configuration Settings (settings.py)

Added email delivery configuration fields to `UnifiSettings`:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `email_enabled` | bool | False | Enable email delivery |
| `smtp_host` | Optional[str] | None | SMTP server hostname |
| `smtp_port` | int | 587 | SMTP port (587=STARTTLS, 465=SMTPS) |
| `smtp_user` | Optional[str] | None | Authentication username |
| `smtp_password` | Optional[str] | None | Authentication password |
| `smtp_use_tls` | bool | True | Enable TLS encryption |
| `email_from` | str | "unifi-scanner@localhost" | Sender address |
| `email_recipients` | str | "" | Comma-separated recipients |
| `timezone` | str | "UTC" | Timezone for subject dates |

Added validation:
- `model_validator` ensures `smtp_host` is set when `email_enabled=True`
- `get_email_recipients()` method parses comma-separated string to list

### EmailDelivery Class (delivery/email.py)

```python
class EmailDelivery:
    """SMTP email delivery with BCC recipients and multipart support."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        use_tls: bool = True,
        from_addr: str = "unifi-scanner@localhost",
        timezone: str = "UTC",
    ) -> None: ...

    def build_subject(self, report: Report) -> str:
        """Build subject: '[N SEVERE] UniFi Report - Jan 24, 2026'"""

    def send(
        self,
        recipients: List[str],
        subject: str,
        html_content: str,
        text_content: str,
    ) -> None:
        """Send multipart email via BCC."""

    def deliver_report(
        self,
        report: Report,
        html_content: str,
        text_content: str,
        recipients: List[str],
    ) -> bool:
        """High-level method, returns True/False."""
```

### Key Implementation Details

**BCC-only Recipients:**
- No `To` or `Cc` headers set on EmailMessage
- Recipients passed directly to `sendmail()` as envelope recipients
- Recipients cannot see each other's addresses

**Severity-aware Subject:**
- With severe findings: `[3 SEVERE] UniFi Report - Jan 24, 2026`
- Without severe: `UniFi Report - Jan 24, 2026`
- Date formatted in configured timezone

**Dual TLS Support:**
- Port 465: Uses `SMTP_SSL` (implicit TLS from connection start)
- Port 587: Uses `SMTP` then `starttls()` (explicit TLS upgrade)
- TLS can be disabled for testing via `use_tls=False`

**Graceful Error Handling:**
- All SMTP errors caught and logged with structlog
- `EmailDeliveryError` raised from `send()` for caller handling
- `deliver_report()` catches errors, returns `False` instead of crashing

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| f0a8bef | feat | Add email configuration settings |
| 9680013 | feat | Create EmailDelivery class for SMTP email sending |

## Verification Results

All success criteria verified:

```python
# Import verification
from unifi_scanner.delivery import EmailDelivery  # OK
from unifi_scanner.delivery import EmailDeliveryError  # OK

# Settings verification
from unifi_scanner.config.settings import UnifiSettings
s = UnifiSettings(host='x', username='y')
print(s.email_enabled)  # False

# Subject line verification
# No severe: "UniFi Report - Jan 25, 2026"
# With 3 severe: "[3 SEVERE] UniFi Report - Jan 25, 2026"
```

## Next Phase Readiness

Ready for:
- **05-02**: File output delivery (separate delivery mechanism)
- **05-03**: Orchestration (will compose with EmailDelivery)

No blockers. Email delivery is isolated and can be used independently.
