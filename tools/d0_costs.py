"""Small, pure summaries of real exported D0 call rows and accepted accounting.

The campaign's allocation/charged counters are deliberately kept separate from
observed HTTP attempts, tokens and request time. Missing terminals stay unknown.
"""
from collections import Counter, defaultdict
import math


def _measure(rows, key, known_key=None):
    values = [row.get(key) for row in rows]
    known = [v for v in values if type(v) in (int, float) and math.isfinite(v)]
    subtotal = math.fsum(row.get(known_key, 0) for row in rows) if known_key else math.fsum(known)
    return {"known_sum": subtotal, "total_for_exported_calls": subtotal if len(known) == len(rows) else None,
            "known_calls": len(known), "unknown_calls": len(rows) - len(known),
            "exported_calls": len(rows)}


def _summary(rows):
    result = {"logical_calls": len(rows),
              "terminal_records": sum(row["terminal_sha256"] is not None for row in rows),
              "terminal_missing_starts": sum(row["terminal_sha256"] is None for row in rows),
              "http_attempts_recorded": sum(row["http_attempts_recorded"] for row in rows),
              "http_total": _measure(rows, "http_attempts_total"),
              "prompt_tokens": _measure(rows, "prompt_tokens_total", "prompt_tokens_known"),
              "completion_tokens": _measure(rows, "completion_tokens_total", "completion_tokens_known"),
              "request_elapsed_s": _measure(rows, "request_elapsed_s"),
              "failure_categories": dict(sorted(Counter(row["failure_category"] for row in rows).items())),
              "planner_format_failure_calls": sum(row["planner_format_failure"] for row in rows)}
    return result


def _physical_timings(groups):
    def measure(values):
        known = [v for v in values if type(v) in (int, float) and math.isfinite(v) and v >= 0]
        subtotal = math.fsum(known)
        return {"known_sum": subtotal, "total_for_exported_groups": subtotal if len(known) == len(values) else None,
                "known_groups": len(known), "unknown_groups": len(values) - len(known), "exported_groups": len(values)}
    fields = ("build_s", "reset_s", "build_reset_s", "replay_s", "validation_s", "restore_wall_s", "cleanup_s", "total_s")
    return {"scope": "117 accepted physical groups; excludes old interrupted/invalidated fragments; not whole-runner or job wall time",
            "physical_groups": len(groups), "rollout_elapsed_s": measure([g.get("rollout_elapsed_s") for g in groups]),
            "recovery_timings": {field: measure([(g.get("recovery_timings") or {}).get(field) for g in groups]) for field in fields},
            "overlap_note": "Recovery total_s is restore wall plus cleanup; build_reset_s contains build_s and reset_s. These components overlap, and rollout elapsed overlaps recovery and model requests. Do not add them."}


def summarize_costs(cost_evidence, accounting):
    """Return descriptive cost totals without inventing calls from ledger totals."""
    rows = cost_evidence["calls"]
    identities = [(row["source_file"], row["call_id"]) for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate physical logical-call identity")
    if cost_evidence["accounting_source_sha256"] != accounting["source"]["sha256"]:
        raise ValueError("Cost evidence and accounting have different source bindings")
    attempts = {row["job_id"]: row for row in accounting["per_attempt"]}
    by_job, by_scope, by_stage, by_phase, by_role = (defaultdict(list) for _ in range(5))
    for row in rows:
        if row["job_id"] not in attempts:
            raise ValueError("Call outside the current campaign")
        by_job[row["job_id"]].append(row)
        by_scope[row["scope"]].append(row)
        by_stage[row["campaign_stage"]].append(row)
        by_phase[row["scope"] + "/" + row["phase"]].append(row)
        by_role[row["scope"] + "/" + row["role"]].append(row)
    per_attempt = []
    for job, attempt in attempts.items():
        observed = _summary(by_job[job])
        recorded = attempt["observed"]["logical_model_calls"]
        if attempt["counts_complete"] and observed["logical_calls"] != recorded:
            raise ValueError("Exported starts do not reconcile with recorded calls: " + job)
        if attempt["counts_complete"] and observed["http_attempts_recorded"] != attempt["observed"]["http_attempts_charged"]:
            raise ValueError("Complete-attempt HTTP mismatch: " + job)
        per_attempt.append({"job_id": job, "stage": attempt["stage"], "status": attempt["status"],
                            "counts_complete": attempt["counts_complete"], "per_call": observed,
                            "accounting_observed": attempt["observed"], "charged": attempt["charged"],
                            "start_minus_accounting_logical": observed["logical_calls"] - recorded,
                            "accounting_http_charged_minus_recorded_attempts": attempt["observed"]["http_attempts_charged"] - observed["http_attempts_recorded"],
                            "unrecorded_calls": 0 if attempt["counts_complete"] else None})
    complete_batch_jobs = {a["job_id"] for a in attempts.values() if a["stage"] == "d0_var" and a["status"] == "complete"}
    accepted = [r for r in rows if r["job_id"] in complete_batch_jobs]
    split = {scope: _summary([r for r in accepted if r["scope"] == scope]) for scope in ("acceptance", "local")}
    if split["acceptance"]["logical_calls"] != accounting["accepted_batch_split"]["backend_logical_calls"] or split["local"]["logical_calls"] != accounting["accepted_batch_split"]["collection_logical_calls"]:
        raise ValueError("Accepted batch acceptance/collection split differs")
    return {"status": "observed_call_evidence_with_explicit_unknowns", "per_call_total": _summary(rows),
            "by_scope": {k: _summary(v) for k, v in sorted(by_scope.items())},
            "by_campaign_stage": {k: _summary(v) for k, v in sorted(by_stage.items())},
            "by_phase": {k: _summary(v) for k, v in sorted(by_phase.items())},
            "by_role": {k: _summary(v) for k, v in sorted(by_role.items())},
            "ten_accepted_batches_split": split, "per_attempt": per_attempt,
            "accounting_totals": accounting["cost_totals"],
            "physical_group_timings": _physical_timings(cost_evidence["accepted_group_calls"]),
            "whole_runner_wall": {"status": "unavailable_in_exported_input", "seconds": None,
                                  "reason": "No complete whole-runner timing input across accepted, resumed and stopped attempts; group elapsed and allocation are separate quantities."},
            "policy_stop_count": accounting["policy_stop_count"],
            "coverage": cost_evidence["coverage"], "limitations": cost_evidence["limitations"],
            "counter_reconciliation": cost_evidence["counter_reconciliation"],
            "timing_note": "Request time, attempt time, rollout time and allocation overlap; do not add them. Charged allocation is a conservative budget charge, not measured GPU busy time."}
