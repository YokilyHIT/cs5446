"""Spec section 37, test 5: evaluation tasks never appear as a train failure
source task (no train/eval leakage in the related-task selection).
"""
import pytest

from preexperiments.common.logging_utils import read_jsonl_all


def test_related_tasks_exclude_failure_source(results_dir):
    failures_path = results_dir / "A_failures_raw.jsonl"
    pairs_path = results_dir / "A_failure_task_pairs.jsonl"
    if not failures_path.exists() or not pairs_path.exists():
        pytest.skip(
            f"{failures_path} / {pairs_path} not found -- run collect_failures.py "
            "and select_related_tasks.py first."
        )

    failures = {r["failure_id"]: r for r in read_jsonl_all(failures_path)}
    pairs = read_jsonl_all(pairs_path)
    assert pairs, f"{pairs_path} is empty."

    for pair in pairs:
        source = failures[pair["failure_id"]]
        assert pair["related_task_id"] != source["task_id"], (
            f"failure {pair['failure_id']}: related task {pair['related_task_id']} "
            f"is the same task the failure itself came from."
        )
        if "gamefile" in source and "related_gamefile" in pair:
            assert pair["related_gamefile"] != source["gamefile"], (
                f"failure {pair['failure_id']}: related gamefile equals the "
                f"failure's own source gamefile."
            )
