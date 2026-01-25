"""Health category rules for UniFi event analysis.

Rules for device health events including PoE disconnect, overload, and power issues.
"""

from typing import List

from unifi_scanner.analysis.rules.base import Rule
from unifi_scanner.models.enums import Category, Severity


HEALTH_RULES: List[Rule] = [
    # MEDIUM: PoE device disconnected
    Rule(
        name="poe_disconnect",
        event_types=["EVT_SW_PoeDisconnect"],
        category=Category.SYSTEM,
        severity=Severity.MEDIUM,
        title_template="[Device Health] PoE device disconnected on {device_name} port {port}",
        description_template=(
            "A Power over Ethernet (PoE) powered device has disconnected from {device_name} "
            "on port {port} (EVT_SW_PoeDisconnect). The device lost power delivery from the "
            "switch, which could indicate cable issues, power budget problems, or device failure."
        ),
        remediation_template=(
            "1. Check the switch's PoE power budget - may be oversubscribed\n"
            "2. Verify the Ethernet cable is properly seated at both ends\n"
            "3. Inspect the cable for damage - try a known-good cable\n"
            "4. Consider using external PoE injectors for high-power devices\n"
            "5. Review if the disconnected device requires more power than the port can supply"
        ),
    ),
    # SEVERE: PoE power budget exceeded (overload)
    Rule(
        name="poe_overload",
        event_types=["EVT_SW_PoeOverload", "EVT_SW_PoeBudgetExceeded"],
        category=Category.SYSTEM,
        severity=Severity.SEVERE,
        title_template="[Device Health] PoE power budget exceeded on {device_name}",
        description_template=(
            "The Power over Ethernet (PoE) power budget has been exceeded on {device_name} "
            "(EVT_SW_PoeOverload/EVT_SW_PoeBudgetExceeded). IMMEDIATE ATTENTION REQUIRED. "
            "Connected PoE devices may lose power or operate erratically. The switch cannot "
            "supply enough power to meet the demand from all connected PoE devices."
        ),
        remediation_template=(
            "1. Identify all PoE devices connected to this switch and their power requirements\n"
            "2. Disconnect non-critical PoE devices temporarily to restore power to critical ones\n"
            "3. Review PoE consumption per port in the UniFi controller\n"
            "4. Consider upgrading to a switch with higher PoE budget capacity\n"
            "5. Use external PoE injectors to offload power from the switch\n"
            "6. Configure PoE power limits per port to prevent budget overruns"
        ),
    ),
]
