"""
Deterministic replay / state restore, required by spec section 19 for
experiment B's counterfactual state reproduction (same ALFWorld state must be
reachable twice, once per branch).

`restore_state` is the ONLY sanctioned way to get back to a specific
decision-point state. It is deliberately NOT "reset in a loop until you
happen to land on the right game" -- that approach is explicitly forbidden
by the spec because it is not guaranteed to terminate and provides no
correctness guarantee. Instead it:

  1. builds a fresh single-game ALFWorld env for the exact `game_id_or_path`
     (see `alfworld_runner.build_single_game_adapter`);
  2. resets it (ALFWorld game instances are pre-generated fixed trial
     folders, so reset() of a single-game env is deterministic -- there is
     no residual randomness left once the game selection is narrowed to one
     file);
  3. replays `action_prefix` in order;
  4. asserts the resulting observation equals `expected_observation` saved
     at collection time.

If step 4 ever fails, spec section 39 says: stop, do not proceed to
experiment B, and fix this function/its assumptions first -- a state
mismatch means Delta_t has no causal interpretation.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional, Sequence

from .alfworld_runner import ALFWorldEnvAdapter, build_single_game_adapter, extract_admissible


class StateRestoreError(RuntimeError):
    """Raised when replaying action_prefix does not reproduce expected_observation."""


@dataclasses.dataclass
class RestoredState:
    adapter: ALFWorldEnvAdapter
    observation: str
    info: Dict[str, Any]
    admissible_actions: List[str]


def restore_state(
    *,
    config: Dict[str, Any],
    split: str,
    game_id_or_path: str,
    action_prefix: Sequence[str],
    expected_observation: Optional[str] = None,
    strict: bool = True,
) -> RestoredState:
    """Rebuild the exact env state right before the decision point.

    Args:
        expected_observation: the observation saved at collection time right
            after executing the last action in `action_prefix` (i.e. the
            decision point's `observation` field). If given and `strict` is
            True, mismatches raise StateRestoreError instead of silently
            continuing -- callers doing the mandatory unit test (spec
            section 37, test 3) should always pass strict=True.
    """
    adapter = build_single_game_adapter(config, split, game_id_or_path)
    obs, info = adapter.reset()

    for i, action in enumerate(action_prefix):
        admissible = extract_admissible(info)
        if action not in admissible:
            raise StateRestoreError(
                f"Replay step {i}: action {action!r} is not admissible in the "
                f"restored env (admissible={admissible}). The action prefix "
                f"was likely recorded against a different game instance or a "
                f"different dataset version than what is currently installed."
            )
        obs, done, success, info = adapter.step(action)
        if done and i < len(action_prefix) - 1:
            raise StateRestoreError(
                f"Replay step {i}: episode ended early during replay of "
                f"action_prefix (len={len(action_prefix)}), before reaching "
                f"the decision point."
            )

    if expected_observation is not None and obs != expected_observation:
        message = (
            "State restore mismatch: replaying action_prefix did not "
            "reproduce the saved observation.\n"
            f"--- expected ---\n{expected_observation}\n"
            f"--- got ---\n{obs}\n"
            f"game_id_or_path={game_id_or_path!r} action_prefix={list(action_prefix)!r}"
        )
        if strict:
            raise StateRestoreError(message)

    adapter._last_info = info
    return RestoredState(
        adapter=adapter,
        observation=obs,
        info=info,
        admissible_actions=extract_admissible(info),
    )
