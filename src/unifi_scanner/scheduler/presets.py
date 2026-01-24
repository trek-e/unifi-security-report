"""Schedule preset definitions."""

from typing import Any, Dict, List, Optional

# Preset schedules with cron-style parameters
SCHEDULE_PRESETS: Dict[str, Dict[str, Any]] = {
    "daily_8am": {"hour": 8, "minute": 0},
    "daily_6pm": {"hour": 18, "minute": 0},
    "weekly_monday_8am": {"day_of_week": "mon", "hour": 8, "minute": 0},
    "weekly_friday_5pm": {"day_of_week": "fri", "hour": 17, "minute": 0},
}


def get_preset(name: str) -> Optional[Dict[str, Any]]:
    """Get schedule preset by name.

    Args:
        name: Preset name (e.g., 'daily_8am')

    Returns:
        Dict of cron parameters, or None if not found
    """
    return SCHEDULE_PRESETS.get(name)


def list_presets() -> List[str]:
    """List available preset names."""
    return list(SCHEDULE_PRESETS.keys())
