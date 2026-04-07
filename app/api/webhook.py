import hmac
import hashlib
import os
import logging
import json
from fastapi import APIRouter, Request, Header, HTTPException, BackgroundTasks
from app.core.config import config, load_config
from app.services.deployer import run_deploy_commands

router = APIRouter()

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

@router.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None),
):
    body = await request.body()

    if not verify_github_signature(body, x_hub_signature_256):
        logging.warning("Invalid signature received")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Reload config to get latest settings
    current_config = load_config(exit_on_error=False) or config

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    repo_name = data.get("repository", {}).get("name")
    branch_ref = data.get("ref", "")

    # current_config.repos is now a Dict[str, RepoConfig] object
    repo_config = current_config.repos.get(repo_name)
    if not repo_config:
        logging.warning(f"No config for: {repo_name}")
        return {"status": "ignored", "reason": f"Repo '{repo_name}' not in config"}

    target_branch = repo_config.branch
    if branch_ref != f"refs/heads/{target_branch}":
        return {"status": "ignored", "reason": f"Push to {branch_ref} ignored"}

    deploy_path = repo_config.path
    if not deploy_path or not os.path.exists(deploy_path):
        logging.error(f"Path '{deploy_path}' missing")
        return {"status": "error", "reason": "Path not found"}

    # Start deployment in background
    background_tasks.add_task(run_deploy_commands, repo_name, repo_config)

    return {"status": "accepted", "message": f"Deployment for {repo_name} started."}
