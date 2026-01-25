# UniFi Security Report

A containerized service that monitors UniFi network logs and delivers plain-English security reports via email or file.

## Features

- **Log Collection**: Fetches events and alarms from UniFi Controller API with WebSocket support for UniFi 10.x+
- **Smart Analysis**: Categorizes issues by severity (low, medium, severe) with deduplication
- **Plain English Reports**: Generates human-readable explanations with remediation steps
- **IPS/IDS Analysis**: Translates Suricata signatures into plain English with threat context
- **Device Health Monitoring**: Tracks temperature, CPU, memory, and PoE status across devices
- **Flexible Delivery**: Email (BCC recipients, severity-aware subjects) or file output
- **Scheduled Execution**: Cron expressions, presets (daily_8am, weekly_monday_8am), or one-shot mode
- **Docker Ready**: Multi-stage build with health checks and non-root user

## Example Report

The scanner generates HTML reports that look like this:

<details>
<summary>Click to view example report HTML</summary>

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>UniFi Security Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #fff; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { background: #2282FF; color: #fff; padding: 20px 30px; border-radius: 4px 4px 0 0; }
        .header h1 { margin: 0 0 10px 0; font-size: 24px; }
        .header p { margin: 0; opacity: 0.9; font-size: 14px; }
        .content { padding: 30px; }
        .summary { background: #f8f9fa; border-radius: 4px; padding: 20px; margin-bottom: 20px; }
        .summary h2 { margin: 0 0 15px 0; font-size: 18px; }
        .counts { display: flex; gap: 15px; }
        .count-box { flex: 1; text-align: center; padding: 10px; border-radius: 4px; }
        .count-box.severe { background: #dc3545; color: #fff; }
        .count-box.medium { background: #fd7e14; color: #fff; }
        .count-box.low { background: #6c757d; color: #fff; }
        .count-box .number { font-size: 24px; font-weight: bold; }
        .count-box .label { font-size: 12px; opacity: 0.9; }
        .section { margin-top: 25px; }
        .section h3 { color: #dc3545; margin-bottom: 15px; font-size: 16px; border-bottom: 2px solid #dc3545; padding-bottom: 5px; }
        .section h3.medium { color: #fd7e14; border-color: #fd7e14; }
        .finding { background: #fff; border: 1px solid #e9ecef; border-radius: 4px; padding: 15px; margin-bottom: 10px; }
        .finding-title { font-weight: 600; margin-bottom: 8px; }
        .finding-desc { color: #666; font-size: 14px; margin-bottom: 10px; }
        .finding-remediation { background: #e7f3ff; border-left: 3px solid #2282FF; padding: 10px; font-size: 13px; }
        .threat-section { margin-top: 30px; background: #fff5f5; border: 1px solid #f5c6cb; border-radius: 4px; padding: 20px; }
        .threat-section h3 { color: #dc3545; margin: 0 0 15px 0; }
        .threat-item { padding: 10px 0; border-bottom: 1px solid #f5c6cb; }
        .threat-item:last-child { border-bottom: none; }
        .health-section { margin-top: 30px; background: #fff3e0; border: 1px solid #ffe0b2; border-radius: 4px; padding: 20px; }
        .health-section h3 { color: #e65100; margin: 0 0 15px 0; }
        .footer { background: #f8f9fa; padding: 20px; text-align: center; color: #6c757d; font-size: 12px; border-top: 1px solid #e9ecef; border-radius: 0 0 4px 4px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>UniFi Security Report</h1>
            <p>Home Network</p>
            <p style="margin-top: 15px; font-size: 12px; opacity: 0.8;">
                Period: Jan 24, 2026 08:00 - Jan 25, 2026 08:00<br>
                Generated: Jan 25, 2026 08:00:15
            </p>
        </div>

        <div class="content">
            <div class="summary">
                <h2>Executive Summary</h2>
                <div class="counts">
                    <div class="count-box severe">
                        <div class="number">2</div>
                        <div class="label">SEVERE</div>
                    </div>
                    <div class="count-box medium">
                        <div class="number">5</div>
                        <div class="label">MEDIUM</div>
                    </div>
                    <div class="count-box low">
                        <div class="number">12</div>
                        <div class="label">LOW</div>
                    </div>
                </div>
            </div>

            <div class="section">
                <h3>SEVERE Findings</h3>
                <div class="finding">
                    <div class="finding-title">IPS Alert: Malware Communication Detected</div>
                    <div class="finding-desc">
                        Blocked connection attempt to known malware command & control server from device 192.168.1.105.
                        Signature: ET MALWARE Win32/Emotet CnC Activity
                    </div>
                    <div class="finding-remediation">
                        <strong>Recommended Action:</strong> Isolate the affected device immediately.
                        Run a full malware scan. Check for unauthorized software installations.
                    </div>
                </div>
                <div class="finding">
                    <div class="finding-title">Access Point Temperature Critical</div>
                    <div class="finding-desc">
                        U6-Pro (Office) temperature is 92°C, exceeding critical threshold of 85°C.
                    </div>
                    <div class="finding-remediation">
                        <strong>Recommended Action:</strong> Check ventilation around the device.
                        Consider relocating to a cooler area. May require hardware replacement if temperature persists.
                    </div>
                </div>
            </div>

            <div class="section">
                <h3 class="medium">MEDIUM Findings</h3>
                <div class="finding">
                    <div class="finding-title">Client Roaming Excessively</div>
                    <div class="finding-desc">
                        iPhone-John roamed between access points 8 times in the last hour, indicating possible coverage gaps or interference.
                    </div>
                    <div class="finding-remediation">
                        <strong>Recommended Action:</strong> Check for overlapping channel usage.
                        Adjust transmit power or add coverage in weak areas.
                    </div>
                </div>
            </div>

            <div class="threat-section">
                <h3>Security Threat Summary</h3>
                <p style="margin-bottom: 15px; font-size: 14px;">3 threats detected from 2 unique source IPs</p>
                <div class="threat-item">
                    <strong>ET SCAN Nmap Scripting Engine</strong><br>
                    <span style="color: #666; font-size: 13px;">
                        Category: Network Scanning | Action: Blocked | Sources: 45.33.32.156 (2 events)
                    </span>
                </div>
                <div class="threat-item">
                    <strong>ET MALWARE Win32/Emotet</strong><br>
                    <span style="color: #666; font-size: 13px;">
                        Category: Malware | Action: Blocked | Sources: 192.168.1.105 (1 event)
                    </span>
                </div>
            </div>

            <div class="health-section">
                <h3>Device Health Summary</h3>
                <p style="margin-bottom: 15px; font-size: 14px;">1 critical, 2 warnings across 8 devices</p>
                <div class="threat-item">
                    <strong>U6-Pro (Office)</strong> - Temperature: 92°C (Critical)<br>
                    <span style="color: #666; font-size: 13px;">Uptime: 45 days | CPU: 12% | Memory: 34%</span>
                </div>
                <div class="threat-item">
                    <strong>USW-24-PoE</strong> - PoE Budget: 89% used (Warning)<br>
                    <span style="color: #666; font-size: 13px;">Uptime: 120 days | CPU: 8% | Memory: 45%</span>
                </div>
            </div>
        </div>

        <div class="footer">
            Generated by UniFi Scanner v0.3.4a1
        </div>
    </div>
</body>
</html>
```

</details>

## Quick Start

### Docker Compose

```bash
# Create secrets
mkdir -p secrets
echo "your-unifi-password" > secrets/unifi_password.txt
echo "your-smtp-password" > secrets/smtp_password.txt

# Configure environment
cat > .env << 'ENVEOF'
UNIFI_HOST=192.168.1.1
UNIFI_USERNAME=admin
UNIFI_SCHEDULE_PRESET=daily_8am
UNIFI_SCHEDULE_TIMEZONE=America/New_York
ENVEOF

# Run
docker-compose up -d
```

### Pull from GitHub Container Registry

```bash
docker pull ghcr.io/trek-e/unifi-security-report:latest
```

### Local Installation

```bash
pip install -e .
unifi-scanner --help
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `UNIFI_HOST` | Controller hostname/IP | Required |
| `UNIFI_USERNAME` | Admin username | Required |
| `UNIFI_PASSWORD` | Admin password | Required |
| `UNIFI_SITE` | Site name | Auto-detect |
| `UNIFI_SCHEDULE_PRESET` | Schedule preset | `daily_8am` |
| `UNIFI_SCHEDULE_CRON` | Cron expression | None |
| `UNIFI_EMAIL_ENABLED` | Enable email delivery | `false` |
| `UNIFI_FILE_ENABLED` | Enable file output | `false` |

See `docker-compose.yml` for all options.

## Version History

| Version | Phase | Features |
|---------|-------|----------|
| v0.3.4a1 | 10 | Integration infrastructure for external services |
| v0.3.3a1 | 9 | Device health monitoring (temperature, CPU, memory, PoE) |
| v0.3.2a1 | 8 | Enhanced IPS/IDS analysis with remediation guidance |
| v0.3.1a1 | 7 | Extended wireless analysis (roaming, DFS, RSSI) |
| v0.3.0a1 | 6 | State persistence to prevent duplicate reports |
| v0.2.0a1 | 1-5 | Production-ready containerized service |

## License

MIT
