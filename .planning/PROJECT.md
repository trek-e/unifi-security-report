# UniFi Scanner

## What This Is

A containerized Linux service that polls UniFi gateway logs, analyzes them for issues, and generates plain-English reports with severity-based categorization. Designed for small business owners and home power-users who want to be responsible network admins without deep networking expertise.

## Core Value

Translate cryptic UniFi logs into understandable findings with actionable remediation steps for serious issues.

## Requirements

### Validated

- Connect to UniFi gateway via API (SSH fallback) — v0.2-alpha
- Poll and collect logs on a configurable schedule — v0.2-alpha
- Parse and normalize UniFi log formats — v0.2-alpha
- Categorize issues by severity (low, medium, severe) — v0.2-alpha
- Generate human-readable explanations for all issues — v0.2-alpha
- Provide step-by-step remediation guidance for severe issues — v0.2-alpha
- Output reports to file (configurable directory) — v0.2-alpha
- Send reports via email (configurable) — v0.2-alpha
- Run as containerized service (Docker) — v0.2-alpha
- Track last successful run to prevent duplicate events — v0.3-alpha
- Configurable initial lookback hours for first run — v0.3-alpha
- Graceful handling of missing/corrupted state — v0.3-alpha

### Validated (v0.4-alpha)

- Extended wireless analysis rules (roaming, channels, DFS radar, flapping) — v0.3.1-alpha
- Enhanced IDS/IPS with plain English threat explanations — v0.3.2-alpha
- Device health monitoring (temperature, PoE, uptime, CPU/memory) — v0.3.3-alpha
- Optional Cybersecure integration (ET PRO signature detection, badge) — v0.4-alpha
- Optional Cloudflare integration (WAF, DNS analytics, tunnel status) — v0.3.5-alpha
- WebSocket support for UniFi Network 10.x+ — v0.3.15-alpha

### Active

- [ ] Interference pattern detection (WIFI-07)
- [ ] Wireless survey recommendations (WIFI-08)
- [ ] Threat intelligence enrichment (SECR-06)
- [ ] Anomaly detection for unusual traffic (SECR-07)

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

## Current State

**Shipped:** v0.4-alpha (2026-01-25)

All planned phases complete. Project has shipped:
- v0.2-alpha: Production-ready containerized service (Phases 1-5)
- v0.3-alpha: State persistence (Phase 6)
- v0.3.1-alpha: Extended wireless analysis (Phase 7)
- v0.3.2-alpha: Enhanced security analysis (Phase 8)
- v0.3.3-alpha: Device health monitoring (Phase 9)
- v0.3.4-alpha: Integration infrastructure (Phase 10)
- v0.3.5-alpha: Cloudflare integration (Phase 11)
- v0.3.15-alpha: WebSocket support (Phase 13)
- v0.4-alpha: Cybersecure integration (Phase 12)

**Next Milestone Goals:**
- v0.5 planning not started
- Potential features: Interference detection, threat intelligence enrichment, anomaly detection

## Codebase

**Stats:**
- 13 phases, 48 plans completed
- ~11,800 lines of Python
- Full test coverage across all modules
- Docker image: ghcr.io/trek-e/unifi-security-report

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| API-first, SSH fallback | API is cleaner but SSH ensures compatibility if API unavailable | ✓ Good |
| Severity tiers (low/med/severe) | Matches user's mental model; severe gets remediation steps | ✓ Good |
| Reports over dashboard for v1 | Faster to ship, dashboard is v2 | ✓ Good |
| CSRF token for UniFi OS | UDM Pro requires x-csrf-token header on all requests | ✓ Good |
| Skip already-reported events | Simple timestamp cutoff, not recurring counts | Good |
| State file in reports dir | Simple, uses existing volume mount | Good |
| Atomic state writes | tempfile.mkstemp + shutil.move prevents corruption | Good |
| Client-side timestamp filtering | UniFi API lacks timestamp filter support | Good |
| 5-minute clock skew tolerance | Handles time drift between scanner and controller | Good |

| Pydantic computed_field | JSON serialization for derived properties | Good |
| ET PRO SID range (2800000-2899999) | Standard Proofpoint ET PRO signature range | Good |
| Any-True Cybersecure aggregation | If any event in group is Cybersecure, mark summary | Good |
| Purple badge for Cybersecure | Differentiates from severity badges | Good |

---
*Last updated: 2026-01-25 after v0.4-alpha milestone completion*
