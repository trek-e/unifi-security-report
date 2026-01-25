"""UniFi API client with device detection and site discovery.

The UnifiClient provides a high-level interface for connecting to UniFi
controllers, handling device type detection, authentication, and site selection
automatically.

Features:
- Automatic device type detection (UDM vs self-hosted)
- Session management with automatic re-authentication on 401
- Exponential backoff retry on connection failures
- Cookie-based session persistence

Example usage:
    from unifi_scanner.config import UnifiSettings
    from unifi_scanner.api import UnifiClient

    settings = UnifiSettings(host="192.168.1.1", username="admin", password="secret")

    with UnifiClient(settings) as client:
        sites = client.get_sites()
        print(f"Found {len(sites)} sites")
"""

from typing import Any, Dict, List, Optional

import httpx
import structlog

from unifi_scanner.config import UnifiSettings
from unifi_scanner.models import DeviceType

from .auth import authenticate, detect_device_type, logout
from .endpoints import get_api_prefix, get_endpoints
from .exceptions import (
    ConnectionError,
    MultipleSitesError,
    SiteNotFoundError,
    UnifiAPIError,
)
from .session import create_retry_decorator, request_with_session_check

logger = structlog.get_logger(__name__)


class UnifiClient:
    """Client for interacting with UniFi Controller API.

    Handles automatic device type detection, authentication, and site discovery.
    Works with both UDM-type devices (UDM Pro, UCG Ultra, Cloud Key Gen2+)
    and self-hosted UniFi Controller installations.

    Attributes:
        settings: UnifiSettings configuration object.
        device_type: Detected device type (set after connect).
        base_url: Base URL of the controller (set after connect).
        api_prefix: API prefix for site-specific endpoints (set after connect).

    Example:
        # As context manager (recommended)
        with UnifiClient(settings) as client:
            sites = client.get_sites()

        # Manual connection management
        client = UnifiClient(settings)
        client.connect()
        try:
            sites = client.get_sites()
        finally:
            client.disconnect()
    """

    def __init__(self, settings: UnifiSettings) -> None:
        """Initialize the UniFi client.

        Args:
            settings: Configuration settings for the UniFi connection.
        """
        self.settings = settings
        self._client: Optional[httpx.Client] = None
        self._authenticated: bool = False

        # These are set during connect()
        self.device_type: Optional[DeviceType] = None
        self.base_url: Optional[str] = None
        self.api_prefix: Optional[str] = None
        self._csrf_token: Optional[str] = None

        # Create retry decorator based on settings
        self._retry = create_retry_decorator(
            max_retries=settings.max_retries,
            min_wait=1,
            max_wait=60,
        )

    def connect(self) -> None:
        """Connect to the UniFi Controller.

        Performs device type detection, establishes connection, and authenticates.
        After successful connection, device_type, base_url, and api_prefix are set.

        Uses exponential backoff retry on connection failures (1s, 2s, 4s... max 60s).

        Raises:
            ConnectionError: Cannot connect to controller after all retries.
            DeviceDetectionError: Cannot determine device type.
            AuthenticationError: Authentication failed.
        """
        # Wrap the actual connect logic with retry decorator
        self._retry(self._connect_internal)()

    def _connect_internal(self) -> None:
        """Internal connection logic (wrapped with retry by connect())."""
        logger.info("connecting", host=self.settings.host)

        # Detect device type and port
        self.device_type, port = detect_device_type(
            host=self.settings.host,
            port=self.settings.port,
            verify_ssl=self.settings.verify_ssl,
            timeout=self.settings.connect_timeout,
        )

        self.base_url = f"https://{self.settings.host}:{port}"
        self.api_prefix = get_api_prefix(self.device_type)

        # Create HTTP client with cookie persistence
        self._client = httpx.Client(
            verify=self.settings.verify_ssl,
            timeout=self.settings.connect_timeout,
        )

        # Authenticate and get CSRF token
        self._csrf_token = authenticate(
            client=self._client,
            base_url=self.base_url,
            device_type=self.device_type,
            username=self.settings.username,
            password=self.settings.password,
        )

        self._authenticated = True

        logger.info(
            "connected",
            device_type=self.device_type.value,
            base_url=self.base_url,
            api_prefix=self.api_prefix or "(none)",
        )

    def disconnect(self) -> None:
        """Disconnect from the UniFi Controller.

        Logs out (best-effort) and closes the HTTP client.
        Safe to call even if not connected.
        """
        if self._client is not None:
            if self._authenticated and self.base_url and self.device_type:
                logout(
                    client=self._client,
                    base_url=self.base_url,
                    device_type=self.device_type,
                )
            self._client.close()
            self._client = None

        self._authenticated = False
        logger.debug("disconnected")

    def get_sites(self) -> List[Dict[str, Any]]:
        """Get list of sites from the controller.

        Returns:
            List of site dictionaries, each containing 'name', 'desc', '_id'.

        Raises:
            UnifiAPIError: API request failed.
            RuntimeError: Not connected.

        Example:
            >>> sites = client.get_sites()
            >>> for site in sites:
            ...     print(f"{site['name']}: {site.get('desc', 'No description')}")
        """
        self._ensure_connected()
        assert self.device_type is not None  # For type checker

        endpoints = get_endpoints(self.device_type)
        response = self._request("GET", endpoints.sites)

        data = response.json()

        # UniFi API wraps data in {"meta": {...}, "data": [...]}
        if isinstance(data, dict) and "data" in data:
            sites = data["data"]
        else:
            sites = data if isinstance(data, list) else []

        logger.debug("sites_retrieved", count=len(sites))
        return sites

    def select_site(self, site_name: Optional[str] = None) -> str:
        """Select a site to use for subsequent operations.

        Args:
            site_name: Name of site to select. If None, auto-selects if only one site.

        Returns:
            Name of the selected site.

        Raises:
            SiteNotFoundError: Specified site does not exist.
            MultipleSitesError: Multiple sites exist but none specified.

        Example:
            >>> site = client.select_site()  # Auto-select if only one
            >>> site = client.select_site("default")  # Select specific site
        """
        sites = self.get_sites()

        if not sites:
            raise UnifiAPIError(
                message="No sites found on controller",
                hint="This is unusual. Check if the controller is properly configured.",
            )

        # Build list of site names for error messages
        site_names = [s.get("name", s.get("_id", "unknown")) for s in sites]

        if site_name:
            # User specified a site - find it
            for site in sites:
                if site.get("name") == site_name:
                    logger.info("site_selected", site=site_name, method="specified")
                    return site_name

            # Site not found
            raise SiteNotFoundError(site_name=site_name, available_sites=site_names)

        # No site specified - try to auto-select
        if len(sites) == 1:
            selected = site_names[0]
            logger.info("site_selected", site=selected, method="auto")
            return selected

        # Multiple sites and none specified
        raise MultipleSitesError(available_sites=site_names)

    def get_events(
        self,
        site: str,
        history_hours: int = 720,
        start: int = 0,
        limit: int = 3000,
    ) -> List[Dict[str, Any]]:
        """Get event logs from the controller for a specific site.

        Retrieves events sorted by time (newest first) within the specified
        time window. The UniFi API limits responses to 3000 events maximum.

        Args:
            site: Site name to retrieve events from.
            history_hours: Number of hours of history to retrieve (default: 720 = 30 days).
            start: Starting offset for pagination (default: 0).
            limit: Maximum number of events to retrieve (default/max: 3000).

        Returns:
            List of event dictionaries, each containing time, key (event type),
            msg (message), and device-specific fields.

        Raises:
            UnifiAPIError: API request failed.
            RuntimeError: Not connected.

        Note:
            If the response indicates truncation (meta.count > len(data)),
            a warning is logged. Use start parameter for pagination.

        Example:
            >>> events = client.get_events("default", history_hours=24)
            >>> for event in events[:5]:
            ...     print(f"{event['key']}: {event.get('msg', 'No message')}")
        """
        self._ensure_connected()
        assert self.device_type is not None  # For type checker

        endpoints = get_endpoints(self.device_type)
        endpoint = endpoints.events.format(site=site)

        # Build request body - API enforces 3000 max
        body = {
            "_sort": "-time",
            "within": history_hours,
            "_start": start,
            "_limit": min(limit, 3000),
        }

        response = self._request("POST", endpoint, json=body)
        data = response.json()

        # Debug: Log raw response structure to diagnose empty results
        logger.debug(
            "events_raw_response",
            response_type=type(data).__name__,
            has_data_key="data" in data if isinstance(data, dict) else False,
            has_meta_key="meta" in data if isinstance(data, dict) else False,
            top_level_keys=list(data.keys()) if isinstance(data, dict) else None,
            is_list=isinstance(data, list),
            list_length=len(data) if isinstance(data, list) else None,
        )

        # Extract events from response wrapper
        if isinstance(data, dict) and "data" in data:
            events = data["data"]
        else:
            events = data if isinstance(data, list) else []

        # Check for truncation
        if isinstance(data, dict) and "meta" in data:
            meta = data["meta"]
            total_count = meta.get("count", len(events))
            if total_count > len(events):
                logger.warning(
                    "events_truncated",
                    retrieved=len(events),
                    total_available=total_count,
                    site=site,
                )

        logger.debug("events_retrieved", count=len(events), site=site)
        return events

    def get_alarms(
        self,
        site: str,
        archived: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Get alarms from the controller for a specific site.

        Args:
            site: Site name to retrieve alarms from.
            archived: Filter by archived status. None returns all alarms,
                     True returns only archived, False returns only active.

        Returns:
            List of alarm dictionaries, each containing time, key (alarm type),
            msg (message), and severity information.

        Raises:
            UnifiAPIError: API request failed.
            RuntimeError: Not connected.

        Example:
            >>> active_alarms = client.get_alarms("default", archived=False)
            >>> print(f"Found {len(active_alarms)} active alarms")
        """
        self._ensure_connected()
        assert self.device_type is not None  # For type checker

        endpoints = get_endpoints(self.device_type)
        endpoint = endpoints.alarms.format(site=site)

        # Build query params
        params: Dict[str, str] = {}
        if archived is not None:
            params["archived"] = "true" if archived else "false"

        response = self._request("GET", endpoint, params=params if params else None)
        data = response.json()

        # Extract alarms from response wrapper
        if isinstance(data, dict) and "data" in data:
            alarms = data["data"]
        else:
            alarms = data if isinstance(data, list) else []

        logger.debug("alarms_retrieved", count=len(alarms), site=site)
        return alarms

    def get_ips_events(
        self,
        site: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: int = 3000,
    ) -> List[Dict[str, Any]]:
        """Get IDS/IPS (Intrusion Detection/Prevention) events from the controller.

        Retrieves security events such as threat detections and blocks from
        the dedicated IPS endpoint. This is separate from regular events.

        Args:
            site: Site name to retrieve IPS events from.
            start: Start timestamp in milliseconds (default: 24 hours ago).
            end: End timestamp in milliseconds (default: now).
            limit: Maximum number of events to retrieve (default/max: 3000).

        Returns:
            List of IPS event dictionaries, each containing timestamp,
            signature info, source/destination IPs, and action taken.

        Raises:
            UnifiAPIError: API request failed.
            RuntimeError: Not connected.

        Example:
            >>> ips_events = client.get_ips_events("default")
            >>> for event in ips_events[:5]:
            ...     print(f"{event.get('signature', 'Unknown')}: {event.get('action')}")
        """
        import time

        self._ensure_connected()
        assert self.device_type is not None  # For type checker

        endpoints = get_endpoints(self.device_type)
        endpoint = endpoints.ips_events.format(site=site)

        # Default time range: last 24 hours
        now_ms = int(time.time() * 1000)
        if end is None:
            end = now_ms
        if start is None:
            start = now_ms - (24 * 60 * 60 * 1000)  # 24 hours ago

        # Build request body - try both parameter formats
        # Some UniFi versions use start/end, others use _start/_end
        body = {
            "start": start,
            "end": end,
            "_start": start,
            "_end": end,
            "_limit": min(limit, 3000),
        }

        # Debug: Log the request being made
        from datetime import datetime, timezone
        start_dt = datetime.fromtimestamp(start / 1000, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end / 1000, tz=timezone.utc)
        logger.debug(
            "ips_events_request",
            endpoint=endpoint,
            start_ms=start,
            end_ms=end,
            start_human=start_dt.isoformat(),
            end_human=end_dt.isoformat(),
            limit=body["_limit"],
        )

        response = self._request("POST", endpoint, json=body)
        data = response.json()

        # If no results, try without time filter to check if endpoint works at all
        if isinstance(data, dict) and len(data.get("data", [])) == 0:
            logger.debug("ips_events_retry_no_filter", message="Retrying without time filter")
            response2 = self._request("POST", endpoint, json={"_limit": 100})
            data2 = response2.json()
            if isinstance(data2, dict) and len(data2.get("data", [])) > 0:
                logger.info(
                    "ips_events_found_without_filter",
                    count=len(data2["data"]),
                    message="Events exist but time filter excluded them",
                )
                data = data2

        # If still no results, try alternative endpoints for UDM Pro
        if isinstance(data, dict) and len(data.get("data", [])) == 0:
            # Try various alternative endpoints
            alt_configs = [
                # REST endpoint for IPS records
                {"method": "GET", "endpoint": f"/proxy/network/api/s/{site}/rest/ipsrecord"},
                # Regular events with IPS key filter
                {"method": "POST", "endpoint": f"/proxy/network/api/s/{site}/stat/event",
                 "json": {"_limit": 500, "key": "EVT_IPS_IpsAlert"}},
                # Try without key filter to see all event types
                {"method": "POST", "endpoint": f"/proxy/network/api/s/{site}/stat/event",
                 "json": {"_limit": 50}},
            ]
            for config in alt_configs:
                try:
                    alt_endpoint = config["endpoint"]
                    logger.debug("ips_events_trying_alt", endpoint=alt_endpoint, method=config["method"])
                    if config["method"] == "GET":
                        alt_response = self._request("GET", alt_endpoint)
                    else:
                        alt_response = self._request("POST", alt_endpoint, json=config.get("json", {}))
                    alt_data = alt_response.json()

                    # Log what we found
                    if isinstance(alt_data, dict):
                        alt_count = len(alt_data.get("data", []))
                        sample_keys = []
                        if alt_count > 0:
                            sample = alt_data["data"][0]
                            sample_keys = list(sample.keys())[:10]
                            # Check for IPS-related keys
                            if "key" in sample:
                                sample_keys.append(f"key={sample.get('key')}")
                    else:
                        alt_count = len(alt_data) if isinstance(alt_data, list) else 0
                        sample_keys = []

                    logger.debug("ips_events_alt_response", endpoint=alt_endpoint, count=alt_count, sample_keys=sample_keys)

                    # For ipsrecord endpoint, any results are good
                    if "ipsrecord" in alt_endpoint and alt_count > 0:
                        logger.info("ips_events_found_alt_endpoint", endpoint=alt_endpoint, count=alt_count)
                        data = alt_data
                        break
                except Exception as e:
                    logger.debug("ips_events_alt_failed", endpoint=alt_endpoint, error=str(e))

        # Debug: Log raw response structure
        logger.debug(
            "ips_events_response",
            response_keys=list(data.keys()) if isinstance(data, dict) else "list",
            meta=data.get("meta") if isinstance(data, dict) else None,
            data_count=len(data.get("data", [])) if isinstance(data, dict) else len(data) if isinstance(data, list) else 0,
        )

        # Extract IPS events from response wrapper
        if isinstance(data, dict) and "data" in data:
            events = data["data"]
        else:
            events = data if isinstance(data, list) else []

        # Debug: Log sample event structure to help troubleshoot
        if events:
            sample = events[0]
            inner = sample.get("inner_alert", {})
            logger.debug(
                "ips_events_retrieved",
                count=len(events),
                site=site,
                sample_has_inner_alert="inner_alert" in sample,
                sample_signature_id=inner.get("signature_id") if inner else sample.get("signature_id"),
                sample_signature=inner.get("signature", "")[:50] if inner else sample.get("signature", "")[:50],
            )
        else:
            logger.debug("ips_events_retrieved", count=0, site=site)

        return events

    def get_devices(
        self,
        site: str,
        device_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get device statistics from the controller.

        Returns detailed device information including system stats,
        temperatures, PoE status, and port information.

        Args:
            site: Site name to retrieve devices from.
            device_type: Optional filter by type (uap, usw, ugw, udm).

        Returns:
            List of device dictionaries with system-stats, temps, etc.

        Raises:
            UnifiAPIError: API request failed.
            RuntimeError: Not connected.

        Example:
            >>> devices = client.get_devices("default")
            >>> for device in devices:
            ...     print(f"{device['name']}: {device.get('type')}")
        """
        self._ensure_connected()
        assert self.device_type is not None  # For type checker

        endpoints = get_endpoints(self.device_type)
        endpoint = endpoints.devices.format(site=site)

        response = self._request("GET", endpoint)
        data = response.json()

        devices = data.get("data", data) if isinstance(data, dict) else data

        # Optional type filter
        if device_type:
            devices = [d for d in devices if d.get("type") == device_type]

        logger.debug("devices_retrieved", count=len(devices), site=site)
        return devices

    def _raw_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make a raw HTTP request without session handling.

        This method performs the actual HTTP request without checking for
        session expiration or handling 401 responses. Use _request() for
        automatic session management.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path.
            **kwargs: Additional arguments passed to httpx.request().

        Returns:
            Raw response object (may be 401 if session expired).

        Raises:
            ConnectionError: Network-level request failed.
            RuntimeError: Not connected.
        """
        self._ensure_connected()
        assert self._client is not None
        assert self.base_url is not None

        url = f"{self.base_url}{endpoint}"

        # Add CSRF token header if available (required for UniFi OS devices)
        if self._csrf_token:
            headers = kwargs.pop("headers", {})
            headers["x-csrf-token"] = self._csrf_token
            kwargs["headers"] = headers

        try:
            return self._client.request(method, url, **kwargs)
        except httpx.RequestError as e:
            raise ConnectionError(
                message=f"Request failed: {e}",
            )

    def _reauthenticate(self) -> None:
        """Re-authenticate with the controller.

        Called automatically when a 401 response is received, indicating
        the session has expired. Performs a fresh authentication using
        the stored credentials.

        Raises:
            AuthenticationError: Re-authentication failed.
            RuntimeError: Not connected or missing connection info.
        """
        if not self._client or not self.base_url or not self.device_type:
            raise RuntimeError("Cannot re-authenticate: not connected")

        logger.debug("reauthenticating", host=self.settings.host)

        self._csrf_token = authenticate(
            client=self._client,
            base_url=self.base_url,
            device_type=self.device_type,
            username=self.settings.username,
            password=self.settings.password,
        )

        self._authenticated = True
        logger.info("reauthenticated", host=self.settings.host)

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an API request with automatic session management.

        Uses request_with_session_check to handle 401 responses by
        re-authenticating and retrying the request.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path.
            **kwargs: Additional arguments passed to httpx.request().

        Returns:
            Response object.

        Raises:
            UnifiAPIError: Request failed or session recovery failed.
            RuntimeError: Not connected.
        """
        self._ensure_connected()

        response = request_with_session_check(self, method, endpoint, **kwargs)

        # Handle common error codes (401 already handled by session check)
        if response.status_code == 401:
            # If we still get 401 after re-auth, it's a real auth failure
            raise UnifiAPIError(
                message="Session expired and re-authentication failed",
                hint="Check your credentials and try reconnecting.",
            )

        if response.status_code == 404:
            raise UnifiAPIError(
                message=f"Endpoint not found: {endpoint}",
                hint="This may indicate wrong device type detection.",
            )

        if response.status_code >= 400:
            raise UnifiAPIError(
                message=f"API error: {response.status_code} {response.reason_phrase}",
            )

        return response

    def _ensure_connected(self) -> None:
        """Ensure client is connected and authenticated.

        Raises:
            RuntimeError: Not connected.
        """
        if self._client is None or not self._authenticated:
            raise RuntimeError(
                "Not connected. Call connect() first or use as context manager."
            )

    def get_session_cookies(self) -> dict[str, str]:
        """Get session cookies for WebSocket authentication.

        Returns cookies from the authenticated REST session, allowing
        the WebSocket client to reuse the same authentication without
        requiring a separate login.

        Returns:
            Dictionary mapping cookie name to cookie value.
            Empty dict if not connected.

        Example:
            >>> cookies = client.get_session_cookies()
            >>> ws_manager.start(
            ...     base_url=client.base_url,
            ...     cookies=cookies,
            ...     ...
            ... )
        """
        if self._client is None or not self._authenticated:
            return {}

        return {
            cookie.name: cookie.value
            for cookie in self._client.cookies.jar
            if cookie.value is not None
        }

    def __enter__(self) -> "UnifiClient":
        """Enter context manager - connect to controller."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Exit context manager - disconnect from controller."""
        self.disconnect()
