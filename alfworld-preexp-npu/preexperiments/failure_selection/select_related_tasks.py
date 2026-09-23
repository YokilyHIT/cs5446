"""
Experiment A3 (spec section 10): for each failure's lesson, select
`related_tasks_k` (3) candidate tasks from the `eval_in_distribution` split
to later evaluate the lesson's transfer effect on.

Selection rule per failure:
  1. Prefer candidates of the same task_type as the failure's source task.
  2. Rank by cosine similarity between the lesson embedding and the
     candidate's goal embedding.
  3. Exclude the failure's own source task/gamefile (never evaluate a
     lesson on the very game it failed on).
  4. If fewer than 3 same-type candidates remain, backfill with the
     next-highest-similarity candidates regardless of type.
"""
from __future__ import annotations

import argparse
import os
from typing import Any, Dict, List, Tuple

from preexperiments.common.alfworld_runner import ALFWorldEnvAdapter
from preexperiments.common.embeddings import Embedder, cosine_sim
from preexperiments.common.logging_utils import append_jsonl, ensure_dirs, load_yaml_config, read_jsonl_all
from preexperiments.failure_selection._common import (
    get_or_build_candidate_record,
    load_candidate_pool_cache,
    reset_output_file,
)


def _list_sorted_game_files(config: Dict[str, Any], split: str) -> List[str]:
    probe = ALFWorldEnvAdapter(config, split)
    return sorted(probe.game_files)


def _select_related(
    *,
    lesson_vec,
    source_task_id: str,
    source_gamefile: str,
    source_task_type: str,
    candidates: List[Dict[str, Any]],
    candidate_vecs: Dict[str, Any],
    k: int,
) -> List[Tuple[Dict[str, Any], float]]:
    filtered = [
        c for c in candidates
        if c["task_id"] != source_task_id and c["gamefile"] != source_gamefile
    ]
    scored = [(c, cosine_sim(lesson_vec, candidate_vecs[c["gamefile"]])) for c in filtered]

    same_type = sorted(
        (t for t in scored if t[0]["task_type"] == source_task_type),
        key=lambda t: -t[1],
    )
    other_type = sorted(
        (t for t in scored if t[0]["task_type"] != source_task_type),
        key=lambda t: -t[1],
    )

    selected = same_type[:k]
    if len(selected) < k:
        need = k - len(selected)
        selected = selected + other_type[:need]
    return selected


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    ensure_dirs(results_dir)

    lessons_file = os.path.join(results_dir, "A_failure_lessons.jsonl")
    failures_file = os.path.join(results_dir, "A_failures_raw.jsonl")
    output_file = os.path.join(results_dir, "A_failure_task_pairs.jsonl")

    for path in (lessons_file, failures_file):
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"missing input file {path}, run collect_failures.py / extract_lessons.py first."
            )

    lessons = read_jsonl_all(lessons_file)
    failures_by_id = {f["failure_id"]: f for f in read_jsonl_all(failures_file)}
    if not lessons:
        raise RuntimeError(f"{lessons_file} is empty; nothing to do.")

    reset_output_file(output_file)

    eval_split = config["splits"]["evaluation"]
    k = config["experiment_a"]["related_tasks_k"]

    game_files = _list_sorted_game_files(config, eval_split)
    cache = load_candidate_pool_cache(results_dir)
    candidates = [
        get_or_build_candidate_record(config, eval_split, gf, cache, results_dir)
        for gf in game_files
    ]

    embedder = Embedder(config)
    candidate_vecs = {c["gamefile"]: embedder.encode_one(c["goal"]) for c in candidates}

    pairs_written = 0
    backfilled_failures = 0
    for lesson_rec in lessons:
        failure_id = lesson_rec["failure_id"]
        source = failures_by_id.get(failure_id)
        if source is None:
            print(f"[select_related_tasks] WARNING: no source failure record for {failure_id}, skipping")
            continue

        lesson_text = lesson_rec["lesson"]
        lesson_vec = embedder.encode_one(lesson_text)

        selected = _select_related(
            lesson_vec=lesson_vec,
            source_task_id=source["task_id"],
            source_gamefile=source.get("gamefile", ""),
            source_task_type=source.get("task_type", "unknown"),
            candidates=candidates,
            candidate_vecs=candidate_vecs,
            k=k,
        )

        if len(selected) < k:
            backfilled_failures += 1
            print(
                f"[select_related_tasks] WARNING: {failure_id} only found "
                f"{len(selected)}/{k} related candidates (candidate pool too small)."
            )

        for rank, (candidate, sim) in enumerate(selected, start=1):
            record = {
                "failure_id": failure_id,
                "lesson": lesson_text,
                "related_task_id": candidate["task_id"],
                "related_gamefile": candidate["gamefile"],
                "related_goal": candidate["goal"],
                "similarity_score": sim,
                "same_task_type": candidate["task_type"] == source.get("task_type", "unknown"),
                "rank": rank,
            }
            append_jsonl(output_file, record)
            pairs_written += 1

    print(
        f"[select_related_tasks] failures={len(lessons)} candidate_pool={len(candidates)} "
        f"pairs_written={pairs_written} failures_needing_backfill={backfilled_failures}\n"
        f"  -> {output_file}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A3: select related eval-split tasks per failure lesson."
    )
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
