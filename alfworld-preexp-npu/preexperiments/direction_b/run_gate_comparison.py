"""Stage 3: Oracle headroom -- the four gate policies (方案 §27-§31, §34 条件 4).

    No Foresight      g = 0            always take a_base
    Always Foresight  g = 1            always take a_fore
    Confidence Gate   g = 1[C > tau]   WorldEvolver-style selective foresight
    Oracle Utility    g = 1[U > 0]     experimental upper bound, not a method

The metric here is ACTION-LEVEL accuracy -- P(chosen action == expert action) --
not episode success rate. 方案 §29 asks for success/steps/invalid, which need
the Stage 2 rollouts; this is the action-level analogue computable from the
Stage 1 data alone, and it answers §34 条件 4 (does the oracle beat the best
confidence threshold?) directly. That distinction is stated rather than papered
over, because the two are not interchangeable: a better next action does not
guarantee a better episode.

Confidence is swept two ways, for the reason recorded in
analyze_confidence_utility: the self-report takes absolute thresholds (§30),
while the logprob confidence is concentrated against 1.0 (p10 = 0.938) and is
swept by coverage quantile instead -- an absolute sweep over {0.3 ... 0.9} would
pass every sample and silently turn the gate into "Always Foresight".

§31 also asks for the foresight usage rate, and §29 notes the distinction that
matters for cost: this gate decides AFTER the world model has already run, so a
usage rate below 100% saves planner context, not world-model compute.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any, Callable, Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_TAB = ROOT / "outputs" / "tables"
OUT_FIG = ROOT / "figures"


def _accuracy(rows: List[Dict[str, Any]], gate: Callable[[Dict[str, Any]], bool]) -> Dict[str, float]:
    """Action accuracy and foresight usage under one gate policy."""
    hits, used = 0, 0
    for r in rows:
        g = gate(r)
        used += int(g)
        hits += int(r["fore_matches_expert"] if g else r["base_matches_expert"])
    n = len(rows)
    return {"accuracy": hits / n, "usage": used / n, "n": n}


def main(args: argparse.Namespace) -> None:
    OUT_TAB.mkdir(parents=True, exist_ok=True)
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in open(DATA_DIR / args.rows)]
    rows = [r for r in rows if r.get("action_utility") is not None]
    if args.exclude_noop:
        rows = [r for r in rows if not r["expert_is_noop"]]
    print(f"[gates] {len(rows)} states\n")

    results: Dict[str, Any] = {"n": len(rows)}

    base = _accuracy(rows, lambda r: False)
    always = _accuracy(rows, lambda r: True)
    oracle = _accuracy(rows, lambda r: r["action_utility"] > 0)
    results["no_foresight"] = base
    results["always_foresight"] = always
    results["oracle_utility"] = oracle

    # --- confidence gates: sweep, then keep the best threshold per signal ---
    sweeps: Dict[str, List[Dict[str, Any]]] = {}

    self_vals = [r["wm_confidence_self_report"] for r in rows
                 if isinstance(r.get("wm_confidence_self_report"), (int, float))
                 and not math.isnan(r["wm_confidence_self_report"])]
    sweeps["self_report"] = []
    for tau in args.tau_sweep:
        e = _accuracy(rows, lambda r, t=tau: (
            isinstance(r.get("wm_confidence_self_report"), (int, float))
            and not math.isnan(r["wm_confidence_self_report"])
            and r["wm_confidence_self_report"] > t))
        e["tau"] = tau
        sweeps["self_report"].append(e)

    lp_vals = [r["wm_confidence_logprob"] for r in rows
               if isinstance(r.get("wm_confidence_logprob"), (int, float))
               and not math.isnan(r["wm_confidence_logprob"])]
    sweeps["logprob"] = []
    for q in args.coverage_sweep:
        tau = float(np.quantile(lp_vals, 1 - q)) if q < 1.0 else -1.0
        e = _accuracy(rows, lambda r, t=tau: (
            isinstance(r.get("wm_confidence_logprob"), (int, float))
            and not math.isnan(r["wm_confidence_logprob"])
            and r["wm_confidence_logprob"] > t))
        e.update({"tau": tau, "target_coverage": q})
        sweeps["logprob"].append(e)
    results["confidence_sweep"] = sweeps

    best = {k: max(v, key=lambda e: e["accuracy"]) for k, v in sweeps.items()}
    results["best_confidence_gate"] = best

    # ---- §31's table ----
    print(f"{'Method':26s} {'ActionAcc':>10s} {'ForesightUsage':>15s}")
    print("-" * 55)
    print(f"{'No Foresight':26s} {base['accuracy']:>9.1%} {base['usage']:>14.1%}")
    print(f"{'Always Foresight':26s} {always['accuracy']:>9.1%} {always['usage']:>14.1%}")
    for k, e in best.items():
        label = f"Confidence Gate ({k})"
        print(f"{label:26s} {e['accuracy']:>9.1%} {e['usage']:>14.1%}   "
              f"(best tau={e['tau']:.4f})")
    print(f"{'Oracle Utility Gate':26s} {oracle['accuracy']:>9.1%} {oracle['usage']:>14.1%}")
    print("-" * 55)

    best_conf_acc = max(e["accuracy"] for e in best.values())
    gap = oracle["accuracy"] - best_conf_acc
    results["oracle_minus_best_confidence"] = gap
    results["oracle_minus_no_foresight"] = oracle["accuracy"] - base["accuracy"]
    print(f"\n§34 条件4: Oracle - 最优ConfidenceGate = {gap:+.1%}  (门槛 >= +5pp)")
    print(f"          Oracle - No Foresight       = {oracle['accuracy'] - base['accuracy']:+.1%}")

    # ---- Figure 4 (方案 §43) ----
    labels = ["No\nForesight", "Always\nForesight",
              "Confidence\nGate (best)", "Oracle\nUtility Gate"]
    accs = [base["accuracy"], always["accuracy"], best_conf_acc, oracle["accuracy"]]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(labels, accs, color=["#999999", "#4c72b0", "#dd8452", "#55a868"])
    for b, a in zip(bars, accs):
        ax.text(b.get_x() + b.get_width() / 2, a + 0.005, f"{a:.1%}",
                ha="center", fontsize=9)
    ax.set_ylabel("action accuracy (matches expert)")
    ax.set_ylim(0, max(accs) * 1.25)
    ax.set_title("Fig 4: Gate performance (action-level)")
    fig.tight_layout()
    fig.savefig(OUT_FIG / f"dirB_fig4_gate_performance{args.tag}.png", dpi=150)
    plt.close(fig)

    path = OUT_TAB / f"dirB_gate_comparison{args.tag}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n-> {path}\n-> {OUT_FIG / ('dirB_fig4_gate_performance' + args.tag + '.png')}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Stage 3: gate comparison / oracle headroom.")
    p.add_argument("--rows", default="action_utility_framingB.jsonl")
    p.add_argument("--tag", default="", help="suffix for the output files, so runs "
                   "on different arms (weak / strongwm) do not overwrite each other")
    p.add_argument("--exclude_noop", action="store_true")
    p.add_argument("--tau_sweep", type=float, nargs="*",
                   default=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95])
    p.add_argument("--coverage_sweep", type=float, nargs="*",
                   default=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    return p


if __name__ == "__main__":
    os.chdir(ROOT)
    main(build_arg_parser().parse_args())
