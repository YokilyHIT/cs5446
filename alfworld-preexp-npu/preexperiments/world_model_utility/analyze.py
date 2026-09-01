"""
Experiment B final aggregation (spec sections 32-34): rebuild the mandatory
CSV and figures from the raw JSONL/JSON files on disk only -- this script
reshapes/plots what the earlier scripts already computed, it does not
recompute statistics itself except for the few counts (helpful/harmful rate,
per-bucket ambiguity rates) that aren't already persisted anywhere -- and
produces a single go/no-go verdict for the "prediction confidence tracks
planning utility" hypothesis.

Phrasing constraint (spec section 34): the verdict/interpretation text must
use ONLY "supported by preliminary evidence" / "weakly supported" / "not
supported under the current setup" -- never claim a hypothesis is "proven".
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from typing import Any, Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config, read_jsonl_all

_CSV_COLUMNS = [
    "point_id", "task_id", "step", "base_action", "foresight_action",
    "action_changed", "wm_prediction", "self_confidence", "semantic_correctness",
    "base_success", "foresight_success", "planning_gain", "ambiguity",
]


def _write_csv(records: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for r in records:
            writer.writerow({col: r[col] for col in _CSV_COLUMNS})


def _ambiguity_bucket(a: float) -> str:
    if a == 0:
        return "Low: A=0"
    if a <= 0.5:
        return "Medium: 0<A<=0.5"
    return "High: A>0.5"


def _plot_confidence_vs_gain(records: List[Dict[str, Any]], path: str) -> None:
    confidence = np.array([r["self_confidence"] for r in records], dtype=float)
    gain = np.array([r["planning_gain"] for r in records], dtype=float)
    rng = np.random.default_rng(2026)
    jitter = rng.uniform(-0.08, 0.08, size=len(gain))

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.scatter(confidence, gain + jitter, alpha=0.6, s=25)
    ax.set_xlabel("Self-reported confidence")
    ax.set_ylabel("Planning gain (jittered for visibility)")
    ax.set_yticks([-1, 0, 1])
    ax.set_title("Confidence vs planning gain\n(y jittered for display; true values are discrete {-1,0,1})")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_mismatch_matrix(changed_eval: List[Dict[str, Any]], tau_c: float, path: str) -> None:
    high = [r for r in changed_eval if r["self_confidence"] >= tau_c]
    low = [r for r in changed_eval if r["self_confidence"] < tau_c]
    matrix = np.array(
        [
            [sum(1 for r in high if r["planning_gain"] == -1), sum(1 for r in high if r["planning_gain"] == 1)],
            [sum(1 for r in low if r["planning_gain"] == -1), sum(1 for r in low if r["planning_gain"] == 1)],
        ]
    )

    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["harmful (gain=-1)", "helpful (gain=+1)"])
    ax.set_yticks([0, 1])
    ax.set_yticklabels([f"high-confidence (>={tau_c:.2f})", f"low-confidence (<{tau_c:.2f})"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(int(matrix[i, j])), ha="center", va="center", color="black")
    ax.set_title("Confidence x outcome mismatch matrix\n(changed-action, evaluation subset; gain=0 excluded)")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _plot_gain_by_ambiguity(changed_records: List[Dict[str, Any]], path: str) -> None:
    buckets = ["Low: A=0", "Medium: 0<A<=0.5", "High: A>0.5"]
    helpful_rates = []
    harmful_rates = []
    for b in buckets:
        subset = [r for r in changed_records if _ambiguity_bucket(r["ambiguity"]) == b]
        n = len(subset)
        helpful_rates.append(sum(1 for r in subset if r["planning_gain"] == 1) / n if n else 0.0)
        harmful_rates.append(sum(1 for r in subset if r["planning_gain"] == -1) / n if n else 0.0)

    x = np.arange(len(buckets))
    width = 0.35
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.bar(x - width / 2, helpful_rates, width, label="P(gain=+1) helpful", color="#4c72b0")
    ax.bar(x + width / 2, harmful_rates, width, label="P(gain=-1) harmful", color="#c44e52")
    ax.set_xticks(x)
    ax.set_xticklabels(buckets)
    ax.set_ylabel("Rate within bucket (changed-action subset)")
    ax.set_title("Foresight helpful/harmful rate by action-ambiguity bucket")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _fmt(x: Any) -> str:
    return "nan" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.3f}"


_MIN_CHANGED_POINTS = 10
_MIN_ANY_SUCCESS_RATE = 0.05


def _check_inconclusive(
    n_changed_eval: int, any_success_rate: float
) -> Tuple[bool, str]:
    """Fixed after review: a near-zero mismatch rate and near-zero oracle
    gain can mean either (a) confidence really does track planning utility
    here, or (b) this run never actually generated enough signal to tell --
    e.g. almost nothing in the changed-action evaluation subset ever
    succeeds via EITHER branch, so `planning_gain` is 0 everywhere by
    construction, not because foresight is harmless. Those two situations
    must not both collapse into "not supported under the current setup" --
    that phrasing claims evidence AGAINST the hypothesis, whereas the second
    situation has no evidence either way. This checks for the second
    situation and returns a distinct INCONCLUSIVE verdict when it applies,
    instead of letting `_go_no_go` interpret silence as a negative result.
    """
    if n_changed_eval < _MIN_CHANGED_POINTS:
        return True, (
            f"Only {n_changed_eval} action-changed decision points fell in the evaluation "
            f"subset (need at least {_MIN_CHANGED_POINTS} for the mismatch-rate/correlation "
            "statistics to be meaningful) -- increase eval_episodes/decision_points_per_episode "
            "or relax the ambiguity/history filters in collect_decision_points.py and re-run "
            "before drawing a go/no-go conclusion."
        )
    if (not math.isnan(any_success_rate)) and any_success_rate < _MIN_ANY_SUCCESS_RATE:
        return True, (
            f"Only {any_success_rate:.1%} of evaluation decision points ever reached success via "
            "EITHER branch (base or foresight) -- planning_gain is ~0 everywhere not because "
            "foresight is harmless, but because the base model essentially never completes these "
            "tasks within max_episode_steps. This run cannot distinguish 'no mismatch exists' from "
            "'the model is too weak to generate any signal to measure'. Raise max_episode_steps, "
            "use an easier eval subset, or use a stronger base model before re-running."
        )
    return False, ""


def _go_no_go(r_mismatch: float, oracle_gain: float, rho_self: float) -> Tuple[str, str]:
    conditions = {
        "R_mismatch>=0.15": (not math.isnan(r_mismatch)) and r_mismatch >= 0.15,
        "G_oracle>=0.05": (not math.isnan(oracle_gain)) and oracle_gain >= 0.05,
        "rho_self<0.70": (not math.isnan(rho_self)) and rho_self < 0.70,
    }
    n_hold = sum(conditions.values())
    summary = f"mismatch_rate={_fmt(r_mismatch)}, oracle_gain={_fmt(oracle_gain)}, rho_self={_fmt(rho_self)}"

    # verdict is a short machine-readable tag (GO/WEAK-GO/NO-GO), matching
    # experiment A's convention -- generate_report.py's recommendation logic
    # keys off this tag. The required phrasing ("supported by preliminary
    # evidence" / "weakly supported" / "not supported under the current
    # setup") always appears in `interpretation` instead, never in `verdict`.
    if (not math.isnan(r_mismatch)) and (not math.isnan(oracle_gain)) and r_mismatch < 0.02 and oracle_gain < 0.01:
        verdict = "NO-GO"
        interpretation = (
            f"Both the mismatch rate and the oracle upper-bound gain are near zero ({summary}), "
            "leaving essentially no room for confidence-gated foresight to help over the base "
            "planner on this evaluation subset. Not supported under the current setup -- stop "
            "direction B."
        )
    elif n_hold >= 2:
        verdict = "GO"
        interpretation = (
            f"{n_hold}/3 go/no-go criteria hold ({summary}). Supported by preliminary evidence -- "
            "meets the strong-support bar for pursuing direction B further."
        )
    elif n_hold == 1:
        verdict = "WEAK-GO"
        interpretation = (
            f"Only {n_hold}/3 go/no-go criteria hold ({summary}); weakly supported by preliminary "
            "evidence and any follow-up should proceed cautiously."
        )
    else:
        verdict = "NO-GO"
        interpretation = f"None of the go/no-go criteria hold ({summary}); not supported under the current setup."

    return verdict, interpretation


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    figures_dir = config["paths"]["figures_dir"]
    ensure_dirs(results_dir, figures_dir)

    branches_path = os.path.join(results_dir, "B_branches_raw.jsonl")
    foresight_path = os.path.join(results_dir, "B_foresight_raw.jsonl")
    eval_stats_path = os.path.join(results_dir, "B_evaluation_stats.json")
    oracle_path = os.path.join(results_dir, "B_oracle_gate.json")
    tau_c_path = os.path.join(results_dir, "B_tau_c.json")

    for p in (branches_path, eval_stats_path, oracle_path, tau_c_path):
        if not os.path.exists(p):
            raise FileNotFoundError(f"missing input file {p}, run the earlier experiment B scripts first.")

    records = read_jsonl_all(branches_path)
    if not records:
        raise RuntimeError(f"{branches_path} contains no records; nothing to do.")
    records.sort(key=lambda r: r["point_id"])

    # B_foresight_raw.jsonl carries no field that isn't already merged into
    # B_branches_raw.jsonl (every column analyze.py needs is already there);
    # it is only read here to report how many collected points did NOT
    # survive restore_state(), which is useful context but not itself an
    # output file.
    foresight_records = read_jsonl_all(foresight_path) if os.path.exists(foresight_path) else []
    restored_ids = {r["point_id"] for r in records}
    n_not_restored = sum(1 for r in foresight_records if r["point_id"] not in restored_ids)

    with open(eval_stats_path, "r", encoding="utf-8") as f:
        eval_stats = json.load(f)
    with open(oracle_path, "r", encoding="utf-8") as f:
        oracle_stats = json.load(f)
    with open(tau_c_path, "r", encoding="utf-8") as f:
        tau_c = json.load(f)["tau_c"]

    csv_path = os.path.join(results_dir, "B_world_model_utility.csv")
    _write_csv(records, csv_path)

    # Same fixed split as evaluate_planning_gain.py/evaluate_oracle_gate.py:
    # sorted point_id, skip the first calibration_points.
    calibration_target = config["experiment_b"]["calibration_points"]
    evaluation = records[calibration_target:]
    changed_eval = [r for r in evaluation if r["action_changed"]]
    changed_all = [r for r in records if r["action_changed"]]

    fig1 = os.path.join(figures_dir, "B_confidence_vs_gain.png")
    fig2 = os.path.join(figures_dir, "B_mismatch_matrix.png")
    fig3 = os.path.join(figures_dir, "B_gain_by_ambiguity.png")
    _plot_confidence_vs_gain(records, fig1)
    _plot_mismatch_matrix(changed_eval, tau_c, fig2)
    _plot_gain_by_ambiguity(changed_all, fig3)

    n_changed_eval = len(changed_eval)
    helpful_rate = (
        sum(1 for r in changed_eval if r["planning_gain"] == 1) / n_changed_eval if n_changed_eval else float("nan")
    )
    harmful_rate = (
        sum(1 for r in changed_eval if r["planning_gain"] == -1) / n_changed_eval if n_changed_eval else float("nan")
    )
    any_success_rate = (
        sum(1 for r in evaluation if r["base_success"] or r["foresight_success"]) / len(evaluation)
        if evaluation else float("nan")
    )

    r_mismatch = eval_stats["R_mismatch"]
    rho_self = eval_stats["rho_self_changed"]
    rho_self_ci = eval_stats["rho_self_changed_ci"]
    rho_sem = eval_stats["rho_sem_changed"]
    rho_sem_ci = eval_stats["rho_sem_changed_ci"]
    oracle_gain = oracle_stats["G_oracle"]
    oracle_gain_ci = oracle_stats["G_oracle_ci"]

    is_inconclusive, inconclusive_reason = _check_inconclusive(n_changed_eval, any_success_rate)
    if is_inconclusive:
        verdict, interpretation = "INCONCLUSIVE", inconclusive_reason
    else:
        verdict, interpretation = _go_no_go(r_mismatch, oracle_gain, rho_self)

    summary = {
        "decision_points": len(records),
        "changed_points": len(changed_all),
        "calibration_points": eval_stats["calibration_n"],
        "evaluation_points": eval_stats["evaluation_n"],
        "mismatch_rate": r_mismatch,
        "rho_self": rho_self,
        "rho_self_ci": rho_self_ci,
        "rho_sem": rho_sem,
        "rho_sem_ci": rho_sem_ci,
        "oracle_gain": oracle_gain,
        "oracle_gain_ci": oracle_gain_ci,
        "helpful_rate": helpful_rate,
        "harmful_rate": harmful_rate,
        "any_success_rate_eval": any_success_rate,
        "verdict": verdict,
        "interpretation": interpretation,
    }

    summary_path = os.path.join(results_dir, "B_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(
        f"[analyze] decision_points={len(records)} changed_points={len(changed_all)} "
        f"not_restored={n_not_restored} verdict={verdict!r}\n"
        f"  -> {csv_path}\n  -> {fig1}\n  -> {fig2}\n  -> {fig3}\n  -> {summary_path}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Final aggregation: CSV, figures, go/no-go verdict.")
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
