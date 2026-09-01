"""
Experiment A8 (spec section 15): Top-K vs All-lessons vs RandomK vs NoMemory
comparison on a fixed 30-task evaluation subset, 3 seeds each.

Only the retrieval POOL differs between conditions -- exactly one lesson is
ever injected into the prompt (top-1 by goal-embedding similarity within
whatever pool the condition uses), so prompt length never confounds the
comparison (spec explicitly warns against concatenating all lessons in).
"""
from __future__ import annotations

import argparse
import json
import math
import os
from typing import Any, Dict, List, Optional

import numpy as np

from preexperiments.common.alfworld_runner import ALFWorldEnvAdapter, build_single_game_adapter, reset_and_attach, rollout
from preexperiments.common.embeddings import Embedder, cosine_sim
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import append_jsonl, ensure_dirs, env_config_block, load_yaml_config, new_run_id, read_jsonl_all
from preexperiments.failure_selection._common import extract_goal, get_or_build_candidate_record, load_candidate_pool_cache, reset_output_file


def _list_sorted_game_files(config: Dict[str, Any], split: str) -> List[str]:
    probe = ALFWorldEnvAdapter(config, split)
    return sorted(probe.game_files)


def _select_eval_subset(game_files_sorted: List[str], size: int) -> List[str]:
    """Deterministic selection rule: evenly-strided sample over the sorted
    game file list (sorted so the rule is stable across re-runs regardless
    of the order ALFWorld's own dataset loader returns). Using an even
    stride across the whole list -- rather than just the first `size`
    alphabetically-sorted entries -- avoids the subset being dominated by
    whichever task_type happens to sort first. NOT randomly sampled, per
    spec section 15's determinism requirement."""
    n = len(game_files_sorted)
    if n <= size:
        return list(game_files_sorted)
    stride = n / size
    indices = [int(i * stride) for i in range(size)]
    return [game_files_sorted[i] for i in indices]


def _top1_from_pool(task_goal_vec: np.ndarray, pool: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not pool:
        return None
    best = None
    best_sim = -2.0
    for entry in pool:
        sim = cosine_sim(task_goal_vec, entry["vec"])
        if sim > best_sim:
            best_sim = sim
            best = entry
    return best


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    ensure_dirs(results_dir)

    lessons_file = os.path.join(results_dir, "A_failure_lessons.jsonl")
    proxy_file = os.path.join(results_dir, "A_proxy_scores.jsonl")
    task_ids_file = os.path.join(results_dir, "A_eval_task_ids.json")
    output_file = os.path.join(results_dir, "A_topk_vs_all_raw.jsonl")

    for path in (lessons_file, proxy_file):
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"missing input file {path}, run extract_lessons.py / score_failure_proxies.py first."
            )

    lessons_by_id = {r["failure_id"]: r for r in read_jsonl_all(lessons_file)}
    proxy_by_id = {r["failure_id"]: r for r in read_jsonl_all(proxy_file)}
    if not lessons_by_id:
        raise RuntimeError(f"{lessons_file} is empty; nothing to do.")

    eval_split = config["splits"]["evaluation"]
    subset_size = config["experiment_a"]["eval_subset_size"]
    topk_fraction = config["experiment_a"]["topk_fraction"]
    random_seed = config["stats"]["bootstrap_seed"]  # fixed, documented seed for RandomK sampling

    game_files_sorted = _list_sorted_game_files(config, eval_split)
    selected_gamefiles = _select_eval_subset(game_files_sorted, subset_size)

    cache = load_candidate_pool_cache(results_dir)
    embedder = Embedder(config)

    selected_tasks = []
    for gf in selected_gamefiles:
        rec = get_or_build_candidate_record(config, eval_split, gf, cache, results_dir)
        selected_tasks.append({
            "task_id": rec["task_id"],
            "gamefile": rec["gamefile"],
            "goal": rec["goal"],
            "goal_vec": embedder.encode_one(rec["goal"]),
        })

    with open(task_ids_file, "w", encoding="utf-8") as f:
        json.dump(
            [{"task_id": t["task_id"], "gamefile": t["gamefile"]} for t in selected_tasks],
            f, indent=2,
        )

    all_lessons = []
    for failure_id, lesson_rec in lessons_by_id.items():
        proxy = proxy_by_id.get(failure_id)
        if proxy is None:
            print(f"[evaluate_topk_vs_all] WARNING: no proxy score for {failure_id}, skipping from lesson pool")
            continue
        lesson_text = lesson_rec["lesson"]
        all_lessons.append({
            "failure_id": failure_id,
            "lesson": lesson_text,
            "utility_proxy": proxy["utility_proxy"],
            "vec": embedder.encode_one(lesson_text),
        })

    if not all_lessons:
        raise RuntimeError("No lessons with proxy scores available; cannot build lesson pool.")

    k = max(1, min(len(all_lessons), math.ceil(topk_fraction * len(all_lessons))))

    topk_pool = sorted(all_lessons, key=lambda e: -e["utility_proxy"])[:k]

    rng = np.random.default_rng(random_seed)
    random_indices = sorted(rng.choice(len(all_lessons), size=k, replace=False).tolist())
    random_pool = [all_lessons[i] for i in random_indices]

    retrieval_pools: Dict[str, Optional[List[Dict[str, Any]]]] = {
        "NoMemory": None,
        "AllLessons": all_lessons,
        "RandomK": random_pool,
        "TopK": topk_pool,
    }

    reset_output_file(output_file)

    split = eval_split
    seeds = config["seeds"]
    llm = load_client_from_config(config)

    episode_count = 0
    for condition in ("NoMemory", "AllLessons", "RandomK", "TopK"):
        pool = retrieval_pools[condition]
        for task in selected_tasks:
            injected = _top1_from_pool(task["goal_vec"], pool) if pool is not None else None
            injected_id = injected["failure_id"] if injected else None
            injected_lesson_text = injected["lesson"] if injected else None

            for seed in seeds:
                adapter = build_single_game_adapter(config, split, task["gamefile"])
                obs, info = reset_and_attach(adapter)
                goal = extract_goal(obs, info)
                run_id = new_run_id("A8")

                result = rollout(
                    adapter,
                    llm=llm,
                    config=config,
                    run_id=run_id,
                    task_id=task["task_id"],
                    game_id_or_path=task["gamefile"],
                    split=split,
                    seed=seed,
                    goal=goal,
                    observation=obs,
                    lesson=injected_lesson_text,
                )
                forced_action_count = sum(1 for r in result.step_records if r.get("action_forced"))
                record = {
                    "run_id": run_id,
                    "condition": condition,
                    "task_id": task["task_id"],
                    "seed": seed,
                    "success": result.success,
                    "steps": result.steps,
                    "injected_lesson_failure_id": injected_id,
                    "forced_action_count": forced_action_count,
                    **env_config_block(config, seed),
                }
                append_jsonl(output_file, record)
                episode_count += 1

    print(
        f"[evaluate_topk_vs_all] lesson_pool={len(all_lessons)} K={k} tasks={len(selected_tasks)} "
        f"episodes={episode_count}\n  -> {output_file}\n  -> {task_ids_file}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A8: NoMemory vs AllLessons vs RandomK vs TopK comparison."
    )
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
