# How to configure SSH for IPS data collection

If you are using a UDM Pro or similar device, the UniFi Network API does not expose IPS/threat events. To collect this data, the scanner must SSH into the device and query MongoDB directly.

This guide describes how to set up SSH key-based authentication.

## Step 1: Generate an SSH Key Pair

If you don't already have an SSH key pair, generate one on your host machine (or the machine running the scanner).

```bash
ssh-keygen -t ed25519 -f ~/.ssh/unifi_key
```

## Step 2: Copy the Public Key to your UniFi Device

You must add the contents of your **public** key (`.pub`) to the `authorized_keys` file on your UniFi device.

```bash
# Replace 192.168.1.1 with your actual UniFi IP
cat ~/.ssh/unifi_key.pub | ssh root@192.168.1.1 "cat >> ~/.ssh/authorized_keys"
```

## Step 3: Configure the Scanner

Update your environment variables or YAML configuration to enable SSH and point to your private key.

### Using Environment Variables

```bash
export UNIFI_SSH_ENABLED="true"
export UNIFI_SSH_KEY_PATH="~/.ssh/unifi_key"
```

### Using YAML Configuration

```yaml
unifi_ssh_enabled: "true"
unifi_ssh_key_path: "/path/to/your/unifi_key"
```

## Verification

Run the scanner with debug logging enabled to verify the SSH connection:

```bash
UNIFI_LOG_LEVEL=DEBUG UNIFI_SSH_ENABLED=true unifi-scanner
```

Look for logs indicating successful SSH connection and MongoDB queries.
