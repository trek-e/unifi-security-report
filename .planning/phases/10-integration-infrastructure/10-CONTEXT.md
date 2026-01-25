# Phase 10: Integration Infrastructure - Context

**Gathered:** 2026-01-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Framework for optional external integrations (Cloudflare, Cybersecure) that fail gracefully without affecting core UniFi report generation. This phase builds the infrastructure only — actual Cloudflare and Cybersecure integrations are separate phases (11 and 12).

</domain>

<decisions>
## Implementation Decisions

### Skip Behavior
- **Silent skip** when integration not configured — no log entry, no mention in report
- **Warn and skip** when integration is partially configured (e.g., API key but no zone ID)
- Flat config with top-level env vars (e.g., `CLOUDFLARE_API_KEY`, `CLOUDFLARE_ZONE_ID`)

### Failure Isolation
- **Complete isolation** — one integration failing does not affect others
- **Error note in section** when integration fails — report shows "Cloudflare: Unable to fetch data" in the integration's section
- **Parallel execution** — integrations run in parallel with each other AND with UniFi data collection

### Circuit Breaker Policy
- **Reset on restart** — circuit breaker state is in-memory, not persisted to disk
- After circuit trips, integration is skipped until cooldown expires

### Integration Registry
- **Separate report sections** — each integration gets its own section (not merged into UniFi sections)
- **Design for extensibility** — structure supports future custom integrations but don't implement plugin system now
- Integrations run in parallel with UniFi collection for faster report generation

### Claude's Discretion
- Per-integration enable toggle (CLOUDFLARE_ENABLED) vs credentials-only detection
- Dynamic plugin discovery vs hardcoded integration list
- Integration failure log level (WARNING vs ERROR based on context)
- Integration timeout duration
- Circuit breaker failure threshold (e.g., 3 or 5 failures)
- Circuit breaker cooldown duration
- Circuit breaker logging policy (once when tripped vs each skip)
- Health endpoint extension for integration status
- Common base class/interface for integrations
- Credential validation timing (startup vs first use)

</decisions>

<specifics>
## Specific Ideas

- Core UniFi functionality must never be blocked by integration failures
- Think of integrations as "nice to have" enrichment, not critical path
- The pattern should make adding new integrations straightforward for future phases

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-integration-infrastructure*
*Context gathered: 2026-01-25*
