#!/bin/bash

# Avanpost Setup Script
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Avanpost Setup...${NC}"

# 1. Create Virtual Environment
if [ ! -d ".venv" ]; then
    echo -e "Creating virtual environment..."
    python3 -m venv .venv
fi

# 2. Install Dependencies
echo -e "Installing dependencies..."
.venv/bin/pip install -r requirements.txt

# 3. Create .env and config.json from examples if they don't exist
if [ ! -f ".env" ]; then
    echo -e "Creating .env from example..."
    cp .env.example .env
    echo -e "${GREEN}ACTION REQUIRED:${NC} Please edit .env and set your GITHUB_WEBHOOK_SECRET."
fi

if [ ! -f "config.yaml" ]; then
    echo -e "Creating config.yaml from example..."
    cp config.yaml.example config.yaml
    echo -e "${GREEN}ACTION REQUIRED:${NC} Please edit config.yaml to map your repositories."
fi

# 4. Check Docker Permissions
if groups $CURRENT_USER | grep &>/dev/null "\bdocker\b"; then
    echo -e "${GREEN}User $CURRENT_USER is in the docker group.${NC}"
else
    echo -e "${GREEN}WARNING:${NC} User $CURRENT_USER is NOT in the docker group."
    echo -e "Deployments will fail unless you run: ${BLUE}sudo usermod -aG docker $CURRENT_USER${NC}"
    echo -e "Then log out and back in."
fi

# 5. Generate Systemd Service
INSTALL_DIR=$(pwd)
CURRENT_USER=$(whoami)

echo -e "Generating avanpost.service..."
cat <<EOF > avanpost.service
[Unit]
Description=Avanpost GitHub Webhook Receiver
After=network.target

[Service]
User=$CURRENT_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/python main.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}Setup complete!${NC}"
echo -e ""
echo -e "${BLUE}To install the service, run:${NC}"
echo -e "  sudo cp avanpost.service /etc/systemd/system/"
echo -e "  sudo systemctl daemon-reload"
echo -e "  sudo systemctl enable avanpost"
echo -e "  sudo systemctl start avanpost"
echo -e ""
echo -e "${BLUE}Note:${NC} Since the service runs as ${GREEN}$CURRENT_USER${NC}, ensure this user has permissions to run 'docker compose' (usually by being in the 'docker' group)."
