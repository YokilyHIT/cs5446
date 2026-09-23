"""Spec section 37, test 2: ALFWorld reset/step works normally.

Skipped when ALFWorld + its dataset aren't installed (see
scripts/setup_env_npu.sh step 8) -- this always runs on the NPU host, never
requires the LLM server, since it only exercises the environment.
"""
import pytest

from preexperiments.common.alfworld_runner import (
    ALFWorldEnvAdapter,
    extract_admissible,
    extract_won,
)
from .conftest import alfworld_available


def test_reset_then_step(config):
    if not alfworld_available():
        pytest.skip("ALFWorld + dataset not installed/downloaded on this machine.")

    adapter = ALFWorldEnvAdapter(config, split=config["splits"]["experience"])
    assert len(adapter.game_files) > 0

    obs, info = adapter.reset()
    assert isinstance(obs, str) and len(obs) > 0

    admissible = extract_admissible(info)
    assert isinstance(admissible, list) and len(admissible) > 0

    action = admissible[0]
    next_obs, done, success, next_info = adapter.step(action)
    assert isinstance(next_obs, str)
    assert isinstance(done, bool)
    assert isinstance(success, bool)
