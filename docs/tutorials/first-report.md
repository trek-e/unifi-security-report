# Your First Security Report

This tutorial walks you through the process of setting up the UniFi Security Report and generating your very first report from scratch.

## Goal

By the end of this tutorial, you will have a running instance of the scanner and a human-readable HTML report in your inbox or local directory.

## Prerequisites

- A UniFi Controller (UDM, UCG, Cloud Key, or self-hosted).
- Admin credentials for the controller.
- Docker installed on your machine.

## Step 1: Prepare the Environment

First, create a directory for your project and set up the necessary secrets.

```bash
mkdir unifi-report-project
cd unifi-report-project
mkdir secrets
```

Create a file for your UniFi password:

```bash
echo "your-admin-password" > secrets/unifi_password.txt
```

## Step 2: Create the Configuration

Create a `.env` file to tell the scanner how to connect to your network.

```bash
cat > .env << 'ENVEOF'
UNIFI_HOST=192.168.1.1
UNIFI_USERNAME=admin
UNIFI_PASSWORD_FILE=/run/secrets/unifi_password
UNIFI_VERIFY_SSL=false
UNIFI_FILE_ENABLED=true
UNIFI_FILE_OUTPUT_DIR=./reports
ENVEOF
```

*Note: If running locally (not in Docker), use `UNIFI_PASSWORD=your-password` instead of `UNIFI_PASSWORD_FILE`.*

## Step 3: Launch the Scanner

If you are using Docker Compose, create a `docker-compose.yml` file:

```yaml
services:
  unifi-scanner:
    image: ghcr.io/trek-e/unifi-security-report:latest
    env_file: .env
    volumes:
      - ./secrets:/run/secrets
      - ./reports:/app/reports
```

Then, start the container:

```bash
docker-compose up -d
```

## Step 4: View Your Report

Wait a few minutes for the first scan to complete. Once finished, check the `reports/` directory:

```bash
ls ./reports
```

Open the generated `.html` file in your web browser to see your security summary.

## Troubleshooting

- **Connection Errors**: Ensure the `UNIFI_HOST` is reachable from your Docker container.
- **Empty Reports**: Check if your user has sufficient permissions in the UniFi Controller.
- **SSL Errors**: If you are using a self-signed certificate, ensure `UNIFI_VERIFY_SSL` is set to `false`.

## Summary

Congratulations! You have successfully deployed the UniFi Security Report. You can now leave it running to receive scheduled reports automatically.
