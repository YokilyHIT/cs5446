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
"""
from __future__ import annotations

import argparse
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
        episode_points = 0
        step = 0
        done = False

        while step < max_steps and not done:
            admissible = extract_admissible(info)
            history_text = format_history(history)
            is_decision_point = (
                episode_points < per_episode_cap
                and len(admissible) >= 2
                and len(history_text) <= _HISTORY_CHAR_CAP
            )

            if is_decision_point:
                total_points += 1
                point_id = f"D{total_points:05d}"
                append_jsonl(
                    dp_path,
                    {
                        "point_id": point_id,
                        "task_id": task_id,
                        "game_id_or_path": gamefile,
                        "seed": _BASE_SEED,
                        "step": step,
                        "goal": goal,
                        "action_prefix": list(action_prefix),
                        "observation": observation,
                        "admissible_actions": list(admissible),
                    },
                )
                episode_points += 1

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

            if total_points >= target_total:
                break
            if episode_points >= per_episode_cap:
                # Spec: stop this episode early once its quota of decision
                # points is collected -- no point running it further.
                break

    if total_points < target_total:
        print(
            f"[collect_decision_points] warning: collected only {total_points}/"
            f"{target_total} target decision points from {episodes_run} episodes."
        )

    print(
        f"[collect_decision_points] episodes_run={episodes_run} decision_points={total_points}\n"
        f"  -> {dp_path}\n"
        f"  -> {raw_path}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="B1: collect base-ReAct decision points on eval_in_distribution."
    )
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
