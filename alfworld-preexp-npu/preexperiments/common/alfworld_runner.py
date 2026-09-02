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
import re
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import prompts
from .llm_client import LLMClient
from .logging_utils import build_step_log


_ALFWORLD_BASE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "alfworld_base_config.yaml"
_alfworld_config_cache: Optional[Dict[str, Any]] = None

# TextWorld is not thread-safe ANYWHERE, so every call into it -- build,
# reset and step alike -- is serialised through this one lock. Two separate
# pieces of module-level mutable state bite, and both fail with errors that
# point nowhere near the real cause:
#   * build/reset: fast_downward.pddl2sas()'s PDDL-to-SAS translator ->
#     `KeyError: (2, 0)` inside translate.build_sas_operator.
#   * step: textworld/envs/pddl/textgen's module-level tatsu `_PARSER`, whose
#     `_rule_stack` two threads pop concurrently -> `IndexError: pop from
#     empty list`.
#
# Serialising costs almost nothing and buys a lot. Episodes are otherwise
# embarrassingly parallel, and vLLM batches concurrent requests: measured on
# this host at 37 tok/s single-stream vs 513 tok/s at 16-way concurrency with
# no per-request latency penalty. An env step is well under 0.1s against an
# LLM call of ~0.5s (spec prompt) to ~13s (adamem_think), so the lock is held
# for a low single-digit percentage of wall time while the expensive part --
# waiting on the model -- stays fully parallel.
_ENV_LOCK = threading.Lock()


def _import_alfred_tw_env():
    """Return the installed ALFWorld's `AlfredTWEnv` class.

    ALFWorld moved this class' import path between releases. Older versions
    re-exported it from the package root (`from alfworld.agents.environment
    import AlfredTWEnv`); alfworld 0.4.x replaced that with a lazy
    `get_environment(env_type)` factory and only exposes the class from the
    submodule `alfworld.agents.environment.alfred_tw_env`, so the old import
    raises ImportError. Try each known spelling in order rather than pinning
    one, so this works across both layouts.
    """
    try:  # alfworld >= 0.4: factory function
        from alfworld.agents.environment import get_environment

        return get_environment("AlfredTWEnv")
    except ImportError:
        pass
    try:  # alfworld >= 0.4: direct submodule import
        from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv

        return AlfredTWEnv
    except ImportError:
        pass
    from alfworld.agents.environment import AlfredTWEnv  # older layout

    return AlfredTWEnv


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
        AlfredTWEnv = _import_alfred_tw_env()  # lazy import, version-tolerant

        alfworld_config = _load_alfworld_config()
        env_type = alfworld_config.get("env", {}).get("type", "AlfredTWEnv")
        if env_type != "AlfredTWEnv":
            raise ValueError(
                f"alfworld_base_config.yaml env.type={env_type!r}, expected "
                f"'AlfredTWEnv' (text-only). The pre-experiments in this repo "
                f"are ReAct/text agents, not AlfredThorEnv/AlfredHybrid."
            )
        with _ENV_LOCK:
            self._env_wrapper = AlfredTWEnv(alfworld_config, train_eval=self.split)
            self.game_files = list(self._env_wrapper.game_files)
            self._env = self._env_wrapper.init_env(batch_size=1)

    def reset(self) -> Tuple[str, Dict[str, Any]]:
        # textworld.gym loads the game lazily, so the Fast Downward PDDL
        # translation happens on the first reset(), not in init_env().
        with _ENV_LOCK:
            obs, info = self._env.reset()
        return obs[0], info

    def step(self, action: str) -> Tuple[str, bool, bool, Dict[str, Any]]:
        with _ENV_LOCK:
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

    AlfredTWEnv = _import_alfred_tw_env()

    alfworld_config = _load_alfworld_config()
    with _ENV_LOCK:
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
    with _ENV_LOCK:
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


_ACTION_TAG_RE = re.compile(r"<action>(.*?)</action>", re.DOTALL | re.IGNORECASE)


def extract_action_from_response(response: str) -> str:
    """Pull the action out of AdaMEM's `<action> ... </action>` tag.

    Copied in behaviour from AdaMEM's
    examples/prompt_agent/gpt4o_alfworld.py::extract_action_from_response
    (commit 4ea93e2), including its fallback of returning the whole response
    when no tag is present -- ground_action() then handles that text the same
    way it handles any other free-form output.
    """
    match = _ACTION_TAG_RE.search(response)
    return match.group(1).strip() if match else response.strip()


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


def _think_then_act(
    llm: LLMClient,
    first_call_prompt: str,
    admissible_actions: Sequence[str],
    seed: int,
    adamem_max_tokens: int,
) -> Tuple[str, bool, int, int]:
    """Shared two-call "adamem_think" mechanism: prefill `<think>` on
    `first_call_prompt` and stop at `</think>` to get a reasoning trace (the
    prefill is required -- this model replies to a bare "reason in <think>"
    instruction with an immediate EOS, at any temperature, without it; see
    llm_client.complete), then feed the reasoning back and decode ONLY the
    action under the same guided_choice constraint the "spec" style uses.
    Used by both `choose_action` (base/ambiguity-resample actions) and
    `choose_foresight_action` (B4) so the two calls stay structurally
    identical -- action_changed should measure "did it see the world-model
    prediction", not "which of the two call sites happened to reason
    differently".
    """
    think_resp = llm.complete(
        first_call_prompt,
        seed=seed,
        max_tokens=adamem_max_tokens,
        prefill="<think>",
        stop=["</think>"],
    )
    reasoning = think_resp.text.strip()
    act_resp = llm.complete(
        first_call_prompt + prompts.ADAMEM_ACTION_AFTER_THINK_SUFFIX.format(reasoning=reasoning),
        seed=seed,
        choices=list(admissible_actions),
    )
    action, forced = ground_action(act_resp.text, admissible_actions)
    return (
        action,
        forced,
        think_resp.prompt_tokens + act_resp.prompt_tokens,
        think_resp.completion_tokens + act_resp.completion_tokens,
    )


