# Phase 11: Cloudflare Integration - Context

**Gathered:** 2026-01-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Enrich UniFi security reports with Cloudflare data — WAF block events, DNS analytics, and tunnel status. Uses the integration infrastructure from Phase 10 (Integration Protocol, circuit breakers, failure isolation).

</domain>

<decisions>
## Implementation Decisions

### Credential Configuration
- **API Token only** — use scoped tokens, not legacy global API key
- **Env var naming**: `CLOUDFLARE_API_TOKEN` (standard naming)
- **Startup validation** — fail fast if token invalid, log warning if partial config
- Integration follows Phase 10 pattern: silent skip if not configured, warn if partial

### WAF Event Display
- Show WAF block events in dedicated Cloudflare section
- Include blocked requests with threat details

### DNS Analytics Scope
- **Full analytics** — blocked queries, allowed queries, top domains, categories, trends
- Handle both Gateway (Zero Trust) and standard DNS gracefully
- Detect available APIs and show what's accessible

### Tunnel Status Handling
- **Skip tunnel section if no tunnels exist** — don't show empty state
- Ready for future use even though not currently using tunnels

### Claude's Discretion
- Zone selection approach (single zone vs all zones)
- WAF event grouping (by rule, IP, or chronological)
- WAF detail level (minimal vs standard vs detailed)
- WAF lookback window (match report window or fixed)
- Whether WAF events affect overall report severity
- Top domains count for DNS analytics
- Client/device breakdown availability based on API
- Tunnel status detail level
- Down tunnel severity level

</decisions>

<specifics>
## Specific Ideas

- Should feel like a natural extension of the UniFi report, not a separate report
- Cloudflare section complements IPS/threat section with edge-level security data
- If Gateway not available, gracefully show what IS available from standard Cloudflare APIs

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-cloudflare-integration*
*Context gathered: 2026-01-25*
