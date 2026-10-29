# Features

The UniFi Security Report provides a comprehensive suite of monitoring and analysis capabilities.

## Core Capabilities

### Log Collection
- **UniFi Controller API**: Fetches events and alarms using standard REST endpoints.
- **WebSocket Support**: Real-time event monitoring for UniFi Network 10.x+.
- **SSH Fallback**: Direct MongoDB querying for deep IPS/IDS visibility on UDM-class devices.

### Smart Analysis
- **Severity Categorization**: Automatically classifies issues as `Low`, `Medium`, or `Severe`.
- **Deduplication**: Prevents alert fatigue by grouping related events into single report entries.
- **Contextual Remediation**: Provides plain-English explanations and actionable steps for every detected issue.

### Specialized Monitoring
- **IPS/IDS Analysis**: Translates Suricata signatures into human-readable threat context.
- **Cybersecure Integration**: Automatically detects and flags threats identified by Proofpoint ET PRO enhanced signatures.
- **Device Health**: Monitors critical hardware metrics including temperature, CPU load, memory usage, and PoE budget.
- **Wireless Intelligence**: Analyzes client behavior to detect roaming issues, DFS events, and signal interference.
- **Cloudflare Integration**: Monitors WAF blocks, DNS filtering, and Cloudflare Tunnel status.

## Delivery Options

- **Email**: Send formatted HTML reports to one or more recipients via SMTP.
- **File Output**: Save reports locally in HTML or plain text formats.
- **Scheduled Execution**: Run reports automatically using presets (e.g., `daily_8am`) or custom cron expressions.
