"""Template system for finding explanations and remediation guidance."""

from unifi_scanner.analysis.templates.explanations import (
    EXPLANATION_TEMPLATES,
    render_explanation,
)
from unifi_scanner.analysis.templates.remediation import (
    REMEDIATION_TEMPLATES,
    render_remediation,
)

__all__ = [
    "EXPLANATION_TEMPLATES",
    "REMEDIATION_TEMPLATES",
    "render_explanation",
    "render_remediation",
]
