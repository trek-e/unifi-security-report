# Phase 4: Report Generation - Research

**Researched:** 2026-01-24
**Domain:** HTML/Plain Text Report Generation with Jinja2
**Confidence:** HIGH

## Summary

This phase transforms analysis findings into professionally formatted, human-readable reports in both HTML and plain text formats. The research focuses on Jinja2 templating for Python, email-compatible HTML/CSS techniques, and integration with the existing FindingFormatter infrastructure.

The existing `FindingFormatter` class already provides `format_grouped_findings()` and `format_text_report()` methods that group findings by severity and generate basic plain text output. The new report generation layer will extend this foundation with Jinja2-powered HTML templates and enhanced plain text formatting that follows the tiered detail levels specified in CONTEXT.md.

**Primary recommendation:** Use Jinja2 3.1.x with PackageLoader, inline CSS for email compatibility, and the checkbox/`:checked` CSS pattern for collapsible LOW findings (with full-content fallback for unsupported clients).

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Jinja2 | >=3.1.6 | Template engine for HTML generation | Standard Python templating, Flask/Django compatible, autoescape security |
| MarkupSafe | >=2.1 (auto-installed) | HTML escaping | Jinja2 dependency, prevents XSS |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| premailer | >=3.10 | Inline CSS conversion | If using embedded `<style>` during development |
| weasyprint | >=60 | PDF generation | Future: if PDF export is needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Jinja2 | Mako | Mako is faster but less common, Jinja2 has better community support |
| Jinja2 | Django templates | Would require Django dependency, overkill for this use case |
| premailer | css-inline | css-inline is Rust-based (faster) but less Python ecosystem integration |

**Installation:**
```bash
pip install Jinja2>=3.1.6
```

Note: premailer is optional - can write inline CSS directly in templates for simplicity.

## Architecture Patterns

### Recommended Project Structure
```
src/unifi_scanner/
├── reports/                    # NEW: Report generation module
│   ├── __init__.py
│   ├── generator.py           # ReportGenerator class
│   ├── templates/             # Jinja2 HTML templates
│   │   ├── base.html          # Base template with CSS, header, footer
│   │   ├── report.html        # Main report template (extends base)
│   │   ├── components/        # Reusable template components
│   │   │   ├── severity_section.html
│   │   │   ├── finding_card.html
│   │   │   └── executive_summary.html
│   └── text_formatter.py      # Enhanced plain text generation
├── analysis/
│   └── formatter.py           # Existing FindingFormatter (reuse)
└── models/
    └── report.py              # Existing Report model (reuse)
```

### Pattern 1: Jinja2 Environment Setup
**What:** Centralized template environment with security defaults
**When to use:** All HTML report generation
**Example:**
```python
# Source: https://jinja.palletsprojects.com/en/stable/api/
from jinja2 import Environment, PackageLoader, select_autoescape

def create_template_environment() -> Environment:
    """Create Jinja2 environment for report templates."""
    return Environment(
        loader=PackageLoader("unifi_scanner.reports", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
```

### Pattern 2: Template Inheritance for Reports
**What:** Base template with CSS/structure, child templates for content
**When to use:** Ensures consistent styling across all report types
**Example:**
```jinja
{# base.html - Source: Jinja2 documentation #}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{{ report_title }}{% endblock %}</title>
    <style>
        {% block styles %}
        {# Inline CSS here for email compatibility #}
        {% endblock %}
    </style>
</head>
<body>
    {% block header %}{% endblock %}
    {% block content %}{% endblock %}
    {% block footer %}{% endblock %}
</body>
</html>
```

```jinja
{# report.html #}
{% extends "base.html" %}
{% block content %}
    {% include "components/executive_summary.html" %}
    {% for section in severity_sections %}
        {% include "components/severity_section.html" %}
    {% endfor %}
{% endblock %}
```

