"""Spec section 37, test 6: no duplicate run/point/failure ids in any raw
result log. Runs over whatever output files currently exist; each file is
individually skipped if absent so this test is meaningful at every stage of
the pipeline, not only at the very end.
"""
import pytest

from preexperiments.common.logging_utils import assert_no_duplicate_run_ids, read_jsonl_all

_FILES_AND_KEYS = [
    ("A_train_episodes_raw.jsonl", "run_id"),
    ("A_pairwise_episodes.jsonl", "run_id"),
    ("A_topk_vs_all_raw.jsonl", "run_id"),
    ("A_failures_raw.jsonl", "failure_id"),
    ("A_failure_lessons.jsonl", "failure_id"),
    ("B_decision_points.jsonl", "point_id"),
    ("B_foresight_raw.jsonl", "point_id"),
    ("B_branches_raw.jsonl", "point_id"),
]


@pytest.mark.parametrize("filename,key", _FILES_AND_KEYS)
def test_no_duplicate_ids(results_dir, filename, key):
    path = results_dir / filename
    if not path.exists():
        pytest.skip(f"{path} not found.")
    records = read_jsonl_all(path)
    if not records:
        pytest.skip(f"{path} is empty.")
    assert_no_duplicate_run_ids(records, key=key)
