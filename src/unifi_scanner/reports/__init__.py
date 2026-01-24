"""Report generation module for UniFi Scanner.

Provides HTML and plain text report generation from analysis findings
using Jinja2 templates.
"""

from .generator import ReportGenerator

__all__ = ["ReportGenerator"]
