import hashlib
import hmac
import json
import os

from fastapi.testclient import TestClient

# Set a mock secret for testing
os.environ["GITHUB_WEBHOOK_SECRET"] = "test-secret"
# Mock config path
os.environ["CONFIG_PATH"] = "config.json.example"

from main import app

client = TestClient(app)


def generate_signature(payload: str, secret: str) -> str:
    mac = hmac.new(
        secret.encode("utf-8"), msg=payload.encode("utf-8"), digestmod=hashlib.sha256
    )
    return f"sha256={mac.hexdigest()}"


def test_health():
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


def test_webhook_wrong_branch():
    payload = {"repository": {"name": "your-repo-name"}, "ref": "refs/heads/develop"}
    sig = generate_signature(json.dumps(payload, separators=(",", ":")), "test-secret")
    response = client.post(
        "/webhook", json=payload, headers={"X-Hub-Signature-256": sig}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_webhook_repo_not_in_config():
    payload = {"repository": {"name": "unknown-repo"}, "ref": "refs/heads/main"}
    sig = generate_signature(json.dumps(payload, separators=(",", ":")), "test-secret")
    response = client.post(
        "/webhook", json=payload, headers={"X-Hub-Signature-256": sig}
    )
    assert response.status_code == 200
    assert "ignored" in response.json()["status"]
