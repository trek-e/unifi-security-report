# Phase 3: Analysis Engine - Context

**Gathered:** 2026-01-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform raw LogEntry objects into categorized Findings with plain English explanations and remediation guidance. The analysis engine detects issues, assigns severity (low/medium/severe), deduplicates repeated events, and generates human-readable explanations. Report formatting and delivery are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Severity Classification
- **SEVERE**: Anything requiring admin action within 24 hours (security threats, critical failures, device issues)
- **MEDIUM**: Performance concerns (high CPU, memory pressure, slow responses) plus warning-level patterns worth monitoring
- **LOW**: Informational only — normal operations, successful updates, routine events (not minor issues that self-resolved)
- **Unknown patterns**: Put in separate "Uncategorized" bucket — don't assign a severity level

### Explanation Style
- Light technical context — uses terms but explains impact ("WAN interface went down for 5 minutes" not "your router lost connection")
- Include what happened AND why it matters ("AP disconnected — devices in that area lost WiFi")
- Device names when available, fallback to MAC address if no name configured
- Include original UniFi event type in parentheses for Googling: "Failed login attempt (EVT_ADMIN_LOGIN_FAILED)"
- Always show absolute timestamps when it happened (not relative time)
- Use controller's timezone for timestamps
- Show category in findings: "[Security] Failed login attempt from 192.168.1.50"

### Categories
Four categories for grouping findings:
1. **Security** — Failed logins, intrusion alerts, unauthorized access
2. **Connectivity** — Device disconnections, WAN outages, client issues
3. **Performance** — High CPU, memory, slow response times
4. **System** — Firmware updates, reboots, config changes

### Remediation Depth
- SEVERE and MEDIUM issues get remediation guidance (not LOW)
- Detail varies by severity:
  - SEVERE: Step-by-step instructions ("1. Open UniFi app 2. Go to Devices...")
  - MEDIUM: High-level guidance ("Check your access point's power and ethernet cable")
- Assume user can handle it — no escalation suggestions to professional help

### Deduplication Strategy
- Group by: same event type + same device
- Time clustering: events within 1 hour are one incident, then new finding starts
- Display format: "Occurred 5 times (first: 2:00 PM, last: 4:30 PM)"
- Recurring flag: issues with many occurrences get marked "Recurring issue" (don't escalate severity)

### Claude's Discretion
- Whether to include links to UniFi documentation (when they add value)
- Exact threshold for "recurring" flag
- Handling of edge cases in event type mapping

</decisions>

<specifics>
## Specific Ideas

- Event types should be included in explanations for searchability (user mentioned wanting to Google issues)
- Categories should be visible in findings, not just implied
- Time clustering at 1 hour boundary to separate incidents

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-analysis-engine*
*Context gathered: 2026-01-24*
