# Avanpost

A lightweight, secure GitHub Webhook receiver built with FastAPI and Pydantic. It automatically deploys your projects on Linux server whenever you push to a tracked branch.

### Key Features

- **Async Deployments:** Responds to GitHub immediately; deployment commands run in the background using `asyncio`.
- **Modular Architecture:** Clean separation between API, configuration, and deployment services.
- **Pydantic Validation:** Robust configuration parsing with automatic type checking and directory validation.
- **Secure:** Validates GitHub's HMAC-SHA256 signatures using a secret key.
- **Health Monitoring:** Detailed `/health` endpoint providing system info and monitored repository status.

---

## 📋 Prerequisites

Before starting the installation, ensure you have:

1. **A Subdomain:** Create an `A` record in your DNS provider pointing to your server IP.
2. **Python 3.10+:** Installed on the host.

---

## 🛠 Installation

### 1. Create a Dedicated User

```bash
sudo useradd -m -s /bin/bash avanpost
sudo usermod -aG docker avanpost
sudo mkdir -p /opt/avanpost
sudo chown avanpost:avanpost /opt/avanpost
```

### 🔑 Note on SSH Keys

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

Back as your **sudo** user, install and start the systemd service:

```bash
sudo cp /opt/avanpost/avanpost.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now avanpost
```

---

## 🔄 Updating Avanpost

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

## 🔍 Monitoring & Health

### Health Check

Visit `https://subdomain.your-domain.com/health` to see the engine status:

- **`status`**: Current application health.
- **`config_loaded`**: Whether the configuration was parsed successfully.
- **`repos_monitored`**: List of repositories currently being tracked.
- **`environment`**: Versions of Git, Docker, and Docker Compose installed on the host.

### Logs

Deployment progress and errors are stored in the log file defined in your config (default `deployments.log`).

```bash
tail -f /opt/avanpost/deployments.log
```

---

## 🔗 GitHub Webhook Setup

1. Go to your GitHub Repository -> **Settings** -> **Webhooks** -> **Add webhook**.
2. **Payload URL**: `https://subdomain.your-domain.com/webhook`
3. **Content type**: `application/json`
4. **Secret**: The secret from your `.env` file.
5. **Which events**: `Just the push event`.
