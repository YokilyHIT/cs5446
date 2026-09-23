"""Spec section 37, test 4: paired conditions (no_lesson / with_lesson) use
the same task/seed. Pure data check over results/A_pairwise_episodes.jsonl --
no live ALFWorld/vLLM required, but the file must already exist (run
preexperiments/failure_selection/evaluate_single_lessons.py first, or its
--max_failures 3 mini-smoke-test variant).
"""
from collections import defaultdict

import pytest

from preexperiments.common.logging_utils import read_jsonl_all


def test_pairwise_conditions_share_task_and_seed(results_dir):
    path = results_dir / "A_pairwise_episodes.jsonl"
    if not path.exists():
        pytest.skip(f"{path} not found -- run evaluate_single_lessons.py first.")

    records = read_jsonl_all(path)
    assert records, f"{path} is empty."

    by_pair = defaultdict(lambda: {"no_lesson": set(), "with_lesson": set()})
    for r in records:
        key = (r["failure_id"], r["task_id"])
        by_pair[key][r["condition"]].add(r["seed"])

    for (failure_id, task_id), seeds_by_condition in by_pair.items():
        assert seeds_by_condition["no_lesson"] == seeds_by_condition["with_lesson"], (
            f"failure_id={failure_id} task_id={task_id}: condition 0 ran seeds "
            f"{seeds_by_condition['no_lesson']} but condition 1 ran "
            f"{seeds_by_condition['with_lesson']} -- pairwise comparison is not valid "
            f"unless both conditions used the identical seed set on the identical task."
        )
