# Phase 5: Delivery & Scheduling - Context

**Gathered:** 2026-01-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Service runs as a scheduled Docker container that delivers reports via email and file. Includes SMTP email delivery with HTML+plaintext multipart, file output to configurable directory, APScheduler-based scheduling, and Docker container packaging. This is the final phase delivering production-ready deployment.

</domain>

<decisions>
## Implementation Decisions

### Email Delivery
- **Recipients**: All recipients via BCC (no To/CC) to avoid reply-all email loops
- **Authentication**: Standard username + password SMTP auth via config/env
- **Subject line**: Severity-aware format, e.g., "[2 SEVERE] UniFi Report - Jan 24, 2026"
- **Failure handling**: Save report to file as fallback when email delivery fails (no retry loop)
- **Format**: HTML with plaintext fallback (multipart/alternative)

### File Output
- **Naming**: Datetime-based, e.g., `unifi-report-2026-01-24-1430.html` (unique per run)
- **Retention**: Configurable "keep last N days" with automatic cleanup of older reports
- **Formats**: Configurable — user chooses which formats (HTML, text, or both) to save
- **Default state**: Disabled by default — only active when output directory is configured

### Scheduling Behavior
- **Configuration**: Both simple presets (daily at 8am, weekly on Monday) AND cron expressions for power users
- **Timezone**: Configurable timezone for schedules (not locked to UTC)
- **One-shot mode**: If no schedule configured, run once and exit (useful for testing/manual runs)
- **Missed runs**: Claude's discretion on catch-up behavior

### Docker Deployment
- **Base image**: Claude's discretion (likely python:3.9-slim for compatibility)
- **Logging**: Claude's discretion (standard containerized approach)
- **Compose file**: Full docker-compose.yml example with all options (env vars, volumes, networks)
- **Secrets**: Both env vars AND Docker secrets support (/run/secrets/ for Swarm/Compose)

### Claude's Discretion
- Base image selection (slim vs alpine)
- Logging approach (stdout-only vs optional file)
- Missed run catch-up behavior
- Retry timing for transient failures before fallback

</decisions>

<specifics>
## Specific Ideas

- BCC-only recipients to avoid "reply all" storms in team inboxes
- Severity in subject line helps triage — "[2 SEVERE]" immediately signals urgency
- Datetime filenames ensure each run is preserved (no overwrites)
- docker-compose.yml should be a complete reference users can customize

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-delivery-scheduling*
*Context gathered: 2026-01-24*
