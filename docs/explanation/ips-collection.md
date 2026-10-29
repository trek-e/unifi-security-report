# About IPS/IDS Data Collection

A significant challenge in monitoring UniFi networks is that the standard REST API often does not expose detailed Intrusion Detection (IDS) or Intrusion Prevention (IPS) event data.

## The Problem

While the UniFi Network interface shows security threats to users, the underlying API endpoints used by the web UI often omit the granular details (like signature names or specific threat categories) required for high-quality security reporting.

## The Solution: SSH Fallback

To overcome this limitation, the UniFi Security Report implements an "SSH Fallback" mechanism for UDM Pro, UCG Ultra, and other UniFi OS-based devices.

### How it Works

1. **Detection**: When the scanner detects it is running on a device type that supports SSH fallback, it attempts to establish an SSH connection.
2. **Direct Query**: Instead of relying on the REST API, the scanner executes commands over SSH to query the local MongoDB instance directly.
3. **Data Extraction**: It extracts threat events from the `mongodb` database, which contains the raw security logs.

### Limitations

While this method provides much richer data than the REST API, it has some trade-offs:

- **Data Granularity**: MongoDB logs contain the core facts (Source IP, Destination IP, Timestamp, Severity), but they may not include the human-friendly signature names or categories that the UniFi UI provides.
- **Authentication**: This method requires SSH key-based authentication, as password-based SSH is typically disabled on modern UniFi OS devices.
- **Resource Usage**: Establishing SSH connections is more resource-intensive than making HTTP requests.

## Configuration

To enable this feature, you must provide an SSH private key via the `UNIFI_SSH_KEY_PATH` environment variable. See the [Configuration Reference](../reference/configuration.md) for a full list of available settings.
