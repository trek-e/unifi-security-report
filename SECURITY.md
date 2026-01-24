# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in UniFi Security Report, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Email the maintainers directly or use GitHub's private vulnerability reporting
3. Include as much detail as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a detailed response within 7 days.

## Security Considerations

### Credentials

- **UniFi credentials** are used to authenticate with your controller's API
- Store passwords using Docker secrets (recommended) or environment variables
- Never commit credentials to version control
- Use a dedicated local admin account with minimal required permissions

```bash
# Recommended: Use Docker secrets
echo "your-password" > secrets/unifi_password.txt
chmod 600 secrets/unifi_password.txt
```

### Network Security

- The scanner connects to your UniFi controller over HTTPS
- SSL verification is enabled by default (`UNIFI_VERIFY_SSL=true`)
- Only disable SSL verification for self-signed certificates on trusted networks
- Use `network_mode: host` only when necessary for connectivity

### Container Security

- Container runs as non-root user (`appuser`, UID 1000)
- Minimal base image (`python:3.12-slim-bookworm`)
- No unnecessary packages or tools installed
- Health check endpoint does not expose sensitive data

### Data Handling

- Log data is fetched from your controller and processed in memory
- Reports are written to the configured output directory
- No data is sent to external services
- No telemetry or analytics are collected

### SMTP Security

- Use TLS for SMTP connections (port 587 with STARTTLS or port 465 with implicit TLS)
- Store SMTP passwords using Docker secrets
- Email recipients receive reports via BCC for privacy

## Best Practices

1. **Keep updated**: Pull the latest container image regularly
   ```bash
   docker pull ghcr.io/trek-e/unifi-security-report:latest
   ```

2. **Limit access**: Restrict access to the reports directory
   ```bash
   chmod 750 reports/
   ```

3. **Review reports**: Regularly review generated security reports and act on findings

4. **Rotate credentials**: Periodically rotate UniFi and SMTP passwords

5. **Monitor logs**: Check container logs for errors or suspicious activity
   ```bash
   docker logs unifi-security-report
   ```

## Dependencies

This project uses the following key dependencies:

- `httpx` - HTTP client with TLS support
- `paramiko` - SSH client (for fallback log collection)
- `pydantic` - Data validation
- `APScheduler` - Job scheduling

Dependencies are pinned to minimum versions and regularly updated for security patches.
