"""Compare an independent recheck (filled results_template.json) with the frozen outputs.

    python -B recheck_4b/compare_recheck.py --results <filled.json> --out <comparison.json>

References are read at run time from aim3_e/results/analysis.public.json and
gpu_analysis/checkpoints/d0_report.json; no reference number is stored in this file.
Counts must match exactly; E proportions within 1e-4; D0 weighted values within 1e-6.
Fields left null are reported as not computed, not as failures. Standard library only.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("always", "no_info", "none")
PAIRS = ("always_minus_no_info", "always_minus_none", "no_info_minus_none")
EFFECTS = ("admission", "info", "revision")
ROLES = {"always": ("draft", "replan"), "no_info": ("draft", "no_info"), "none": ("draft",)}


def mean(entry):
    return entry["mean"] if entry.get("mean") is not None else entry.get("available_case_mean")


def interval(comparison, level):
    found = (comparison.get("intervals") or {}).get(level)
    return [found["low"], found["high"]] if found else None


def e_reference(a):
    comparisons, sensitivity = a["comparisons"], a["sensitivity_both_no_policy_failure"]
    diagnostics, cost = a["policy_failure_diagnostics"], a["selected_cost_by_arm"]
    paired = {}
    for name in PAIRS:
        c = comparisons[name]
        paired[name] = {"rescued": c["observed_rescued"], "harmed": c["observed_harmed"],
                        "difference": c["difference"], "interval_95": interval(c, "0.95"),
                        "mcnemar_p": c["mcnemar_exact_two_sided_p"]}
    paired["always_minus_no_info"]["interval_975"] = interval(comparisons["always_minus_no_info"], "0.975")
    failures = {arm: {role: {"calls": diagnostics[arm]["by_decision_role"][role]["planner_calls"],
                             "failures": diagnostics[arm]["by_decision_role"][role]["policy_failures"]}
                      for role in ROLES[arm]} for arm in ARMS}
    failures["length_384_failures_all_arms"] = sum(
        bool(m.get("length_at_384")) for arm in ARMS for m in diagnostics[arm]["mechanisms"])
    return {
        "arms": {arm: {"successes": a["arm_outcomes"][arm]["study_successes"],
                       "policy_failed": a["arm_outcomes"][arm]["policy_failed"]} for arm in ARMS},
        "paired": paired,
        "sensitivity_both_no_policy_failure": {
            name: {"kept": sensitivity[name]["n_surviving_pairs"],
                   "difference": (sensitivity[name]["comparison"] or {}).get("difference")} for name in PAIRS},
        "failures": failures,
        "cost": {arm: {"logical_calls": cost[arm]["known_components"]["logical_calls"],
                       "prompt_tokens": cost[arm]["known_components"]["known_prompt_tokens"],
                       "completion_tokens": cost[arm]["known_components"]["known_completion_tokens"],
                       "request_seconds": cost[arm]["known_components"]["sum_known_request_elapsed_s"]}
                 for arm in ARMS},
    }


def d0_reference(d):
    integrity, metrics = d["integrity"], d["metrics"]
    core = metrics["aggregate"]["core_A"]
    differences = integrity["observed_difference_counts_unweighted"]
    actions = integrity["action_changes_unweighted"]
    relation = metrics["relationships"]["confidence_accuracy"]
    return {
        "unweighted": {
            "successes": {b: integrity["branch_outcome_counts_unweighted"][b]["1"] for b in "DNP"},
            "nonzero_differences": {k: sum(v for key, v in differences[k].items() if key not in ("0", "None"))
                                    for k in EFFECTS},
            "action_changes": {k: [actions[k]["changed"], actions[k]["comparable"]] for k in EFFECTS},
        },
        "weighted": {
            "mean_Y": {b: mean(core["branch_available"][b]) for b in "DNP"},
            "mean_difference": {k: mean(core["observed_U"][k]) for k in EFFECTS},
            "EM": mean(core["accuracy"]["EM"]),
            "token_F1": mean(core["accuracy"]["token_F1"]),
            "rank_corr_EM": relation["EM"]["spearman"],
            "rank_corr_token_F1": relation["token_F1"]["spearman"],
        },
        "confidence_quartiles": [
            {"EM": mean(b["summary"]["accuracy"]["EM"]), "token_F1": mean(b["summary"]["accuracy"]["token_F1"]),
             **{k: mean(b["summary"]["observed_U"][k]) for k in EFFECTS}}
            for b in sorted(metrics["confidence_bins"], key=lambda b: b["bin"])],
        "G": dict(metrics["ranking_diagnostics"]["confidence"]["G"]),
    }


def compare(mine, ref, path, tolerance, rows):
    if isinstance(ref, dict):
        for key, value in ref.items():
            compare((mine or {}).get(key) if isinstance(mine, dict) else None, value, f"{path}.{key}", tolerance, rows)
        return
    if isinstance(ref, list) and ref and isinstance(ref[0], dict):
        for index, value in enumerate(ref):
            item = mine[index] if isinstance(mine, list) and index < len(mine) else None
            compare(item, value, f"{path}[{index}]", tolerance, rows)
        return
    if mine is None or (isinstance(mine, list) and any(x is None for x in mine)):
        rows.append({"field": path, "status": "not_computed", "reference": ref})
        return
    pairs = list(zip(mine, ref)) if isinstance(ref, list) else [(mine, ref)]
    if isinstance(ref, list) and len(mine) != len(ref):
        rows.append({"field": path, "status": "mismatch", "mine": mine, "reference": ref})
        return
    ok = all(m == r if isinstance(r, int) and not isinstance(r, bool) else
             (r is None and m is None) or (r is not None and abs(float(m) - float(r)) <= tolerance)
             for m, r in pairs)
    rows.append({"field": path, "status": "match" if ok else "mismatch", "mine": mine, "reference": ref})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    mine = json.loads(args.results.read_text(encoding="utf-8"))
    e_ref = e_reference(json.loads((ROOT / "aim3_e/results/analysis.public.json").read_text(encoding="utf-8")))
    d0_ref = d0_reference(json.loads((ROOT / "gpu_analysis/checkpoints/d0_report.json").read_text(encoding="utf-8")))
    rows = []
    compare(mine.get("E"), e_ref, "E", 1e-4, rows)
    compare(mine.get("D0"), d0_ref, "D0", 1e-6, rows)
    summary = {status: sum(r["status"] == status for r in rows) for status in ("match", "mismatch", "not_computed")}
    report = {"recheck_by": mine.get("recheck_by"), "summary": summary, "fields": rows}
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for row in rows:
        if row["status"] == "mismatch":
            print(f"MISMATCH {row['field']}: mine={row['mine']} reference={row['reference']}")
    print(json.dumps(summary))
    raise SystemExit(1 if summary["mismatch"] else 0)


if __name__ == "__main__":
    main()
