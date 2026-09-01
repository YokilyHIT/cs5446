"""
Experiment A1 (spec section 8): run the NO-MEMORY ReAct agent on the `train`
split and collect raw failure trajectories.

Stopping rule is a RACE between two conditions -- whichever triggers first
wins: `max_train_episodes` episodes attempted OR `min_failures` failures
collected. This is deliberately "or", not "and": if failures are rare we
must still stop at max_train_episodes, and if failures are common we stop
as soon as we have enough of them.
"""
from __future__ import annotations

import argparse
import os
from typing import Any, Dict, List

from preexperiments.common.alfworld_runner import (
    ALFWorldEnvAdapter,
    build_single_game_adapter,
    extract_task_id,
    reset_and_attach,
    rollout,
)
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import (
    append_jsonl,
    ensure_dirs,
    env_config_block,
    load_yaml_config,
    new_run_id,
)
from preexperiments.failure_selection._common import (
    extract_goal,
    extract_task_type,
    reset_output_file,
)


def _list_sorted_game_files(config: Dict[str, Any], split: str) -> List[str]:
    """One-off adapter build just to read `game_files`, sorted so partial
    re-runs of this script always walk episodes in the same order."""
    probe = ALFWorldEnvAdapter(config, split)
    return sorted(probe.game_files)


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    ensure_dirs(results_dir)

    output_file = args.output_file or os.path.join(results_dir, "A_failures_raw.jsonl")
    all_episodes_file = os.path.join(results_dir, "A_train_episodes_raw.jsonl")
    reset_output_file(output_file)
    reset_output_file(all_episodes_file)

    split = config["splits"]["experience"]
    max_episodes = args.max_episodes or config["experiment_a"]["max_train_episodes"]
    min_failures = config["experiment_a"]["min_failures"]
    seed = args.seed if args.seed is not None else 13

    llm = load_client_from_config(config)
    game_files = _list_sorted_game_files(config, split)

    failure_count = 0
    episodes_run = 0
    stop_reason = "exhausted_game_files"

    for gamefile in game_files:
        if episodes_run >= max_episodes:
            stop_reason = "max_train_episodes_reached"
            break
        if failure_count >= min_failures:
            stop_reason = "min_failures_reached"
            break

        # Rebuilding a single-game adapter per episode re-parses AlfredTWEnv
        # for the whole split each time, which is wasteful but simple and
        # the documented safe default (see alfworld_runner module docstring)
        # -- swap in a cached env_wrapper here if this becomes too slow.
        adapter = build_single_game_adapter(config, split, gamefile)
        obs, info = reset_and_attach(adapter)
        goal = extract_goal(obs, info)
        task_id = extract_task_id(gamefile)
        task_type = extract_task_type(gamefile)

        run_id = new_run_id("A1")
        result = rollout(
            adapter,
            llm=llm,
            config=config,
            run_id=run_id,
            task_id=task_id,
            game_id_or_path=gamefile,
            split=split,
            seed=seed,
            goal=goal,
            observation=obs,
            lesson=None,
        )
        episodes_run += 1
        forced_action_count = sum(1 for r in result.step_records if r.get("action_forced"))

        episode_record = {
            "run_id": run_id,
            "task_id": task_id,
            "task_type": task_type,
            "gamefile": gamefile,
            "goal": goal,
            "success": result.success,
            "steps": result.steps,
            "forced_action_count": forced_action_count,
            "seed": seed,
            **env_config_block(config, seed),
        }
        append_jsonl(all_episodes_file, episode_record)

        if not result.success:
            failure_count += 1
            failure_record = {
                "failure_id": f"F{failure_count:04d}",
                "task_id": task_id,
                "task_type": task_type,
                "gamefile": gamefile,
                "goal": goal,
                "trajectory": result.step_records,
                "final_observation": result.final_observation,
                "forced_action_count": forced_action_count,
                "seed": seed,
                **env_config_block(config, seed),
            }
            append_jsonl(output_file, failure_record)

    print(
        f"[collect_failures] episodes_run={episodes_run} failures_found={failure_count} "
        f"stop_reason={stop_reason}\n"
        f"  -> {output_file}\n"
        f"  -> {all_episodes_file}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A1: collect raw no-memory ReAct failures on the train split."
    )
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    parser.add_argument("--max_episodes", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--output_file", default=None)
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
