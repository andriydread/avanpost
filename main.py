import os
import json
import hmac
import hashlib
import logging
import subprocess
from fastapi import FastAPI, Request, Header, HTTPException
from dotenv import load_dotenv

# Load the env variables
load_dotenv()

# Setup logging to file
logging.basicConfig(
    filename="deployments.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = FastAPI()

# Strip qoutes just in case
mapping_str = os.getenv("REPO_MAPPING", "{}").strip("'").strip('"')
repo_mapping = json.loads(mapping_str)

def verify_github_signature(payload_body, signature_header):
    """Verify that the payload was sent from GitHub using the HMAC-SHA256 signature"""
    
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    
    if not secret or not signature_header:
        print("Missing secret or signature header")
        return False
        
    if not signature_header.startswith("sha256="):
        return False
        
    actual_sig = signature_header.split("sha256=")[1]
    
    mac = hmac.new(secret.encode(), msg=payload_body, digestmod=hashlib.sha256)
    expected_sig = mac.hexdigest()

    return hmac.compare_digest(expected_sig, actual_sig)

def run_deploy_commands(path):
    """Runs the actual git and docker commands """
    
    try:
        logging.info(f"Starting deployment at {path}")
        
        print(f"Running git pull in {path}")
        subprocess.run(["git", "pull", "origin", "main"], cwd=path, check=True)
        
        print(f"Running 'docker compose' in {path}")
        subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=path, check=True)
        
        logging.info("Deployment finished successfully")
        return True
    
    except Exception as e:
        logging.error(f"Deployment failed! Error: {str(e)}")
        print(f"Error during deploy: {e}")
        return False


@app.post("/webhook")
async def webhook(request: Request, x_hub_signature_256: str = Header(None)):
    body = await request.body()
    
    if not verify_github_signature(body, x_hub_signature_256):
        logging.warning("Bad signature received")
        raise HTTPException(status_code=403, detail="Forbidden - invalid signature")

    data = json.loads(body)
    
    repo_name = data.get("repository", {}).get("name")
    branch = data.get("ref", "")

    if branch != "refs/heads/main":
        return {"status": "ignored", "reason": "not main branch"}

    deploy_path = repo_mapping.get(repo_name)
    
    if not deploy_path:
        logging.warning(f"No path found for repo: {repo_name}")
        return {"status": "error", "reason": "repo not mapped"}
    
    if not os.path.exists(deploy_path):
        logging.error(f"The path {deploy_path} does not exist on this server!")
    
    success = run_deploy_commands(deploy_path)
    
    if success:
        return {"status": "success", "message": f"Deployed {repo_name}"}
    else:
        return {"status": "failed", "message": "Check logs for errors"}
if __name__ == "__main__":
    import uvicorn
    port_env = os.getenv("PORT", "8001")
    uvicorn.run(app, host="0.0.0.0", port=int(port_env))

