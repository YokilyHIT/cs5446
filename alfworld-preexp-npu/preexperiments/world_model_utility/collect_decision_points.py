"""
Experiment B1 (spec section 20): run the base ReAct planner on 30 fixed
`eval_in_distribution` episodes and record up to 5 "decision points" per
episode (states with >=2 admissible actions) for later foresight analysis.

The base planner loop is driven manually here (rather than via
alfworld_runner.rollout()'s step_callback) so that each decision point can be
recorded with an explicit, unambiguous `action_prefix` -- the exact list of
actions taken so far in THIS episode -- which is required by
replay_state.restore_state() downstream. Threading that same information
through rollout()'s step_callback would require reconstructing it from
partial EpisodeResult state, which is more fragile than just owning the loop.

IMPORTANT (fixed after review): earlier versions of this script stopped an
episode as soon as it had collected `decision_points_per_episode` qualifying
states. Since almost every ALFWorld step has >=2 admissible actions, that
meant every episode was cut off after its first ~5 steps -- i.e. all 150
decision points came from the "walk to the room" opening of each task, where
the choice of action barely affects final success. It also meant episodes
were never allowed to finish, so this script could not report how often the
base planner actually succeeds at all (needed to sanity-check the go/no-go
verdict downstream, see world_model_utility/analyze.py's INCONCLUSIVE gate).

This version instead runs every episode to completion (done or
max_episode_steps), collects EVERY qualifying candidate state along the way,
and then subsamples `decision_points_per_episode` of them spread evenly
across the whole episode (see `_select_spread`) -- so decision points come
from early, middle, and late game states, not just the opening.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Tuple

from preexperiments.common.alfworld_runner import (
    ALFWorldEnvAdapter,
    build_single_game_adapter,
    choose_action,
    extract_admissible,
    extract_task_id,
    format_history,
    reset_and_attach,
)
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import (
    append_jsonl,
    build_step_log,
    ensure_dirs,
    load_yaml_config,
    new_run_id,
)
from preexperiments.world_model_utility._common import (
    extract_goal_and_observation,
    reset_output_file,
)

# History-length cap (spec section 20): once the formatted history text for
# an episode grows past this, keep running the episode with the base planner
# but stop recording new decision points from it -- an overlong history field
# would push the ReAct prompt past what's meaningfully usable anyway.
_HISTORY_CHAR_CAP = 6000

_BASE_SEED = 13


def _list_sorted_game_files(config: Dict[str, Any], split: str) -> List[str]:
    """One-off adapter build just to read `game_files`, sorted so this
    script always selects the same 30 episodes across re-runs."""
    probe = ALFWorldEnvAdapter(config, split)
    return sorted(probe.game_files)


def _select_spread(candidates: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
    """Pick up to `k` candidates evenly spread across the (step-ordered)
    candidate list, instead of always taking the first `k` -- so decision
    points aren't all clustered in the episode's opening steps."""
    n = len(candidates)
    if n <= k:
        return list(candidates)
    if k <= 1:
        return [candidates[0]]
    step_size = (n - 1) / (k - 1)
    indices = sorted({round(i * step_size) for i in range(k)})
    return [candidates[i] for i in indices]


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    ensure_dirs(results_dir)

    dp_path = os.path.join(results_dir, "B_decision_points.jsonl")
    raw_path = os.path.join(results_dir, "B_base_episodes_raw.jsonl")
    reset_output_file(dp_path)
    reset_output_file(raw_path)

    split = config["splits"]["evaluation"]
    eb_cfg = config["experiment_b"]
    n_episodes = eb_cfg["eval_episodes"]
    per_episode_cap = eb_cfg["decision_points_per_episode"]
    target_total = eb_cfg["target_decision_points"]
    max_steps = config["sampling"]["max_episode_steps"]

    llm = load_client_from_config(config)
    all_gamefiles = _list_sorted_game_files(config, split)
    if len(all_gamefiles) < n_episodes:
        print(
            f"[collect_decision_points] warning: split {split!r} has only "
            f"{len(all_gamefiles)} games, fewer than requested {n_episodes} episodes."
        )
    chosen_gamefiles = all_gamefiles[:n_episodes]

    total_points = 0
    episodes_run = 0
    episodes_succeeded = 0
    total_steps_run = 0
    total_forced_actions = 0

    for gamefile in chosen_gamefiles:
        if total_points >= target_total:
            break

        adapter = build_single_game_adapter(config, split, gamefile)
        raw_obs, info = reset_and_attach(adapter)
        goal, observation = extract_goal_and_observation(raw_obs)
        task_id = extract_task_id(gamefile)
        run_id = new_run_id("B1base")
        episodes_run += 1

        history: List[Tuple[str, str]] = []
        action_prefix: List[str] = []
        candidates: List[Dict[str, Any]] = []
        step = 0
        done = False
        success = False

        # Run the FULL episode (see module docstring: no early cutoff once a
        # quota of candidates is reached) so decision points can be sampled
        # from across the whole trajectory, and so we know whether the base
        # planner ever actually succeeds on this task.
        while step < max_steps and not done:
            admissible = extract_admissible(info)
            history_text = format_history(history)
            if len(admissible) >= 2 and len(history_text) <= _HISTORY_CHAR_CAP:
                candidates.append(
                    {
                        "task_id": task_id,
                        "game_id_or_path": gamefile,
                        "seed": _BASE_SEED,
                        "step": step,
                        "goal": goal,
                        "action_prefix": list(action_prefix),
                        "observation": observation,
                        "admissible_actions": list(admissible),
                    }
                )

            action, forced, prompt_tokens, completion_tokens = choose_action(
                llm,
                goal=goal,
                observation=observation,
                history=history,
                admissible_actions=admissible,
                seed=_BASE_SEED,
                lesson=None,
            )
            next_obs, done, success, info = adapter.step(action)
            total_steps_run += 1
            total_forced_actions += int(forced)

            append_jsonl(
                raw_path,
                build_step_log(
                    run_id=run_id,
                    task_id=task_id,
                    game_id_or_path=gamefile,
                    split=split,
                    seed=_BASE_SEED,
                    step=step,
                    goal=goal,
                    observation=observation,
                    admissible_actions=list(admissible),
                    action=action,
                    next_observation=next_obs,
                    done=done,
                    success=success,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    model=config["model"]["name"],
                    temperature=config["sampling"]["temperature"],
                    top_p=config["sampling"]["top_p"],
                    max_episode_steps=max_steps,
                    extra={"action_forced": forced},
                ),
            )

            history.append((action, next_obs))
            action_prefix.append(action)
            observation = next_obs
            step += 1

        episodes_succeeded += int(success)

        for cand in _select_spread(candidates, per_episode_cap):
            if total_points >= target_total:
                break
            total_points += 1
            point_id = f"D{total_points:05d}"
            append_jsonl(dp_path, {"point_id": point_id, **cand})

    forced_rate = (total_forced_actions / total_steps_run) if total_steps_run else float("nan")
    success_rate = (episodes_succeeded / episodes_run) if episodes_run else float("nan")

    summary_path = os.path.join(results_dir, "B_base_episode_success_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "episodes_run": episodes_run,
                "episodes_succeeded": episodes_succeeded,
                "success_rate": success_rate,
                "total_steps": total_steps_run,
                "forced_action_count": total_forced_actions,
                "forced_action_rate": forced_rate,
            },
            f,
            indent=2,
        )

    if total_points < target_total:
        print(
            f"[collect_decision_points] warning: collected only {total_points}/"
            f"{target_total} target decision points from {episodes_run} episodes."
        )

    print(
        f"[collect_decision_points] episodes_run={episodes_run} decision_points={total_points} "
        f"base_success_rate={success_rate:.3f} forced_action_rate={forced_rate:.3f}\n"
        f"  -> {dp_path}\n"
        f"  -> {raw_path}\n"
        f"  -> {summary_path}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="B1: collect base-ReAct decision points on eval_in_distribution."
    )
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
