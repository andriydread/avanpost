import os
import sys
from typing import Dict, List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

load_dotenv()

# One place for hardcoded fallback defaults
DEFAULT_BRANCH = "main"
DEFAULT_TIMEOUT = 900
DEFAULT_LOG_FILE = "deployments.log"

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")


class RepoConfig(BaseModel):
    """Blueprint for ONE repository"""

    path: str
    branch: str = DEFAULT_BRANCH
    timeout: int = DEFAULT_TIMEOUT
    deploy_commands: Optional[List[str]] = Field(None, alias="commands")

    @model_validator(mode="after")
    def validate_path(self) -> "RepoConfig":
        self.path = os.path.abspath(self.path)
        if not os.path.exists(self.path):
            raise ValueError(f"VPS Folder Missing: {self.path}")
        return self


class AppConfig(BaseModel):
    """Blueprint for the YAML file"""

    log_file: str = DEFAULT_LOG_FILE
    repos: Dict[str, RepoConfig]


def load_config(exit_on_error=True) -> Optional[AppConfig]:
    if not os.path.exists(CONFIG_PATH):
        if exit_on_error:
            print(f"File {CONFIG_PATH} not found.")
            sys.exit(1)
        return None

    try:
        with open(CONFIG_PATH, "r") as f:
            raw_dictionary = yaml.safe_load(f) or {}
            # This triggers the Pydantic building process
            return AppConfig(**raw_dictionary)

    except Exception as e:
        if exit_on_error:
            print(f"YAML/Config Error: {e}")
            sys.exit(1)
        return None


# Initial load
config = load_config(exit_on_error=True)
