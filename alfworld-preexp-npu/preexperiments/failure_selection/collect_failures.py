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
from preexperiments.common.parallel import add_workers_arg, ordered_map
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

    # Concurrency changes WHICH episodes get run, but not which failures get
    # kept. Sequentially the loop stops as soon as `min_failures` is reached;
    # here all `max_episodes` candidates run and the first `min_failures`
    # failures IN SORTED GAMEFILE ORDER are kept. Because the sequential
    # version walked that same sorted order, both select the identical failure
    # set -- this one just does more episodes to get there.
    #
    # Keeping the order matters beyond tidiness: failure_id is assigned by
    # position, and score_failure_proxies computes each lesson's novelty
    # against strictly-earlier lessons in file order, so a shuffled file would
    # silently change the proxy scores.
    candidates = game_files[:max_episodes]

    def run_episode(gamefile):
        adapter = build_single_game_adapter(config, split, gamefile)
        obs, info = reset_and_attach(adapter)
        goal = extract_goal(obs, info)
        run_id = new_run_id("A1")
        result = rollout(
            adapter,
            llm=llm,
            config=config,
            run_id=run_id,
            task_id=extract_task_id(gamefile),
            game_id_or_path=gamefile,
            split=split,
            seed=seed,
            goal=goal,
            observation=obs,
            lesson=None,
        )
        return {
            "run_id": run_id,
            "gamefile": gamefile,
            "task_id": extract_task_id(gamefile),
            "task_type": extract_task_type(gamefile),
            "goal": goal,
            "result": result,
        }

    outcomes = ordered_map(run_episode, candidates, workers=args.workers,
                           label="collect_failures", progress_every=10)
    episodes_run = len(outcomes)

    failure_count = 0
    for o in outcomes:
        result = o["result"]
        forced_action_count = sum(1 for r in result.step_records if r.get("action_forced"))
        append_jsonl(all_episodes_file, {
            "run_id": o["run_id"],
            "task_id": o["task_id"],
            "task_type": o["task_type"],
            "gamefile": o["gamefile"],
            "goal": o["goal"],
            "success": result.success,
            "steps": result.steps,
            "seed": seed,
            "forced_action_count": forced_action_count,
            **env_config_block(config, seed),
        })
        if result.success or failure_count >= min_failures:
            continue
        failure_count += 1
        append_jsonl(output_file, {
            "failure_id": f"F{failure_count:04d}",
            "task_id": o["task_id"],
            "task_type": o["task_type"],
            "gamefile": o["gamefile"],
            "goal": o["goal"],
            "trajectory": result.step_records,
            "final_observation": result.final_observation,
            "seed": seed,
            "forced_action_count": forced_action_count,
            **env_config_block(config, seed),
        })
    stop_reason = ("min_failures_reached" if failure_count >= min_failures
                   else "max_train_episodes_reached")

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
    add_workers_arg(parser)
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
