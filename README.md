# Lazy-Watcher (Mini CI/CD)

A lightweight Python/FastAPI webhook receiver to automatically pull code and restart Docker containers when code is pushed to the `main` branch.

## Setup on VPS

1. **Clone the repository:**

   ```bash
   git clone url /opt/lazy-watcher
   cd /opt/lazy-watcher
   ```

2. **Setup Python Environment:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**

   ```bash
   cp .env.example .env
   nano .env
   ```

   _Add your GitHub Secret and configure the JSON `REPO_MAPPING`._

4. **Setup Systemd Service:**
   ```bash
   sudo cp lazy-watcher.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable lazy-watcher
   sudo systemctl start lazy-watcher
   ```

## Nginx Configuration (New Subdomain)

1. **Create a new Nginx config file:**

   ```bash
   sudo nano /etc/nginx/sites-available/lazy-watcher
   ```

2. **Paste this configuration (Replace `your-domain.dev` with actual domain):**

   ```nginx
   server {
       listen 80;
       server_name lazy-deploy."your-domain.dev";

       location / {
           proxy_pass http://127.0.0.1:8001;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

3. **Enable the site and restart Nginx:**

   ```bash
   sudo ln -s /etc/nginx/sites-available/lazy-watcher /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

4. **(Optional) Add SSL with Certbot:**
   ```bash
   sudo certbot --nginx -d deploy.domain.dev
   ```

## GitHub Configuration

1. Go to your Repository -> Settings -> Webhooks -> **Add webhook**.
2. **Payload URL**: `https://lazy-deploy."your-domain.dev"/webhook`
3. **Content type**: `application/json`
4. **Secret**: (Paste the `GITHUB_WEBHOOK_SECRET` from `.env` file)
5. **Which events**: Select "Just the `push` event."