### Pattern 3: Report Generator Class
**What:** Single class orchestrating template rendering
**When to use:** Main entry point for report generation
**Example:**
```python
class ReportGenerator:
    """Generates HTML and plain text reports from Report objects."""

    def __init__(
        self,
        display_timezone: str = "UTC",
        report_title: str = "UniFi Network Report",
    ):
        self.formatter = FindingFormatter(display_timezone)
        self.env = create_template_environment()
        self.report_title = report_title

    def generate_html(self, report: Report) -> str:
        """Generate HTML report from Report model."""
        template = self.env.get_template("report.html")
        context = self._build_context(report)
        return template.render(**context)

    def generate_text(self, report: Report) -> str:
        """Generate plain text report from Report model."""
        # Use enhanced text formatting with tiered detail
        ...

    def _build_context(self, report: Report) -> dict:
        """Build template context from Report model."""
        grouped = self.formatter.format_grouped_findings(report.findings)
        return {
            "report_title": self.report_title,
            "site_name": report.site_name,
            "period_start": report.period_start,
            "period_end": report.period_end,
            "generated_at": report.generated_at,
            "severe_findings": grouped["severe"],
            "medium_findings": grouped["medium"],
            "low_findings": grouped["low"],
            "counts": {
                "severe": report.severe_count,
                "medium": report.medium_count,
                "low": report.low_count,
                "total": len(report.findings),
            },
        }
```

### Anti-Patterns to Avoid
- **External CSS in emails:** Email clients strip `<link>` tags - always use inline CSS
- **Complex CSS (flexbox, grid):** Poor email client support - use tables for layout
- **JavaScript in reports:** Email clients block JS - use CSS-only interactivity
- **CSS shorthand properties:** Some clients don't parse shorthand - write explicit properties
- **Large images as base64:** Bloats HTML size, may trigger spam filters - use URLs or omit
- **Nested template inheritance:** Hard to debug - keep to 2 levels max (base + child)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML escaping | Manual string replacement | Jinja2 autoescape | XSS prevention, handles edge cases |
| Template variables | f-strings in HTML | Jinja2 `{{ var }}` | Security, separation of concerns |
| Email CSS inlining | Regex-based converter | premailer or write inline directly | Edge cases with selectors, media queries |
| Date formatting | Custom strftime everywhere | FindingFormatter.format_timestamp() | Already exists, handles timezone |
| Severity grouping | Manual list filtering | FindingFormatter.format_grouped_findings() | Already exists, tested |

**Key insight:** The existing FindingFormatter already handles the hard parts (timezone conversion, occurrence summaries, severity grouping). The report generator should compose these, not reimplement them.

## Common Pitfalls

### Pitfall 1: Gmail Clipping
**What goes wrong:** Gmail clips emails over 102KB with "View entire message" link
**Why it happens:** Large HTML reports with embedded CSS or base64 images
**How to avoid:**
- Keep total HTML under 100KB
- Minimize CSS (avoid repetition)
- Don't embed images as base64
- Consider summary reports with links to full report
**Warning signs:** Test emails show "[Message clipped]"

### Pitfall 2: Email Client CSS Stripping
**What goes wrong:** Styles don't render in Gmail, Outlook, or webmail
**Why it happens:** Email clients strip `<style>` tags and `<head>` content
**How to avoid:**
- Use inline styles on EVERY element that needs styling
- Don't rely on `<style>` blocks for critical styling
- Test with Litmus or Email on Acid
**Warning signs:** Report looks unstyled in email preview

### Pitfall 3: Outlook Rendering Issues
**What goes wrong:** Tables misalign, background colors disappear
**Why it happens:** Outlook uses Word's rendering engine
**How to avoid:**
- Use `border-collapse: collapse` on tables
- Set explicit widths on table cells
- Use `bgcolor` attribute for backgrounds (in addition to CSS)
- Use MSO conditional comments for Outlook-specific fixes
**Warning signs:** Report looks different in Outlook vs other clients

### Pitfall 4: Mobile Rendering
**What goes wrong:** Report is unreadable on phones
**Why it happens:** Fixed-width layouts, tiny text
**How to avoid:**
- Use `max-width: 600px` with `width: 100%` for containers
- Use `font-size: 16px` minimum for body text
- Use `@media` queries for responsive adjustments (some clients support)
- Test on mobile devices
**Warning signs:** Need to zoom/scroll horizontally on phone

### Pitfall 5: Collapsible Sections Fail
**What goes wrong:** LOW findings section always expanded or broken
**Why it happens:** `<details>`/`<summary>` have near-zero email client support
**How to avoid:**
- Use checkbox/`:checked` CSS pattern (better support)
- Always include full fallback content
- Consider "collapsed by default" as progressive enhancement
- Accept that some clients will show all content
**Warning signs:** Section toggle doesn't work in webmail

