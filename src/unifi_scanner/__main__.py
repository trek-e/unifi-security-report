"""
Entry point for the unifi-scanner CLI.

Usage:
    unifi-scanner             Run the scanner service (scheduled)
    unifi-scanner --run-once  Run once immediately and exit
    unifi-scanner --test      Validate configuration and connection, then exit
    unifi-scanner --help      Show help message
    unifi-scanner --version   Show version and exit

Exit Codes:
    0 - Success
    1 - Configuration error (invalid settings, missing required values)
    2 - Connection error (cannot reach UniFi Controller)
    3 - Authentication error (invalid credentials, wrong account type)
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from types import FrameType
    from unifi_scanner.api import UnifiClient, WebSocketManager
    from unifi_scanner.config import UnifiSettings

from unifi_scanner import __version__

# Module-level managers for lifecycle management
# These persist across scheduled runs to share authentication state
_ws_manager: Optional["WebSocketManager"] = None
_rest_client: Optional["UnifiClient"] = None
_rest_client_site: Optional[str] = None

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
Exit Codes:
  0   Success
  1   Configuration error
  2   Connection error (cannot reach controller)
  3   Authentication error (invalid credentials)

Environment Variables:
  CONFIG_PATH           Path to YAML configuration file
  UNIFI_HOST            UniFi Controller hostname or IP
  UNIFI_USERNAME        UniFi admin username
  UNIFI_PASSWORD        UniFi admin password
  UNIFI_PASSWORD_FILE   Path to file containing password (Docker secrets)
  UNIFI_PORT            Controller port (auto-detected if not set)
  UNIFI_SITE            Site name (auto-selected if only one site)
  UNIFI_VERIFY_SSL      Enable SSL verification (default: true)
  UNIFI_POLL_INTERVAL   Poll interval in seconds (default: 300)
  UNIFI_LOG_LEVEL       Logging level: DEBUG, INFO, WARNING, ERROR
  UNIFI_LOG_FORMAT      Log format: json or text

Examples:
  # Run with config file
  CONFIG_PATH=/etc/unifi-scanner/config.yaml unifi-scanner

  # Test configuration and connection
  unifi-scanner --test

  # Run once immediately (manual trigger)
  unifi-scanner --run-once

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
        help="Test configuration and connection, then exit",
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run one report cycle immediately and exit (manual trigger)",
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


def print_banner(
    config: "UnifiSettings",
    client: Optional["UnifiClient"] = None,
) -> None:
    """Print startup banner with version and configuration summary.

    Displays a professional banner showing the service version,
    detected controller type, site, poll interval, and log settings.

    Args:
        config: Configuration settings object.
        client: Optional connected UnifiClient for device type info.
    """
    lines = [
        "",
        f"UniFi Scanner v{__version__}",
        "=" * 40,
    ]

    if client and client.device_type:
        lines.append(f"Controller: {client.device_type.value}")
        lines.append(f"Base URL:   {client.base_url}")

    lines.extend([
        f"Poll Interval: {config.poll_interval}s",
        f"Log Level:     {config.log_level}",
        f"Log Format:    {config.log_format}",
        "=" * 40,
        "",
    ])

    for line in lines:
        print(line)


def start_session(config: "UnifiSettings", log: Any) -> Optional["WebSocketManager"]:
    """Start persistent REST session and WebSocket manager.

    Creates a REST client that persists across scheduled runs, avoiding
    repeated authentication. If WebSocket is enabled, starts the WebSocket
    manager using cookies from the REST session.

    Args:
        config: Configuration settings.
        log: Logger instance.

    Returns:
        WebSocketManager instance if started, None if WebSocket disabled or failed.
    """
    global _rest_client, _rest_client_site

    # Import here to avoid circular imports
    from unifi_scanner.api import UnifiClient, WebSocketManager

    try:
        # Create persistent REST client (not as context manager - stays alive)
        _rest_client = UnifiClient(config)
        _rest_client.connect()
        _rest_client_site = _rest_client.select_site(config.site)

        log.debug(
            "rest_session_started",
            base_url=_rest_client.base_url,
            site=_rest_client_site,
        )

    except Exception as e:
        log.warning(
            "rest_session_failed",
            error=str(e),
            message="REST session failed, jobs will create their own connections",
        )
        _rest_client = None
        _rest_client_site = None
        return None

    # Start WebSocket if enabled
    if not config.websocket_enabled:
        log.info("websocket_disabled", message="WebSocket disabled via configuration")
        return None

    try:
        cookies = _rest_client.get_session_cookies()

        if not cookies:
            log.warning(
                "websocket_no_cookies",
                message="No session cookies available for WebSocket",
            )
            return None

        # Ensure we have base_url and device_type (should be set after connect)
        if not _rest_client.base_url or not _rest_client.device_type:
            log.warning(
                "websocket_missing_client_info",
                message="Client missing base_url or device_type after connect",
            )
            return None

        # Create and start WebSocket manager
        ws_manager = WebSocketManager()
        ws_manager.start(
            base_url=_rest_client.base_url,
            site=_rest_client_site,
            cookies=cookies,
            device_type=_rest_client.device_type,
            verify_ssl=config.verify_ssl,
        )

        log.info(
            "websocket_started",
            base_url=_rest_client.base_url,
            site=_rest_client_site,
        )
        return ws_manager

    except Exception as e:
        log.warning(
            "websocket_start_failed",
            error=str(e),
            message="WebSocket failed to start, continuing with REST-only",
        )
        return None


def stop_session(log: Any) -> None:
    """Stop the global WebSocket manager and REST client if running.

    Args:
        log: Logger instance.
    """
    global _ws_manager, _rest_client, _rest_client_site

    if _ws_manager is not None:
        try:
            if _ws_manager.is_running():
                _ws_manager.stop()
                log.info("websocket_stopped")
        except Exception as e:
            log.warning("websocket_stop_error", error=str(e))
        _ws_manager = None

    if _rest_client is not None:
        try:
            _rest_client.disconnect()
            log.debug("rest_session_stopped")
        except Exception as e:
            log.warning("rest_session_stop_error", error=str(e))
        _rest_client = None
        _rest_client_site = None


def run_report_job() -> None:
    """Execute one report generation and delivery cycle.

    This function is called by the scheduler on each scheduled run,
    or once in one-shot mode. It runs the complete pipeline:
    1. Read state (last successful run timestamp)
    2. Connect to UniFi API (or reuse persistent session)
    3. Collect logs (filtered by since_timestamp, with WebSocket events if available)
    4. Analyze logs
    5. Collect and analyze IPS events
    6. Generate report
    7. Deliver via configured channels
    8. Update state only after successful delivery
    """
    global _ws_manager, _rest_client, _rest_client_site

    from unifi_scanner.analysis import AnalysisEngine
    from unifi_scanner.analysis.ips import IPSAnalyzer, IPSEvent
    from unifi_scanner.analysis.rules import get_default_registry
    from unifi_scanner.api import UnifiClient
    from unifi_scanner.config.loader import get_config
    from unifi_scanner.delivery import DeliveryManager, EmailDelivery, FileDelivery
    from unifi_scanner.health import HealthStatus, update_health_status
    from unifi_scanner.logging import get_logger
    from unifi_scanner.logs.collector import LogCollector
    from unifi_scanner.models.enums import DeviceType
    from unifi_scanner.models.report import Report
    from unifi_scanner.reports.generator import ReportGenerator
    from unifi_scanner.state import StateManager

    log = get_logger()
    config = get_config()

    log.info("job_starting")
    update_health_status(HealthStatus.HEALTHY, {"last_run": "starting"})

    # Initialize state manager (state file in reports directory)
    state_dir = config.file_output_dir or "./reports"
    state_manager = StateManager(state_dir=state_dir)

    # Read last successful run timestamp
    last_run = state_manager.read_last_run()
    if last_run:
        log.info("state_loaded", last_run=last_run.isoformat())
        since_timestamp = last_run
    else:
        # First run - use initial lookback
        since_timestamp = datetime.now(timezone.utc) - timedelta(
            hours=config.initial_lookback_hours
        )
        log.info("first_run", lookback_hours=config.initial_lookback_hours)

    # Determine whether to use persistent client or create a new one
    # Persistent client is available in scheduled mode after start_session()
    # One-shot mode (--run-once) won't have a persistent client
    use_persistent = _rest_client is not None and _rest_client_site is not None
    own_client: Optional[UnifiClient] = None

    try:
        if use_persistent:
            client = _rest_client
            site = _rest_client_site
            log.debug("using_persistent_session")
        else:
            # Create own client (one-shot mode or session startup failed)
            own_client = UnifiClient(config)
            own_client.connect()
            client = own_client
            site = client.select_site(config.site)

        # Collect logs (filtered by since_timestamp, with WebSocket events if available)
        collector = LogCollector(
            client=client,
            settings=config,
            site=site,
            ws_manager=_ws_manager,
        )
        log_entries = collector.collect(since_timestamp=since_timestamp)
        log.info("logs_collected", count=len(log_entries))

        # Handle empty result (no new events since last run)
        if not log_entries:
            log.info(
                "no_new_events",
                since=since_timestamp.isoformat(),
                message="No new events since last report",
            )

        # Analyze logs with default rules
        registry = get_default_registry()
        engine = AnalysisEngine(registry=registry)
        findings = engine.analyze(log_entries)
        log.info("analysis_complete", findings_count=len(findings))

        # Collect and analyze IPS events (reuse events already fetched by LogCollector)
        ips_analysis = None
        try:
            raw_ips_events = collector.raw_ips_events

            # If API returns empty, try MongoDB via SSH (UDM Pro workaround)
            if not raw_ips_events and config.ssh_enabled and config.ssh_key_path:
                log.debug("ips_api_empty_trying_mongodb")
                try:
                    from unifi_scanner.logs.mongo_ips_collector import MongoIPSCollector

                    mongo_collector = MongoIPSCollector(
                        host=config.host,
                        username=config.ssh_username or "root",
                        key_path=config.ssh_key_path,
                        key_passphrase=config.ssh_key_passphrase,
                        timeout=config.ssh_timeout,
                    )
                    mongo_alerts = mongo_collector.collect(
                        since_timestamp=since_timestamp,
                        limit=1000,
                    )

                    if mongo_alerts:
                        # Convert MongoDB alerts to IPSEvent objects
                        ips_events = [IPSEvent.from_mongodb_alert(a) for a in mongo_alerts]
                        ips_analyzer = IPSAnalyzer(event_threshold=10)
                        ips_analysis = ips_analyzer.process_events(ips_events)
                        log.info(
                            "ips_analysis_complete",
                            source="mongodb",
                            event_count=len(ips_events),
                            blocked_threats=len(ips_analysis.blocked_threats),
                            detected_threats=len(ips_analysis.detected_threats),
                        )
                    else:
                        log.debug("no_ips_events_mongodb", since=since_timestamp.isoformat())

                except Exception as e:
                    log.warning("ips_mongodb_collection_failed", error=str(e))

            elif raw_ips_events:
                # Convert API events to IPSEvent objects and analyze
                ips_events = [IPSEvent.from_api_event(e) for e in raw_ips_events]
                ips_analyzer = IPSAnalyzer(event_threshold=10)
                ips_analysis = ips_analyzer.process_events(ips_events)
                log.info(
                    "ips_analysis_complete",
                    source="api",
                    event_count=len(ips_events),
                    blocked_threats=len(ips_analysis.blocked_threats),
                    detected_threats=len(ips_analysis.detected_threats),
                )
            else:
                log.debug("no_ips_events", since=since_timestamp.isoformat())

        except Exception as e:
            # IPS analysis is optional - don't fail the whole report
            log.warning("ips_analysis_failed", error=str(e))

        # Collect and analyze device health
        health_analysis = None
        try:
            from unifi_scanner.analysis.device_health import DeviceHealthAnalyzer, DeviceStats

            raw_devices = client.get_devices(site=site)
            if raw_devices:
                device_stats = [DeviceStats.from_api_response(d) for d in raw_devices]
                health_analyzer = DeviceHealthAnalyzer()
                health_analysis = health_analyzer.analyze_devices(device_stats)
                log.info(
                    "health_analysis_complete",
                    device_count=len(device_stats),
                    critical=len(health_analysis.critical_findings),
                    warnings=len(health_analysis.warning_findings),
                )
            else:
                log.debug("no_devices_found", site=site)
        except Exception as e:
            # Health analysis is optional - don't fail the whole report
            log.warning("health_analysis_failed", error=str(e))

        # Build report
        now = datetime.now(timezone.utc)
        report = Report(
            period_start=since_timestamp,  # Use actual cutoff timestamp
            period_end=now,
            site_name=site,
            controller_type=client.device_type or DeviceType.UNKNOWN,
            findings=findings,
            log_entry_count=len(log_entries),
        )

        # Generate report content in a single asyncio.run() call
        # Integrations (e.g. Cloudflare WAF) run once and results are
        # shared between both HTML and text generation.
        async def _generate_reports() -> tuple[str, str]:
            from unifi_scanner.integrations import IntegrationRunner
            runner = IntegrationRunner(config)
            integrations = await runner.run_all()

            generator = ReportGenerator(
                display_timezone=config.schedule_timezone,
            )
            html = await generator.generate_html(
                report, ips_analysis=ips_analysis,
                health_analysis=health_analysis, integrations=integrations,
            )
            text = await generator.generate_text(
                report, ips_analysis=ips_analysis,
                health_analysis=health_analysis, integrations=integrations,
            )
            return html, text

        html_content, text_content = asyncio.run(_generate_reports())

        # Set up delivery
        email_delivery = None
        if config.email_enabled and config.smtp_host:
            email_delivery = EmailDelivery(
                smtp_host=config.smtp_host,
                smtp_port=config.smtp_port,
                smtp_user=config.smtp_user,
                smtp_password=config.smtp_password,
                use_tls=config.smtp_use_tls,
                from_addr=config.email_from,
                timezone=config.schedule_timezone,
            )

        file_delivery = None
        if config.file_enabled and config.file_output_dir:
            file_delivery = FileDelivery(
                output_dir=config.file_output_dir,
                file_format=config.file_format,
                retention_days=config.file_retention_days,
                timezone=config.schedule_timezone,
            )

        # Deliver
        manager = DeliveryManager(
            email_delivery=email_delivery,
            file_delivery=file_delivery,
        )

        recipients = config.get_email_recipients()

        success = manager.deliver(
            report=report,
            html_content=html_content,
            text_content=text_content,
            email_recipients=recipients,
        )

        if success:
            # Update state only after successful delivery
            state_manager.write_last_run(
                timestamp=report.generated_at,
                report_count=len(findings),
            )
            log.info(
                "job_complete",
                status="success",
                state_updated=report.generated_at.isoformat(),
            )
            update_health_status(HealthStatus.HEALTHY, {"last_run": "success"})
        else:
            log.warning("job_complete", status="delivery_failed")
            update_health_status(HealthStatus.UNHEALTHY, {"last_run": "delivery_failed"})

    except Exception as e:
        log.error("job_failed", error=str(e))
        update_health_status(HealthStatus.UNHEALTHY, {"last_run": str(e)})
    finally:
        # Clean up own client if we created one (one-shot mode)
        if own_client is not None:
            own_client.disconnect()


def main() -> int:
    """Main entry point for unifi-scanner.

    Returns:
        Exit code (0=success, 1=config error, 2=connection error, 3=auth error)
    """
    args = parse_args()

    # Import here to avoid circular imports and allow --help without dependencies
    from unifi_scanner.api import UnifiClient
    from unifi_scanner.api.exceptions import AuthenticationError, ConnectionError
    from unifi_scanner.config.loader import ConfigurationError, load_config
    from unifi_scanner.health import HealthStatus, clear_health_status, update_health_status
    from unifi_scanner.logging import configure_logging, get_logger
    from unifi_scanner.scheduler import ScheduledRunner

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

    # Test mode: verify config and connection, then exit
    if args.test:
        update_health_status(HealthStatus.STARTING)
        try:
            with UnifiClient(config) as client:
                site = client.select_site(config.site)
                print_banner(config, client)
                print(f"Site: {site}")
                print("Configuration and connection: OK")
                update_health_status(HealthStatus.HEALTHY, {"site": site})
                return EXIT_SUCCESS
        except ConnectionError as e:
            log.error("connection_failed", error=str(e))
            print(f"\nConnection error: {e}", file=sys.stderr)
            update_health_status(HealthStatus.UNHEALTHY, {"error": str(e)})
            return EXIT_CONNECTION_ERROR
        except AuthenticationError as e:
            log.error("authentication_failed", error=str(e))
            print(f"\nAuthentication error: {e}", file=sys.stderr)
            update_health_status(HealthStatus.UNHEALTHY, {"error": str(e)})
            return EXIT_AUTH_ERROR
        except Exception as e:
            log.error("test_failed", error=str(e))
            print(f"\nTest failed: {e}", file=sys.stderr)
            update_health_status(HealthStatus.UNHEALTHY, {"error": str(e)})
            return EXIT_CONFIG_ERROR
        finally:
            clear_health_status()

    # Run-once mode: execute one report cycle and exit
    if args.run_once:
        print_banner(config)
        log.info("run_once_mode", message="Running single report cycle")
        update_health_status(HealthStatus.STARTING)
        try:
            run_report_job()
            clear_health_status()
            return EXIT_SUCCESS
        except Exception as e:
            log.error("run_once_failed", error=str(e))
            print(f"\nReport generation failed: {e}", file=sys.stderr)
            clear_health_status()
            return EXIT_CONFIG_ERROR

    # Normal mode - print banner and start service
    global _ws_manager
    print_banner(config)
    log.info("starting", version=__version__)
    update_health_status(HealthStatus.STARTING)

    # Set up signal handler for config reload (Unix only)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, handle_sighup)

    # Start persistent REST session and WebSocket manager (if enabled)
    # This authenticates once and shares the session across scheduled runs
    _ws_manager = start_session(config, log)

    # Mark service as healthy now that session is established
    # This happens before the scheduler starts, so Docker healthcheck passes
    # while waiting for the first scheduled run
    update_health_status(HealthStatus.HEALTHY, {"status": "waiting_for_schedule"})

    # Initialize scheduler
    runner = ScheduledRunner(timezone=config.schedule_timezone)

    log.info(
        "service_starting",
        schedule_preset=config.schedule_preset,
        schedule_cron=config.schedule_cron,
        timezone=config.schedule_timezone,
        websocket_enabled=_ws_manager is not None,
        email_enabled=config.email_enabled,
        email_configured=bool(config.email_enabled and config.smtp_host),
        email_recipients_count=len(config.get_email_recipients()),
        file_enabled=config.file_enabled,
    )

    try:
        runner.run(
            func=run_report_job,
            cron_expr=config.schedule_cron,
            preset=config.schedule_preset,
        )
        return EXIT_SUCCESS
    except KeyboardInterrupt:
        log.info("shutdown", reason="keyboard interrupt")
        print("\nShutdown requested, exiting...")
        stop_session(log)
        runner.shutdown()
        clear_health_status()
        return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
