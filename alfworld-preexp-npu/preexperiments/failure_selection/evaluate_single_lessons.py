"""
Experiment A4 (spec section 11): strict pairwise (no_lesson vs with_lesson)
evaluation of each failure's lesson on its 3 related tasks, across all 3
seeds. This script does a plain full re-run each time -- a pre-experiment
does not need crash-recovery/checkpointing, per the spec.
"""
from __future__ import annotations

import argparse
import os
from typing import Any, Dict, List

from preexperiments.common.alfworld_runner import build_single_game_adapter, reset_and_attach, rollout
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.parallel import add_workers_arg, ordered_map
from preexperiments.common.logging_utils import append_jsonl, ensure_dirs, env_config_block, load_yaml_config, new_run_id, read_jsonl_all
from preexperiments.failure_selection._common import extract_goal, reset_output_file


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    ensure_dirs(results_dir)

    pairs_file = os.path.join(results_dir, "A_failure_task_pairs.jsonl")
    output_file = os.path.join(results_dir, "A_pairwise_episodes.jsonl")

    if not os.path.exists(pairs_file):
        raise FileNotFoundError(
            f"missing input file {pairs_file}, run select_related_tasks.py first."
        )

    pairs = read_jsonl_all(pairs_file)
    if not pairs:
        raise RuntimeError(f"{pairs_file} is empty; nothing to do.")

    reset_output_file(output_file)

    max_failures = args.max_failures or config["experiment_a"]["max_failures_evaluated"]

    ordered_failure_ids: List[str] = []
    for p in pairs:
        if p["failure_id"] not in ordered_failure_ids:
            ordered_failure_ids.append(p["failure_id"])
    selected_failure_ids = ordered_failure_ids[:max_failures]
    selected_ids = set(selected_failure_ids)

    pairs_by_failure: Dict[str, List[Dict[str, Any]]] = {}
    for p in pairs:
        if p["failure_id"] in selected_ids:
            pairs_by_failure.setdefault(p["failure_id"], []).append(p)
    for plist in pairs_by_failure.values():
        plist.sort(key=lambda r: r["rank"])

    split = config["splits"]["evaluation"]
    seeds = config["seeds"]
    llm = load_client_from_config(config)

    # Build the full (failure, task, seed, condition) job list first, then run
    # it through the pool. Episodes are entirely independent -- each builds its
    # own single-game env -- so the only thing concurrency changes is wall
    # clock. ordered_map returns results in job order, so the JSONL is written
    # deterministically no matter what order they finish in.
    jobs = []
    for failure_id in selected_failure_ids:
        for pair in pairs_by_failure[failure_id]:
            for seed in seeds:
                for condition, lesson in (("no_lesson", None), ("with_lesson", pair["lesson"])):
                    jobs.append({
                        "failure_id": failure_id,
                        "task_id": pair["related_task_id"],
                        "gamefile": pair["related_gamefile"],
                        "seed": seed,
                        "condition": condition,
                        "lesson": lesson,
                    })

    def run_job(job):
        adapter = build_single_game_adapter(config, split, job["gamefile"])
        obs, info = reset_and_attach(adapter)
        goal = extract_goal(obs, info)
        run_id = new_run_id("A4")
        result = rollout(
            adapter,
            llm=llm,
            config=config,
            run_id=run_id,
            task_id=job["task_id"],
            game_id_or_path=job["gamefile"],
            split=split,
            seed=job["seed"],
            goal=goal,
            observation=obs,
            lesson=job["lesson"],
        )
        return {
            "run_id": run_id,
            "failure_id": job["failure_id"],
            "task_id": job["task_id"],
            "condition": job["condition"],
            "seed": job["seed"],
            "success": result.success,
            "steps": result.steps,
            "forced_action_count": sum(1 for r in result.step_records if r.get("action_forced")),
            **env_config_block(config, job["seed"]),
        }

    records = ordered_map(run_job, jobs, workers=args.workers,
                          label="evaluate_single_lessons", progress_every=20)
    for record in records:
        append_jsonl(output_file, record)
    episode_count = len(records)

    print(
        f"[evaluate_single_lessons] failures_evaluated={len(selected_failure_ids)} "
        f"episodes={episode_count}\n  -> {output_file}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A4: pairwise no_lesson vs with_lesson evaluation."
    )
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    parser.add_argument("--max_failures", type=int, default=None)
    add_workers_arg(parser)
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
