"""
UniFi Scanner - Translate cryptic UniFi logs into understandable findings.

This package provides tools to connect to UniFi Controllers, collect and analyze
logs, and produce actionable security findings with remediation guidance.

Features:
- Configuration via YAML with environment variable overrides
- Docker secrets support for sensitive credentials
- Structured logging (JSON for production, text for development)
- Robust connection handling with retry and backoff
"""

__version__ = "0.5.1b1"
__all__ = ["__version__"]
