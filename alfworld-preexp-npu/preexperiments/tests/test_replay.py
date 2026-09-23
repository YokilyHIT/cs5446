"""Spec section 37, test 3: same task + action prefix restores to the same
observation. This is the single most important correctness gate for
experiment B (spec section 39: if this fails, do not proceed with
experiment B at all).
"""
import pytest

from preexperiments.common.alfworld_runner import ALFWorldEnvAdapter, extract_admissible
from preexperiments.common.replay_state import restore_state, StateRestoreError
from .conftest import alfworld_available


def test_restore_state_reproduces_observation(config):
    if not alfworld_available():
        pytest.skip("ALFWorld + dataset not installed/downloaded on this machine.")

    split = config["splits"]["evaluation"]
    adapter = ALFWorldEnvAdapter(config, split=split)
    gamefile = sorted(adapter.game_files)[0]

    from preexperiments.common.alfworld_runner import build_single_game_adapter

    fresh = build_single_game_adapter(config, split, gamefile)
    obs0, info0 = fresh.reset()
    admissible = extract_admissible(info0)
    action_prefix = [admissible[0]]
    obs1, done, success, info1 = fresh.step(action_prefix[0])

    restored = restore_state(
        config=config,
        split=split,
        game_id_or_path=gamefile,
        action_prefix=action_prefix,
        expected_observation=obs1,
        strict=True,
    )
    assert restored.observation == obs1


def test_restore_state_raises_on_mismatch(config):
    if not alfworld_available():
        pytest.skip("ALFWorld + dataset not installed/downloaded on this machine.")

    split = config["splits"]["evaluation"]
    from preexperiments.common.alfworld_runner import ALFWorldEnvAdapter, build_single_game_adapter

    adapter = ALFWorldEnvAdapter(config, split=split)
    gamefile = sorted(adapter.game_files)[0]
    fresh = build_single_game_adapter(config, split, gamefile)
    _, info0 = fresh.reset()
    admissible = extract_admissible(info0)

    with pytest.raises(StateRestoreError):
        restore_state(
            config=config,
            split=split,
            game_id_or_path=gamefile,
            action_prefix=[admissible[0]],
            expected_observation="this text will never match a real observation",
            strict=True,
        )
