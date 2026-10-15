"""Export a portable derived D0 snapshot from the accepted local archive.

Standard library only; reads existing evidence and writes a new output directory.
It never runs an environment, model, network request, or production finalizer.
The source archive is intentionally not shipped with the small analysis package.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


FINAL = Path("cs5446_modified/research_progress/2026-10-14-d0var-completion")
BUNDLE = Path("cs5446_modified/research_progress/2026-10-12-source-closeout-v12/artifacts-attempt1/bundle/bundle.json")
COUNTS = Path(".review-cache/d0-sparse-review-20261015/independent_counts.json")


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check(condition, message):
    if not condition:
        raise ValueError(message)


def pick(value, names):
    return {name: value[name] for name in names if name in value}


def write_new(path, document):
    document["sha256"] = digest(document)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def logical_audit_path(value):
    text = value.replace("\\", "/")
    marker = "/project/"
    check(marker in text, "Unexpected source audit path")
    return text.split(marker, 1)[1]


def export(source_root, output):
    root = source_root.resolve()
    check(not (output / "data").exists(), "Output data directory already exists; choose a new directory")
    bindings = {}

    def local(value):
        # Old absolute paths in original metadata can be relocated as a complete
        # archive. No personal prefix is included in an exported binding.
        text = str(value).replace("\\", "/")
        for marker in ("/.review-cache/", "/cs5446_modified/"):
            if marker in text:
                return root / (marker[1:] + text.split(marker, 1)[1])
        candidate = Path(value)
        return candidate if candidate.is_absolute() else root / candidate

    def bind(path, expected=None, role="source"):
        path = path.resolve()
        relative = path.relative_to(root).as_posix()
        if relative not in bindings:
            raw = path.read_bytes()
            bindings[relative] = {"logical_path": relative, "size": len(raw),
                                  "sha256": hashlib.sha256(raw).hexdigest(),
                                  "roles": []}
        result = bindings[relative]
        if expected is not None:
            check(result["sha256"] == expected["sha256"] and result["size"] == expected["size"],
                  "Source binding mismatch: " + relative)
        if role not in result["roles"]:
            result["roles"].append(role)
        return {key: result[key] for key in ("logical_path", "size", "sha256")}

    accounting_path = root / FINAL / "FINAL_ACCOUNTING_SUMMARY.json"
    index_path = root / FINAL / "FINAL_EVIDENCE_INDEX.json"
    accounting, index = read(accounting_path), read(index_path)
    index_by = {local(row["local_path"]).resolve(): row for row in index["files"]}
    check(index["status"] == "complete" and index["all_indexed_bytes_verified"] is True,
          "Final evidence index is not complete")
    accounting_binding = bind(accounting_path, index_by[accounting_path.resolve()], "accepted_accounting")
    index_binding = bind(index_path, role="accepted_evidence_index")
    review_path = root / COUNTS
    prior = read(review_path)
    prior_by = {local(row["local_path"]).resolve(): row for row in prior["bindings"]}
    bind(review_path, role="independent_count_comparison")
    bundle_path = root / BUNDLE
    bundle = read(bundle_path)
    bundle_binding = bind(bundle_path, role="original_source_selection_bundle")
    games_by = {game["canonical_game_id"]: game for game in bundle["games"]}
    check(bundle["D0_game_count"] == 24 and bundle["selected_state_count"] == 71,
          "Unexpected original selection coverage")
    points, games, trajectories = [], [], []
    checked_bundle = False
    for game in accounting["per_game"]:
        gid = game["game_id"]
        original_game = games_by[gid]
        shard_path = bundle_path.parent / original_game["file"]["path"]
        shard_binding = bind(shard_path, original_game["file"], "original_selected_state_shard")
        shard = read(shard_path)
        states = {state["state_id"]: state for state in shard["states"]}
        check(set(states) == set(original_game["state_ids"]), "Original state identities differ")
        mp = local(game["manifest"]["local_path"])
        manifest_binding = bind(mp, index_by[mp.resolve()], "accepted_manifest")
        check(manifest_binding["sha256"] == game["manifest"]["sha256"], "Accounting manifest differs")
        m = read(mp)
        check(m["status"] == "complete" and m["canonical_game_id"] == gid, "Incomplete/wrong manifest")
        if not checked_bundle:
            candidates = [f for f in m["inputs"]["caller_inputs"]["files"] if f["path"] == BUNDLE.as_posix()]
            check(len(candidates) == 1, "Original source bundle binding absent")
            bind(bundle_path, candidates[0], "manifest_bound_source_selection")
            checked_bundle = True
        fp = mp.parent / "finalization.json"
        finalization_binding = bind(fp, index_by[fp.resolve()], "accepted_finalization")
        fin = read(fp)
        check(fin["status"] == "complete" and fin["manifest"]["sha256"] == manifest_binding["sha256"],
              "Finalization does not bind accepted manifest")
        raw_bindings = {}
        for name in ("first_actions.jsonl", "prediction_references.jsonl", "rollouts.jsonl"):
            path = mp.parent / name
            raw_bindings[name] = bind(path, prior_by[path.resolve()], "independently_bound_runner_records")
        first = {row["state_id"]: row for row in records(mp.parent / "first_actions.jsonl")}
        refs = {row["state_id"]: row for row in records(mp.parent / "prediction_references.jsonl")}
        rolls = {row["rollout_id"]: row for row in records(mp.parent / "rollouts.jsonl")}
        tasks = defaultdict(dict)
        for task in m["planned_tasks"]:
            check(task["branch"] not in tasks[task["state_id"]], "Duplicate branch task")
            tasks[task["state_id"]][task["branch"]] = task
        checks = {row["state_id"]: row for row in m["planned_D_checks"]}
        check(set(states) == set(first) == set(tasks) == set(checks), "Original selected points differ")
        check(len(rolls) == len(m["planned_groups"]) == game["physical_groups"], "Physical groups differ")
        groups = {row["group_id"]: row for row in m["planned_groups"]}
        k = original_game["original_k_j"]
        check(k == len(states) == game["state_count"], "Original state count differs")
        games.append({"canonical_game_id": gid, "position_0based": game["position"],
                      "original_k_j": k, "original_game_weight": 1 / 24, "status": "complete",
                      "physical_group_count": len(rolls), "accepted_job_id": game["job_id"],
                      "manifest_source": manifest_binding})
        for sid in original_game["state_ids"]:
            state, event, task = states[sid], first[sid], tasks[sid]
            check(event["state"] == state["state"] and event["remaining_budget"] == state["remaining_budget"],
                  "State view/budget differs from selected source")
            check(state["remaining_budget"] == 30 - state["step_id"] and state["original_k_j"] == k,
                  "Original budget/weight metadata differs")
            check(state["statistical_weight"] == 1 / (24 * k), "Original weight differs")
            source_failed = state["source_decision_status"] == "source_draft_policy_failure"
            check(source_failed == (event["local_confidence_event_exists"] is False), "Source failure differs")
            pred = event.get("prediction")
            compact_pred = {key: value for key, value in pred.items() if key != "wm_token_logprobs"} if pred else None
            reference = refs.get(sid)
            dr = rolls.get(task["D"].get("rollout_id"))
            if reference:
                check(dr is not None and reference["actual_D_first_observation"] == dr["first_actual_observation"]
                      == dr["step_log"][0]["next_obs"], "D reference is not the actual rollout observation")
                check(reference["D_replay_status"] == checks[sid]["status"] == "passed"
                      and reference["reference_measurement_validity"] == dr["measurement_validity"] == "valid",
                      "Unqualified actual D reference")
                check(reference["prediction_sha256"] == digest(pred), "Prediction binding differs")
            else:
                check(source_failed and dr is None, "Non-source-failure point lacks D reference")
            branches = {}
            for branch in "DNP":
                t, f = task[branch], event["branches"][branch]
                group = groups.get(t.get("group_id"))
                if not source_failed:
                    check(t["measurement_validity"] == "valid" and checks[sid]["status"] == "passed",
                          "Non-valid accepted branch")
                    if group:
                        check(group["measurement_validity"] == "valid", "Non-valid accepted physical group")
                branches[branch] = {"raw_Y": t["Y_study"], "outcome_status": t["outcome_status"],
                    "measurement_validity": t["measurement_validity"], "first_action": f["action"],
                    "in_visible_menu": f["in_visible_menu"], "group_id": t.get("group_id"),
                    "rollout_id": t.get("rollout_id"), "first_action_policy_failure": f["status"] == "policy_failed",
                    "first_action_failure_evidence": f.get("failure"), "not_run_reason": t.get("not_run_reason")}
            audit = pick(event["source_draft"], ("audit_sha256", "call_id", "new_model_calls",
                "submitted_request_sha256", "terminal_sha256"))
            audit["audit_logical_path"] = logical_audit_path(event["source_draft"]["audit_path"])
            point = {"canonical_game_id": gid, "game_position_0based": game["position"], "state_id": sid,
                "state_spec_sha256": event["state_spec_sha256"], "source_selected_state_sha256": digest(state),
                "step_id": state["step_id"], "remaining_budget": state["remaining_budget"],
                "original_k_j": k, "original_game_weight": state["original_game_weight"],
                "statistical_weight": state["statistical_weight"], "source_decision_status": state["source_decision_status"],
                "state_status": "complete", "evidence_qualification": "derived_from_accepted_r1_finalization",
                "state": state["state"], "draft_action": state["candidate_action"],
                "draft_in_visible_menu": event["branches"]["D"]["in_visible_menu"],
                "source_episode_outcome_status": state["source_baseline_outcome_status"],
                "source_episode_raw_Y": state["source_Y_study"],
                "source_draft_failure": pick(event.get("source_policy_failure") or {},
                    ("reason", "stage", "decision_role", "step", "call_id")) or None,
                "source_draft_evidence": audit, "local_confidence_event_exists": event["local_confidence_event_exists"],
                "prediction": compact_pred, "original_prediction_sha256": digest(pred) if pred else None,
                "prediction_usable": event["analysis_eligibility"]["prediction_usable"],
                "confidence_scoreable": event["analysis_eligibility"]["confidence_scoreable"],
                "admission": event.get("admission"), "D_check": checks[sid], "branches": branches,
                "physical_groups": [g for g in m["planned_groups"] if g["state_id"] == sid],
                "D_reference": {"available": reference is not None,
                    "measurement_validity": reference["reference_measurement_validity"] if reference else "not_applicable",
                    "observation": reference["actual_D_first_observation"] if reference else None,
                    "source_rollout_id": reference["rollout_id"] if reference else None,
                    "D_replay_status": checks[sid]["status"]},
                "cross_job_state": sid in game["cross_job_state_ids"],
                "source_binding_paths": {"manifest": manifest_binding["logical_path"],
                    "finalization": finalization_binding["logical_path"], "source_shard": shard_binding["logical_path"],
                    **{name: row["logical_path"] for name, row in raw_bindings.items()}}}
            points.append(point)
        for roll in rolls.values():
            trajectories.append({"canonical_game_id": gid,
                **pick(roll, ("state_id", "state_spec_sha256", "rollout_id", "group_id", "branches",
                    "first_action", "first_actual_observation", "Y_study", "outcome_status", "measurement_validity",
                    "termination_reason", "remaining_budget", "new_mu_calls", "repeat_index")),
                "policy_failure": pick(roll.get("policy_failure") or {}, ("reason", "stage", "decision_role", "step")) or None,
                "steps": [pick(step, ("step", "phase", "action", "next_obs", "success", "done",
                    "executed_in_visible_menu", "remaining_budget_before", "remaining_budget_after")) for step in roll["step_log"]],
                "source_binding_path": raw_bindings["rollouts.jsonl"]["logical_path"]})

    valid = [p for p in points if all(p["branches"][b]["raw_Y"] is not None for b in "DNP")]
    failed = [p for p in points if p["source_decision_status"] == "source_draft_policy_failure"]
    summary = {"games": len(games), "points": len(points), "valid_DNP_points": len(valid),
        "source_failure_points": len(failed), "physical_groups": len(trajectories),
        "cross_job_states": sum(p["cross_job_state"] for p in points),
        "success_counts": {b: sum(p["branches"][b]["raw_Y"] for p in valid) for b in "DNP"},
        "changed_executable_first_actions": {},
        "D_check_status": dict(Counter(p["D_check"]["status"] for p in points)),
        "all_point_original_weight_mass": math.fsum(p["statistical_weight"] for p in points),
        "valid_DNP_original_weight_mass": math.fsum(p["statistical_weight"] for p in valid)}
    for b in "NP":
        pairs = [p for p in valid if p["branches"][b]["first_action"] is not None and p["branches"]["D"]["first_action"] is not None]
        summary["changed_executable_first_actions"][b] = {"changed": sum(p["branches"][b]["first_action"] != p["branches"]["D"]["first_action"] for p in pairs), "denominator": len(pairs)}
    check((len(games), len(points), len(valid), len(failed), len(trajectories), summary["cross_job_states"]) == (24, 71, 68, 3, 117, 1), "Coverage changed")
    check(summary["success_counts"] == {"D": 9, "N": 8, "P": 8}, "Y counts changed")
    check(summary["changed_executable_first_actions"] == {"N": {"changed": 20, "denominator": 67}, "P": {"changed": 31, "denominator": 68}}, "Action counts changed")
    for p in failed:
        check(p["prediction"] is None and not p["prediction_usable"] and not p["confidence_scoreable"]
              and all(p["branches"][b]["raw_Y"] is None for b in "DNP"), "Source failure has manufactured local data")
    n_failure = [p for p in points if p["branches"]["N"]["first_action_policy_failure"]]
    check(len(n_failure) == 1 and n_failure[0]["branches"]["N"]["raw_Y"] == 0
          and n_failure[0]["branches"]["N"]["measurement_validity"] == "valid", "N first-action failure semantics changed")
    # Compare every selected point, not merely aggregate outcome counts.
    prior_points = {(p["game_id"], p["state_id"]): p for p in prior["points"]}
    for p in points:
        old = prior_points[(p["canonical_game_id"], p["state_id"])]
        check({b: p["branches"][b]["raw_Y"] for b in "DNP"} == old["Y"]
              and {b: p["branches"][b]["first_action"] for b in "DNP"} == old["actions"]
              and p["D_reference"]["observation"] == old["D_reference"]
              and (p["prediction"] or {}).get("wm_mean_logprob") == old["mean_logprob"]
              and (p["prediction"] or {}).get("wm_confidence_logprob") == old["confidence"]
              and p["statistical_weight"] == old["weight"], "Independent point comparison differs")
    summary["independent_review_EM_count"] = prior["summary"]["EM_count"]
    summary["independent_review_accuracy_count"] = prior["summary"]["accuracy_count"]
    check((summary["independent_review_EM_count"], summary["independent_review_accuracy_count"]) == (28, 68), "EM review counts differ")
    dataset = {"schema_version": 1, "kind": "d0_descriptive_dataset", "status": "complete",
        "D0_game_count": 24, "original_selected_state_count": 71,
        "snapshot_scope": "derived_portable_development_snapshot_metrics_cases_and_sensitivity_only",
        "source_bindings_verification": "Export checked accepted manifests/finalizations against FINAL_EVIDENCE_INDEX, runner files against independent count bindings, source shards against original bundle, and every point against independent review. No new production finalization or full audit.",
        "source_bindings_file": "source_bindings.json", "cost_summary_file": "final_accounting_summary.json",
        "trajectory_summary_file": "d0_rollout_summaries.json",
        "full_provenance_audit_performed": False, "cost_analysis_performed": False,
        "collection_complete_is_not_full_report_complete": True,
        "prediction_omitted_fields": ["wm_token_logprobs"],
        "omitted_evidence": ["full raw token/top-logprob evidence", "full request/cost audit trails", "runtime/hardware receipts", "source/replay restoration artifacts"],
        "games": games, "points": points, "export_verification": summary}
    costs = {"schema_version": 1, "kind": "derived_accepted_accounting_excerpt", "source": accounting_binding,
        "original_kind": accounting["kind"], "original_created_at": accounting["created_at"],
        "scope": accounting["scope"], "cost_totals": accounting["cost_totals"],
        "accepted_batch_split": accounting["accepted_batch_split"], "original_935310": accounting["original_935310"],
        "policy_stop_count": accounting["policy_stop_count"], "coverage": accounting["coverage"],
        "per_attempt": [pick(row, ("job_id", "stage", "batch_id", "status", "counts_complete", "observed", "charged",
                                  "reservation_sha256", "finish_sha256")) for row in accounting["per_attempt"]],
        "completion_row_sha256": accounting["completion_row_sha256"],
        "limitations": "Faithful accounting excerpt; observed stopped-attempt counters can be incomplete; charged are conservative reservations, not successful calls or actual failure counts. Does not reconstruct production cost_evidence or run cost diagnostics."}
    trajectories_doc = {"schema_version": 1, "kind": "derived_all_accepted_physical_group_trajectory_summaries",
        "selection": "All 117 accepted groups; no filtering by outcome. Formal development examples are selected separately by frozen hash order.",
        "omitted": ["request messages", "model/token completions", "full per-step admissible menus", "runtime evidence"],
        "groups": trajectories}
    sources = {"schema_version": 1, "kind": "derived_snapshot_source_bindings", "original_artifacts_included": False,
        "logical_path_base": "original source project root; archives are not included in this repository package",
        "accounting_source": accounting_binding, "final_evidence_index_source": index_binding,
        "source_selection_bundle": bundle_binding, "files": list(bindings.values()),
        "verification_scope": dataset["source_bindings_verification"]}
    data_dir = output / "data"
    data_dir.mkdir(parents=True)
    write_new(data_dir / "d0_snapshot.json", dataset)
    write_new(data_dir / "d0_rollout_summaries.json", trajectories_doc)
    write_new(data_dir / "final_accounting_summary.json", costs)
    write_new(data_dir / "source_bindings.json", sources)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    export(args.source_root, args.out)
