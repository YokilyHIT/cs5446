"""All accepted physical paths and the unchanged frozen N/P hash selector.

This is a CPU analysis adapter. A ready selection is an engineering candidate
list; it does not run a replay or establish population reproducibility.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SIDE = ROOT / "research_progress/2026-10-10-d0-analysis/sidecar"
sys.path.insert(0, str(SIDE))
from analysis_diagnostics import summarize_diagnostics

FROZEN_FILES = {
    "research_progress/2026-10-10-np-audit/sidecar/np_selection.py":
        "f0ed5c9f8368968f3bdb5a1ce551f7c9595508f4093f745b2b832fc1651153da",
    "research_progress/2026-10-10-np-audit/NP_AUDIT_SPEC.json":
        "8c372bfef25fe1421db6112e0d3f6807297151fa82b8b4dd4045355060f90c3a",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_seal(value):
    require(value.get("sha256") == digest({k: v for k, v in value.items() if k != "sha256"}),
            "Input content seal differs")


def frozen_selector():
    for name, expected in FROZEN_FILES.items():
        require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected,
                "Frozen N/P source changed: " + name)
    path = ROOT / next(iter(FROZEN_FILES))
    spec = importlib.util.spec_from_file_location("d0_frozen_np_selection", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _index(snapshot, rollouts, evidence=None):
    points = {(p["canonical_game_id"], p["state_id"]): p for p in snapshot["points"]}
    require(len(points) == len(snapshot["points"]), "Duplicate original point")
    groups, physical_ids = {}, set()
    for group in rollouts["groups"]:
        rid = group["rollout_id"]
        key = group["canonical_game_id"], group["state_id"]
        physical_key = (*key, group["group_id"])
        require(rid not in groups and physical_key not in physical_ids, "Duplicate physical rollout")
        require(key in points, "Rollout is outside the original selected states")
        require(group["repeat_index"] == 0, "Only the accepted r=1 path is supported")
        point = points[key]
        planned = [g for g in point["physical_groups"] if g["group_id"] == group["group_id"]]
        require(len(planned) == 1 and planned[0]["rollout_id"] == rid, "Physical group binding differs")
        require(sorted(planned[0]["branches"]) == sorted(group["branches"]), "Physical branch ownership differs")
        require(group["steps"] and group["steps"][0]["phase"] == "first_action", "Missing executed first action")
        require(group["steps"][0]["action"] == group["first_action"] == planned[0]["action"],
                "First action does not match physical group")
        require(group["steps"][0]["next_obs"] == group["first_actual_observation"], "First observation differs")
        for branch in group["branches"]:
            task = point["branches"][branch]
            require(task["rollout_id"] == rid and task["group_id"] == group["group_id"] and
                    task["first_action"] == group["first_action"] and task["raw_Y"] == group["Y_study"],
                    "Logical branch does not match its physical rollout")
        groups[rid] = group
        physical_ids.add(physical_key)
    expected = {g["rollout_id"] for p in points.values() for g in p["physical_groups"]}
    require(expected == set(groups), "Accepted physical group coverage differs")
    for point in points.values():
        ref = point["D_reference"]
        if ref["available"]:
            d = groups[point["branches"]["D"]["rollout_id"]]
            require(ref["source_rollout_id"] == d["rollout_id"] and
                    d["first_action"] == point["draft_action"] and
                    ref["observation"] == d["steps"][0]["next_obs"],
                    "Accuracy reference is not the actual D first observation")
        else:
            require(point["source_decision_status"] == "source_draft_policy_failure", "Missing D reference")
    evidence_by = {}
    if evidence is not None:
        check_seal(evidence)
        require(evidence["snapshot_content_sha256"] == snapshot["sha256"] and
                evidence["rollouts_content_sha256"] == rollouts["sha256"], "Recovery evidence binds different inputs")
        evidence_by = {g["rollout_id"]: g for g in evidence["groups"]}
        require(len(evidence_by) == len(evidence["groups"]) and set(evidence_by) == set(groups),
                "Recovery evidence group coverage differs")
        for rid, row in evidence_by.items():
            group = groups[rid]
            for field in ("canonical_game_id", "state_id", "group_id", "branches", "new_mu_calls"):
                require(row[field] == group[field], "Recovery binding differs: " + field)
            require(row["rollout_file"]["logical_path"] == group["source_binding_path"], "Original rollout file differs")
    return points, groups, evidence_by


def diagnostics(snapshot, rollouts, evidence=None):
    """Use every accepted physical rollout once and verify every D reference."""
    points, groups, evidence_by = _index(snapshot, rollouts, evidence)
    # The frozen diagnostic consumes only genuine physical-path records from
    # this field. No synthetic calls or full hydrated-report claims are added.
    adapted = dict(snapshot)
    adapted["cost_evidence"] = {"physical_groups": [
        {**g, "game_id": g["canonical_game_id"], "step_log": g["steps"]} for g in groups.values()]}
    result = summarize_diagnostics(adapted)
    physical = result["physical_behavior"]
    for row, group in zip(physical["groups"], groups.values()):
        row.update({key: group[key] for key in ("rollout_id", "first_action", "first_actual_observation",
                   "new_mu_calls", "termination_reason", "outcome_status", "Y_study", "policy_failure")})
        row["source_binding_path"] = group["source_binding_path"]
        row["recovery_binding"] = evidence_by.get(group["rollout_id"], {}).get("recovery")
        row["continuation_audit_source"] = evidence_by.get(group["rollout_id"], {}).get("call_audit")
    physical.update({
        "executed_transitions": sum(len(g["steps"]) for g in groups.values()),
        "recorded_new_mu_calls": sum(g["new_mu_calls"] for g in groups.values()),
        "termination_counts": dict(sorted(Counter(g["termination_reason"] for g in groups.values()).items())),
        "outcome_counts": dict(sorted(Counter(g["outcome_status"] for g in groups.values()).items())),
        "branch_sharing_counts": dict(sorted(Counter("=".join(sorted(g["branches"])) for g in groups.values()).items())),
        "maximum_action_streak": max((r["longest_executed_action_streak"] for r in physical["groups"]), default=0),
    })
    # This is an exhaustive outcome inventory, distinct from frozen illustrative
    # case selection. Every discordant state is included by the same rule.
    discordances = []
    for point in points.values():
        ys = {b: point["branches"][b]["raw_Y"] for b in "DNP"}
        if None in ys.values() or len(set(ys.values())) == 1:
            continue
        branches = {}
        for branch in "DNP":
            task = point["branches"][branch]
            group = groups.get(task["rollout_id"])
            branches[branch] = {"Y": ys[branch], "first_action": task["first_action"],
                "rollout_id": task["rollout_id"], "first_action_policy_failure": task["first_action_policy_failure"],
                "first_action_failure_evidence": task["first_action_failure_evidence"],
                "termination_reason": group["termination_reason"] if group else "first_action_policy_failure",
                "executed_transitions": len(group["steps"]) if group else 0,
                "first_actual_observation": group["first_actual_observation"] if group else None,
                "action_observation_path": group["steps"] if group else []}
        discordances.append({"canonical_game_id": point["canonical_game_id"], "state_id": point["state_id"],
            "game_position_0based": point["game_position_0based"], "step_id": point["step_id"],
            "remaining_budget": point["remaining_budget"], "branches": branches,
            "observed_U": {"admission": ys["P"]-ys["D"], "info": ys["P"]-ys["N"], "revision": ys["N"]-ys["D"]}})
    result["state_outcome_discordances"] = discordances
    result["validation"] = {"physical_rollouts_joined": len(groups),
        "D_first_observations_verified": sum(p["D_reference"]["available"] for p in points.values()),
        "raw_recovery_bindings": len(evidence_by), "repetitions_per_physical_group": 1,
        "deduplication": "actual rollout_id plus canonical game/state/physical group, never branch count",
        "scope": "Portable accepted evidence joins; no new environment execution or full production re-audit"}
    result["interpretation"] = (
        "D0 r=1 development paths. Repetitions and no-op feedback are observed behavior, not established causes. "
        "Observed Y differences do not identify true conditional utility; D checks do not replace separate N/P replay.")
    return result


def select_np_candidates(snapshot, rollouts, evidence, cost_evidence):
    """Join fresh logical continuation calls, then invoke frozen two-pass hashing."""
    points, groups, evidence_by = _index(snapshot, rollouts, evidence)
    require(evidence is not None, "N/P selection requires physical recovery bindings")
    check_seal(cost_evidence)
    require(cost_evidence["np_evidence_content_sha256"] == evidence["sha256"],
            "Fresh mu audit binds different physical evidence")
    audited = {row["rollout_id"]: row for row in cost_evidence["accepted_group_calls"]}
    require(len(audited) == len(cost_evidence["accepted_group_calls"]) and set(audited) == set(groups),
            "Audited continuation group coverage differs")
    candidates, seen_calls = [], set()
    for rid, group in groups.items():
        row, audit = evidence_by[rid], audited[rid]
        require(audit["status"] == "verified_against_original_call_rows", "Fresh mu audit is incomplete")
        require(audit["game_id"] == group["canonical_game_id"] and audit["state_id"] == group["state_id"] and
                audit["group_id"] == group["group_id"], "Audited physical group identity differs")
        ids = audit["call_ids"]
        require(len(ids) == len(set(ids)) == audit["new_mu_calls"] == group["new_mu_calls"],
                "Fresh mu count does not match logical call IDs")
        require(audit["audit_source"] == row["call_audit"], "Fresh mu ledger binding differs")
        for cid in ids:
            key = (audit["audit_source"]["logical_path"], cid)
            require(key not in seen_calls, "Logical continuation call assigned to multiple physical groups")
            seen_calls.add(key)
        require(row["recovery"]["input_validation_status"] == "passed" and
                row["recovery"]["restoration_completed"] is True, "Unqualified physical restoration")
        point = points[(group["canonical_game_id"], group["state_id"])]
        candidates.append({key: group[key] for key in ("canonical_game_id", "state_id", "group_id", "branches",
                                                    "first_action", "outcome_status", "measurement_validity")})
        candidates[-1].update({"draft_action": point["draft_action"], "new_mu_calls": len(ids),
            "binding": {"rollout_id": rid, "rollout_file": row["rollout_file"],
                "rollout_sha256": row["rollout_sha256"], "recovery": row["recovery"],
                "call_audit": row["call_audit"], "new_mu_call_ids": ids,
                "snapshot_content_sha256": snapshot["sha256"], "cost_evidence_content_sha256": cost_evidence["sha256"]}})
    inventory = {"schema_version": 1, "kind": "np_audit_candidate_inventory", "status": snapshot["status"],
        "candidates": candidates,
        "state_dispositions": [{"canonical_game_id": p["canonical_game_id"], "state_id": p["state_id"],
            "source_decision_status": p["source_decision_status"],
            "branches_without_physical_rollout": [b for b in "DNP" if p["branches"][b]["rollout_id"] is None]}
            for p in points.values() if not p["physical_groups"] or any(p["branches"][b]["rollout_id"] is None for b in "DNP")],
        "evidence_scope": "Accepted source r=1 paths and actual continuation ledger IDs; selection is not a replay receipt",
        "frozen_selector_sources": FROZEN_FILES,
    }
    return frozen_selector().build_plan(inventory)