### Pitfall 6: Template Security (XSS)
**What goes wrong:** User-controlled content in reports executes as HTML
**Why it happens:** Autoescape disabled or `| safe` filter misused
**How to avoid:**
- Always use `autoescape=select_autoescape(['html', 'xml'])`
- Never use `| safe` filter on user-provided content
- Sanitize metadata fields before template rendering
**Warning signs:** HTML entities appearing in report, or script injection

## Code Examples

Verified patterns from official sources:

### Jinja2 Environment Setup
```python
# Source: https://jinja.palletsprojects.com/en/stable/api/
from jinja2 import Environment, PackageLoader, select_autoescape

env = Environment(
    loader=PackageLoader("unifi_scanner.reports", "templates"),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,      # Remove first newline after block tag
    lstrip_blocks=True,    # Strip leading whitespace before blocks
)
```

### Template Rendering with Context
```python
# Source: https://jinja.palletsprojects.com/en/stable/api/
template = env.get_template("report.html")
html_output = template.render(
    report_title="UniFi Network Report",
    site_name="Main Office",
    severe_findings=grouped["severe"],
    medium_findings=grouped["medium"],
    low_findings=grouped["low"],
)
```

### Email-Safe Inline CSS (UniFi-Inspired)
```html
<!-- Source: Email on Acid best practices, UniFi brand colors -->
<table role="presentation" style="width: 100%; max-width: 600px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; border-collapse: collapse;">
    <tr>
        <td style="background-color: #2282FF; padding: 20px; text-align: center;">
            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600;">
                UniFi Network Report
            </h1>
        </td>
    </tr>
</table>
```

### Severity Badge CSS
```html
<!-- Inline severity badges for email compatibility -->
<!-- SEVERE -->
<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; background-color: #dc3545; color: #ffffff; font-size: 12px; font-weight: 600; text-transform: uppercase;">
    SEVERE
</span>

<!-- MEDIUM -->
<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; background-color: #fd7e14; color: #ffffff; font-size: 12px; font-weight: 600; text-transform: uppercase;">
    MEDIUM
</span>

<!-- LOW -->
<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; background-color: #6c757d; color: #ffffff; font-size: 12px; font-weight: 600; text-transform: uppercase;">
    LOW
</span>

<!-- Recurring badge -->
<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; background-color: #0559C9; color: #ffffff; font-size: 11px; font-weight: 500; margin-left: 4px;">
    Recurring
</span>
```

### Collapsible Section (Checkbox/Checked Pattern)
```html
<!--
    Source: Litmus community - checkbox method has best email support
    Fallback: Shows all content if CSS not supported
-->
<style>
    .low-findings-content { display: none; }
    #toggle-low:checked ~ .low-findings-content { display: block; }
    /* Hide checkbox visually */
    #toggle-low { position: absolute; left: -9999px; }
</style>

<input type="checkbox" id="toggle-low" />
<label for="toggle-low" style="cursor: pointer; color: #2282FF; text-decoration: underline;">
    Show LOW severity findings ({{ low_count }})
</label>
<div class="low-findings-content">
    <!-- LOW findings here -->
</div>

<!-- Fallback for clients that strip styles -->
<noscript>
    <style>.low-findings-content { display: block !important; }</style>
</noscript>
```

### Numbered Remediation Steps
```html
<!-- Remediation formatted as numbered list -->
<div style="background-color: #f8f9fa; padding: 12px 16px; border-left: 4px solid #2282FF; margin-top: 12px;">
    <strong style="color: #212529; font-size: 14px;">Recommended Actions:</strong>
    <ol style="margin: 8px 0 0 0; padding-left: 20px; color: #495057; font-size: 14px; line-height: 1.6;">
        <li>Check the source IP address - is it from your network or external?</li>
        <li>Review the UniFi controller access logs for patterns of failed attempts.</li>
        <li>If external, consider blocking the IP in your firewall settings.</li>
    </ol>
</div>
```

