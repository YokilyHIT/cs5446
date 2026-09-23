"""
Experiment B10 (spec section 30): point-level oracle upper bound on what a
confidence-gate policy could achieve versus an oracle that always picks the
better of the two branches.

For each evaluation point: `g_conf = self_confidence >= tau_c` selects which
branch the confidence-gate policy would have used (`Y_conf`); `A_oracle =
max(base_success, foresight_success) - Y_conf` is the per-point regret of the
confidence-gate policy against the best-of-both-branches oracle; `G_oracle =
mean(A_oracle)` is the upper bound on how much a perfectly-calibrated gate
could still gain. This reuses the SAME fixed calibration/evaluation split as
evaluate_planning_gain.py (sorted point_id, skip the first calibration_points)
and the tau_c that script already locked -- recomputed here rather than
imported so this script only depends on files on disk, not on evaluate_
planning_gain.py's in-memory state.
"""
from __future__ import annotations

import argparse
import json
import os

from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config, read_jsonl_all
from preexperiments.common.stats import bootstrap_ci


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    ensure_dirs(results_dir)

    branches_path = os.path.join(results_dir, "B_branches_raw.jsonl")
    tau_c_path = os.path.join(results_dir, "B_tau_c.json")
    if not os.path.exists(branches_path):
        raise FileNotFoundError(f"missing input file {branches_path}, run build_counterfactual_pairs.py first.")
    if not os.path.exists(tau_c_path):
        raise FileNotFoundError(f"missing input file {tau_c_path}, run evaluate_planning_gain.py first.")

    records = read_jsonl_all(branches_path)
    if not records:
        raise RuntimeError(f"{branches_path} contains no records; nothing to do.")
    records.sort(key=lambda r: r["point_id"])

    with open(tau_c_path, "r", encoding="utf-8") as f:
        tau_c_data = json.load(f)
    tau_c = tau_c_data["tau_c"]

    # Take the calibration size from the value evaluate_planning_gain.py
    # actually used (recorded in B_tau_c.json) rather than re-reading the
    # config, so the two scripts can never disagree about where the
    # calibration/evaluation boundary is -- e.g. when a reduced-size smoke run
    # overrode it. Still a pure function of files on disk.
    calibration_target = tau_c_data.get("calibration_n", config["experiment_b"]["calibration_points"])
    evaluation = records[calibration_target:]
    if not evaluation:
        raise RuntimeError("evaluation subset is empty; cannot compute the oracle gate.")

    stats_cfg = config["stats"]
    oracle_gaps = []
    base_successes = []
    foresight_successes = []
    gate_successes = []

    for r in evaluation:
        base_success = int(r["base_success"])
        foresight_success = int(r["foresight_success"])
        g_conf = r["self_confidence"] >= tau_c
        y_conf = foresight_success if g_conf else base_success
        # g_oracle = r["planning_gain"] > 0 is available for reference but is
        # NOT used here -- G_oracle compares the confidence-gate policy
        # against the best-of-both-branches upper bound, not against
        # whichever branch happened to win.
        a_oracle = max(base_success, foresight_success) - y_conf
        oracle_gaps.append(a_oracle)
        base_successes.append(base_success)
        foresight_successes.append(foresight_success)
        gate_successes.append(y_conf)

    g_oracle, lo, hi = bootstrap_ci(
        oracle_gaps, n_resamples=stats_cfg["bootstrap_resamples"], seed=stats_cfg["bootstrap_seed"]
    )

    output = {
        "G_oracle": g_oracle,
        "G_oracle_ci": [lo, hi],
        "evaluation_n": len(evaluation),
        "mean_base_success": float(sum(base_successes) / len(base_successes)),
        "mean_foresight_success": float(sum(foresight_successes) / len(foresight_successes)),
        "mean_confidence_gate_success": float(sum(gate_successes) / len(gate_successes)),
    }

    output_path = os.path.join(results_dir, "B_oracle_gate.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(
        f"[evaluate_oracle_gate] G_oracle={g_oracle:.3f} ci=[{lo:.3f},{hi:.3f}] "
        f"evaluation_n={len(evaluation)}\n  -> {output_path}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="B10: point-level oracle upper bound on the confidence gate.")
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
