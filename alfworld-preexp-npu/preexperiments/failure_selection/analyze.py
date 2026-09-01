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


def compute_trial_counts(pairwise_episodes: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[int]]]:
    """Per-failure (n, k) trial/success counts for each condition, used only
    by `simulate_luck_baseline` below (not written to any CSV)."""
    counts: Dict[str, Dict[str, List[int]]] = {}
    for rec in pairwise_episodes:
        fid = rec["failure_id"]
        c = counts.setdefault(fid, {"no_lesson": [0, 0], "with_lesson": [0, 0]})
        cell = c[rec["condition"]]
        cell[0] += 1
        cell[1] += int(bool(rec["success"]))
    return counts


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
# Luck baseline (added after review): is the observed per-failure delta
# heterogeneity distinguishable from pure chance?
# ---------------------------------------------------------------------------

def simulate_luck_baseline(
    trial_counts: Dict[str, Dict[str, List[int]]],
    observed_var_delta: float,
    observed_p_delta_le0: float,
    n_resamples: int,
    seed: int,
) -> Dict[str, Any]:
    """Fixed after review: the pipeline used to compute Var(delta) and
    P(delta<=0) across failures and treat any nonzero spread as evidence that
    "some lessons are better than others". With only 3 tasks x 3 seeds = 9
    trials per condition per failure, a meaningful-looking spread can appear
    from pure sampling noise alone -- like judging two coins from 9 flips
    each.

    This simulates the null hypothesis "no failure's lesson has any true
    effect on success probability": for each failure, pool its no_lesson and
    with_lesson trials into one success rate p_i (the failure's estimated
    task difficulty with lesson quality removed), then redraw BOTH
    conditions' outcomes from Binomial(n, p_i). Repeating this `n_resamples`
    times gives the distribution of Var(delta)/P(delta<=0) expected under
    pure chance. The returned p-values are the fraction of null replicates
    at least as extreme as the real data -- a small p-value means the real
    heterogeneity is unlikely to be chance alone.
    """
    failure_ids = [
        fid for fid, c in trial_counts.items()
        if c["no_lesson"][0] > 0 and c["with_lesson"][0] > 0
    ]
    if len(failure_ids) < 2:
        return {
            "n_failures": len(failure_ids),
            "n_simulations": n_resamples,
            "var_delta_pvalue": float("nan"),
            "p_delta_le0_pvalue": float("nan"),
            "note": "fewer than 2 failures had trials in both conditions; luck baseline not computable.",
        }

    rng = np.random.default_rng(seed)
    null_var = np.empty(n_resamples)
    null_p_le0 = np.empty(n_resamples)
    deltas = np.empty(len(failure_ids))

    for rep in range(n_resamples):
        for i, fid in enumerate(failure_ids):
            n0, k0 = trial_counts[fid]["no_lesson"]
            n1, k1 = trial_counts[fid]["with_lesson"]
            p_pool = (k0 + k1) / (n0 + n1)
            sim0 = rng.binomial(n0, p_pool) / n0
            sim1 = rng.binomial(n1, p_pool) / n1
            deltas[i] = sim1 - sim0
        null_var[rep] = np.var(deltas)
        null_p_le0[rep] = np.mean(deltas <= 0)

    return {
        "n_failures": len(failure_ids),
        "n_simulations": n_resamples,
        "var_delta_pvalue": float(np.mean(null_var >= observed_var_delta)),
        "p_delta_le0_pvalue": float(np.mean(null_p_le0 >= observed_p_delta_le0)),
        "note": (
            "p-values are the fraction of pure-chance (binomial-null) simulated replicates "
            "at least as extreme as the observed statistic; small p-value = observed "
            "heterogeneity is unlikely to be sampling noise alone."
        ),
    }


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

_MIN_FAILURES_EVALUATED = 5
_LUCK_ALPHA = 0.10  # observed heterogeneity must beat pure chance at this significance to count as "real"


