import subprocess
import sys
import platform
from fastapi import APIRouter
from app.core.config import config, load_config

router = APIRouter()

def get_version(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else "Not installed"
    except Exception:
        return "Not installed"

@router.get("/health")
async def health():
    current_config = load_config(exit_on_error=False) or config
    
    return {
        "status": "healthy",
        "config_loaded": bool(current_config.repos),
        "repos_monitored": list(current_config.repos.keys()),
        "environment": {
            "python_version": sys.version,
            "os": platform.system(),
            "git_version": get_version(["git", "--version"]),
            "docker_version": get_version(["docker", "--version"]),
            "docker_compose_version": get_version(["docker", "compose", "version"]),
        }
    }
