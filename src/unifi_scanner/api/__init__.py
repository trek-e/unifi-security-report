"""UniFi API client module.

This module provides the UnifiClient class for connecting to UniFi controllers,
along with supporting authentication, endpoint definitions, custom exceptions,
and session management with retry logic.

WebSocket support for UniFi Network 10.x+:
- UnifiWebSocketClient: Real-time event streaming via WebSocket
- WebSocketEventBuffer: Thread-safe event collection
- BufferedEvent: Parsed event dataclass
"""

from unifi_scanner.api.client import UnifiClient
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
from unifi_scanner.api.session import create_retry_decorator, request_with_session_check
from unifi_scanner.api.websocket import (
    BufferedEvent,
    UnifiWebSocketClient,
    WebSocketEventBuffer,
    parse_unifi_event,
)

__all__ = [
    # Client
    "UnifiClient",
    # WebSocket
    "BufferedEvent",
    "UnifiWebSocketClient",
    "WebSocketEventBuffer",
    "parse_unifi_event",
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
    # Session
    "create_retry_decorator",
    "request_with_session_check",
]
