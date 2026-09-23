"""
Experiment A7 (spec section 14): novelty + transferability proxy signals for
each failure's lesson, computed WITHOUT looking at any evaluation outcome
(A_pairwise_episodes.jsonl) -- these are meant to be predictive proxies, not
derived from the ground truth they're later correlated against in analyze.py.
"""
from __future__ import annotations

import argparse
import os
import re
from typing import List

import numpy as np

from preexperiments.common import prompts
from preexperiments.common.embeddings import Embedder, cosine_sim
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import append_jsonl, ensure_dirs, load_yaml_config, read_jsonl_all
from preexperiments.failure_selection._common import reset_output_file

_NUMBER_RE = re.compile(r"-?\d*\.?\d+")


def _parse_transferability(text: str, failure_id: str) -> float:
    match = _NUMBER_RE.search(text)
    if not match:
        print(
            f"[score_failure_proxies] WARNING: could not parse transferability "
            f"number for {failure_id} from response {text!r}; defaulting to 0.5"
        )
        return 0.5
    try:
        value = float(match.group(0))
    except ValueError:
        print(
            f"[score_failure_proxies] WARNING: unparseable transferability number "
            f"for {failure_id} ({match.group(0)!r}); defaulting to 0.5"
        )
        return 0.5
    return max(0.0, min(1.0, value))


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    ensure_dirs(results_dir)

    lessons_file = os.path.join(results_dir, "A_failure_lessons.jsonl")
    output_file = os.path.join(results_dir, "A_proxy_scores.jsonl")

    if not os.path.exists(lessons_file):
        raise FileNotFoundError(
            f"missing input file {lessons_file}, run extract_lessons.py first."
        )

    # Novelty is defined relative to strictly-earlier failures in collection
    # order, so this must be read in file order (which equals failure_id
    # order: F0001, F0002, ...), not re-sorted.
    lessons = read_jsonl_all(lessons_file)
    if not lessons:
        raise RuntimeError(f"{lessons_file} is empty; nothing to do.")

    reset_output_file(output_file)

    embedder = Embedder(config)
    llm = load_client_from_config(config)
    temperature = config["experiment_a"]["lesson_temperature"]
    seed = 13

    lesson_vecs: List[np.ndarray] = []
    for idx, rec in enumerate(lessons):
        lesson_text = rec["lesson"]
        vec = embedder.encode_one(lesson_text)

        if idx == 0:
            novelty = 1.0
        else:
            novelty = 1.0 - max(cosine_sim(vec, prev) for prev in lesson_vecs)
        lesson_vecs.append(vec)

        prompt = prompts.TRANSFERABILITY_PROMPT.format(lesson=lesson_text)
        resp = llm.complete(prompt, seed=seed, temperature=temperature)
        transferability = _parse_transferability(resp.text, rec["failure_id"])

        utility_proxy = (novelty + transferability) / 2.0
        append_jsonl(output_file, {
            "failure_id": rec["failure_id"],
            "novelty": novelty,
            "transferability": transferability,
            "utility_proxy": utility_proxy,
        })

    print(f"[score_failure_proxies] scored={len(lessons)} failures\n  -> {output_file}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A7: novelty + transferability utility proxy per failure."
    )
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
