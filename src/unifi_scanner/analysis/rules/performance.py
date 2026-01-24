"""Performance category rules for UniFi event analysis.

Rules for system performance issues like high CPU, memory, interference, and speed problems.
"""

from typing import List

from unifi_scanner.analysis.rules.base import Rule
from unifi_scanner.models.enums import Category, Severity


PERFORMANCE_RULES: List[Rule] = [
    # MEDIUM: Wireless interference detected
    Rule(
        name="ap_interference",
        event_types=["EVT_AP_Interference", "EVT_AP_RADAR_DETECTED"],
        category=Category.PERFORMANCE,
        severity=Severity.MEDIUM,
        title_template="[Performance] Wireless interference detected on {device_name}",
        description_template=(
            "Access point {device_name} is experiencing wireless interference "
            "(EVT_AP_Interference). This can cause slower speeds, dropped connections, "
            "and poor client experience. The AP may automatically change channels to avoid it."
        ),
        remediation_template=(
            "1. Check for nearby devices using the same frequency (microwaves, baby monitors)\n"
            "2. Review channel settings - consider switching to a less congested channel\n"
            "3. Use the controller's RF scan to identify interference sources\n"
            "4. Consider reducing transmit power to minimize overlap with neighbors\n"
            "5. If using DFS channels, radar detection may force channel changes"
        ),
    ),
    # MEDIUM: High CPU usage
    Rule(
        name="high_cpu_usage",
        event_types=["EVT_AP_HIGH_CPU", "EVT_SW_HIGH_CPU", "EVT_GW_HIGH_CPU"],
        category=Category.PERFORMANCE,
        severity=Severity.MEDIUM,
        title_template="[Performance] High CPU usage on {device_name}",
        description_template=(
            "Device {device_name} is experiencing high CPU usage (EVT_*_HIGH_CPU). "
            "This can slow down network processing, cause packet drops, and affect "
            "overall network performance. It may indicate the device is overloaded."
        ),
        remediation_template=(
            "1. Check what services are enabled on the device (IPS, DPI, etc.)\n"
            "2. Consider disabling resource-intensive features if not needed\n"
            "3. Check for firmware updates that may improve efficiency\n"
            "4. If this device handles too much traffic, consider adding capacity\n"
            "5. Reboot the device to clear any stuck processes"
        ),
    ),
    # MEDIUM: High memory usage
    Rule(
        name="high_memory_usage",
        event_types=["EVT_AP_HIGH_MEMORY", "EVT_SW_HIGH_MEMORY", "EVT_GW_HIGH_MEMORY"],
        category=Category.PERFORMANCE,
        severity=Severity.MEDIUM,
        title_template="[Performance] High memory usage on {device_name}",
        description_template=(
            "Device {device_name} is experiencing high memory usage (EVT_*_HIGH_MEMORY). "
            "This can cause instability, slow performance, or unexpected reboots if the "
            "device runs out of available memory."
        ),
        remediation_template=(
            "1. Reboot the device to clear memory (schedule during low-usage period)\n"
            "2. Check for firmware updates that may include memory leak fixes\n"
            "3. Review enabled features - disable any that aren't actively needed\n"
            "4. Check client count - too many clients can consume memory\n"
            "5. If persistent, the device may need replacement with a higher-capacity model"
        ),
    ),
    # MEDIUM: Speed test results below expected
    Rule(
        name="speed_test_slow",
        event_types=["EVT_SPEED_TEST_FAIL", "EVT_SPEED_TEST_SLOW"],
        category=Category.PERFORMANCE,
        severity=Severity.MEDIUM,
        title_template="[Performance] Speed test below expected on {device_name}",
        description_template=(
            "A speed test from {device_name} returned results below your expected "
            "bandwidth (EVT_SPEED_TEST_SLOW). This could indicate ISP issues, network "
            "congestion, or problems with your equipment."
        ),
        remediation_template=(
            "1. Run additional speed tests to confirm - one test may not be accurate\n"
            "2. Check if other devices are using significant bandwidth\n"
            "3. Test directly connected to your modem to isolate the issue\n"
            "4. Contact your ISP if speeds are consistently below your plan\n"
            "5. Check for QoS settings that might be limiting bandwidth"
        ),
    ),
    # MEDIUM: Channel utilization high
    Rule(
        name="channel_utilization_high",
        event_types=["EVT_AP_CHANNEL_UTIL_HIGH", "EVT_HIGH_CHANNEL_UTILIZATION"],
        category=Category.PERFORMANCE,
        severity=Severity.MEDIUM,
        title_template="[Performance] High channel utilization on {device_name}",
        description_template=(
            "Access point {device_name} is reporting high channel utilization "
            "(EVT_AP_CHANNEL_UTIL_HIGH). This means the wireless channel is congested, "
            "which can cause slower speeds and connectivity issues for clients."
        ),
        remediation_template=(
            "1. Check how many clients are connected to this AP\n"
            "2. Consider adding another AP to spread the load\n"
            "3. Enable band steering to move capable clients to 5GHz\n"
            "4. Review if any clients are using excessive bandwidth\n"
            "5. Change to a less congested channel using the RF scan feature"
        ),
    ),
]
