---
phase: 08-enhanced-security
plan: 03
subsystem: security
tags: [ips, suricata, remediation, jinja2, templates, security]

# Dependency graph
requires:
  - phase: 08-01
    provides: IPSEvent model and signature parsing
  - phase: 08-02
    provides: IPSAnalyzer with ThreatAnalysisResult, SourceIPSummary
provides:
  - IPS remediation templates with severity-adjusted guidance
  - get_remediation() and get_false_positive_note() functions
  - HTML threat section template for email reports
  - Plain text threat section template
affects: [08-04, report-generation, email-templates]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - SafeDict for safe template variable substitution
    - Severity-adjusted remediation (step-by-step vs brief vs explanation)
    - Email-compatible HTML with inline CSS

key-files:
  created:
    - src/unifi_scanner/analysis/ips/remediation.py
    - src/unifi_scanner/reports/templates/threat_section.html
    - src/unifi_scanner/reports/templates/threat_section.txt
    - tests/test_ips_remediation.py
  modified: []

key-decisions:
  - "SafeDict returns [key] placeholder instead of 'Unknown' for consistency"
  - "Remediation covers 20+ ET categories including obscure ones"
  - "False positive notes only for categories with common benign triggers"
  - "HTML template uses inline CSS for email client compatibility"

patterns-established:
  - "IPS remediation follows same SafeDict pattern as existing templates"
  - "Jinja2 threat sections use ips_analysis context variable from analyzer"

# Metrics
duration: 4min
completed: 2026-01-25
---

# Phase 8 Plan 3: IPS Report Templates Summary

**Category-specific IPS remediation templates with severity-adjusted guidance and Jinja2 report sections for threat display**

## Performance

- **Duration:** 4 min
- **Started:** 2026-01-25T05:26:18Z
- **Completed:** 2026-01-25T05:30:25Z
- **Tasks:** 2
- **Files created:** 4

## Accomplishments

- Created IPS_REMEDIATION_TEMPLATES covering 20+ ET categories (SCAN, MALWARE, POLICY, EXPLOIT, DOS, COINMINING, P2P, TOR, PHISHING, TROJAN, BOTCC, and more)
- Implemented severity-adjusted detail: SEVERE gets step-by-step numbered instructions, MEDIUM gets brief actionable advice, LOW gets explanation only
- Added false positive notes for POLICY, P2P, USER_AGENTS, GAMES, and CHAT categories
- Created HTML threat section template with inline CSS for email compatibility
- Created plain text threat section template with ASCII formatting
- Both templates gracefully handle empty ips_analysis

## Task Commits

Each task was committed atomically:

1. **Task 1: Create IPS remediation templates** - `d5dbe04` (feat)
2. **Task 2: Create threat section templates** - `5c3a19b` (feat)

## Files Created/Modified

- `src/unifi_scanner/analysis/ips/remediation.py` - IPS_REMEDIATION_TEMPLATES dict with get_remediation() and get_false_positive_note() exports
- `tests/test_ips_remediation.py` - 24 tests covering templates, severity levels, content quality
- `src/unifi_scanner/reports/templates/threat_section.html` - Jinja2 HTML template for threat summary in email reports
- `src/unifi_scanner/reports/templates/threat_section.txt` - Plain text template for threat summary (78 lines)

## Decisions Made

- **SafeDict placeholder format:** Used `[key]` format instead of `Unknown` for missing template variables - clearer when debugging
- **Template coverage:** Included all 20+ ET categories from signature_parser plus generic fallback
- **False positive notes:** Only added for categories with common benign triggers (streaming, gaming, chat) per CONTEXT.md guidance about reducing alarm fatigue
- **No escalation advice:** Per CONTEXT.md, templates do not suggest "consult a professional" - only what user can do themselves

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Remediation templates ready for integration with ThreatSummary in 08-04
- Report templates ready to include in main report.html/report.txt
- All 83 IPS tests passing (59 from 08-01/08-02 + 24 from 08-03)

---
*Phase: 08-enhanced-security*
*Completed: 2026-01-25*
