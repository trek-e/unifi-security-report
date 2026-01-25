# Phase 8: Enhanced Security Analysis - Context

**Gathered:** 2026-01-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Translate Suricata IDS/IPS alerts into plain English with actionable context. Users understand what threats were detected, which were blocked, and what (if anything) they should do about it.

</domain>

<decisions>
## Implementation Decisions

### Threat presentation
- Group alerts by severity first (Severe → Medium → Low), then by category within severity
- Show plain English description + signature ID (e.g., "Port scan detected (ET SCAN Nmap)")
- Deduplicate alerts with count: "Port scan from 192.168.1.50 (seen 47 times)"
- Translate Suricata categories to friendly names:
  - ET SCAN → Reconnaissance
  - ET MALWARE → Malware Activity
  - ET POLICY → Policy Violation
  - (etc.)

### Source IP summaries
- Threshold-based: only highlight IPs with 10+ events (no fixed top-N limit)
- Show IP + event count + breakdown by type: "192.168.1.50: 47 events (32 scans, 15 policy violations)"
- Separate sections for "External Threats" and "Internal Concerns"

### Remediation guidance
- Severity-adjusted detail:
  - Severe: step-by-step remediation actions
  - Medium: brief actionable advice
  - Low: explanation of what happened (no action needed)
- Include UniFi-specific instructions when applicable, generic network advice otherwise
- No escalation advice ("consult a professional") — just what the user can do themselves
- Note common false positives to reduce alarm fatigue (e.g., "Policy violations from streaming services are usually harmless")

### Blocked vs detected
- Separate sections: "Threats Detected" section appears first, then "Threats Blocked"
- If IPS is in detection-only mode, note this: "Note: IPS is in detection mode. Threats are logged but not blocked."

### Claude's Discretion
- Geographic info for external IPs (decide based on implementation complexity)
- Urgency weighting between blocked vs detected findings

</decisions>

<specifics>
## Specific Ideas

No specific product references — open to standard approaches that achieve the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-enhanced-security*
*Context gathered: 2026-01-25*
