"""Render the four baseline figures from existing aggregate JSON only.

No experiment, checker, inference procedure, or project analysis code is run.
Requires Python and matplotlib. Run from any directory:
    python -B path/to/figures/plot_baseline.py
The source JSON paths are resolved relative to this repository: the team repository
layout (report_4b/figures) or the original local project layout. PNG and SVG
outputs plus figure_sources.json are written next to this script.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import sys

import matplotlib
import numpy

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


OUT = Path(__file__).resolve().parent
LAYOUTS = (  # (base, D0 report JSON, E analysis JSON); the first complete layout is used
    (OUT.parents[1], "gpu_analysis/checkpoints/d0_report.json", "aim3_e/results/analysis.public.json"),
    (OUT.parents[3], ".review-cache/github-gpu-20261015/gpu_analysis/checkpoints/d0_report.json",
     "cs5446_modified/research_progress/2026-10-18-aim3-e-run/analysis.json"),
)
PROJECT, D0_PATH, E_PATH = next((base, base / d0, base / e) for base, d0, e in LAYOUTS
                                if (base / d0).is_file() and (base / e).is_file())
D0 = json.loads(D0_PATH.read_text(encoding="utf-8"))
E = json.loads(E_PATH.read_text(encoding="utf-8"))
BLUE, ORANGE, GREEN = "#0072B2", "#D55E00", "#009E73"
GRAY, INK = "#707780", "#17212B"
ARM_ORDER = ["always", "no_info", "none"]
ARM_LABELS = ["Always", "no_info", "none"]
ARM_COLORS = [BLUE, GREEN, GRAY]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#ADB4BB",
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "svg.fonttype": "none",
    "svg.hashsalt": "cs5446-4b-baseline-v1",
})

PROVENANCE = {
    "purpose": "Presentation of existing frozen aggregate outputs; no new inference.",
    "sources": {
        "D0": {"path": D0_PATH.relative_to(PROJECT).as_posix(), "sha256": hashlib.sha256(D0_PATH.read_bytes()).hexdigest()},
        "E": {"path": E_PATH.relative_to(PROJECT).as_posix(), "sha256": hashlib.sha256(E_PATH.read_bytes()).hexdigest()},
    },
    "public_copies": {"D0": "gpu_analysis/checkpoints/d0_report.json", "E": "aim3_e/results/analysis.public.json"},
    "rendering": {"python": platform.python_version(), "matplotlib": matplotlib.__version__,
                  "numpy": numpy.__version__, "backend": matplotlib.get_backend(),
                  "environment": Path(sys.prefix).name},
    "figures": {},
}


def save(fig, name, title, description, data):
    """Write formats without timestamps; SVG retains selectable text."""
    fig.savefig(OUT / f"{name}.png", dpi=220, metadata={"Title": title, "Description": description})
    fig.savefig(OUT / f"{name}.svg", metadata={"Title": title, "Description": description, "Date": None})
    plt.close(fig)
    PROVENANCE["figures"][name] = {"title": title, "description": description, **data}


def foot(fig, text):
    fig.text(0.075, 0.035, text, ha="left", va="bottom", fontsize=9, color="#46515D", linespacing=1.5)


def title(fig, text):
    fig.suptitle(text, x=0.075, y=0.965, ha="left", fontsize=17, fontweight="bold")


def grid(ax):
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#E6E9ED", linewidth=0.7)


def plot_action_outcome():
    keys = ["admission", "info", "revision"]
    labels = ["P - D\nwith prediction vs draft", "P - N\nwith vs without prediction", "N - D\nredecision vs draft"]
    action = D0["integrity"]["action_changes_unweighted"]
    outcomes = D0["integrity"]["observed_difference_counts_unweighted"]
    counts = []
    for key in keys:
        values = outcomes[key]
        comparable = sum(n for value, n in values.items() if value != "None")
        changed = sum(n for value, n in values.items() if value not in ("0", "None"))
        counts.append({"comparison": key, "actions_changed": action[key]["changed"],
                       "actions_comparable": action[key]["comparable"],
                       "terminal_outcomes_changed": changed, "terminal_outcomes_comparable": comparable})
    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    fig.subplots_adjust(left=.085, right=.97, top=.82, bottom=.27)
    title(fig, "D0: changed actions rarely change the terminal outcome")
    width = .33
    for offset, numerator, denominator, color, label in [
        (-width/2, "actions_changed", "actions_comparable", BLUE, "First action changed (parsable pairs)"),
        (width/2, "terminal_outcomes_changed", "terminal_outcomes_comparable", ORANGE, "Observed terminal outcome changed"),
    ]:
        vals = [100 * row[numerator] / row[denominator] for row in counts]
        bars = ax.bar([i + offset for i in range(3)], vals, width, color=color, label=label)
        for bar, row, val in zip(bars, counts, vals):
            ax.text(bar.get_x()+bar.get_width()/2, val+1.1,
                    f"{row[numerator]}/{row[denominator]}\n({val:.1f}%)", ha="center", va="bottom", fontsize=10)
    ax.set_xticks(range(3), labels)
    ax.set_ylabel("Unweighted proportion of comparable states (%)")
    ax.set_ylim(0, 60)
    ax.legend(loc="upper right", frameon=False, fontsize=10)
    grid(ax)
    foot(fig, "24 development games; 68 complete D/N/P states; one continuation per physical group (r = 1).\n"
         "D: execute the draft. N: redecide without prediction. P: redecide with prediction.\n"
         "Three source-draft failures remain missing. A nonparsable N action reduces action-pair denominators only; its outcome remains 0.")
    save(fig, "01_d0_action_outcome", "D0 actions and terminal outcomes", "Unweighted descriptive counts, not an inferential comparison.", {
        "fields": ["integrity.action_changes_unweighted", "integrity.observed_difference_counts_unweighted"], "values": counts,
        "denominator_note": "Action pairs involving N exclude one nonparsable action; outcome pairs retain it. All three source-draft failures remain missing.",
    })


def plot_confidence():
    metrics = D0["metrics"]
    bins = metrics["confidence_bins"]
    x = list(range(4))
    em = [b["summary"]["accuracy"]["EM"]["mean"] for b in bins]
    f1 = [b["summary"]["accuracy"]["token_F1"]["mean"] for b in bins]
    utility = {key: [b["summary"]["observed_U"][key]["mean"] for b in bins] for key in ["admission", "info", "revision"]}
    rel = metrics["relationships"]["confidence_accuracy"]
    rank = metrics["ranking_diagnostics"]["confidence"]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 6.8))
    fig.subplots_adjust(left=.075, right=.975, top=.78, bottom=.27, wspace=.28)
    title(fig, "D0: confidence ranks prediction accuracy; utility is sparse")
    ax.set_title("a  Textual prediction accuracy", loc="left", pad=12)
    for vals, color, marker, label in [(em, BLUE, "o", "Exact match (EM)"), (f1, GREEN, "s", "Token F1")]:
        ax.plot(x, vals, color=color, marker=marker, linewidth=2, markersize=6, label=label)
        for xi, val in zip(x, vals):
            ax.annotate(f"{val:.3f}", (xi, val), xytext=(0, 10 if label == "Token F1" else -16), textcoords="offset points", ha="center", color=color, fontsize=10)
    ax.set_ylim(-.08, 1.04)
    ax.set_ylabel("Weighted mean textual match")
    ax.legend(loc="lower left", frameon=False, fontsize=10)
    ax.text(.01, 1.11, f"Weighted rank correlation: EM {rel['EM']['spearman']:.3f}; F1 {rel['token_F1']['spearman']:.3f}", transform=ax.transAxes, fontsize=10)
    bx.set_title("b  Observed terminal-outcome differences", loc="left", pad=12)
    width = .23
    for offset, key, color, label in [(-width,"admission",BLUE,"P - D"), (0,"info",ORANGE,"P - N"), (width,"revision",GREEN,"N - D")]:
        vals=utility[key]
        bx.bar([i+offset for i in x], vals, width, color=color, label=label, zorder=3)
        bx.scatter([i+offset for i,v in zip(x, vals) if v==0], [0 for v in vals if v==0], color=color, s=18, zorder=4)
    bx.axhline(0, color=GRAY, linewidth=1)
    bx.set_ylim(-.085, .085)
    bx.set_yticks([-.06, -.03, 0, .03, .06])
    bx.set_ylabel("Weighted mean observed Y difference")
    bx.legend(loc="upper left", frameon=False, ncol=3, fontsize=10, handlelength=1.2, columnspacing=1.1)
    bx.text(.01, 1.11, "P - D: one negative state in group 2; no positive state", transform=bx.transAxes, fontsize=10)
    bx.annotate("-0.058", (1-width, utility["admission"][1]), xytext=(-9, -14), textcoords="offset points", ha="center", color=BLUE, fontsize=10)
    bx.annotate("+0.058", (3, utility["info"][3]), xytext=(0, 8), textcoords="offset points", ha="center", color=ORANGE, fontsize=10)
    bx.annotate("-0.058", (3+width, utility["revision"][3]), xytext=(0, -14), textcoords="offset points", ha="center", color=GREEN, fontsize=10)
    for panel in (ax, bx):
        panel.set_xticks(x, ["1\nHighest", "2", "3", "4\nLowest"])
        panel.set_xlabel("Confidence group (descending mean log probability)")
        grid(panel)
    foot(fig, "68 qualified states in 24 development games; r = 1. Original weights: 1/(24 k_j), normalized within the qualified set.\n"
         "Each group contains 25% of qualified weight; boundary/tie mass is split, so group membership counts cannot be added.\n"
         f"Descriptive only. Confidence G_admission = {rank['G']['admission']:.4f}; analytic random-ranking G_admission = {rank['analytic_Random_G']['admission']:.0f}. No new intervals or tests.")
    save(fig, "02_d0_confidence", "D0 confidence, prediction accuracy and observed utility", "Frozen weighted quartile summaries and descriptive rank correlation.", {
        "fields": ["metrics.confidence_bins[*].summary.accuracy", "metrics.confidence_bins[*].summary.observed_U", "metrics.relationships.confidence_accuracy.*.spearman", "metrics.ranking_diagnostics.confidence.G", "metrics.ranking_diagnostics.confidence.analytic_Random_G"],
        "order": "descending_mean_logprob", "EM": em, "token_F1": f1, "observed_U": utility,
        "spearman_definition": rel["EM"]["spearman_definition"],
        "weighted_rank_correlations": {k: rel[k]["spearman"] for k in ["EM", "token_F1"]},
        "G_admission": rank["G"]["admission"], "random_G_admission": rank["analytic_Random_G"]["admission"],
        "bin_denominators": [b["summary"]["denominator"] for b in bins],
    })


def plot_e_outcomes():
    arms = E["arm_outcomes"]
    primary = E["comparisons"]["always_minus_no_info"]
    ci = primary["intervals"]["0.975"]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(12, 6.6), gridspec_kw={"width_ratios": [1, 1.15]})
    fig.subplots_adjust(left=.075, right=.97, top=.80, bottom=.26, wspace=.28)
    title(fig, "E: the primary success-rate difference remains unresolved")
    ax.set_title("a  Success at 30 environment steps", loc="left", pad=18)
    values = [100*arms[a]["study_success_rate"] for a in ARM_ORDER]
    ax.bar(range(3), values, color=ARM_COLORS, width=.62)
    for i, (a, val) in enumerate(zip(ARM_ORDER, values)):
        arm_ci=arms[a]["study_success_rate_ci95"]
        ax.errorbar(i, val, yerr=[[val-100*arm_ci['low']], [100*arm_ci['high']-val]], fmt="none", color=INK, capsize=5, linewidth=1.3)
        ax.text(i, 100*arm_ci['high']+1, f"{arms[a]['study_successes']}/{arms[a]['planned']}\n{val:.2f}%", ha="center", va="bottom", fontsize=10)
    ax.set_xticks(range(3), ARM_LABELS)
    ax.set_ylim(0, 34)
    ax.set_ylabel("SR@30 (%)")
    grid(ax)
    ax.text(.02, .96, "Bars: observed SR; whiskers: existing 95% Wilson CI", transform=ax.transAxes, fontsize=9, va="top")
    bx.set_title("b  Primary paired contrast: Always - no_info", loc="left", pad=18)
    estimate, low, high = [100*v for v in [primary["difference"], ci["low"], ci["high"]]]
    bx.axvline(0, color=GRAY, linestyle="--", linewidth=1.1)
    bx.errorbar(estimate, 0, xerr=[[estimate-low], [high-estimate]], fmt="o", color=BLUE, markersize=9, capsize=8, linewidth=2.4)
    bx.text(estimate, .21, f"{estimate:+.2f} pp", ha="center", color=BLUE, fontsize=13, fontweight="bold", bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
    bx.text(low, -.14, f"{low:.2f}", ha="center", fontsize=11)
    bx.text(high, -.14, f"+{high:.2f}", ha="center", fontsize=11)
    bx.set_xlim(-17, 18)
    bx.set_ylim(-.6, .62)
    bx.set_yticks([])
    bx.spines['left'].set_visible(False)
    bx.set_xlabel("Difference in SR@30 (percentage points)")
    bx.text(.5, .94, "97.5% conservative paired interval", transform=bx.transAxes, ha="center", fontsize=11, bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
    n_pairs = primary["n_planned_pairs"]
    rescued, harmed = primary["observed_rescued"], primary["observed_harmed"]
    n_differ = rescued + harmed
    bx.text(.5, .14, f"direction = {ci['direction']}\n{n_pairs-n_differ}/{n_pairs} pairs agree; {n_differ} differ ({rescued} rescued, {harmed} harmed)", transform=bx.transAxes, ha="center", fontsize=10, linespacing=1.5, bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
    foot(fig, "134 fixed candidate unseen games; 402 arm episodes. Planner content failures count as 0; no missing outcomes.\n"
         "Primary interval copied from the frozen analysis: Clopper-Pearson rescue/harm bounds with Bonferroni adjustment.\n"
         "Historical use of E is unverified. Arithmetic availability does not certify untouched evaluation; non-significance is not equivalence.")
    save(fig, "03_e_outcomes", "E success rates and primary paired interval", "All intervals copied from the existing frozen analysis; no interval is recomputed.", {
        "fields": ["arm_outcomes.*.study_successes", "arm_outcomes.*.planned", "arm_outcomes.*.study_success_rate", "arm_outcomes.*.study_success_rate_ci95", "comparisons.always_minus_no_info"],
        "arm_order": ARM_ORDER, "successes": [arms[a]["study_successes"] for a in ARM_ORDER], "success_rates": [arms[a]["study_success_rate"] for a in ARM_ORDER],
        "primary_difference": primary["difference"], "primary_interval": ci,
        "n_pairs": primary["n_planned_pairs"], "rescued": primary["observed_rescued"], "harmed": primary["observed_harmed"],
        "history_eligibility": E["history_eligibility"],
    })


def plot_cost():
    cost = E["selected_cost_by_arm"]
    fig, axs = plt.subplots(1, 2, figsize=(11.8, 6.3))
    fig.subplots_adjust(left=.085, right=.97, top=.78, bottom=.27, wspace=.27)
    title(fig, "E: Always uses more model requests and request time")
    records = {}
    for ax, key, subtitle, ylabel in [
        (axs[0], "logical_calls", "a  Recorded model calls", "Logical model calls"),
        (axs[1], "sum_known_request_elapsed_s", "b  Sum of known request elapsed time", "Request elapsed time (seconds)"),
    ]:
        vals=[cost[a]["known_components"][key] for a in ARM_ORDER]
        ratios=[v/vals[-1] for v in vals]
        records[key]={"values": vals, "relative_to_none": ratios}
        ax.bar(range(3), vals, color=ARM_COLORS, width=.62)
        for i,(v,ratio) in enumerate(zip(vals, ratios)):
            ax.text(i, v+max(vals)*.035, f"{v:,.0f}\n{ratio:.2f}x none", ha="center", va="bottom", fontsize=11)
        ax.set_xticks(range(3),ARM_LABELS)
        ax.set_ylabel(ylabel)
        ax.set_title(subtitle,loc="left",pad=18)
        ax.set_ylim(0,max(vals)*1.28)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x,p:f"{x:,.0f}"))
        grid(ax)
    foot(fig, "Totals across 134 games per arm. Always includes draft planning, the world model, and redecision.\n"
         "Known request elapsed times exclude environment execution, setup, teardown and queue time; they are not GPU wall time.\n"
         "All selected attempts are attempt 1. No unknown timing is imputed as zero; all calls in these selected totals have recorded latency.")
    save(fig, "04_e_cost", "E recorded model costs", "Existing selected-arm totals with arithmetic display ratios to none; no resource-time extrapolation.", {
        "fields": ["selected_cost_by_arm.*.known_components.logical_calls", "selected_cost_by_arm.*.known_components.sum_known_request_elapsed_s", "selected_cost_by_arm.*.known_components.calls_without_latency"],
        "arm_order": ARM_ORDER, **records,
        "calls_without_latency": [cost[a]["known_components"]["calls_without_latency"] for a in ARM_ORDER],
    })


if __name__ == "__main__":
    plot_action_outcome()
    plot_confidence()
    plot_e_outcomes()
    plot_cost()
    (OUT / "figure_sources.json").write_text(json.dumps(PROVENANCE, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("Rendered four PNG/SVG figure pairs and figure_sources.json from existing aggregates.")
