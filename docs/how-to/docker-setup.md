# How to run with Docker Compose

This guide describes how to deploy the UniFi Security Report using Docker Compose. This is the recommended method for most users.

## Prerequisites

- Docker and Docker Compose installed on your host machine.
- Access to your UniFi Controller.
- (Optional) An SMTP server for email reports.

## Step 1: Prepare Secrets

To avoid putting sensitive credentials in plain text, create a `secrets` directory and store your passwords in files.

```bash
mkdir -p secrets
echo "your-unifi-password" > secrets/unifi_password.txt
echo "your-smtp-password" > secrets/smtp_password.txt
```

## Step 2: Configure Environment

Create a `.env` file in the same directory as your `docker-compose.yml`.

```bash
cat > .env << 'ENVEOF'
UNIFI_HOST=192.168.1.1
UNIFI_USERNAME=admin
UNIFI_SCHEDULE_PRESET=daily_8am
UNIFI_SCHEDULE_TIMEZONE=America/New_York
ENVEOF
```

## Step 3: Launch the Container

Run the following command to start the service in detached mode:

```bash
docker-compose up -d
```

## Verifying the Deployment

Check the logs to ensure the service has connected to your UniFi Controller:

```bash
docker-compose logs -f
```

You should see a message similar to:
`INFO connecting host=192.168.1.1`
`INFO connected device_type=UDM api_prefix=/proxy/network`
