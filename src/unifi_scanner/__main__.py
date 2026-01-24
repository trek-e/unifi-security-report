"""
Entry point for the unifi-scanner CLI.

Usage:
    unifi-scanner           Run the scanner service
    unifi-scanner --test    Validate configuration and exit
    unifi-scanner --help    Show help message
"""

from __future__ import annotations

import argparse
import signal
import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from types import FrameType

from unifi_scanner import __version__

# Exit codes
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_CONNECTION_ERROR = 2
EXIT_AUTH_ERROR = 3


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="unifi-scanner",
        description="Translate cryptic UniFi logs into understandable findings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  CONFIG_PATH           Path to YAML configuration file
  UNIFI_HOST            UniFi Controller hostname or IP
  UNIFI_USERNAME        UniFi admin username
  UNIFI_PASSWORD        UniFi admin password
  UNIFI_PASSWORD_FILE   Path to file containing password (Docker secrets)
  UNIFI_PORT            Controller port (auto-detected if not set)
  UNIFI_VERIFY_SSL      Enable SSL verification (default: true)
  UNIFI_LOG_LEVEL       Logging level: DEBUG, INFO, WARNING, ERROR
  UNIFI_LOG_FORMAT      Log format: json or text

Examples:
  # Run with config file
  CONFIG_PATH=/etc/unifi-scanner/config.yaml unifi-scanner

  # Test configuration validity
  unifi-scanner --test

  # Run with environment variables only
  UNIFI_HOST=192.168.1.1 UNIFI_USERNAME=admin UNIFI_PASSWORD=secret unifi-scanner
""",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Validate configuration and exit",
    )
    return parser.parse_args()


def handle_sighup(signum: int, frame: Optional[FrameType]) -> None:
    """Handle SIGHUP signal for configuration reload."""
    from unifi_scanner.config.loader import reload_config
    from unifi_scanner.logging import get_logger

    log = get_logger()
    log.info("received_sighup", action="reloading configuration")
    try:
        reload_config()
        log.info("config_reloaded", status="success")
    except Exception as e:
        log.error("config_reload_failed", error=str(e))


def print_banner(config_path: Optional[str], log_level: str) -> None:
    """Print startup banner with version and configuration summary."""
    from unifi_scanner.logging import get_logger

    log = get_logger()
    log.info(
        "startup",
        version=__version__,
        config_file=config_path or "env-only",
        log_level=log_level,
    )


def main() -> int:
    """Main entry point for unifi-scanner."""
    args = parse_args()

    # Import here to avoid circular imports and allow --help without dependencies
    from unifi_scanner.config.loader import ConfigurationError, get_config, load_config
    from unifi_scanner.logging import configure_logging, get_logger

    # Load configuration
    try:
        config = load_config()
    except ConfigurationError as e:
        # Configuration errors are already logged by loader
        print(f"Configuration error: {e}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except SystemExit as e:
        # Validation errors cause sys.exit(1) in loader
        return e.code if isinstance(e.code, int) else EXIT_CONFIG_ERROR

    # Configure logging based on settings
    configure_logging(log_format=config.log_format, log_level=config.log_level)
    log = get_logger()

    # Get config path for banner
    import os

    config_path = os.environ.get("CONFIG_PATH")

    # Print startup banner
    print_banner(config_path, config.log_level)

    # Test mode: validate config and exit
    if args.test:
        log.info("config_valid", message="Configuration is valid")
        print("Configuration valid")
        return EXIT_SUCCESS

    # Set up signal handler for config reload (Unix only)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, handle_sighup)

    # Main service loop (placeholder for now)
    log.info("service_starting", poll_interval=config.poll_interval)
    try:
        # Future: actual polling loop will go here
        log.info("service_ready", message="UniFi Scanner ready (no polling implemented yet)")
        # For now, just exit cleanly
        return EXIT_SUCCESS
    except KeyboardInterrupt:
        log.info("shutdown", reason="keyboard interrupt")
        print("\nShutdown requested, exiting...")
        return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
