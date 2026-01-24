---
phase: 04-report-generation
plan: 02
subsystem: reports
tags: [html, jinja2, templates, email-compatibility]

dependency_graph:
  requires: ["04-01"]
  provides:
    - generate_html() method
    - HTML template hierarchy (base -> report -> components)
    - Email-compatible inline CSS styling
    - Collapsible LOW section with checkbox toggle
  affects: ["04-03"]

tech_stack:
  added: []
  patterns:
    - Jinja2 template inheritance (extends/blocks)
    - Component-based template architecture
    - Inline CSS for email compatibility
    - CSS checkbox toggle pattern for collapsibility

key_files:
  created:
    - src/unifi_scanner/reports/templates/base.html
    - src/unifi_scanner/reports/templates/report.html
    - src/unifi_scanner/reports/templates/components/executive_summary.html
    - src/unifi_scanner/reports/templates/components/severity_section.html
    - src/unifi_scanner/reports/templates/components/finding_card.html
    - tests/test_reports_html.py
  modified:
    - src/unifi_scanner/reports/generator.py
    - tests/test_reports_generator.py

decisions:
  - decision: "Table-based layout for email"
    context: "Email clients strip <style> tags and don't support flexbox/grid"
    outcome: "All layout uses <table role='presentation'> with inline styles"
  - decision: "Checkbox toggle for LOW section"
    context: "LOW findings should be collapsed by default to reduce noise"
    outcome: "Pure CSS :checked pseudo-selector pattern, no JavaScript"
  - decision: "Tiered detail in finding cards"
    context: "LOW findings only need summary, SEVERE/MEDIUM need full detail"
    outcome: "Jinja conditional hides description and remediation for LOW"

metrics:
  duration: 4 min
  completed: 2026-01-24
---

# Phase 04 Plan 02: HTML Report Templates Summary

HTML template system with UniFi-inspired styling and email-compatible inline CSS for professional report generation.

## What Was Built

### Template Hierarchy

1. **base.html** - Foundation template with:
   - HTML5 document structure (DOCTYPE, lang, meta tags)
   - Progressive enhancement `<style>` block for browsers
   - Email-safe table layout (600px max-width, centered)
   - UniFi brand colors (#2282FF blue) and severity colors
   - CSS checkbox toggle for collapsible sections
   - Template blocks: title, header, content, footer

2. **report.html** - Main report extending base:
   - Header with title, site name, period, generation time
   - Includes executive summary component
   - Severity sections in order: SEVERE -> MEDIUM -> LOW
   - LOW section wrapped in checkbox toggle for collapse

3. **Component Templates**:
   - `executive_summary.html` - Counts, total, Action Required callout
   - `severity_section.html` - Section header with badge, finding loop
   - `finding_card.html` - Card with border, badges, device info, remediation

### generate_html() Implementation

```python
def generate_html(self, report: Report) -> str:
    template = self.env.get_template("report.html")
    context = self._build_context(report)
    return template.render(**context)
```

## Task Completion

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create base template | b505d1a | base.html |
| 2 | Create report and components | ce80791 | report.html, 3 components |
| 3 | Implement generate_html() + tests | 8c32829 | generator.py, test_reports_html.py |

## Tests Added

21 new tests in `test_reports_html.py`:

- **Basics**: returns string, DOCTYPE, title, site name
- **Ordering**: SEVERE before MEDIUM before LOW
- **Executive Summary**: counts, action required callout
- **Badges**: correct colors (red/orange/gray)
- **Recurring**: [Recurring] badge for 5+ occurrences
- **Remediation**: displayed for SEVERE/MEDIUM, hidden for LOW
- **Toggle**: checkbox and low-content class present
- **Empty Sections**: no SEVERE heading when 0 severe
- **XSS Prevention**: HTML entities escaped
- **Email Compatibility**: many inline styles, table layout

## Verification Results

```
All template files present in templates/ and templates/components/
32 tests pass (21 HTML + 11 generator)
generate_html() returns 5700+ chars HTML for empty report
42+ inline style= attributes for email compatibility
```

## Deviations from Plan

None - plan executed exactly as written.

## Key Technical Details

### Email Compatibility

All CSS inline on elements:
```html
<td style="background-color: #dc3545; color: #ffffff; padding: 4px 12px;">SEVERE</td>
```

The `<style>` block is progressive enhancement only (browsers that support it).

### Severity Badge Colors

| Severity | Background | Used For |
|----------|------------|----------|
| SEVERE | #dc3545 | Red badges and borders |
| MEDIUM | #fd7e14 | Orange badges and borders |
| LOW | #6c757d | Gray badges and borders |

### Collapsible LOW Section

Pure CSS pattern (no JavaScript):
```html
<input type="checkbox" id="toggle-low" style="position: absolute; left: -9999px;" />
<label for="toggle-low">Show LOW severity findings (3)</label>
<div class="low-content" style="display: none;">...</div>
```

## Success Criteria Status

| Criterion | Status |
|-----------|--------|
| generate_html() returns complete HTML | PASS |
| SEVERE first, then MEDIUM, then LOW | PASS |
| Executive summary with counts | PASS |
| Severity badges correct colors | PASS |
| LOW section collapsible | PASS |
| All CSS inline (email compatible) | PASS |
| Remediation for SEVERE/MEDIUM | PASS |
| HTML escaping prevents XSS | PASS |

## Next Phase Readiness

HTML templates complete. Ready for 04-03 (if not already done) to implement text template, then 04-04 for CLI integration.
