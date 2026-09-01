import os
from pathlib import Path

import pytest

from preexperiments.common.logging_utils import load_yaml_config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "preexperiments" / "configs" / "preexperiment.yaml"


@pytest.fixture(scope="session")
def config():
    return load_yaml_config(CONFIG_PATH)


@pytest.fixture(scope="session")
def results_dir(config):
    return PROJECT_ROOT / config["paths"]["results_dir"]


def alfworld_available() -> bool:
    try:
        import alfworld.agents.environment  # noqa: F401
    except ImportError:
        return False
    data_root = os.environ.get("ALFWORLD_DATA", os.path.expanduser("~/.cache/alfworld"))
    return Path(data_root).exists()


def vllm_server_available(config) -> bool:
    try:
        from preexperiments.common.llm_client import load_client_from_config

        client = load_client_from_config(config)
        return client.health_check()
    except Exception:
        return False
