# Phase 1: Foundation & API Connection - Context

**Gathered:** 2026-01-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish reliable UniFi Controller integration with configuration system, core data models, and authentication that persists across sessions. This phase delivers the foundation that all subsequent phases build upon — config management, API connectivity, session handling, and data structures.

</domain>

<decisions>
## Implementation Decisions

### Configuration approach
- Env vars override YAML config (YAML is base, env vars are runtime overrides)
- CONFIG_PATH env var points to YAML file location
- Support Docker secrets pattern: UNIFI_PASSWORD_FILE reads password from file
- Fail fast at startup — validate all config immediately, exit if invalid
- Include unifi-scanner.example.yaml with all options documented
- Hot reload on SIGHUP signal
- Env var prefix: UNIFI_ (e.g., UNIFI_HOST, UNIFI_PASSWORD)
- Log level configurable via UNIFI_LOG_LEVEL (DEBUG/INFO/WARN/ERROR)
- Log format configurable via UNIFI_LOG_FORMAT (json or text)
- Port auto-detect with override: try common ports (443, 8443, 11443), allow UNIFI_PORT
- SSL verification on by default, allow UNIFI_VERIFY_SSL=false to disable
- No custom CA certificate support — just disable verification for self-signed
- Site auto-discover: list available sites, use first if only one
- If multiple sites found and none specified: error with list of available sites
- Poll interval configurable in Phase 1 (UNIFI_POLL_INTERVAL)

### Connection handling
- Connection timeout configurable via UNIFI_CONNECT_TIMEOUT
- Exponential backoff on connection failure (1s, 2s, 4s, 8s... up to max)
- Max retries configurable via UNIFI_MAX_RETRIES
- Session expiration: log the event, then re-authenticate and retry
- File-based health check (write status to file for Docker health check)
- --test flag for connection test mode (verify config and exit)
- Log detected device type on startup (always, not just debug)
- Fresh authentication each poll (not persistent session)

### Error messaging
- User-friendly errors at INFO level, technical details at DEBUG
- Specific guidance on auth failure: "Ensure you're using a LOCAL admin account, not cloud SSO"
- List all config validation errors at once on startup
- Meaningful exit codes: 1=config error, 2=connection error, 3=auth error, etc.
- Show startup banner with version, detected device type, site, poll interval
- Deprecation warnings: warn and continue (don't fail on deprecated options)
- Never include sensitive data in logs — always redact
- Include troubleshooting hints in network error messages

### Data model design
- Findings link back to original LogEntry IDs that triggered them
- Include 'metadata' or 'extras' field on models for future extensibility
- All models JSON serializable for storage/debugging

### Claude's Discretion
- Minimal required settings (just UniFi connection vs also requiring email)
- Exact LogEntry fields (based on what UniFi API provides)
- Specific exit code values
- Exact backoff timing and max delay

</decisions>

<specifics>
## Specific Ideas

- Use Docker secrets pattern for password handling (_FILE suffix)
- Startup banner should feel professional — version, config summary, detected environment
- Error messages should help non-experts ("Is the UniFi Controller running?")

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation-api-connection*
*Context gathered: 2026-01-24*
