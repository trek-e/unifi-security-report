"""UniFi API client module.

This module provides the UnifiClient class for connecting to UniFi controllers,
along with supporting authentication, endpoint definitions, and custom exceptions.
"""

from unifi_scanner.api.endpoints import (
    API_PREFIXES,
    Endpoints,
    get_api_prefix,
    get_endpoints,
)
from unifi_scanner.api.exceptions import (
    AuthenticationError,
    ConnectionError,
    DeviceDetectionError,
    MultipleSitesError,
    SiteNotFoundError,
    UnifiAPIError,
)

# UnifiClient will be added after implementation
__all__ = [
    # Exceptions
    "AuthenticationError",
    "ConnectionError",
    "DeviceDetectionError",
    "MultipleSitesError",
    "SiteNotFoundError",
    "UnifiAPIError",
    # Endpoints
    "API_PREFIXES",
    "Endpoints",
    "get_api_prefix",
    "get_endpoints",
]
