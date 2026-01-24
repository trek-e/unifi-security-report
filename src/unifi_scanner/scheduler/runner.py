"""Scheduled runner using APScheduler."""

from datetime import datetime, timedelta
from typing import Any, Callable, Optional

import structlog
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from unifi_scanner.scheduler.presets import SCHEDULE_PRESETS, get_preset

log = structlog.get_logger()


class SchedulerError(Exception):
    """Raised when scheduler configuration fails."""

    pass


class ScheduledRunner:
    """APScheduler-based service runner.

    Supports:
    - Cron expressions (5-field format)
    - Named presets (daily_8am, weekly_monday_8am, etc.)
    - One-shot mode (no schedule = run once and exit)
    - Configurable timezone
    """

    def __init__(
        self,
        timezone: str = "UTC",
        misfire_grace_time: int = 3600,  # 1 hour
    ) -> None:
        """Initialize scheduler.

        Args:
            timezone: IANA timezone for schedule (e.g., 'America/New_York')
            misfire_grace_time: Seconds after scheduled time to still run missed job
        """
        self.timezone = timezone
        self.misfire_grace_time = misfire_grace_time
        self._scheduler: Optional[BlockingScheduler] = None
        self._job_func: Optional[Callable[[], None]] = None

    def _create_scheduler(self) -> BlockingScheduler:
        """Create configured BlockingScheduler."""
        job_defaults = {
            "coalesce": True,  # Combine missed runs into one
            "misfire_grace_time": self.misfire_grace_time,
            "max_instances": 1,  # Prevent concurrent runs
        }
        return BlockingScheduler(
            timezone=self.timezone,
            job_defaults=job_defaults,
        )

    def _add_cron_job(
        self,
        scheduler: BlockingScheduler,
        func: Callable[[], None],
        cron_expr: str,
    ) -> None:
        """Add job with cron expression (5-field format).

        Args:
            scheduler: The scheduler to add job to
            func: Function to execute on schedule
            cron_expr: Cron expression (min hour day month weekday)
        """
        # IMPORTANT: Always pass timezone explicitly to from_crontab()
        # It does NOT inherit from scheduler timezone
        trigger = CronTrigger.from_crontab(cron_expr, timezone=self.timezone)
        scheduler.add_job(func, trigger, id="report_job")
        log.info(
            "job_scheduled",
            schedule_type="cron",
            cron=cron_expr,
            timezone=self.timezone,
        )

    def _add_preset_job(
        self,
        scheduler: BlockingScheduler,
        func: Callable[[], None],
        preset: str,
    ) -> None:
        """Add job using preset schedule.

        Args:
            scheduler: The scheduler to add job to
            func: Function to execute on schedule
            preset: Preset name (e.g., 'daily_8am')

        Raises:
            SchedulerError: If preset is unknown
        """
        params = get_preset(preset)
        if params is None:
            available = ", ".join(SCHEDULE_PRESETS.keys())
            raise SchedulerError(
                f"Unknown schedule preset: '{preset}'. Available: {available}"
            )

        scheduler.add_job(
            func,
            "cron",
            timezone=self.timezone,
            **params,
            id="report_job",
        )
        log.info(
            "job_scheduled",
            schedule_type="preset",
            preset=preset,
            params=params,
            timezone=self.timezone,
        )

    def run_once(self, func: Callable[[], None]) -> None:
        """Execute function once immediately, then exit.

        Used when no schedule is configured (one-shot mode).

        Args:
            func: Function to execute
        """
        log.info("one_shot_mode", message="Running once and exiting")
        scheduler = self._create_scheduler()

        # Schedule for 1 second from now
        run_time = datetime.now() + timedelta(seconds=1)
        scheduler.add_job(
            func,
            "date",
            run_date=run_time,
            id="oneshot_job",
        )

        # Shutdown after job completes
        def shutdown_after_job(event: Any) -> None:
            scheduler.shutdown(wait=False)

        scheduler.add_listener(shutdown_after_job, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        scheduler.start()

    def run(
        self,
        func: Callable[[], None],
        cron_expr: Optional[str] = None,
        preset: Optional[str] = None,
    ) -> None:
        """Start the scheduler with the given job.

        If neither cron_expr nor preset is provided, runs in one-shot mode.

        Args:
            func: Function to execute on schedule
            cron_expr: Optional cron expression (5-field)
            preset: Optional preset name

        Raises:
            SchedulerError: If both cron_expr and preset are provided
        """
        if cron_expr and preset:
            raise SchedulerError("Cannot specify both cron expression and preset")

        # One-shot mode if no schedule
        if not cron_expr and not preset:
            self.run_once(func)
            return

        # Create scheduler and add job
        self._scheduler = self._create_scheduler()
        self._job_func = func

        if cron_expr:
            self._add_cron_job(self._scheduler, func, cron_expr)
        else:
            self._add_preset_job(self._scheduler, func, preset)  # type: ignore

        # Add error listener for logging
        def on_job_error(event: Any) -> None:
            log.error("job_failed", error=str(event.exception))

        self._scheduler.add_listener(on_job_error, EVENT_JOB_ERROR)

        # Start blocking scheduler (runs until interrupted)
        log.info("scheduler_starting", timezone=self.timezone)
        try:
            self._scheduler.start()
        except KeyboardInterrupt:
            log.info("scheduler_shutdown", reason="keyboard interrupt")

    def shutdown(self) -> None:
        """Gracefully shutdown the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=True)
            log.info("scheduler_shutdown", reason="explicit shutdown")
