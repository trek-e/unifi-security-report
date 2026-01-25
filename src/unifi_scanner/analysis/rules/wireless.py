"""Wireless category rules for UniFi event analysis.

Rules for client roaming, band switching, channel changes, and DFS radar events.
Includes helpers for RSSI-to-quality translation and radio band formatting.
"""

from typing import List, Optional

from unifi_scanner.analysis.rules.base import Rule
from unifi_scanner.models.enums import Category, Severity


# RSSI thresholds for signal quality classification (WIFI-05)
RSSI_THRESHOLDS = {
    "Excellent": -50,  # >= -50 dBm
    "Good": -60,       # -50 to -60 dBm
    "Fair": -70,       # -60 to -70 dBm
    "Poor": -80,       # -70 to -80 dBm
    # < -80 dBm = Very Poor
}


def rssi_to_quality(rssi: Optional[int]) -> str:
    """Convert RSSI (dBm) to human-readable quality label.

    Args:
        rssi: Signal strength in dBm (negative number) or None

    Returns:
        Quality label: Excellent, Good, Fair, Poor, or Very Poor
    """
    if rssi is None:
        return "Unknown"
    if rssi >= -50:
        return "Excellent"
    elif rssi >= -60:
        return "Good"
    elif rssi >= -70:
        return "Fair"
    elif rssi >= -80:
        return "Poor"
    else:
        return "Very Poor"


# Radio band codes used by UniFi
RADIO_BANDS = {
    "ng": "2.4GHz",
    "na": "5GHz",
    "6e": "6GHz",
}


def format_radio_band(radio_code: Optional[str]) -> str:
    """Convert UniFi radio code to human-readable band.

    Args:
        radio_code: UniFi code (ng, na, 6e) or None

    Returns:
        Human-readable band name or original code if unknown
    """
    if radio_code is None:
        return "Unknown"
    return RADIO_BANDS.get(radio_code, radio_code)


WIRELESS_RULES: List[Rule] = [
    # LOW: Client roaming (WIFI-01)
    Rule(
        name="client_roaming",
        event_types=["EVT_WU_Roam", "EVT_WG_Roam"],
        category=Category.WIRELESS,
        severity=Severity.LOW,
        title_template="[Wireless] Client roamed from {ap_from_name} to {ap_to_name}",
        description_template=(
            "A client device roamed to access point {device_name} "
            "(EVT_WU_Roam for users, EVT_WG_Roam for guests). This is normal wireless "
            "mobility behavior - the client moved between APs while maintaining its "
            "network connection. Signal: {rssi_quality} ({rssi} dBm). Frequent roaming may indicate coverage overlap or "
            "signal strength issues, but occasional roaming is expected."
        ),
        remediation_template=None,  # LOW severity - no remediation needed
    ),
    # LOW: Band switching (WIFI-02)
    Rule(
        name="band_switch",
        event_types=["EVT_WU_RoamRadio", "EVT_WG_RoamRadio"],
        category=Category.WIRELESS,
        severity=Severity.LOW,
        title_template="[Wireless] Client switched from {radio_from_display} to {radio_to_display} on {device_name}",
        description_template=(
            "A client device switched radio bands on {device_name} "
            "(EVT_WU_RoamRadio/EVT_WG_RoamRadio). This typically happens when band "
            "steering moves clients between 2.4GHz and 5GHz frequencies. 5GHz offers "
            "faster speeds but shorter range, while 2.4GHz has better wall penetration. "
            "Band switching is normal WiFi optimization behavior."
        ),
        remediation_template=None,  # LOW severity - no remediation needed
    ),
    # MEDIUM: AP channel change (WIFI-03)
    Rule(
        name="ap_channel_change",
        event_types=["EVT_AP_ChannelChange"],
        category=Category.WIRELESS,
        severity=Severity.MEDIUM,
        title_template="[Wireless] AP {device_name} changed channel from {channel_from} to {channel_to}",
        description_template=(
            "Access point {device_name} changed its wireless channel "
            "(EVT_AP_ChannelChange). This usually happens automatically when the AP "
            "detects interference from neighboring networks or devices and moves to "
            "a cleaner channel. Frequent channel changes may indicate a congested "
            "wireless environment."
        ),
        remediation_template=(
            "1. Check if WiFi AI/Auto-optimize is enabled - this causes automatic changes\n"
            "2. Survey nearby WiFi networks using a WiFi analyzer app\n"
            "3. Look for non-WiFi interference sources (microwaves, baby monitors, Bluetooth)\n"
            "4. Consider manually assigning channels if auto-selection is unstable\n"
            "5. For 5GHz, prefer non-DFS channels (36-48) to avoid radar-triggered changes"
        ),
    ),
    # MEDIUM: DFS radar detected (WIFI-04)
    Rule(
        name="dfs_radar_detected",
        event_types=["EVT_AP_RADAR_DETECTED", "EVT_AP_Interference", "EVT_AP_ChannelChange"],
        category=Category.WIRELESS,
        severity=Severity.MEDIUM,
        title_template="[Wireless] DFS radar detected on {device_name}",
        description_template=(
            "Access point {device_name} detected radar on a DFS (Dynamic Frequency Selection) "
            "channel (EVT_AP_RADAR_DETECTED) and must vacate the channel for 30 minutes per FCC "
            "regulations. DFS channels (52-144 in 5GHz) are shared with weather radar and "
            "military systems. Radar detection causes temporary channel changes and may briefly "
            "affect clients."
        ),
        remediation_template=(
            "1. Consider using non-DFS channels (36-48) to avoid radar interruptions\n"
            "2. Check if you're near an airport, military base, or weather station\n"
            "3. If radar events are frequent, permanently move to non-DFS channels\n"
            "4. Note: Some regions require DFS for certain 5GHz channels\n"
            "5. The AP will automatically return to the channel after 30 minutes if clear"
        ),
        pattern=r"[Rr]adar.*(detected|hit)",
    ),
]