### Mobile-Responsive Container
```html
<!-- Source: Email on Acid best practices -->
<table role="presentation" style="width: 100%; max-width: 600px; margin: 0 auto;" cellpadding="0" cellspacing="0">
    <tr>
        <td style="padding: 20px;">
            <!-- Content here - will shrink on mobile -->
        </td>
    </tr>
</table>

<!-- Add media query for clients that support it -->
<style>
    @media screen and (max-width: 600px) {
        .content-table { width: 100% !important; }
        .content-cell { padding: 12px !important; }
    }
</style>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| External CSS files | Inline CSS | Always for email | Only reliable method |
| `<details>`/`<summary>` | Checkbox/`:checked` pattern | 2020+ | Better email client support |
| Float layouts | Table-based layouts | Still current for email | Email clients don't support flexbox reliably |
| Embedded `<style>` only | Hybrid (inline + embedded for media queries) | 2022+ | Gmail still strips `<style>`, but other clients use it |
| Manual CSS inlining | Automated tools (premailer) | 2018+ | Development efficiency |

**Deprecated/outdated:**
- `<font>` tags: Use CSS instead, though still supported
- Absolute positioning: Unreliable in email clients
- CSS Grid/Flexbox: Only 30-40% email client support
- Background images via CSS: Use `background` attribute on `<td>` for Outlook

## Open Questions

Things that couldn't be fully resolved:

1. **Exact `:checked` support percentage**
   - What we know: Works in Gmail, Apple Mail, iOS Mail, many webmail clients
   - What's unclear: Exact percentage, Outlook desktop behavior
   - Recommendation: Implement with full fallback - show all LOW findings if CSS fails

2. **Network name auto-detection**
   - What we know: CONTEXT.md requests auto-detect from UniFi controller
   - What's unclear: Which API endpoint provides site/network name
   - Recommendation: Planner should verify `Report.site_name` is populated by earlier phases

3. **UniFi controller link format**
   - What we know: CONTEXT.md allows discretion on including links to controller
   - What's unclear: URL format varies by controller type (UDM, CloudKey, hosted)
   - Recommendation: Make links optional, configurable, with controller base URL setting

## Sources

### Primary (HIGH confidence)
- [Jinja2 Documentation - Templates](https://jinja.palletsprojects.com/en/stable/templates/) - Template inheritance, blocks
- [Jinja2 Documentation - API](https://jinja.palletsprojects.com/en/stable/api/) - Environment setup, autoescape
- [GitHub Jinja Releases](https://github.com/pallets/jinja/releases) - Version 3.1.6 current stable

### Secondary (MEDIUM confidence)
- [Email on Acid - Best Practices](https://www.emailonacid.com/blog/article/email-development/email-development-best-practices-2/) - Inline CSS, table layouts
- [Mailtrap - Email CSS](https://mailtrap.io/blog/email-css/) - CSS dos and don'ts
- [Stack Abuse - Email Templates](https://stackabuse.com/building-custom-email-templates-with-html-and-css-in-python/) - Jinja2 setup
- [Litmus Community](https://litmus.com/community/discussions/1104-css3-accordion-in-email) - Checkbox/checked pattern

### Tertiary (LOW confidence)
- [Brandfetch - Ubiquiti](https://brandfetch.com/ui.com) - Brand color #2282FF (Dodger Blue)
- Web searches for current HTML email practices - verified against official sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Jinja2 is the Python standard, well-documented
- Architecture: HIGH - Patterns verified against official Jinja2 docs
- Email CSS: MEDIUM - Best practices vary by client, tested patterns
- Collapsible sections: MEDIUM - Checkbox method has better support but not universal
- Pitfalls: HIGH - Well-documented across multiple email development resources

**Research date:** 2026-01-24
**Valid until:** 2026-02-24 (30 days - email client support is stable)

## Integration Notes

### Existing Code to Leverage
The existing codebase already provides:

1. **`FindingFormatter`** (`analysis/formatter.py`):
   - `format_grouped_findings()` - Groups findings into severe/medium/low
   - `format_timestamp()` - Timezone-aware timestamp formatting
   - `format_occurrence_summary()` - Human-readable occurrence text
   - `format_text_report()` - Basic plain text report (can be enhanced)

2. **`Report` model** (`models/report.py`):
   - `severe_count`, `medium_count`, `low_count` computed properties
   - `period_start`, `period_end`, `generated_at` timestamps
   - `site_name`, `controller_type` metadata

3. **`Finding` model** (`models/finding.py`):
   - `is_recurring` property (5+ occurrences)
   - `is_actionable` property (SEVERE with remediation)
   - `remediation` field with numbered steps

### Template Directory Location
Templates should go in `src/unifi_scanner/reports/templates/` to work with `PackageLoader("unifi_scanner.reports", "templates")`.

### Pyproject.toml Update Required
Add Jinja2 to dependencies:
```toml
dependencies = [
    # ... existing ...
    "Jinja2>=3.1.6",
]
```
