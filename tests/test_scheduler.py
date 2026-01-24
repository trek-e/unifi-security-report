"""Tests for scheduler."""

from unittest.mock import MagicMock, patch

import pytest

from unifi_scanner.scheduler.presets import SCHEDULE_PRESETS, get_preset, list_presets
from unifi_scanner.scheduler.runner import ScheduledRunner, SchedulerError


class TestPresets:
    """Test schedule presets."""

    def test_list_presets(self) -> None:
        """Lists all available presets."""
        presets = list_presets()
        assert "daily_8am" in presets
        assert "weekly_monday_8am" in presets

    def test_get_preset_daily(self) -> None:
        """Get daily preset parameters."""
        params = get_preset("daily_8am")
        assert params is not None
        assert params["hour"] == 8
        assert params["minute"] == 0

    def test_get_preset_weekly(self) -> None:
        """Get weekly preset parameters."""
        params = get_preset("weekly_monday_8am")
        assert params is not None
        assert params["day_of_week"] == "mon"
        assert params["hour"] == 8

    def test_get_preset_unknown(self) -> None:
        """Unknown preset returns None."""
        assert get_preset("nonexistent") is None

    def test_all_presets_have_hour_minute(self) -> None:
        """All presets must have hour and minute."""
        for name, params in SCHEDULE_PRESETS.items():
            assert "hour" in params, f"Preset {name} missing hour"
            assert "minute" in params, f"Preset {name} missing minute"


class TestScheduledRunner:
    """Test scheduler runner."""

    def test_init_defaults(self) -> None:
        """Default initialization."""
        runner = ScheduledRunner()
        assert runner.timezone == "UTC"
        assert runner.misfire_grace_time == 3600

    def test_init_custom_timezone(self) -> None:
        """Custom timezone initialization."""
        runner = ScheduledRunner(timezone="America/New_York")
        assert runner.timezone == "America/New_York"

    def test_init_custom_misfire_grace_time(self) -> None:
        """Custom misfire grace time initialization."""
        runner = ScheduledRunner(misfire_grace_time=7200)
        assert runner.misfire_grace_time == 7200

    def test_both_cron_and_preset_raises(self) -> None:
        """Cannot specify both cron and preset."""
        runner = ScheduledRunner()

        with pytest.raises(SchedulerError, match="Cannot specify both"):
            runner.run(
                func=lambda: None,
                cron_expr="0 8 * * *",
                preset="daily_8am",
            )

    @patch("unifi_scanner.scheduler.runner.BlockingScheduler")
    def test_run_with_preset(self, mock_scheduler_class: MagicMock) -> None:
        """Run with preset schedule."""
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        # Make start() raise to exit immediately (runner catches KeyboardInterrupt)
        mock_scheduler.start.side_effect = KeyboardInterrupt

        runner = ScheduledRunner(timezone="UTC")
        job_func = MagicMock()

        # run() catches KeyboardInterrupt gracefully, so no exception propagates
        runner.run(func=job_func, preset="daily_8am")

        mock_scheduler.add_job.assert_called_once()
        call_kwargs = mock_scheduler.add_job.call_args[1]
        assert call_kwargs["hour"] == 8
        assert call_kwargs["minute"] == 0

    @patch("unifi_scanner.scheduler.runner.BlockingScheduler")
    def test_run_with_cron(self, mock_scheduler_class: MagicMock) -> None:
        """Run with cron expression."""
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler
        mock_scheduler.start.side_effect = KeyboardInterrupt

        runner = ScheduledRunner(timezone="America/New_York")
        job_func = MagicMock()

        # run() catches KeyboardInterrupt gracefully
        runner.run(func=job_func, cron_expr="30 9 * * *")

        # Verify job was added with trigger
        mock_scheduler.add_job.assert_called_once()

    @patch("unifi_scanner.scheduler.runner.BlockingScheduler")
    def test_one_shot_mode(self, mock_scheduler_class: MagicMock) -> None:
        """One-shot mode when no schedule specified."""
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        runner = ScheduledRunner()
        job_func = MagicMock()

        runner.run_once(job_func)

        # Verify date trigger used (one-shot)
        mock_scheduler.add_job.assert_called_once()
        call_args = mock_scheduler.add_job.call_args
        assert call_args[0][1] == "date"  # Trigger type

    @patch("unifi_scanner.scheduler.runner.BlockingScheduler")
    def test_run_no_schedule_triggers_one_shot(
        self, mock_scheduler_class: MagicMock
    ) -> None:
        """run() with no cron_expr or preset triggers one-shot mode."""
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        runner = ScheduledRunner()
        job_func = MagicMock()

        # run() with neither cron_expr nor preset should call run_once internally
        runner.run(func=job_func)

        # Verify date trigger was used (one-shot behavior)
        mock_scheduler.add_job.assert_called_once()
        call_args = mock_scheduler.add_job.call_args
        assert call_args[0][1] == "date"

    def test_run_with_invalid_preset_raises(self) -> None:
        """Unknown preset raises SchedulerError."""
        runner = ScheduledRunner()

        with pytest.raises(SchedulerError, match="Unknown schedule preset"):
            runner.run(func=lambda: None, preset="nonexistent_preset")

    @patch("unifi_scanner.scheduler.runner.BlockingScheduler")
    def test_scheduler_job_defaults(self, mock_scheduler_class: MagicMock) -> None:
        """Verify job defaults are set correctly."""
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        runner = ScheduledRunner(timezone="UTC", misfire_grace_time=3600)
        _ = runner._create_scheduler()

        # Verify scheduler was created with correct job defaults
        call_kwargs = mock_scheduler_class.call_args[1]
        assert call_kwargs["timezone"] == "UTC"
        job_defaults = call_kwargs["job_defaults"]
        assert job_defaults["coalesce"] is True
        assert job_defaults["misfire_grace_time"] == 3600
        assert job_defaults["max_instances"] == 1

    @patch("unifi_scanner.scheduler.runner.BlockingScheduler")
    def test_shutdown(self, mock_scheduler_class: MagicMock) -> None:
        """Shutdown stops the scheduler."""
        mock_scheduler = MagicMock()
        mock_scheduler.running = True
        mock_scheduler_class.return_value = mock_scheduler
        mock_scheduler.start.side_effect = KeyboardInterrupt

        runner = ScheduledRunner()

        # run() catches KeyboardInterrupt gracefully
        runner.run(func=lambda: None, preset="daily_8am")

        # Now shutdown
        runner.shutdown()

        mock_scheduler.shutdown.assert_called_once_with(wait=True)
