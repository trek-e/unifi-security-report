# Configuration

All settings use the `UNIFI_` prefix as environment variables. Configuration is loaded in this order (highest priority first):

1. Environment variables (`UNIFI_*`)
2. Docker secrets (`UNIFI_*_FILE` pointing to a file)
3. YAML config file (set `CONFIG_PATH=/path/to/config.yml`)
4. Default values

## Connection (Required)

| Variable | Description | Default |
|----------|-------------|---------|
| `UNIFI_HOST` | Controller hostname or IP address | Required |
| `UNIFI_USERNAME` | Admin username (must be a local account, not cloud SSO) | Required |
| `UNIFI_PASSWORD` | Admin password (or use `UNIFI_PASSWORD_FILE` for Docker secrets) | Required |
| `UNIFI_PORT` | Controller port | Auto-detect (tries 443, 8443, 11443) |
| `UNIFI_VERIFY_SSL` | Verify SSL certificates (set `false` for self-signed certs) | `true` |
| `UNIFI_SITE` | UniFi site name | Auto-detect |
| `UNIFI_CONNECT_TIMEOUT` | Connection timeout in seconds | `10` |
| `UNIFI_MAX_RETRIES` | Retry attempts on connection failure | `5` |

## Schedule

| Variable | Description | Default |
|----------|-------------|---------|
| `UNIFI_SCHEDULE_PRESET` | Preset: `daily_8am`, `daily_6pm`, `weekly_monday_8am`, `weekly_friday_5pm` | None |
| `UNIFI_SCHEDULE_CRON` | Custom cron expression (5-field: `min hour day month weekday`) | None |
| `UNIFI_SCHEDULE_TIMEZONE` | Timezone for schedule (IANA format) | `UTC` |
| `UNIFI_POLL_INTERVAL` | Polling interval in seconds (used between report cycles) | `300` |
| `UNIFI_INITIAL_LOOKBACK_HOURS` | Hours of history to process on first run (1-720) | `24` |

## Email Delivery

| Variable | Description | Default |
|----------|-------------|---------|
| `UNIFI_EMAIL_ENABLED` | Enable email delivery | `false` |
| `UNIFI_SMTP_HOST` | SMTP server hostname | Required when email enabled |
| `UNIFI_SMTP_PORT` | SMTP port (`587` for STARTTLS, `465` for implicit TLS) | `587` |
| `UNIFI_SMTP_USER` | SMTP auth username | None |
| `UNIFI_SMTP_PASSWORD` | SMTP auth password | None |
| `UNIFI_SMTP_USE_TLS` | Enable TLS encryption | `true` |
| `UNIFI_EMAIL_FROM` | Sender address | `unifi-scanner@localhost` |
| `UNIFI_EMAIL_RECIPIENTS` | Comma-separated recipient addresses (all sent via BCC) | None |
| `UNIFI_TIMEZONE` | Timezone for report timestamps and email subjects | `UTC` |

**Example — Gmail with app password:**
```yaml
UNIFI_EMAIL_ENABLED: "true"
UNIFI_SMTP_HOST: smtp.gmail.com
UNIFI_SMTP_PORT: "587"
UNIFI_SMTP_USER: you@gmail.com
UNIFI_SMTP_PASSWORD: your-app-password
UNIFI_EMAIL_FROM: you@gmail.com
UNIFI_EMAIL_RECIPIENTS: admin@example.com,backup@example.com
```

**Example — Local relay (no auth):**
```yaml
UNIFI_EMAIL_ENABLED: "true"
UNIFI_SMTP_HOST: 192.168.1.50
UNIFI_SMTP_PORT: "25"
UNIFI_SMTP_USE_TLS: "false"
UNIFI_EMAIL_FROM: scanner@home.local
UNIFI_EMAIL_RECIPIENTS: you@example.com
```

## File Output

| Variable | Description | Default |
|----------|-------------|---------|
| `UNIFI_FILE_ENABLED` | Enable file output | `false` |
| `UNIFI_FILE_OUTPUT_DIR` | Directory for report files | Required when file enabled |
| `UNIFI_FILE_FORMAT` | Format: `html`, `text`, or `both` | `both` |
| `UNIFI_FILE_RETENTION_DAYS` | Days to retain report files (0 = keep forever) | `30` |

## SSH Settings (for IPS via MongoDB)

The UniFi Network API does not expose IPS/threat events. To collect blocked threat data, the scanner can SSH into UDM Pro devices and query MongoDB directly. This requires SSH key authentication (password auth is disabled on UDM Pro).

| Variable | Description | Default |
|----------|-------------|---------|
| `UNIFI_SSH_ENABLED` | Enable SSH fallback for logs/IPS | `true` |
| `UNIFI_SSH_KEY_PATH` | Path to SSH private key file | None |
| `UNIFI_SSH_KEY_PASSPHRASE` | Passphrase for encrypted key | None |
| `UNIFI_SSH_USERNAME` | SSH username | `root` |
| `UNIFI_SSH_PASSWORD` | SSH password (if not using key auth) | None |
| `UNIFI_SSH_TIMEOUT` | SSH command timeout in seconds (5-300) | `30` |

## WebSocket (UniFi 10.x+)

| Variable | Description | Default |
|----------|-------------|---------|
| `UNIFI_WEBSOCKET_ENABLED` | Enable WebSocket for real-time WiFi events | `true` |
| `UNIFI_WEBSOCKET_BUFFER_SIZE` | Max events to buffer between reports (100-100000) | `10000` |

## Logging

| Variable | Description | Default |
|----------|-------------|---------|
| `UNIFI_LOG_LEVEL` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `UNIFI_LOG_FORMAT` | Output format: `json` (production) or `text` (development) | `json` |

## Docker Secrets

Any setting can be loaded from a file using the `_FILE` suffix pattern:

```yaml
environment:
  UNIFI_PASSWORD_FILE: /run/secrets/unifi_password
  UNIFI_SMTP_PASSWORD_FILE: /run/secrets/smtp_password
secrets:
  unifi_password:
    file: ./secrets/unifi_password.txt
  smtp_password:
    file: ./secrets/smtp_password.txt
```

## YAML Configuration

Set `CONFIG_PATH` to load settings from a YAML file instead of environment variables:

```yaml
# config.yml
host: 192.168.1.1
username: admin
password: your-password
verify_ssl: false
schedule_preset: daily_8am
schedule_timezone: America/New_York
email_enabled: true
smtp_host: smtp.gmail.com
smtp_port: 587
smtp_user: you@gmail.com
smtp_password: your-app-password
email_from: you@gmail.com
email_recipients: admin@example.com
file_enabled: true
file_output_dir: /app/reports
```

```bash
docker run -v ./config.yml:/app/config.yml -e CONFIG_PATH=/app/config.yml ghcr.io/trek-e/unifi-security-report
```

> Environment variables override YAML values when both are set.
