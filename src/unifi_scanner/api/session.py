"""Session management with retry logic and exponential backoff.

This module provides retry decorators using tenacity for resilient
API operations, and session-aware request handling that automatically
re-authenticates on session expiration.

Example usage:
    from unifi_scanner.api.session import create_retry_decorator, request_with_session_check

    retry = create_retry_decorator(max_retries=5, logger=logger)

    @retry
    def fetch_data():
        return client.get("/api/data")
"""

import logging
from typing import TYPE_CHECKING, Any, Callable

import httpx
import structlog
from tenacity import (
    RetryCallState,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from unifi_scanner.api.client import UnifiClient

logger = structlog.get_logger(__name__)


def create_retry_decorator(
    max_retries: int = 5,
    min_wait: float = 1,
    max_wait: float = 60,
    log_level: int = logging.WARNING,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Create a tenacity retry decorator with exponential backoff.

    Creates a decorator that retries on connection and timeout errors,
    with exponential backoff starting at min_wait seconds and capping
    at max_wait seconds.

    Args:
        max_retries: Maximum number of retry attempts.
        min_wait: Minimum wait time in seconds between retries.
        max_wait: Maximum wait time in seconds between retries.
        log_level: Log level for retry attempt messages.

    Returns:
        A tenacity retry decorator.

    Example:
        >>> retry = create_retry_decorator(max_retries=3)
        >>> @retry
        ... def connect_to_server():
        ...     return httpx.get("https://example.com")

    Backoff sequence (with min=1, max=60):
        Attempt 1: immediate
        Attempt 2: wait 1-2 seconds
        Attempt 3: wait 2-4 seconds
        Attempt 4: wait 4-8 seconds
        ...
        Capped at 60 seconds max
    """
    # Get a stdlib logger for tenacity's before_sleep_log
    stdlib_logger = logging.getLogger(__name__)

    return retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(stdlib_logger, log_level),
        reraise=True,
    )


def request_with_session_check(
    client: "UnifiClient",
    method: str,
    endpoint: str,
    **kwargs: Any,
) -> httpx.Response:
    """Make a request with automatic re-authentication on session expiration.

    If the request returns a 401 Unauthorized response, this function
    will re-authenticate and retry the request once.

    Args:
        client: UnifiClient instance to use for the request.
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path.
        **kwargs: Additional arguments passed to the request.

    Returns:
        httpx.Response from the successful request.

    Raises:
        UnifiAPIError: If re-authentication fails or request still fails after retry.
        httpx.RequestError: For network-level errors.

    Note:
        This function handles session expiration gracefully. When a 401
        is received, it logs the event, re-authenticates, and retries.
        If the retry also fails with 401, an error is raised.
    """
    response = client._raw_request(method, endpoint, **kwargs)

    if response.status_code == 401:
        logger.info(
            "session_expired",
            message="Session expired, re-authenticating",
            endpoint=endpoint,
        )
        client._reauthenticate()
        response = client._raw_request(method, endpoint, **kwargs)

    return response
