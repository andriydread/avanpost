import hashlib
import hmac
import json
import os
import yaml
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Set environment variables for testing
os.environ["GITHUB_WEBHOOK_SECRET"] = "test-secret"
os.environ["CONFIG_PATH"] = "test_config.yaml"

# Create a dummy config file for the module to load during import
test_config = {
    "branch": "main",
    "timeout": 60,
    "auto_cleanup": False,
    "repos": {
        "test-repo": {
            "path": os.getcwd(),
            "branch": "main"
        }
    }
}
with open("test_config.yaml", "w") as f:
    yaml.dump(test_config, f)

from main import app, run_deploy_commands, load_config

client = TestClient(app)
...


def generate_signature(payload: str, secret: str) -> str:
    mac = hmac.new(
        secret.encode("utf-8"), msg=payload.encode("utf-8"), digestmod=hashlib.sha256
    )
    return f"sha256={mac.hexdigest()}"


def test_health():
    with patch("main.load_config") as mock_load:
        mock_load.return_value = {"repos": {"test": {"path": "/tmp"}}}
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


def test_webhook_invalid_signature():
    payload = {"repository": {"name": "test-repo"}}
    response = client.post(
        "/webhook", json=payload, headers={"X-Hub-Signature-256": "sha256=invalid"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid signature"


def test_webhook_no_signature():
    payload = {"repository": {"name": "test-repo"}}
    response = client.post("/webhook", json=payload)
    assert response.status_code == 403


@patch("main.load_config")
@patch("os.path.exists")
def test_webhook_success_triggers_background_task(mock_exists, mock_load):
    mock_exists.return_value = True
    mock_load.return_value = {
        "repos": {
            "your-repo-name": {
                "path": "/opt/your-app",
                "branch": "main"
            }
        }
    }
    
    payload = {
        "repository": {"name": "your-repo-name"},
        "ref": "refs/heads/main"
    }
    sig = generate_signature(json.dumps(payload, separators=(",", ":")), "test-secret")
    
    with patch("main.BackgroundTasks.add_task") as mock_add_task:
        response = client.post(
            "/webhook", 
            json=payload, 
            headers={"X-Hub-Signature-256": sig}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
        mock_add_task.assert_called_once()


@patch("subprocess.run")
def test_run_deploy_commands_default(mock_run):
    # Mock successful git pull and docker compose
    mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")
    
    repo_config = {
        "path": "/tmp/test",
        "branch": "main",
        "timeout": 60,
        "auto_cleanup": False
    }
    
    run_deploy_commands("test-repo", repo_config)
    
    # Should call git pull, docker compose up, and docker compose ps
    assert mock_run.call_count >= 2
    args, kwargs = mock_run.call_args_list[0]
    assert "git" in args[0]


@patch("subprocess.run")
def test_run_deploy_commands_custom(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")
    
    repo_config = {
        "path": "/tmp/test",
        "branch": "main",
        "timeout": 60,
        "commands": ["echo hello", "ls -la"]
    }
    
    run_deploy_commands("test-repo", repo_config)
    
    # Should call exactly 2 custom commands
    assert mock_run.call_count == 2
    assert mock_run.call_args_list[0][0][0] == "echo hello"
    assert mock_run.call_args_list[1][0][0] == "ls -la"


@patch("subprocess.run")
def test_run_deploy_commands_cleanup(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="success", stderr="")
    
    repo_config = {
        "path": "/tmp/test",
        "branch": "main",
        "timeout": 60,
        "auto_cleanup": True
    }
    
    run_deploy_commands("test-repo", repo_config)
    
    # Last call should be prune
    last_call_args = mock_run.call_args_list[-1][0][0]
    assert "prune" in last_call_args or "prune" in str(last_call_args)
