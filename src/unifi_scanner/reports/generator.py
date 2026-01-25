"""Report generator with Jinja2 template support.

Provides the ReportGenerator class for generating HTML and plain text
reports from analysis findings using Jinja2 templates.
"""

from typing import Any, Dict, Optional

from jinja2 import Environment, PackageLoader, select_autoescape

from unifi_scanner.analysis.formatter import FindingFormatter
from unifi_scanner.analysis.ips import ThreatAnalysisResult
from unifi_scanner.models.report import Report


class ReportGenerator:
    """Generator for HTML and plain text reports using Jinja2 templates.

    Orchestrates template rendering and composes with FindingFormatter
    for display-ready finding data.

    Attributes:
        env: Jinja2 Environment configured with PackageLoader
        formatter: FindingFormatter for converting findings to display format
        report_title: Default title for generated reports
    """

    def __init__(
        self,
        display_timezone: str = "UTC",
        report_title: str = "UniFi Network Report",
    ) -> None:
        """Initialize ReportGenerator with Jinja2 environment.

        Args:
            display_timezone: IANA timezone name for timestamp display
                (e.g., 'America/New_York'). Defaults to 'UTC'.
            report_title: Default title for generated reports.
        """
        self.report_title = report_title
        self.formatter = FindingFormatter(display_timezone=display_timezone)

        # Configure Jinja2 environment
        self.env = Environment(
            loader=PackageLoader("unifi_scanner.reports", "templates"),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _build_context(
        self,
        report: Report,
        ips_analysis: Optional[ThreatAnalysisResult] = None,
    ) -> Dict[str, Any]:
        """Build template context from a Report.

        Groups findings by severity and prepares all data needed for
        template rendering.

        Args:
            report: Report containing findings to format
            ips_analysis: Optional IPS threat analysis results

        Returns:
            Dictionary with template context:
            - report_title: Title for the report
            - site_name: UniFi site name
            - period_start: Formatted start time
            - period_end: Formatted end time
            - generated_at: Formatted generation time
            - severe_findings: List of formatted severe findings
            - medium_findings: List of formatted medium findings
            - low_findings: List of formatted low findings
            - counts: Dictionary with severity counts and total
            - ips_analysis: IPS threat analysis results (or None)
        """
        grouped = self.formatter.format_grouped_findings(report.findings)

        return {
            "report_title": self.report_title,
            "site_name": report.site_name,
            "period_start": self.formatter.format_timestamp(report.period_start),
            "period_end": self.formatter.format_timestamp(report.period_end),
            "generated_at": self.formatter.format_timestamp(report.generated_at),
            "severe_findings": grouped["severe"],
            "medium_findings": grouped["medium"],
            "low_findings": grouped["low"],
            "counts": {
                "severe_count": len(grouped["severe"]),
                "medium_count": len(grouped["medium"]),
                "low_count": len(grouped["low"]),
                "total": len(report.findings),
            },
            "ips_analysis": ips_analysis,
        }

    def generate_html(
        self,
        report: Report,
        ips_analysis: Optional[ThreatAnalysisResult] = None,
    ) -> str:
        """Generate HTML report from Report model.

        HTML reports display findings organized by severity (SEVERE first,
        then MEDIUM, then LOW) with an executive summary and professional
        UniFi-inspired styling. All CSS is inline for email compatibility.

        Args:
            report: Report object containing findings to render
            ips_analysis: Optional IPS threat analysis results

        Returns:
            Complete HTML document as string
        """
        template = self.env.get_template("report.html")
        context = self._build_context(report, ips_analysis)
        return template.render(**context)

    def generate_text(
        self,
        report: Report,
        ips_analysis: Optional[ThreatAnalysisResult] = None,
    ) -> str:
        """Generate plain text report from Report model.

        Plain text reports use tiered detail levels:
        - SEVERE: Full detail (title, description, occurrence, remediation)
        - MEDIUM: Summary (title, brief description, occurrence, remediation)
        - LOW: One-liner (title and occurrence count only)

        Args:
            report: Report object containing findings to render
            ips_analysis: Optional IPS threat analysis results

        Returns:
            Plain text report as string
        """
        template = self.env.get_template("report.txt")
        context = self._build_context(report, ips_analysis)
        return template.render(**context)
