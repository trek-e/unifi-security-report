# UniFi Scanner

Translate cryptic UniFi logs into understandable findings with actionable remediation.

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Run with config file
CONFIG_PATH=/etc/unifi-scanner/config.yaml unifi-scanner

# Test configuration validity
unifi-scanner --test

# Run with environment variables
UNIFI_HOST=192.168.1.1 UNIFI_USERNAME=admin UNIFI_PASSWORD=secret unifi-scanner
```

## Configuration

See `unifi-scanner.example.yaml` for all configuration options.
