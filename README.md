# Avanpost

A lightweight, secure GitHub Webhook receiver built with FastAPI and Pydantic. It automatically deploys your projects on Linux server whenever you push to a tracked branch.

## Key Features

- **Async Deployments:** Responds to GitHub immediately; deployment commands run in the background using `asyncio`.
- **Modular Architecture:** Separation between API, configuration, and deployment services.
- **Pydantic Validation:** Robust configuration parsing with automatic type checking and directory validation.
- **Secure:** Validates GitHub's HMAC-SHA256 signatures using a secret key.
- **Health Monitoring:** `/health` endpoint providing system info and monitored repository status.

---

## Table of Contents

- [Installation](#installation)
- [Reverse Proxy & SSL](#reverse-proxy--ssl)
- [GitHub Webhook Setup](#github-webhook-setup)
- [Updating Avanpost](#updating-avanpost)
- [Monitoring & Health](#monitoring--health)

## Prerequisites

Before starting the installation, ensure you have:

1. **A Subdomain:** Create an `A` record in your DNS provider pointing to your server IP.
2. **Python 3.10+:** Installed on the host (including `pip` and `venv`).
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv git -y
   ```

---

## Installation

### 1. Create a Dedicated User

```bash
sudo useradd -m -s /bin/bash avanpost
sudo usermod -aG docker avanpost
sudo mkdir -p /opt/avanpost
sudo chown avanpost:avanpost /opt/avanpost
```

### Note on SSH Keys

The `avanpost` user needs an SSH key added to GitHub to perform `git pull` operations.

```bash
sudo su - avanpost
ssh-keygen -t ed25519
cat ~/.ssh/id_ed25519.pub # Copy SSH key to GitHub
ssh -T git@github.com     # Verify connection
exit
```

### 2. Clone and Setup

```bash
sudo su - avanpost
cd /opt/avanpost
git clone https://github.com/andriydread/avanpost.git .
./setup.sh
```

### 3. Configuration

While still logged in as `avanpost`, edit the generated files:

- **`.env`**: Set your `GITHUB_WEBHOOK_SECRET` and optional `PORT` (default 8001).
- **`config.yaml`**: Map your repository names to their local paths and deployment commands.

Generate a secure `GITHUB_WEBHOOK_SECRET` with:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

```bash
nano .env
nano config.yaml
exit
```

#### `config.yaml` Example:

```yaml
log_file: "deployments.log"

repos:
  my-web-app:
    path: "/opt/my-web-app"
    branch: "main"
    timeout: 600
    commands:
      - git fetch origin main
      - git reset --hard origin/main
      - docker compose up -d --build

  analytics-api:
    path: "/home/user/projects/analytics"
    branch: "prod"
    commands:
      - ./deploy.sh
```

**Configuration Fields:**

| Field      | Description                                          | Default           |
| :--------- | :--------------------------------------------------- | :---------------- |
| `path`     | **Required.** Absolute path to the local repository. | -                 |
| `branch`   | The branch to track for deployments.                 | `main`            |
| `timeout`  | Max seconds to wait for each command.                | `900`             |
| `commands` | List of shell commands to run for deployment.        | -                 |
| `log_file` | Name of the deployment log file.                     | `deployments.log` |

---

### 4. Enable the Service

Back as your **sudo** user, install and start the generated systemd service:

```bash
sudo cp /opt/avanpost/avanpost.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now avanpost
```

---

## Reverse Proxy & SSL

For production, avanpost should be run behind a reverse proxy like Nginx and enabled HTTPS.

### 1. Install Nginx and Certbot

```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx -y
```

### 2. Configure Nginx

Create a new site configuration:

```bash
sudo nano /etc/nginx/sites-available/avanpost
```

Paste the following configuration (replace `subdomain.your-domain.com` with your actual domain):

```nginx
server {
    listen 80;
    server_name subdomain.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the configuration and restart Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/avanpost /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 3. Obtain SSL Certificate

Run Certbot to automatically configure HTTPS:

```bash
sudo certbot --nginx -d subdomain.your-domain.com
```

Follow the interactive prompts to finish the setup. Certbot will automatically update your Nginx configuration to support SSL and redirect HTTP to HTTPS.

---

## GitHub Webhook Setup

1. Go to your GitHub Repository -> **Settings** -> **Webhooks** -> **Add webhook**.
2. **Payload URL**: `https://subdomain.your-domain.com/webhook`
3. **Content type**: `application/json`
4. **Secret**: The secret from your `.env` file.
5. **Which events**: `Just the push event`.

---

## Updating Avanpost

To update Avanpost to the latest version on your server:

```bash
# 1. Switch to the app user and pull changes
sudo su - avanpost
cd /opt/avanpost
git pull origin main
./setup.sh
exit

# 2. Back as root/sudo user, restart the service
sudo systemctl restart avanpost
```

---

## Monitoring & Health

### Health Check

Visit `https://subdomain.your-domain.com/health` to see the engine status.

| Field | Description | Type |
| :--- | :--- | :--- |
| `status` | Current application health. | `str` |
| `config_loaded` | Whether the configuration was parsed successfully. | `bool` |
| `repos_monitored` | List of repositories currently being tracked. | `list` |
| `environment` | Versions of Git, Docker, and Docker Compose installed on the host. | `dict` |

### Logs

Deployment progress and errors are stored in the log file defined in your config (default `deployments.log`).

```bash
tail -f /opt/avanpost/deployments.log
```
