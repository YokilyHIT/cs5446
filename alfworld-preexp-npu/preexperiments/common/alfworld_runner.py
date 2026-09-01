"""
Shared ALFWorld <-> LLM plumbing used by both experiment A (failure_selection)
and experiment B (world_model_utility).

Design notes / known-API risk (read before touching this file):

  This module targets ALFWorld's TextWorld-only environment class,
  `alfworld.agents.environment.AlfredTWEnv` (config["env"]["type"] must be
  "AlfredTWEnv" -- NOT AlfredThorEnv/AlfredHybrid, since the spec's pre-
  experiments are pure-text ReAct agents). That class is what every public
  ALFWorld text-agent baseline (ReAct, Reflexion, ExpeL, AdaMEM's own
  examples/prompt_agent/gpt4o_alfworld.py) is built on, and it exposes two
  attributes this module leans on:

    - `env_wrapper.game_files`: list[str] of concrete game file paths for
      the requested split (train / eval_in_distribution / ...).
    - `env_wrapper.init_env(batch_size)`: builds the actual batched TextWorld
      gym env (wrapped with ALFWorld's Inform7/AlfredDemangler feedback
      wrappers) from whatever `game_files` currently holds.

  `restore_state()` below exploits this: to replay a *specific* game
  deterministically (spec section 19), it builds a normal AlfredTWEnv for
  the split, then narrows `game_files` down to exactly the one gamefile
  before calling `init_env(batch_size=1)`. This reuses ALFWorld's own
  wrapper stack (so observation text formatting matches exactly) instead of
  reimplementing it, and avoids the explicitly-forbidden "reset in a loop
  until you happen to land on the right game" approach.

  This does assume `game_files` and `init_env` keep their current names in
  whatever ALFWorld version pip installs. **The first thing to do on the
  actual NPU host (spec section 38, step 1) is run
  `scripts/inspect_alfworld_api.py`**, which prints the live attribute/key
  names for the installed version so this file can be patched before any
  real experiment runs if something has drifted. Everywhere below that reads
  an `info` dict uses `_first_present()` to try several historically-used
  key spellings for exactly this reason.
"""
from __future__ import annotations

import copy
import dataclasses
import difflib
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import prompts
from .llm_client import LLMClient
from .logging_utils import build_step_log


_ALFWORLD_BASE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "alfworld_base_config.yaml"
_alfworld_config_cache: Optional[Dict[str, Any]] = None


