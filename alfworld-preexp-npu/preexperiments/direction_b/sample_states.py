"""Stage 0/1 step 1: sample ALFWorld decision states off EXPERT trajectories.

方向二预实验方案 §7 asks for decision states drawn from expert/demonstration
trajectories, each keeping the expert's next action, so that Action-Level
Utility (§11) can be computed as

    U^action = 1[a_fore == a*] - 1[a_base == a*]

which gives every sampled state a label instead of waiting for an episode to
terminate. That matters here: the previous round's utility came from binary
episode success and produced only 11 non-zero labels out of 150 states.

Two constraints discovered by reading ALFWorld's source, both of which shape
this script:

  * `expert_plan` is only attached when `general.training_method == "dagger"`
    AND the split is `train` (alfred_tw_env.py: `expert_plan = True if
    self.train_eval == "train" else False`). So expert-labelled states can
    only come from the TRAIN split. That is acceptable for a confidence-vs-
    utility diagnostic -- it is not a generalisation test -- but it must be
    stated in the report.
  * Building a dagger-mode train env takes ~66s because it walks all 3553
    games and attaches the expert wrapper. Rebuilding per episode would
    dominate runtime, so the env wrapper is built ONCE and `game_files` is
    reassigned per episode (the same trick build_single_game_adapter uses).

The expert is ALFWorld's handcoded expert, and it frequently proposes pure
observation actions (`look`, `inventory`). On those steps almost no planner
will match it, so U^action collapses to 0 and the state carries no signal.
They are still recorded, flagged with `expert_is_noop`, so the downstream
analysis can decide whether to include them rather than having that choice
silently baked in here.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from preexperiments.common.alfworld_runner import (
    _ENV_LOCK,
    _import_alfred_tw_env,
    _load_alfworld_config,
    extract_admissible,
    extract_task_id,
    format_history,
    visible_actions,
)
from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config
from preexperiments.failure_selection._common import extract_goal, extract_task_type

OUT_DIR = Path(__file__).resolve().parents[2] / "data"
_NOOP_VERBS = {"look", "inventory", "examine", "help"}


def _expert_action(info: Dict[str, Any]) -> str:
    plan = info.get("extra.expert_plan")
    if not plan:
        return ""
    first = plan[0]
    if isinstance(first, (list, tuple)):
        first = first[0] if first else ""
    return str(first).strip()


def _build_train_env_wrapper():
    """One dagger-mode AlfredTWEnv over the train split, reused for every
    episode. See module docstring for why this is not rebuilt per episode."""
    cfg = copy.deepcopy(_load_alfworld_config())
    cfg["general"]["training_method"] = "dagger"  # required for expert_plan
    AlfredTWEnv = _import_alfred_tw_env()
    with _ENV_LOCK:
        return AlfredTWEnv(cfg, train_eval="train")


def _select_spread(items: List[Any], k: int) -> List[Any]:
    """Evenly-spread subsample, so states come from early/middle/late steps of
    the trajectory rather than clustering at the start."""
    n = len(items)
    if n <= k:
        return list(items)
    if k <= 1:
        return [items[0]]
    stride = (n - 1) / (k - 1)
    idx = sorted({round(i * stride) for i in range(k)})
    return [items[i] for i in idx]


def main(args: argparse.Namespace) -> None:
    ensure_dirs(OUT_DIR)
    out_path = OUT_DIR / args.out
    if out_path.exists():
        out_path.unlink()

    config = load_yaml_config(args.config)
    max_steps = config["sampling"]["max_episode_steps"]
    history_length = config["sampling"].get("history_length", 50)

    wrapper = _build_train_env_wrapper()
    all_games = sorted(wrapper.game_files)
    # Evenly strided over the sorted list: ALFWorld paths begin with the task
    # type, so taking the first N would draw almost everything from one or two
    # task families.
    n_ep = min(args.episodes, len(all_games))
    stride = len(all_games) / n_ep
    chosen = [all_games[int(i * stride)] for i in range(n_ep)]
    print(f"[sample_states] train split has {len(all_games)} games; "
          f"walking {len(chosen)} expert trajectories", flush=True)

    total = 0
    for ep_i, gamefile in enumerate(chosen):
        with _ENV_LOCK:
            wrapper.game_files = [gamefile]
            if hasattr(wrapper, "num_games"):
                wrapper.num_games = 1
            env = wrapper.init_env(batch_size=1)
            raw_obs, info = env.reset()
        obs = raw_obs[0]
        goal = extract_goal(obs, info)
        task_id, task_type = extract_task_id(gamefile), extract_task_type(gamefile)

        history: List[tuple] = []
        candidates: List[Dict[str, Any]] = []
        done = False
        for step in range(max_steps):
            if done:
                break
            expert = _expert_action(info)
            if not expert:
                break
            admissible = visible_actions(extract_admissible(info))
            candidates.append({
                "episode_id": f"E{ep_i:04d}",
                "task_id": task_id,
                "task_type": task_type,
                "gamefile": gamefile,
                "goal": goal,
                "step_id": step,
                "history": format_history(history, max_turns=history_length),
                "current_observation": obs,
                "admissible_actions": admissible,
                "expert_action": expert,
                "expert_is_noop": expert.split()[0] in _NOOP_VERBS,
                "action_prefix": [a for a, _ in history],
            })
            # Follow the expert exactly, so every state we sample is one the
            # expert itself reaches -- states along a wrong path would have no
            # meaningful expert action to compare against.
            with _ENV_LOCK:
                nxt, _, dones, info = env.step([expert])
            obs, done = nxt[0], bool(dones[0])
            history.append((expert, obs))

        picked = _select_spread(candidates, args.per_episode)
        with open(out_path, "a", encoding="utf-8") as f:
            for c in picked:
                total += 1
                f.write(json.dumps({"state_id": f"S{total:05d}", **c}, ensure_ascii=False) + "\n")
        if (ep_i + 1) % 5 == 0 or ep_i + 1 == len(chosen):
            print(f"[sample_states] {ep_i+1}/{len(chosen)} episodes, {total} states", flush=True)

    print(f"[sample_states] done: {total} states -> {out_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sample expert-labelled ALFWorld decision states.")
    p.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    p.add_argument("--episodes", type=int, default=100, help="how many expert trajectories to walk")
    p.add_argument("--per_episode", type=int, default=5, help="states sampled per trajectory")
    p.add_argument("--out", default="sampled_states.jsonl")
    return p


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[2])
    main(build_arg_parser().parse_args())
