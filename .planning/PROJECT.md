# UniFi Scanner

## What This Is

A containerized Linux service that polls UniFi gateway logs, analyzes them for issues, and generates plain-English reports with severity-based categorization. Designed for small business owners and home power-users who want to be responsible network admins without deep networking expertise.

## Core Value

Translate cryptic UniFi logs into understandable findings with actionable remediation steps for serious issues.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Connect to UniFi gateway via API (SSH fallback)
- [ ] Poll and collect logs on a configurable schedule
- [ ] Parse and normalize UniFi log formats
- [ ] Categorize issues by severity (low, medium, severe)
- [ ] Generate human-readable explanations for all issues
- [ ] Provide step-by-step remediation guidance for severe issues
- [ ] Output reports to file (configurable directory)
- [ ] Send reports via email (configurable)
- [ ] Run as containerized service (Docker)

### Out of Scope

- Dashboard UI — defer to v2 (Grafana integration)
- Multi-network/multi-gateway support — v1 is single gateway
- Real-time alerting — v1 is periodic reports only
- Automatic remediation — recommendations only, no auto-fix
- Mobile app — reports are email/file based

## Context

**Target users:** Non-expert network admins with UniFi equipment. They have the hardware but not the knowledge to interpret logs effectively.

**UniFi ecosystem:** UniFi Controller provides API access to device data and logs. Direct SSH to gateway is possible as fallback. Log formats vary by device type and firmware version.

**Report use case:** Admin reviews report periodically (daily/weekly), understands network health at a glance, and has clear next steps for anything serious.

## Constraints

- **Deployment**: Must run containerized (Docker) on Linux
- **Network access**: Requires local network access to UniFi gateway/controller
- **API dependency**: UniFi API is not officially documented; may change between versions

## Current Milestone: v0.3-alpha — No Duplicate Reports

**Goal:** Prevent the same events from being reported in every scheduled run

**Target features:**
- Track last successful report timestamp
- Only process events that occurred after last report
- Persist state in reports directory (.last_run.json)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| API-first, SSH fallback | API is cleaner but SSH ensures compatibility if API unavailable | ✓ Good |
| Severity tiers (low/med/severe) | Matches user's mental model; severe gets remediation steps | ✓ Good |
| Reports over dashboard for v1 | Faster to ship, dashboard is v2 | ✓ Good |
| CSRF token for UniFi OS | UDM Pro requires x-csrf-token header on all requests | ✓ Good |
| Skip already-reported events | Simple timestamp cutoff, not recurring counts | — Pending |
| State file in reports dir | Simple, uses existing volume mount | — Pending |

---
*Last updated: 2026-01-24 after v0.3-alpha milestone start*