def _load_alfworld_config() -> Dict[str, Any]:
    """Loads ALFWorld's OWN config schema (env/dataset/logic/...), which is a
    different shape from this project's preexperiment.yaml pipeline config.
    `ALFWorldEnvAdapter` and `build_single_game_adapter` take the pipeline
    config as their `config` argument (for a single consistent interface
    across all preexperiment scripts) but translate to this ALFWorld-native
    config internally before ever touching `AlfredTWEnv`.
    """
    global _alfworld_config_cache
    if _alfworld_config_cache is not None:
        return _alfworld_config_cache

    import yaml

    data_root = os.environ.get("ALFWORLD_DATA", os.path.expanduser("~/.cache/alfworld"))
    with open(_ALFWORLD_BASE_CONFIG_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read().replace("{ALFWORLD_DATA}", data_root)
    _alfworld_config_cache = yaml.safe_load(raw_text)
    return _alfworld_config_cache


# ---------------------------------------------------------------------------
# Info-dict key compatibility helpers
# ---------------------------------------------------------------------------

_GAMEFILE_KEYS = ["extra.gamefile", "extra.game_file", "gamefile", "game_file"]
_ADMISSIBLE_KEYS = ["admissible_commands", "admissible_actions"]
_WON_KEYS = ["won"]


def _first_present(info: Dict[str, Any], candidates: List[str]) -> Any:
    for key in candidates:
        if key in info:
            return info[key]
    raise KeyError(
        f"None of the expected info keys {candidates} were found. "
        f"Available keys: {sorted(info.keys())}. "
        f"Run scripts/inspect_alfworld_api.py and update _GAMEFILE_KEYS / "
        f"_ADMISSIBLE_KEYS in preexperiments/common/alfworld_runner.py."
    )


def extract_gamefile(info: Dict[str, Any], batch_idx: int = 0) -> str:
    val = _first_present(info, _GAMEFILE_KEYS)
    return val[batch_idx] if isinstance(val, (list, tuple)) else val


def extract_admissible(info: Dict[str, Any], batch_idx: int = 0) -> List[str]:
    val = _first_present(info, _ADMISSIBLE_KEYS)
    return list(val[batch_idx]) if isinstance(val[0], (list, tuple)) else list(val)


def extract_won(info: Dict[str, Any], batch_idx: int = 0) -> bool:
    val = _first_present(info, _WON_KEYS)
    return bool(val[batch_idx]) if isinstance(val, (list, tuple)) else bool(val)


def extract_task_id(gamefile: str) -> str:
    """ALFWorld gamefiles live at .../<task_type>-<...>/trial_.../*.tw-pddl or
    similar; use the trial directory name as a stable, human-readable task id."""
    parts = gamefile.replace("\\", "/").split("/")
    for part in reversed(parts):
        if part.startswith("trial_"):
            return part
    # fallback: parent directory name
    return parts[-2] if len(parts) >= 2 else gamefile


# ---------------------------------------------------------------------------
# Environment adapter
# ---------------------------------------------------------------------------

class ALFWorldEnvAdapter:
    """Thin wrapper around one batch_size=1 ALFWorld AlfredTWEnv instance."""

    def __init__(self, config: Dict[str, Any], split: str):
        self.config = config
        self.split = split
        self._env_wrapper = None
        self._env = None
        self.game_files: List[str] = []
        self._build()

    def _build(self) -> None:
        from alfworld.agents.environment import AlfredTWEnv  # lazy import

        alfworld_config = _load_alfworld_config()
        env_type = alfworld_config.get("env", {}).get("type", "AlfredTWEnv")
        if env_type != "AlfredTWEnv":
            raise ValueError(
                f"alfworld_base_config.yaml env.type={env_type!r}, expected "
                f"'AlfredTWEnv' (text-only). The pre-experiments in this repo "
                f"are ReAct/text agents, not AlfredThorEnv/AlfredHybrid."
            )
        self._env_wrapper = AlfredTWEnv(alfworld_config, train_eval=self.split)
        self.game_files = list(self._env_wrapper.game_files)
        self._env = self._env_wrapper.init_env(batch_size=1)

    def reset(self) -> Tuple[str, Dict[str, Any]]:
        obs, info = self._env.reset()
        return obs[0], info

    def step(self, action: str) -> Tuple[str, bool, bool, Dict[str, Any]]:
        obs, scores, dones, info = self._env.step([action])
        done = bool(dones[0])
        success = extract_won(info) if done else False
        return obs[0], done, success, info

    def current_gamefile(self, info: Dict[str, Any]) -> str:
        return extract_gamefile(info)


def build_single_game_adapter(config: Dict[str, Any], split: str, gamefile: str) -> ALFWorldEnvAdapter:
    """Construct an adapter restricted to exactly one game file, for
    deterministic replay (see module docstring)."""
    adapter = ALFWorldEnvAdapter.__new__(ALFWorldEnvAdapter)
    adapter.config = config
    adapter.split = split

    from alfworld.agents.environment import AlfredTWEnv

    alfworld_config = _load_alfworld_config()
    env_wrapper = AlfredTWEnv(alfworld_config, train_eval=split)
    all_files = list(env_wrapper.game_files)
    matches = [g for g in all_files if g == gamefile]
    if not matches:
        matches = [g for g in all_files if g.replace("\\", "/") == gamefile.replace("\\", "/")]
    if not matches:
        raise RuntimeError(
            f"gamefile {gamefile!r} not found among {len(all_files)} games in "
            f"split={split!r}. The game may belong to a different split, or "
            f"the installed ALFWorld dataset differs from the one used to "
            f"originally collect this trajectory."
        )

    env_wrapper.game_files = [matches[0]]
    if hasattr(env_wrapper, "num_games"):
        env_wrapper.num_games = 1

    adapter._env_wrapper = env_wrapper
    adapter.game_files = [matches[0]]
    adapter._env = env_wrapper.init_env(batch_size=1)
    return adapter


# ---------------------------------------------------------------------------
# Action selection (ReAct-style, one call per step)
# ---------------------------------------------------------------------------

def format_history(history: Sequence[Tuple[str, str]], max_turns: int = 8) -> str:
    if not history:
        return "(no actions taken yet)"
    trimmed = history[-max_turns:]
    lines = []
    for i, (action, obs) in enumerate(trimmed):
        lines.append(f"> {action}\n{obs}")
    return "\n".join(lines)


def format_admissible(actions: Sequence[str]) -> str:
    return "\n".join(f"- {a}" for a in actions)


def ground_action(raw_text: str, admissible_actions: Sequence[str]) -> Tuple[str, bool]:
    """Map free-form model output onto one legal admissible action.

    Returns (action, was_forced). `was_forced=True` means the model's raw
    output did not exactly match any admissible action and a fallback
    heuristic (case/whitespace-insensitive match, then closest string match,
    then first admissible action) had to be used. This grounding step is
    applied identically to every condition/experiment, so it cannot bias any
    A-vs-B or lesson-vs-no-lesson comparison -- it only keeps the episode
    from crashing on a malformed model output.
    """
    text = raw_text.strip().strip('"').strip("'")
    if text in admissible_actions:
        return text, False

    norm_map = {a.strip().lower(): a for a in admissible_actions}
    if text.strip().lower() in norm_map:
        return norm_map[text.strip().lower()], False

    close = difflib.get_close_matches(text, admissible_actions, n=1, cutoff=0.6)
    if close:
        return close[0], True

    return admissible_actions[0], True


def choose_action(
    llm: LLMClient,
    *,
    goal: str,
    observation: str,
    history: Sequence[Tuple[str, str]],
    admissible_actions: Sequence[str],
    seed: int,
    lesson: Optional[str] = None,
) -> Tuple[str, bool, int, int]:
    """Returns (grounded_action, was_forced, prompt_tokens, completion_tokens)."""
    template = prompts.REACT_ACTION_WITH_LESSON_PROMPT if lesson else prompts.REACT_ACTION_PROMPT
    prompt = template.format(
        goal=goal,
        observation=observation,
        history=format_history(history),
        admissible_actions=format_admissible(admissible_actions),
        lesson=lesson or "",
    )
    resp = llm.complete(prompt, seed=seed)
    action, forced = ground_action(resp.text, admissible_actions)
    return action, forced, resp.prompt_tokens, resp.completion_tokens


# ---------------------------------------------------------------------------
# Episode-level rollout
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class EpisodeResult:
    success: bool
    done: bool
    steps: int
    step_records: List[Dict[str, Any]]
    history: List[Tuple[str, str]]
    final_observation: str


def rollout(
    adapter: ALFWorldEnvAdapter,
    *,
    llm: LLMClient,
    config: Dict[str, Any],
    run_id: str,
    task_id: str,
    game_id_or_path: str,
    split: str,
    seed: int,
    goal: str,
    observation: str,
    history: Optional[List[Tuple[str, str]]] = None,
    start_step: int = 0,
    lesson: Optional[str] = None,
    forced_first_action: Optional[str] = None,
    step_callback: Optional[Callable[[int, str, str, List[str], Dict[str, Any]], None]] = None,
) -> EpisodeResult:
    """Run a ReAct agent from the given (already reset/restored) `adapter`
    state until success/done/max_steps.

    `forced_first_action`, if given, is used verbatim for the very first
    step of this call (no LLM call) -- this is how experiment B executes
    branch actions (a_t^(0) or a_t^(W)) at a decision point before handing
    control back to the ordinary base planner for the rest of the rollout.

    `step_callback(step, observation, goal, admissible_actions, info)` is
    invoked before each action is chosen -- experiment B's decision-point
    collector uses this to inspect candidate states without altering control
    flow.
    """
    sampling_cfg = config["sampling"]
    max_steps = sampling_cfg["max_episode_steps"]

    history = list(history) if history else []
    step_records: List[Dict[str, Any]] = []
    step = start_step
    obs = observation
    done = False
    success = False

    # We need the *current* admissible actions/info for `obs`, which the
    # caller's reset()/restore already produced; the loop below re-derives
    # them after every env.step() call.
    info = getattr(adapter, "_last_info", None)

    while step < max_steps and not done:
        if info is None:
            raise RuntimeError(
                "rollout() requires the caller to attach the info dict from "
                "the initiating reset()/restore_state() call to "
                "adapter._last_info before invoking rollout()."
            )
        admissible_actions = extract_admissible(info)

        if step_callback is not None:
            step_callback(step, obs, goal, list(admissible_actions), info)

        if step == start_step and forced_first_action is not None:
            action = forced_first_action
            forced = action not in admissible_actions
            prompt_tokens = completion_tokens = 0
        else:
            action, forced, prompt_tokens, completion_tokens = choose_action(
                llm,
                goal=goal,
                observation=obs,
                history=history,
                admissible_actions=admissible_actions,
                seed=seed,
                lesson=lesson,
            )

        next_obs, done, success, info = adapter.step(action)
        adapter._last_info = info

        record = build_step_log(
            run_id=run_id,
            task_id=task_id,
            game_id_or_path=game_id_or_path,
            split=split,
            seed=seed,
            step=step,
            goal=goal,
            observation=obs,
            admissible_actions=list(admissible_actions),
            action=action,
            next_observation=next_obs,
            done=done,
            success=success,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=config["model"]["name"],
            temperature=sampling_cfg["temperature"],
            top_p=sampling_cfg["top_p"],
            max_episode_steps=max_steps,
            extra={"action_forced": forced},
        )
        step_records.append(record)
        history.append((action, next_obs))
        obs = next_obs
        step += 1

    return EpisodeResult(
        success=success,
        done=done,
        steps=step,
        step_records=step_records,
        history=history,
        final_observation=obs,
    )


def reset_and_attach(adapter: ALFWorldEnvAdapter) -> Tuple[str, Dict[str, Any]]:
    """reset() and stash `info` on the adapter so rollout() can read
    admissible actions for the very first step without a redundant call."""
    obs, info = adapter.reset()
    adapter._last_info = info
    return obs, info
