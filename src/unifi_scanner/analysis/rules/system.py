"""System category rules for UniFi event analysis.

Rules for firmware updates, device restarts, adoption, and configuration changes.
"""

from typing import List

from unifi_scanner.analysis.rules.base import Rule
from unifi_scanner.models.enums import Category, Severity


SYSTEM_RULES: List[Rule] = [
    # LOW: Firmware upgraded successfully
    Rule(
        name="firmware_upgraded",
        event_types=["EVT_AP_Upgraded", "EVT_SW_Upgraded", "EVT_GW_Upgraded", "EVT_DEVICE_UPGRADED"],
        category=Category.SYSTEM,
        severity=Severity.LOW,
        title_template="[System] Firmware upgraded on {device_name}",
        description_template=(
            "Device {device_name} has been upgraded to new firmware (EVT_*_Upgraded). "
            "Firmware updates typically include bug fixes, security patches, and new features. "
            "The device may have rebooted to apply the update."
        ),
        remediation_template=None,  # LOW severity - no remediation needed
    ),
    # LOW: Device restarted (planned/expected)
    Rule(
        name="device_restarted",
        event_types=["EVT_AP_Restarted", "EVT_SW_Restarted", "EVT_GW_Restarted"],
        category=Category.SYSTEM,
        severity=Severity.LOW,
        title_template="[System] Device {device_name} restarted",
        description_template=(
            "Device {device_name} has restarted (EVT_*_Restarted). This could be from a "
            "firmware update, manual reboot, or scheduled maintenance. The device should "
            "resume normal operation automatically."
        ),
        remediation_template=None,  # LOW severity - no remediation needed
    ),
    # MEDIUM: Device restarted unexpectedly
    Rule(
        name="device_restarted_unknown",
        event_types=["EVT_AP_RestartedUnknown", "EVT_SW_RestartedUnknown", "EVT_GW_RestartedUnknown"],
        category=Category.SYSTEM,
        severity=Severity.MEDIUM,
        title_template="[System] Device {device_name} restarted unexpectedly",
        description_template=(
            "Device {device_name} restarted for an unknown reason (EVT_*_RestartedUnknown). "
            "This could indicate hardware issues, firmware bugs, or power problems. "
            "Occasional unexpected restarts may be normal, but frequent ones warrant investigation."
        ),
        remediation_template=(
            "1. Check the device's power supply and connections\n"
            "2. Review logs around the restart time for error messages\n"
            "3. Ensure the device isn't overheating - check ventilation\n"
            "4. Update firmware if an update is available\n"
            "5. If this happens frequently, the device may need replacement"
        ),
    ),
    # LOW: Device adopted
    Rule(
        name="device_adopted",
        event_types=["EVT_AP_Adopted", "EVT_SW_Adopted", "EVT_GW_Adopted", "EVT_DEVICE_ADOPTED"],
        category=Category.SYSTEM,
        severity=Severity.LOW,
        title_template="[System] New device {device_name} adopted",
        description_template=(
            "A new UniFi device {device_name} ({device_mac}) has been adopted into your "
            "network (EVT_*_Adopted). The device is now managed by your controller and "
            "will receive configuration and firmware updates."
        ),
        remediation_template=None,  # LOW severity - no remediation needed
    ),
    # LOW: Configuration changed
    Rule(
        name="config_changed",
        event_types=["EVT_CONFIG_CHANGED", "EVT_SITE_CONFIG_CHANGED"],
        category=Category.SYSTEM,
        severity=Severity.LOW,
        title_template="[System] Configuration changed by {user}",
        description_template=(
            "A configuration change was made to your UniFi network by {user} "
            "(EVT_CONFIG_CHANGED). This is logged for audit purposes. Check the controller "
            "for specific details about what was modified."
        ),
        remediation_template=None,  # LOW severity - no remediation needed
    ),
    # LOW: Backup created
    Rule(
        name="backup_created",
        event_types=["EVT_BACKUP_CREATED", "EVT_AUTO_BACKUP"],
        category=Category.SYSTEM,
        severity=Severity.LOW,
        title_template="[System] Backup created on {device_name}",
        description_template=(
            "A backup of your UniFi controller configuration was created (EVT_BACKUP_CREATED). "
            "Regular backups help protect against data loss and make it easier to restore "
            "your network configuration if needed."
        ),
        remediation_template=None,  # LOW severity - no remediation needed
    ),
    # LOW: Update available
    Rule(
        name="update_available",
        event_types=["EVT_AP_UPDATE_AVAILABLE", "EVT_SW_UPDATE_AVAILABLE", "EVT_GW_UPDATE_AVAILABLE"],
        category=Category.SYSTEM,
        severity=Severity.LOW,
        title_template="[System] Firmware update available for {device_name}",
        description_template=(
            "A firmware update is available for {device_name} (EVT_*_UPDATE_AVAILABLE). "
            "Updates typically include security patches and bug fixes. Consider scheduling "
            "an update during low-traffic hours."
        ),
        remediation_template=None,  # LOW severity - no remediation needed
    ),
]
