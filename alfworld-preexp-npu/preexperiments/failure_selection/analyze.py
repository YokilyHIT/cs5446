"""
Final aggregation script for experiment A (spec sections 12/13/14/16: A5, A6,
A7-correlation, go/no-go). Rebuilds every statistic from ONLY the raw
JSONL/JSON files on disk -- no in-memory state from the other scripts is
required or used, so this analysis is independently reproducible from the
logs alone.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from typing import Any, Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from preexperiments.common import stats
from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config, read_jsonl_all


def _require_file(path: str, hint: str) -> None:
    if not os.path.exists(path):
        raise FileNotFoundError(f"missing input file {path}, run {hint} first.")


# ---------------------------------------------------------------------------
# A5 (section 12): per-failure mean success / delta
# ---------------------------------------------------------------------------

def compute_failure_utility(pairwise_episodes: List[Dict[str, Any]], lessons_by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_failure: Dict[str, Dict[str, List[bool]]] = {}
    for rec in pairwise_episodes:
        fid = rec["failure_id"]
        by_failure.setdefault(fid, {"no_lesson": [], "with_lesson": []})
        by_failure[fid][rec["condition"]].append(bool(rec["success"]))

    rows = []
    for fid, conditions in by_failure.items():
        no_lesson = conditions["no_lesson"]
        with_lesson = conditions["with_lesson"]
        mean_no = float(np.mean(no_lesson)) if no_lesson else float("nan")
        mean_with = float(np.mean(with_lesson)) if with_lesson else float("nan")
        delta = mean_with - mean_no
        lesson_rec = lessons_by_id.get(fid, {})
        rows.append({
            "failure_id": fid,
            "task_type": lesson_rec.get("task_type", "unknown"),
            "lesson": lesson_rec.get("lesson", ""),
            "mean_success_no_lesson": mean_no,
            "mean_success_with_lesson": mean_with,
            "delta": delta,
        })
    rows.sort(key=lambda r: r["failure_id"])
    return rows


def write_failure_utility_csv(rows: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["failure_id", "task_type", "lesson", "mean_success_no_lesson", "mean_success_with_lesson", "delta"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# A6 (section 13): delta distribution stats + histogram
# ---------------------------------------------------------------------------

def compute_delta_distribution(deltas: List[float]) -> Dict[str, float]:
    arr = np.asarray(deltas, dtype=float)
    n = len(arr)
    if n == 0:
        return {"p_delta_lt0": float("nan"), "p_delta_eq0": float("nan"), "p_delta_gt0": float("nan"), "var_delta": float("nan")}
    return {
        "p_delta_lt0": float(np.mean(arr < 0)),
        "p_delta_eq0": float(np.mean(arr == 0)),
        "p_delta_gt0": float(np.mean(arr > 0)),
        "var_delta": float(np.var(arr)),
    }


def plot_delta_histogram(deltas: List[float], path: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(deltas, bins=min(20, max(5, len(deltas) // 2)), color="#4C72B0", edgecolor="white")
    ax.set_xlabel("delta_i")
    ax.set_ylabel("count")
    ax.set_title("Per-failure lesson utility (delta = with_lesson - no_lesson success rate)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# A7 correlation (section 14): utility_proxy vs delta
# ---------------------------------------------------------------------------

def compute_proxy_correlation(
    proxy_scores: List[Dict[str, Any]],
    utility_rows: List[Dict[str, Any]],
    n_resamples: int,
    seed: int,
) -> Tuple[List[Dict[str, Any]], float, float, float, float]:
    delta_by_id = {r["failure_id"]: r["delta"] for r in utility_rows}
    rows = []
    for rec in proxy_scores:
        fid = rec["failure_id"]
        if fid not in delta_by_id:
            continue
        rows.append({
            "failure_id": fid,
            "utility_proxy": rec["utility_proxy"],
            "delta": delta_by_id[fid],
        })
    rows.sort(key=lambda r: r["failure_id"])

    if len(rows) < 2:
        return rows, float("nan"), float("nan"), float("nan"), float("nan")

    x = [r["utility_proxy"] for r in rows]
    y = [r["delta"] for r in rows]
    rho, p, lo, hi = stats.spearman_with_ci(x, y, n_resamples=n_resamples, seed=seed)
    return rows, rho, p, lo, hi


def write_proxy_correlation_csv(rows: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["failure_id", "utility_proxy", "delta"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# A8: success-rate comparison across the 4 conditions
# ---------------------------------------------------------------------------

def compute_condition_success_rates(
    topk_vs_all: List[Dict[str, Any]], n_resamples: int, seed: int
) -> Dict[str, Tuple[float, float, float]]:
    by_condition: Dict[str, List[bool]] = {}
    for rec in topk_vs_all:
        by_condition.setdefault(rec["condition"], []).append(bool(rec["success"]))

    results = {}
    for condition, values in by_condition.items():
        results[condition] = stats.bootstrap_ci(values, n_resamples=n_resamples, seed=seed)
    return results


def plot_condition_bar_chart(sr_by_condition: Dict[str, Tuple[float, float, float]], path: str) -> None:
    order = [c for c in ("NoMemory", "AllLessons", "RandomK", "TopK") if c in sr_by_condition]
    points = [sr_by_condition[c][0] for c in order]
    lo_err = [sr_by_condition[c][0] - sr_by_condition[c][1] for c in order]
    hi_err = [sr_by_condition[c][2] - sr_by_condition[c][0] for c in order]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(order, points, yerr=[lo_err, hi_err], capsize=5, color="#55A868")
    ax.set_ylabel("success rate")
    ax.set_title("A8: success rate by lesson-retrieval condition (95% bootstrap CI)")
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Go / No-Go (section 16)
# ---------------------------------------------------------------------------

def determine_verdict(p_delta_le0: float, rho_u: float, sr_diff: float) -> Tuple[str, str]:
    # Hard requirement (spec section 16): never claim "our hypothesis is
    # proven" -- the interpretation text must always use one of the exact
    # phrasings "supported by preliminary evidence" (GO), "weakly supported"
    # (WEAK-GO), or "not supported under the current setup" (NO-GO).
    if (p_delta_le0 >= 0.20 and rho_u >= 0.30) or (sr_diff >= 0.05):
        return "GO", (
            "Selective failure learning is supported by preliminary evidence: "
            f"P(delta<=0)={p_delta_le0:.2f}, rho_U={rho_u:.2f}, "
            f"SR_TopK-SR_All={sr_diff:.2f}."
        )
    if p_delta_le0 > 0 and abs(rho_u) < 0.15:
        return "WEAK-GO", (
            "Selective failure learning is weakly supported: some failures show "
            f"delta<=0 (P={p_delta_le0:.2f}), so selection matters in principle, "
            f"but the current utility proxy is weak (rho_U={rho_u:.2f}, near 0)."
        )
    if p_delta_le0 < 0.05 and sr_diff <= 0:
        return "NO-GO", (
            "Selective failure learning is not supported under the current setup: "
            f"almost all lessons show delta>0 (P(delta<=0)={p_delta_le0:.2f}) and "
            f"SR_TopK does not exceed SR_All (diff={sr_diff:.2f})."
        )
    # None of the three crisp rules fired cleanly; pick whichever verdict the
    # numbers most resemble and say so explicitly rather than forcing a fit.
    if p_delta_le0 >= 0.10 or rho_u >= 0.15 or sr_diff >= 0.0:
        return "WEAK-GO", (
            "Result pattern does not cleanly match the GO or NO-GO thresholds; "
            f"weakly supported is the closest fit given P(delta<=0)={p_delta_le0:.2f}, "
            f"rho_U={rho_u:.2f}, SR_TopK-SR_All={sr_diff:.2f}."
        )
    return "NO-GO", (
        "Result pattern does not cleanly match the GO or WEAK-GO thresholds; "
        f"not supported under the current setup is the closest fit given "
        f"P(delta<=0)={p_delta_le0:.2f}, rho_U={rho_u:.2f}, SR_TopK-SR_All={sr_diff:.2f}."
    )


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    figures_dir = config["paths"]["figures_dir"]
    ensure_dirs(results_dir, figures_dir)

    failures_file = os.path.join(results_dir, "A_failures_raw.jsonl")
    train_episodes_file = os.path.join(results_dir, "A_train_episodes_raw.jsonl")
    lessons_file = os.path.join(results_dir, "A_failure_lessons.jsonl")
    pairwise_file = os.path.join(results_dir, "A_pairwise_episodes.jsonl")
    proxy_file = os.path.join(results_dir, "A_proxy_scores.jsonl")
    topk_vs_all_file = os.path.join(results_dir, "A_topk_vs_all_raw.jsonl")

    _require_file(failures_file, "collect_failures.py")
    _require_file(lessons_file, "extract_lessons.py")
    _require_file(pairwise_file, "evaluate_single_lessons.py")
    _require_file(proxy_file, "score_failure_proxies.py")
    _require_file(topk_vs_all_file, "evaluate_topk_vs_all.py")

    failures = read_jsonl_all(failures_file)
    lessons = read_jsonl_all(lessons_file)
    lessons_by_id = {r["failure_id"]: r for r in lessons}
    pairwise_episodes = read_jsonl_all(pairwise_file)
    proxy_scores = read_jsonl_all(proxy_file)
    topk_vs_all = read_jsonl_all(topk_vs_all_file)

    train_episode_count = len(read_jsonl_all(train_episodes_file)) if os.path.exists(train_episodes_file) else None
    if train_episode_count is None:
        print(f"[analyze] WARNING: {train_episodes_file} not found; train_episode count omitted from summary.")

    n_resamples = config["stats"]["bootstrap_resamples"]
    boot_seed = config["stats"]["bootstrap_seed"]

    # --- A5 ---
    utility_rows = compute_failure_utility(pairwise_episodes, lessons_by_id)
    failure_utility_csv = os.path.join(results_dir, "A_failure_utility.csv")
    write_failure_utility_csv(utility_rows, failure_utility_csv)

    # --- A6 ---
    deltas = [r["delta"] for r in utility_rows if not np.isnan(r["delta"])]
    delta_stats = compute_delta_distribution(deltas)
    hist_path = os.path.join(figures_dir, "A_failure_utility_hist.png")
    plot_delta_histogram(deltas, hist_path)

    # --- A7 correlation ---
    proxy_corr_rows, rho_u, rho_p, rho_lo, rho_hi = compute_proxy_correlation(
        proxy_scores, utility_rows, n_resamples, boot_seed
    )
    proxy_corr_csv = os.path.join(results_dir, "A_proxy_correlation.csv")
    write_proxy_correlation_csv(proxy_corr_rows, proxy_corr_csv)

    # --- A8 ---
    sr_by_condition = compute_condition_success_rates(topk_vs_all, n_resamples, boot_seed)
    bar_chart_path = os.path.join(figures_dir, "A_topk_vs_all.png")
    plot_condition_bar_chart(sr_by_condition, bar_chart_path)

    sr_diff_point = sr_diff_lo = sr_diff_hi = float("nan")
    if "TopK" in sr_by_condition and "AllLessons" in sr_by_condition:
        topk_values = [bool(r["success"]) for r in topk_vs_all if r["condition"] == "TopK"]
        all_values = [bool(r["success"]) for r in topk_vs_all if r["condition"] == "AllLessons"]
        sr_diff_point, sr_diff_lo, sr_diff_hi = stats.bootstrap_diff_ci(
            topk_values, all_values, n_resamples=n_resamples, seed=boot_seed
        )

    # --- Go / No-Go ---
    p_delta_le0 = delta_stats["p_delta_lt0"] + delta_stats["p_delta_eq0"]
    verdict, interpretation = determine_verdict(
        p_delta_le0 if not np.isnan(p_delta_le0) else 0.0,
        rho_u if not np.isnan(rho_u) else 0.0,
        sr_diff_point if not np.isnan(sr_diff_point) else 0.0,
    )

    summary: Dict[str, Any] = {
        "data_counts": {
            "train_episodes": train_episode_count,
            "failures_collected": len(failures),
            "failures_with_lessons": len(lessons),
            "failures_evaluated_pairwise": len({r["failure_id"] for r in pairwise_episodes}),
            "pairwise_episodes": len(pairwise_episodes),
            "topk_vs_all_episodes": len(topk_vs_all),
        },
        "a6_delta_distribution": delta_stats,
        "a7_correlation": {
            "rho_u": rho_u,
            "p_value": rho_p,
            "ci_lo": rho_lo,
            "ci_hi": rho_hi,
            "n_resamples": n_resamples,
            "bootstrap_seed": boot_seed,
        },
        "a8_success_rates": {
            condition: {"point": point, "ci_lo": lo, "ci_hi": hi}
            for condition, (point, lo, hi) in sr_by_condition.items()
        },
        "a8_sr_topk_minus_all": {
            "point": sr_diff_point,
            "ci_lo": sr_diff_lo,
            "ci_hi": sr_diff_hi,
        },
        "go_no_go": {
            "p_delta_le0": p_delta_le0,
            "verdict": verdict,
            "interpretation": interpretation,
        },
    }

    summary_path = os.path.join(results_dir, "A_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(
        f"[analyze] verdict={verdict}\n"
        f"  P(delta<=0)={p_delta_le0:.3f} rho_U={rho_u:.3f} SR_TopK-SR_All={sr_diff_point:.3f}\n"
        f"  -> {failure_utility_csv}\n"
        f"  -> {proxy_corr_csv}\n"
        f"  -> {hist_path}\n"
        f"  -> {bar_chart_path}\n"
        f"  -> {summary_path}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A5/A6/A7-correlation/A8/go-no-go aggregation from raw logs."
    )
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