def choose_foresight_action(
    llm: LLMClient,
    *,
    goal: str,
    observation: str,
    admissible_actions: Sequence[str],
    base_action: str,
    predicted_next_observation: str,
    seed: int,
    prompt_style: Optional[str] = None,
    adamem_max_tokens: int = 512,
) -> Tuple[str, bool, int, int]:
    """B4 (spec section 23), with the same `prompt_style` switch `choose_action`
    uses. Spec's fixed FORESIGHT_CONDITIONED_ACTION_PROMPT text is never
    altered; when `prompt_style="adamem_think"`, `ADAMEM_THINK_FORESIGHT_SUFFIX`
    is appended ONLY to elicit the same two-call reasoning-then-action
    mechanism B2's base action gets under that style (known-issue fix: without
    this, action_changed would confound "saw the prediction" with "got to
    think at all" whenever prompt_style=adamem_think, since B2 reasons and B4
    didn't).
    """
    style = prompt_style or "spec"
    base_prompt = prompts.FORESIGHT_CONDITIONED_ACTION_PROMPT.format(
        goal=goal,
        observation=observation,
        admissible_actions=format_admissible(admissible_actions),
        base_action=base_action,
        predicted_next_observation=predicted_next_observation,
    )
    if style == "adamem_think":
        first_call_prompt = base_prompt + prompts.ADAMEM_THINK_FORESIGHT_SUFFIX
        return _think_then_act(llm, first_call_prompt, admissible_actions, seed, adamem_max_tokens)

    resp = llm.complete(base_prompt, seed=seed, choices=list(admissible_actions))
    action, forced = ground_action(resp.text, admissible_actions)
    return action, forced, resp.prompt_tokens, resp.completion_tokens


def choose_action(
    llm: LLMClient,
    *,
    goal: str,
    observation: str,
    history: Sequence[Tuple[str, str]],
    admissible_actions: Sequence[str],
    seed: int,
    lesson: Optional[str] = None,
    constrain_to_admissible: bool = True,
    prompt_style: Optional[str] = None,
    adamem_max_tokens: int = 512,
) -> Tuple[str, bool, int, int]:
    """Returns (grounded_action, was_forced, prompt_tokens, completion_tokens).

    `constrain_to_admissible` (spec section 5.1: "这样预实验主要研究 planning,
    而不是 action formatting") makes the server decode into EXACTLY one of
    `admissible_actions` via vLLM's guided_choice. This is not cosmetic --
    measured on this host, Qwen3-4B-Instruct-2507 free-decoding this prompt
    produced a non-admissible action on 51% of steps. They were not
    malformed, just not currently legal (e.g. "examine bowl 1" while the
    legal move was "take bowl 1 from desk 1"), and ground_action()'s difflib
    fallback then silently mapped them onto a DIFFERENT object's action
    ("examine desk 1"). Because that fallback is deterministic and leaves the
    state unchanged, the agent re-received an identical prompt and looped on
    the same wrong action until max_episode_steps -- i.e. most "failures"
    measured formatting, not planning, which is exactly the confound the
    spec's prompt design set out to avoid.
    """
    style = prompt_style or "spec"
    if style == "adamem_think":
        # Two calls per step -- see _think_then_act for why. AdaMEM's
        # no-memory prompt already contains its own "reason in <think>" ask,
        # so it's used verbatim as the first-call text (no extra suffix
        # needed the way choose_foresight_action needs one).
        template = (
            prompts.ADAMEM_THINK_ACTION_WITH_LESSON_PROMPT
            if lesson
            else prompts.ADAMEM_THINK_ACTION_PROMPT
        )
        prompt = template.format(
            goal=goal,
            observation=observation,
            history=format_history(history),
            admissible_actions=format_admissible(admissible_actions),
            lesson=lesson or "",
        )
        return _think_then_act(llm, prompt, admissible_actions, seed, adamem_max_tokens)

    template = prompts.REACT_ACTION_WITH_LESSON_PROMPT if lesson else prompts.REACT_ACTION_PROMPT
    prompt = template.format(
        goal=goal,
        observation=observation,
        history=format_history(history),
        admissible_actions=format_admissible(admissible_actions),
        lesson=lesson or "",
    )
    resp = llm.complete(
        prompt,
        seed=seed,
        choices=list(admissible_actions) if constrain_to_admissible else None,
    )
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
    max_steps: Optional[int] = None,
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

    `max_steps`, if given, overrides `config["sampling"]["max_episode_steps"]`
    as the absolute step-index ceiling (the loop runs `while step < max_steps`,
    so this is compared directly against `step`/`start_step`, not added to
    them). Known-issue fix: experiment B's branch continuations used to
    default to the global ceiling, which left late decision points (e.g.
    step 29 of 30) with only 1 step of remaining budget -- both branches then
    fail identically not because foresight was unhelpful but because neither
    branch had any room to prove itself. build_counterfactual_pairs.py passes
    `start_step + config["sampling"]["max_episode_steps"]` here so every
    branch gets a full fresh budget counted from the decision point, not from
    episode start.
    """
    sampling_cfg = config["sampling"]
    max_steps = max_steps if max_steps is not None else sampling_cfg["max_episode_steps"]

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
                prompt_style=sampling_cfg.get("prompt_style", "spec"),
                adamem_max_tokens=sampling_cfg.get("adamem_max_tokens", 512),
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
