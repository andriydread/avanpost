import hashlib
import hmac
import json
import yaml
import logging
import os
import subprocess
import sys
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

# Load the env variables
load_dotenv()

# Load config
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"CRITICAL: Config file {CONFIG_PATH} not found.")
        sys.exit(1)
    try:
        with open(CONFIG_PATH, "r") as f:
            data = yaml.safe_load(f)

            if not data or "repos" not in data or not isinstance(data["repos"], dict):
                print("CRITICAL: 'repos' dictionary missing in config file.")
                sys.exit(1)
            # Validate each repository configuration
            for repo_name, repo_conf in data["repos"].items():
                if "path" not in repo_conf:
                    print(f"CRITICAL: 'path' missing for repo '{repo_name}'")
                    sys.exit(1)

                # Ensure path is absolute and exists
                abs_path = os.path.abspath(repo_conf["path"])
                if not os.path.isabs(repo_conf["path"]):
                    print(
                        f"WARNING: Path for '{repo_name}' is not absolute. Normalized to: {abs_path}"
                    )

                if not os.path.exists(abs_path):
                    print(
                        f"CRITICAL: Path '{abs_path}' for repo '{repo_name}' does not exist."
                    )
                    sys.exit(1)

                # Update with normalized absolute path
                repo_conf["path"] = abs_path
                # Default branch to main
                repo_conf.setdefault("branch", "main")
                # Default timeout to 900 seconds (15 mins)
                repo_conf.setdefault("timeout", 900)

            return data
    except Exception as e:
        print(f"CRITICAL: Error loading config: {e}")
        sys.exit(1)


config = load_config()

# Setup logging with Rotation (5 files of 1MB each)
log_handler = RotatingFileHandler(
    config.get("log_file", "deployments.log"), maxBytes=1024 * 1024, backupCount=10
)
logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

app = FastAPI()


def verify_github_signature(payload_body: bytes, signature_header: str):
    """Verify that the payload was sent from GitHub using the HMAC-SHA256 signature"""
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")

    if not secret:
        logging.error("GITHUB_WEBHOOK_SECRET is not set in environment")
        return False

    if not signature_header:
        logging.warning("X-Hub-Signature-256 header is missing")
        return False

    if not signature_header.startswith("sha256="):
        logging.warning(f"Invalid signature format: {signature_header[:10]}...")
        return False

    try:
        actual_sig = signature_header.split("sha256=")[1]
        mac = hmac.new(
            secret.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256
        )
        expected_sig = mac.hexdigest()

        return hmac.compare_digest(expected_sig, actual_sig)
    except Exception as e:
        logging.error(f"Error during signature verification: {e}")
        return False


def run_deploy_commands(repo_name, repo_config):
    """Background task to run git and docker commands"""
    path = repo_config["path"]
    branch = repo_config["branch"]
    timeout = repo_config["timeout"]

    try:
        logging.info(
            f"--- Starting deployment for {repo_name} ({branch}) at {path} ---"
        )

        # 1-Git Pull
        logging.info(f"[{repo_name}] Running git pull")
        result_pull = subprocess.run(
            ["git", "pull", "origin", branch],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result_pull.stdout:
            logging.info(f"[{repo_name}] Git pull output: {result_pull.stdout.strip()}")

        if result_pull.returncode != 0:
            logging.error(f"[{repo_name}] Git pull failed: {result_pull.stderr}")
            return

        # 2-Docker Compose
        logging.info(f"[{repo_name}] Running docker compose up -d --build")
        result_docker = subprocess.run(
            ["docker", "compose", "up", "-d", "--build"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result_docker.stdout:
            logging.info(
                f"[{repo_name}] Docker compose output: {result_docker.stdout.strip()}"
            )

        if result_docker.returncode != 0:
            logging.error(
                f"[{repo_name}] Docker compose failed: {result_docker.stderr}"
            )
            return

        # 3-Health Check (Verify containers are running)
        logging.info(f"[{repo_name}] Verifying container health")
        result_ps = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result_ps.returncode == 0:
            try:
                # Some versions return multiple JSON objects, one per line
                containers = []
                for line in result_ps.stdout.strip().split("\n"):
                    if line:
                        containers.append(json.loads(line))

                # Check status of each container
                # Note: Field names can vary between docker compose versions (State vs Status)
                unhealthy = []
                for container in containers:
                    state = (
                        container.get("State") or container.get("Status", "").lower()
                    )
                    name = container.get("Name") or container.get("Service", "unknown")

                    if "running" not in state and "up" not in state:
                        unhealthy.append(f"{name} ({state})")

                if unhealthy:
                    logging.warning(
                        f"[{repo_name}] Some containers are not running: {', '.join(unhealthy)}"
                    )
                else:
                    logging.info(
                        f"[{repo_name}] All containers are healthy and running."
                    )
            except Exception as e:
                logging.warning(
                    f"[{repo_name}] Could not parse health check output: {e}"
                )
        else:
            logging.warning(
                f"[{repo_name}] Health check command failed: {result_ps.stderr}"
            )

        logging.info(f"--- [{repo_name}] Deployment finished successfully ---")

    except Exception as e:
        logging.error(f"[{repo_name}] Unexpected error during deployment: {str(e)}")


@app.get("/health")
async def health():
    return {"status": "healthy", "config_loaded": bool(config.get("repos"))}


@app.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None),
):
    body = await request.body()

    if not verify_github_signature(body, x_hub_signature_256):
        logging.warning("Invalid signature received")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    repo_name = data.get("repository", {}).get("name")
    branch_ref = data.get("ref", "")

    repo_config = config.get("repos", {}).get(repo_name)
    if not repo_config:
        logging.warning(f"No config for: {repo_name}")
        return {"status": "ignored", "reason": f"Repo '{repo_name}' not in config"}

    target_branch = repo_config.get("branch", "main")
    if branch_ref != f"refs/heads/{target_branch}":
        return {"status": "ignored", "reason": f"Push to {branch_ref} ignored"}

    deploy_path = repo_config.get("path")
    if not deploy_path or not os.path.exists(deploy_path):
        logging.error(f"Path '{deploy_path}' missing")
        return {"status": "error", "reason": "Path not found"}

    # Start deployment in background
    background_tasks.add_task(run_deploy_commands, repo_name, repo_config)

    return {"status": "accepted", "message": f"Deployment for {repo_name} started."}


if __name__ == "__main__":
    import uvicorn

    # Get port from .env or default to 8001
    port = int(os.getenv("PORT", "8001"))
    # Bind to 127.0.0.1 for better security behind a reverse proxy
    uvicorn.run(app, host="127.0.0.1", port=port)
