"""Targeted checks for actual physical joins, D references and frozen selection."""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from d0_paths import diagnostics, digest, frozen_selector, select_np_candidates


def read(name):
    return json.loads((ROOT / "gpu_analysis/data" / name).read_text(encoding="utf-8"))


@pytest.fixture
def inputs():
    return read("d0_snapshot.json"), read("d0_rollout_summaries.json"), read("d0_np_evidence.json")


def test_all_actual_paths_once_and_terminal_failures(inputs):
    result = diagnostics(*inputs)
    physical = result["physical_behavior"]
    assert result["validation"]["physical_rollouts_joined"] == 117
    assert result["validation"]["D_first_observations_verified"] == 68
    assert physical["executed_transitions"] == 1397
    assert physical["recorded_new_mu_calls"] == 1295
    assert physical["adjacent_mu_repetition"] == {"numerator": 277, "denominator": 1280, "rate": 277 / 1280}
    assert physical["mu_exact_Nothing_happens"] == {"numerator": 123, "denominator": 1280, "rate": 123 / 1280}
    assert physical["outcome_counts"] == {"complete": 102, "policy_failed": 15}
    assert result["D_checks"]["coverage"]["new_mu_request_pairs"] == 770


def test_repeated_branch_cannot_duplicate_physical_path(inputs):
    dataset, rollouts, _ = inputs
    rollouts["groups"].append(deepcopy(rollouts["groups"][0]))
    with pytest.raises(ValueError, match="Duplicate physical rollout"):
        diagnostics(dataset, rollouts)


def test_prediction_accuracy_cannot_use_revised_P_observation(inputs):
    dataset, rollouts, _ = inputs
    point = next(p for p in dataset["points"] if p["D_reference"]["available"] and
                 p["branches"]["P"]["rollout_id"] != p["branches"]["D"]["rollout_id"])
    revised = next(g for g in rollouts["groups"] if g["rollout_id"] == point["branches"]["P"]["rollout_id"])
    point["D_reference"]["observation"] = revised["first_actual_observation"]
    with pytest.raises(ValueError, match="actual D first observation"):
        diagnostics(dataset, rollouts)


def test_missing_N_action_is_audited_failure_not_physical_path(inputs):
    result = diagnostics(*inputs)
    cases = result["state_outcome_discordances"]
    assert len(cases) == 2
    failed = next(c for c in cases if c["state_id"].endswith(":10"))
    assert failed["game_position_0based"] == 13
    assert failed["branches"]["N"]["first_action"] is None
    assert failed["branches"]["N"]["rollout_id"] is None
    assert failed["branches"]["N"]["Y"] == 0
    assert failed["observed_U"] == {"admission": 0, "info": 1, "revision": -1}
    exhausted = next(c for c in cases if c["state_id"].endswith(":16"))
    assert exhausted["branches"]["P"]["termination_reason"] == "budget_exhausted"
    assert exhausted["branches"]["P"]["first_action"] == failed["branches"]["P"]["first_action"]


def test_resumed_group_retains_original_execution_ledger(inputs):
    dataset, rollouts, evidence = inputs
    resumed = [g for g in evidence["groups"] if "j943506" in g["rollout_file"]["logical_path"] and
               g["call_audit"] is not None and "d0var-935310" in g["call_audit"]["logical_path"]]
    assert resumed
    assert all("game-0004/runner/calls/" in g["call_audit"]["logical_path"] for g in resumed)
    result = diagnostics(dataset, rollouts, evidence)
    rows = {g["rollout_id"]: g for g in result["physical_behavior"]["groups"]}
    assert rows[resumed[0]["rollout_id"]]["continuation_audit_source"] == resumed[0]["call_audit"]


def test_frozen_selector_bytes_and_caps():
    module = frozen_selector()
    assert (module.TARGET_GROUPS, module.MIN_GAMES, module.MAX_GROUPS_PER_GAME, module.MIN_NEW_MU_CALLS) == (6, 4, 2, 10)


def test_real_frozen_selection_keeps_policy_failure_tails(inputs):
    plan = select_np_candidates(*inputs, read("d0_cost_evidence.json"))
    assert plan["status"] == "ready"
    assert (plan["denominators"]["eligible_groups"], plan["denominators"]["eligible_games"]) == (26, 12)
    assert (plan["coverage"]["selected_groups"], plan["coverage"]["selected_games"]) == (6, 6)
    assert plan["denominators"]["selected_new_mu_calls"] == 83
    assert sum(c["eligible"] and c["outcome_status"] == "policy_failed" for c in plan["candidates"]) == 3
    assert sum(c["outcome_status"] == "policy_failed" for c in plan["selected"]) == 2
    assert [c["state_id"].split(":")[-1] for c in plan["selected"]] == ["3", "19", "10", "18", "12", "19"]
    assert [c["new_mu_calls"] for c in plan["selected"]] == [17, 10, 19, 11, 16, 10]
    assert all(c["first_action"] != c["draft_action"] for c in plan["selected"])
    assert plan["denominators"]["source_draft_policy_failure_points"] == 3
    assert plan["runtime_authorized"] is False


def test_stale_fresh_mu_count_is_rejected(inputs):
    costs = read("d0_cost_evidence.json")
    group = next(g for g in costs["accepted_group_calls"] if g["call_ids"])
    group["call_ids"].pop()
    costs["sha256"] = digest({k: v for k, v in costs.items() if k != "sha256"})
    with pytest.raises(ValueError, match="Fresh mu count"):
        select_np_candidates(*inputs, costs)


def test_all_117_original_physical_timings_are_available(inputs):
    evidence = inputs[2]
    assert len(evidence["groups"]) == 117
    for group in evidence["groups"]:
        assert math.isfinite(group["rollout_elapsed_s"]) and group["rollout_elapsed_s"] >= 0
        timings = group["recovery_timings"]
        assert timings["restoration_completed"] is True
        for field in ("restore_wall_s", "cleanup_s", "total_s"):
            assert math.isfinite(timings[field]) and timings[field] >= 0
