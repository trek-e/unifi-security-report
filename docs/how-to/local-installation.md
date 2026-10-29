# How to install locally

This guide describes how to install and run the UniFi Security Report directly on your host machine using `pip`.

## Prerequisites

- Python 3.10 or higher.
- `pip` installed.

## Step 1: Clone the Repository

```bash
git clone https://github.com/trek-e/unifi-security-report.git
cd unifi-security-report
```

## Step 2: Install in Editable Mode

It is recommended to install the package in editable mode within a virtual environment.

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install the package
pip install -e .
```

## Step 3: Run a One-Shot Report

You can run the scanner immediately by providing configuration via environment variables.

```bash
UNIFI_HOST=192.168.1.1 \
UNIFI_USERNAME=admin \
UNIFI_PASSWORD=your-password \
unifi-scanner --help
```

To run a full analysis and generate a report:

```bash
UNIFI_HOST=192.168.1.1 \
UNIFI_USERNAME=admin \
UNIFI_PASSWORD=your-password \
UNIFI_FILE_ENABLED=true \
UNIFI_FILE_OUTPUT_DIR=./reports \
unifi-scanner
```
