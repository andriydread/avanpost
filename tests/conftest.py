import os
import yaml
import pytest

@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    # Set environment variables for testing
    os.environ["GITHUB_WEBHOOK_SECRET"] = "test-secret"
    os.environ["CONFIG_PATH"] = "test_config.yaml"

    # Create a dummy config file for the module to load during import
    test_config = {
        "branch": "main",
        "timeout": 60,
        "auto_cleanup": False,
        "repos": {"test-repo": {"path": os.getcwd(), "branch": "main"}},
    }
    with open("test_config.yaml", "w") as f:
        yaml.dump(test_config, f)

@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    # Cleanup dummy config file
    if os.path.exists("test_config.yaml"):
        os.remove("test_config.yaml")
