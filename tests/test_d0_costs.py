"""Necessary real-data cost reconciliation and missingness checks."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from d0_costs import summarize_costs


@pytest.fixture(scope="module")
def evidence():
    return tuple(json.loads((ROOT / "gpu_analysis/data" / name).read_text(encoding="utf-8"))
                 for name in ("d0_cost_evidence.json", "final_accounting_summary.json"))


def test_recorded_calls_and_accepted_split_reconcile(evidence):
    costs, accounting = evidence
    summary = summarize_costs(costs, accounting)
    assert summary["per_call_total"]["logical_calls"] == 2200
    assert summary["per_call_total"]["terminal_records"] == 2199
    assert summary["by_campaign_stage"]["d0_var"]["logical_calls"] == 1614
    assert summary["by_campaign_stage"]["d0_source"]["logical_calls"] == 586
    split = summary["ten_accepted_batches_split"]
    assert (split["acceptance"]["logical_calls"], split["local"]["logical_calls"]) == (100, 1236)
    assert len(costs["accepted_group_calls"]) == 117
    assert all(len(g["call_ids"]) == g["new_mu_calls"] for g in costs["accepted_group_calls"])
    timing = summary["physical_group_timings"]
    assert timing["rollout_elapsed_s"]["known_groups"] == 117
    assert timing["recovery_timings"]["restore_wall_s"]["known_groups"] == 117
    assert timing["recovery_timings"]["total_s"]["known_groups"] == 117
    assert summary["whole_runner_wall"]["seconds"] is None


def test_incomplete_attempt_is_unknown_not_zero_or_charged(evidence):
    costs, accounting = evidence
    summary = summarize_costs(costs, accounting)
    original = next(a for a in summary["per_attempt"] if a["job_id"] == "935310")
    assert original["per_call"]["logical_calls"] == 278
    assert original["per_call"]["terminal_records"] == 277
    assert original["start_minus_accounting_logical"] == 1
    assert original["accounting_http_charged_minus_recorded_attempts"] == 2
    assert original["charged"]["logical_model_calls"] == 6490
    assert original["unrecorded_calls"] is None
    assert original["per_call"]["http_total"]["total_for_exported_calls"] is None
    assert original["per_call"]["prompt_tokens"]["total_for_exported_calls"] is None
    assert original["per_call"]["prompt_tokens"]["known_sum"] > 0
    orphan_ids = {r["call_id"] for r in costs["calls"] if r["terminal_sha256"] is None}
    assert len(orphan_ids) == 1
    assert not orphan_ids.intersection(cid for g in costs["accepted_group_calls"] for cid in g["call_ids"])


def test_duplicate_physical_call_rejected(evidence):
    costs, accounting = evidence
    altered = deepcopy(costs)
    altered["calls"].append(altered["calls"][0])
    with pytest.raises(ValueError, match="Duplicate physical logical-call"):
        summarize_costs(altered, accounting)
