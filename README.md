# UniFi Security Report

A containerized service that monitors UniFi network logs and delivers plain-English security reports via email or file.

## Features

- **Log Collection**: Fetches events and alarms from UniFi Controller API with SSH fallback
- **Smart Analysis**: Categorizes issues by severity (low, medium, severe) with deduplication
- **Plain English Reports**: Generates human-readable explanations with remediation steps
- **Flexible Delivery**: Email (BCC recipients, severity-aware subjects) or file output
- **Scheduled Execution**: Cron expressions, presets (daily_8am, weekly_monday_8am), or one-shot mode
- **Docker Ready**: Multi-stage build with health checks and non-root user

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

## License

MIT