def determine_verdict(
    p_delta_le0: float,
    rho_u: float,
    sr_diff: float,
    n_failures_evaluated: int,
    luck_pvalue: float,
) -> Tuple[str, str]:
    # Hard requirement (spec section 16): never claim "our hypothesis is
    # proven" -- the interpretation text must always use one of the exact
    # phrasings "supported by preliminary evidence" (GO), "weakly supported"
    # (WEAK-GO), or "not supported under the current setup" (NO-GO).
    #
    # Fixed after review: raw P(delta<=0)/rho_U thresholds alone cannot tell
    # a real effect apart from noise at n=9 trials/condition per failure --
    # two coins each flipped 9 times can easily "look" 5-vs-3 different by
    # chance. `luck_pvalue` (from simulate_luck_baseline, a binomial-null
    # simulation) estimates how likely the observed P(delta<=0) is under
    # "no failure's lesson has any true effect"; GO now additionally
    # requires this to be unlikely under pure chance (p < _LUCK_ALPHA).
    if n_failures_evaluated < _MIN_FAILURES_EVALUATED:
        return "INCONCLUSIVE", (
            f"Only {n_failures_evaluated} failures had pairwise evaluation data -- too few "
            f"(need >= {_MIN_FAILURES_EVALUATED}) to distinguish a real per-failure effect from "
            "sampling noise. Increase experiment_a.max_failures_evaluated and re-run before "
            "drawing a conclusion."
        )

    luck_ok = (not np.isnan(luck_pvalue)) and luck_pvalue < _LUCK_ALPHA
    luck_note = (
        f"luck-baseline p={luck_pvalue:.2f} (< {_LUCK_ALPHA} = distinguishable from pure chance)"
        if not np.isnan(luck_pvalue) else "luck-baseline not computable"
    )

    if sr_diff >= 0.05:
        return "GO", (
            "Selective failure learning is supported by preliminary evidence: "
            f"SR_TopK-SR_All={sr_diff:.2f} meets the 5-point bar on its own, independent of the "
            f"per-failure delta analysis (P(delta<=0)={p_delta_le0:.2f}, rho_U={rho_u:.2f})."
        )
    if p_delta_le0 >= 0.20 and rho_u >= 0.30 and luck_ok:
        return "GO", (
            "Selective failure learning is supported by preliminary evidence: "
            f"P(delta<=0)={p_delta_le0:.2f}, rho_U={rho_u:.2f}, and the observed per-failure "
            f"heterogeneity is unlikely to be pure sampling noise ({luck_note})."
        )
    if p_delta_le0 >= 0.20 and rho_u >= 0.30 and not luck_ok:
        return "WEAK-GO", (
            f"Raw thresholds are met (P(delta<=0)={p_delta_le0:.2f}, rho_U={rho_u:.2f}) but the "
            f"observed per-failure heterogeneity is NOT statistically distinguishable from a "
            f"pure-chance baseline ({luck_note}) -- weakly supported until a larger sample "
            "(more failures and/or more tasks/seeds per failure) rules out noise."
        )
    if p_delta_le0 > 0 and abs(rho_u) < 0.15:
        return "WEAK-GO", (
            "Selective failure learning is weakly supported: some failures show "
            f"delta<=0 (P={p_delta_le0:.2f}), so selection matters in principle, "
            f"but the current utility proxy is weak (rho_U={rho_u:.2f}, near 0). "
            f"({luck_note})"
        )
    if p_delta_le0 < 0.05 and sr_diff <= 0:
        return "NO-GO", (
            "Selective failure learning is not supported under the current setup: "
            f"almost all lessons show delta>0 (P(delta<=0)={p_delta_le0:.2f}) and "
            f"SR_TopK does not exceed SR_All (diff={sr_diff:.2f})."
        )
    # None of the crisp rules fired cleanly; pick whichever verdict the
    # numbers most resemble and say so explicitly rather than forcing a fit.
    if p_delta_le0 >= 0.10 or rho_u >= 0.15 or sr_diff >= 0.0:
        return "WEAK-GO", (
            "Result pattern does not cleanly match the GO or NO-GO thresholds; "
            f"weakly supported is the closest fit given P(delta<=0)={p_delta_le0:.2f}, "
            f"rho_U={rho_u:.2f}, SR_TopK-SR_All={sr_diff:.2f} ({luck_note})."
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

    # --- Luck baseline (added after review) ---
    trial_counts = compute_trial_counts(pairwise_episodes)
    p_delta_le0 = delta_stats["p_delta_lt0"] + delta_stats["p_delta_eq0"]
    luck_baseline = simulate_luck_baseline(
        trial_counts,
        observed_var_delta=delta_stats["var_delta"],
        observed_p_delta_le0=p_delta_le0 if not np.isnan(p_delta_le0) else 0.0,
        n_resamples=n_resamples,
        seed=boot_seed,
    )

    # --- Go / No-Go ---
    verdict, interpretation = determine_verdict(
        p_delta_le0 if not np.isnan(p_delta_le0) else 0.0,
        rho_u if not np.isnan(rho_u) else 0.0,
        sr_diff_point if not np.isnan(sr_diff_point) else 0.0,
        n_failures_evaluated=len(deltas),
        luck_pvalue=luck_baseline["p_delta_le0_pvalue"],
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
        "a6_luck_baseline": luck_baseline,
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
        f"  P(delta<=0)={p_delta_le0:.3f} rho_U={rho_u:.3f} SR_TopK-SR_All={sr_diff_point:.3f} "
        f"luck_baseline_pvalue={luck_baseline['p_delta_le0_pvalue']:.3f}\n"
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
