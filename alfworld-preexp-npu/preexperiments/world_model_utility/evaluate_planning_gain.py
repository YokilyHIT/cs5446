"""
Experiment B7-B9 (spec sections 27-29): lock a confidence-gate threshold on a
calibration subset, then report the mismatch rate and confidence/planning-gain
correlations on a held-out evaluation subset.

The calibration/evaluation split is BY FIXED ORDER (sorted point_id), never
random and never re-drawn across re-runs (spec section 28: "don't repeatedly
re-split at random") -- the first `calibration_points` records calibrate
`tau_c`, and everything after that is evaluation. Report both the "changed
subset" (action_changed == True, the PRIMARY analysis per spec section 27)
and "all evaluation points" versions of every correlation.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from typing import Any, Dict, List

import numpy as np

from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config, read_jsonl_all
from preexperiments.common.stats import bootstrap_ci, mcnemar_exact, spearman_with_ci


def _correlations(subset: List[Dict[str, Any]], n_resamples: int, seed: int) -> Dict[str, Any]:
    n = len(subset)
    if n < 2:
        return {
            "n": n,
            "rho_self": float("nan"),
            "rho_self_p": float("nan"),
            "rho_self_ci": [float("nan"), float("nan")],
            "rho_sem": float("nan"),
            "rho_sem_p": float("nan"),
            "rho_sem_ci": [float("nan"), float("nan")],
        }
    confidence = [r["self_confidence"] for r in subset]
    semantic = [r["semantic_correctness"] for r in subset]
    gain = [r["planning_gain"] for r in subset]
    rho_self, p_self, lo_self, hi_self = spearman_with_ci(confidence, gain, n_resamples=n_resamples, seed=seed)
    rho_sem, p_sem, lo_sem, hi_sem = spearman_with_ci(semantic, gain, n_resamples=n_resamples, seed=seed)
    return {
        "n": n,
        "rho_self": rho_self,
        "rho_self_p": p_self,
        "rho_self_ci": [lo_self, hi_self],
        "rho_sem": rho_sem,
        "rho_sem_p": p_sem,
        "rho_sem_ci": [lo_sem, hi_sem],
    }


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    ensure_dirs(results_dir)

    branches_path = os.path.join(results_dir, "B_branches_raw.jsonl")
    if not os.path.exists(branches_path):
        raise FileNotFoundError(f"missing input file {branches_path}, run build_counterfactual_pairs.py first.")

    records = read_jsonl_all(branches_path)
    if not records:
        raise RuntimeError(f"{branches_path} contains no records; nothing to do.")
    records.sort(key=lambda r: r["point_id"])

    eb_cfg = config["experiment_b"]
    stats_cfg = config["stats"]
    # Spec section 28 fixes this at "first 50 of 150 points". The override
    # exists only so a reduced-size smoke run (10 points) can still exercise
    # this script and everything downstream of it -- with the config value of
    # 50, a 10-point run puts every point in calibration, leaves evaluation
    # empty, and evaluate_oracle_gate.py/analyze.py abort before they are ever
    # tested. Real runs must leave it unset and use the config value.
    calibration_target = args.calibration_points or eb_cfg["calibration_points"]
    target_usage = eb_cfg["confidence_gate_target_usage"]

    calibration = records[:calibration_target]
    evaluation = records[calibration_target:]
    if len(calibration) < calibration_target:
        print(
            f"[evaluate_planning_gain] warning: only {len(calibration)}/{calibration_target} "
            f"calibration points available (fewer decision points survived restore than planned)."
        )
    if not evaluation:
        print("[evaluate_planning_gain] warning: evaluation subset is empty.")

    # tau_c is picked so that the fraction of calibration points at/above it
    # is as close as possible to `target_usage`: that fraction is exactly
    # `1 - quantile_level`, so tau_c = the (1 - target_usage) quantile of the
    # calibration confidences (target_usage=0.5 -> tau_c = median).
    confidences = [r["self_confidence"] for r in calibration]
    tau_c = float(np.quantile(confidences, 1 - target_usage)) if confidences else 0.5

    tau_c_path = os.path.join(results_dir, "B_tau_c.json")
    with open(tau_c_path, "w", encoding="utf-8") as f:
        json.dump({"tau_c": tau_c, "target_usage": target_usage, "calibration_n": len(calibration)}, f, indent=2)

    changed_eval = [r for r in evaluation if r["action_changed"]]
    n_changed = len(changed_eval)
    n_resamples = stats_cfg["bootstrap_resamples"]
    seed = stats_cfg["bootstrap_seed"]

    if n_changed > 0:
        n_high_conf_harmful = sum(1 for r in changed_eval if r["self_confidence"] >= tau_c and r["planning_gain"] == -1)
        n_low_conf_helpful = sum(1 for r in changed_eval if r["self_confidence"] < tau_c and r["planning_gain"] == 1)
        r_mismatch = (n_high_conf_harmful + n_low_conf_helpful) / n_changed
        # Spec section 35 asks for a bootstrap 95% CI on paired-success
        # comparisons; R_mismatch is itself a mean of a per-point 0/1
        # indicator (mismatch or not), so the same machinery applies directly.
        mismatch_indicator = [
            1
            if (r["self_confidence"] >= tau_c and r["planning_gain"] == -1)
            or (r["self_confidence"] < tau_c and r["planning_gain"] == 1)
            else 0
            for r in changed_eval
        ]
        _, r_mismatch_ci_lo, r_mismatch_ci_hi = bootstrap_ci(
            mismatch_indicator, n_resamples=n_resamples, seed=seed
        )
    else:
        n_high_conf_harmful = n_low_conf_helpful = 0
        r_mismatch = float("nan")
        r_mismatch_ci_lo = r_mismatch_ci_hi = float("nan")

    # Spec section 35 ("对于paired success：优先额外报告McNemar exact test"): the
    # paired comparison here is base_success vs foresight_success on the SAME
    # decision point. b/c are the two discordant-pair counts -- these are
    # exactly the planning_gain=-1/+1 counts over the evaluation set (points
    # with planning_gain=0, including all unchanged-action points now that
    # build_counterfactual_pairs.py skips re-running Branch W for them, are
    # concordant and contribute nothing to McNemar by construction).
    n_harmful_all = sum(1 for r in evaluation if r["planning_gain"] == -1)
    n_helpful_all = sum(1 for r in evaluation if r["planning_gain"] == 1)
    mcnemar_p = mcnemar_exact(n_harmful_all, n_helpful_all) if evaluation else float("nan")

    changed_corr = _correlations(changed_eval, n_resamples, seed)
    all_corr = _correlations(evaluation, n_resamples, seed)

    output = {
        "calibration_n": len(calibration),
        "evaluation_n": len(evaluation),
        "changed_n_eval": n_changed,
        "tau_c": tau_c,
        "target_usage": target_usage,
        "R_mismatch": r_mismatch,
        "R_mismatch_ci": [r_mismatch_ci_lo, r_mismatch_ci_hi],
        "n_high_conf_harmful": n_high_conf_harmful,
        "n_low_conf_helpful": n_low_conf_helpful,
        "n_harmful_all_eval": n_harmful_all,
        "n_helpful_all_eval": n_helpful_all,
        "mcnemar_p_value": mcnemar_p,
        "rho_self_changed": changed_corr["rho_self"],
        "rho_self_changed_p": changed_corr["rho_self_p"],
        "rho_self_changed_ci": changed_corr["rho_self_ci"],
        "rho_sem_changed": changed_corr["rho_sem"],
        "rho_sem_changed_p": changed_corr["rho_sem_p"],
        "rho_sem_changed_ci": changed_corr["rho_sem_ci"],
        "rho_self_all": all_corr["rho_self"],
        "rho_self_all_p": all_corr["rho_self_p"],
        "rho_self_all_ci": all_corr["rho_self_ci"],
        "rho_sem_all": all_corr["rho_sem"],
        "rho_sem_all_p": all_corr["rho_sem_p"],
        "rho_sem_all_ci": all_corr["rho_sem_ci"],
    }

    stats_path = os.path.join(results_dir, "B_evaluation_stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    r_mismatch_str = "nan" if math.isnan(r_mismatch) else f"{r_mismatch:.3f}"
    print(
        f"[evaluate_planning_gain] tau_c={tau_c:.3f} calibration_n={len(calibration)} "
        f"evaluation_n={len(evaluation)} changed_n_eval={n_changed} R_mismatch={r_mismatch_str}\n"
        f"  -> {tau_c_path}\n  -> {stats_path}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="B7-B9: confidence-gate calibration, mismatch rate, confidence/gain correlations."
    )
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    parser.add_argument(
        "--calibration_points",
        type=int,
        default=None,
        help="Override experiment_b.calibration_points (smoke tests only; real runs use the config value).",
    )
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
