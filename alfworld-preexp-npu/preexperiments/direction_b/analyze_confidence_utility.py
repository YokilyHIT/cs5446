"""Stage 1 analysis: Confidence vs Planning Utility (方案 §18, §20-§26, §34).

方案 §26 is explicit that the four-quadrant / selection-error view matters more
than a correlation coefficient, and that is doubly true here: the self-reported
confidence is heavily tied (6 distinct values over 30 states in Stage 0), which
cripples a rank correlation but leaves quadrant counts perfectly readable.

Two confidence signals are analysed side by side (方案 §9):
  * self-report  -- swept over the absolute thresholds §30 lists
  * logprob      -- WorldEvolver's q_t = exp(mean token logprob). Its values sit
                    against the ceiling (Stage 0: p10 = 0.938, p90 = 0.996), so
                    an absolute sweep over {0.3 ... 0.9} would pass every sample
                    and reproduce the degenerate gate seen earlier. It is swept
                    by COVERAGE QUANTILE instead, which is also how WorldEvolver
                    validates it (Fig. 11: Exact Match on the top-confidence
                    prefix).

Correctness is reported under all four metrics rather than one, because the
choice of metric materially changed the picture once already.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.stats import pearsonr, spearmanr  # noqa: E402

from preexperiments.direction_b.metrics import risk_coverage  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_FIG = ROOT / "figures"
OUT_TAB = ROOT / "outputs" / "tables"

CONF_KEYS = {
    "self_report": "wm_confidence_self_report",
    "logprob": "wm_confidence_logprob",
}
CORRECTNESS_KEYS = ["correctness_exact_match", "correctness_token_f1",
                    "correctness_fact_f1", "correctness_cosine"]


def _finite(xs: Sequence[Any]) -> List[float]:
    return [x for x in xs if isinstance(x, (int, float)) and not math.isnan(x)]


def _corr(x: Sequence[float], y: Sequence[float]):
    pairs = [(a, b) for a, b in zip(x, y)
             if isinstance(a, (int, float)) and isinstance(b, (int, float))
             and not math.isnan(a) and not math.isnan(b)]
    if len(pairs) < 3:
        return float("nan"), float("nan"), float("nan"), float("nan")
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return float("nan"), float("nan"), float("nan"), float("nan")
    pr, pp = pearsonr(xs, ys)
    sr, sp = spearmanr(xs, ys)
    return pr, pp, sr, sp


def quadrants(rows: List[Dict], conf_key: str, tau: float) -> Dict[str, Any]:
    """方案 §22-§24: the 2x2 table and the four selection-error rates."""
    usable = [r for r in rows
              if r.get("action_utility") is not None
              and isinstance(r.get(conf_key), (int, float))
              and not math.isnan(r[conf_key])]
    if not usable:
        return {}
    hi_u = lambda r: r["action_utility"] > 0          # noqa: E731
    hi_c = lambda r: r[conf_key] > tau                # noqa: E731
    A = sum(1 for r in usable if hi_c(r) and hi_u(r))       # high C, useful
    B = sum(1 for r in usable if hi_c(r) and not hi_u(r))   # high C, not useful
    C = sum(1 for r in usable if not hi_c(r) and hi_u(r))   # low C, useful
    D = sum(1 for r in usable if not hi_c(r) and not hi_u(r))
    n_hi, n_useful = A + B, A + C
    return {
        "tau": tau, "n": len(usable), "A": A, "B": B, "C": C, "D": D,
        # §24
        "precision": (A / n_hi) if n_hi else float("nan"),
        "recall": (A / n_useful) if n_useful else float("nan"),
        "FUAR": (B / n_hi) if n_hi else float("nan"),      # false useless acceptance
        "FURR": (C / n_useful) if n_useful else float("nan"),  # false useful rejection
        "usage_rate": n_hi / len(usable),
    }


def main(args: argparse.Namespace) -> None:
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    OUT_TAB.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in open(DATA_DIR / args.rows)]
    if args.exclude_noop:
        rows = [r for r in rows if not r["expert_is_noop"]]
    usable = [r for r in rows if r.get("action_utility") is not None]

    out: Dict[str, Any] = {"n_rows": len(rows), "n_usable": len(usable),
                           "exclude_expert_noop": bool(args.exclude_noop)}

    # ---- Table 1: dataset statistics (方案 §44) ----
    from collections import Counter
    out["dataset"] = {
        "n_episodes": len({r["episode_id"] for r in rows}),
        "task_type": dict(Counter(r["task_type"] for r in rows)),
        "expert_noop_frac": sum(r["expert_is_noop"] for r in rows) / max(len(rows), 1),
        "step_id_median": float(np.median([r["step_id"] for r in rows])),
    }

    # ---- §18: the four action-level rates ----
    u = [r["action_utility"] for r in usable]
    changed = [r for r in usable if r["baseline_changed"]]
    out["action_level"] = {
        "AIR": u.count(1) / len(u) if u else float("nan"),
        "AHR": u.count(-1) / len(u) if u else float("nan"),
        "ACR": len(changed) / len(usable) if usable else float("nan"),
        "P_improve_given_changed": (
            sum(1 for r in changed if r["action_utility"] == 1) / len(changed)
            if changed else float("nan")),
        "base_match_expert": sum(r["base_matches_expert"] for r in usable) / max(len(usable), 1),
        "fore_match_expert": sum(bool(r["fore_matches_expert"]) for r in usable) / max(len(usable), 1),
        "action_forced_rate": sum(r["action_forced"] for r in usable) / max(len(usable), 1),
    }

    # ---- §25: correlations, and the confidence-vs-correctness sanity check ----
    out["correlations"] = {}
    for cname, ckey in CONF_KEYS.items():
        conf = [r.get(ckey) for r in usable]
        pr, pp, sr, sp = _corr(conf, [r["action_utility"] for r in usable])
        entry = {"vs_utility": {"pearson": pr, "pearson_p": pp,
                                "spearman": sr, "spearman_p": sp}}
        # Does the confidence even track prediction correctness? If not, the
        # utility comparison is testing a broken instrument, not a hypothesis.
        for mk in CORRECTNESS_KEYS:
            _, _, s_r, s_p = _corr(conf, [r.get(mk) for r in usable])
            entry[f"vs_{mk}"] = {"spearman": s_r, "spearman_p": s_p}
        out["correlations"][cname] = entry

    # ---- WorldEvolver Fig.11 style risk-coverage on every correctness metric --
    out["risk_coverage"] = {}
    for cname, ckey in CONF_KEYS.items():
        conf = [r.get(ckey) for r in usable]
        out["risk_coverage"][cname] = {
            mk: risk_coverage(conf, [r.get(mk) for r in usable])
            for mk in CORRECTNESS_KEYS
        }

    # ---- §22-§24 + §30: quadrants over a threshold sweep ----
    out["quadrant_sweep"] = {}
    taus_self = args.tau_sweep
    out["quadrant_sweep"]["self_report"] = [
        quadrants(usable, CONF_KEYS["self_report"], t) for t in taus_self
    ]
    # logprob: thresholds set BY QUANTILE, see module docstring.
    lp = _finite([r.get(CONF_KEYS["logprob"]) for r in usable])
    out["quadrant_sweep"]["logprob"] = []
    if lp:
        for q in args.coverage_sweep:
            tau = float(np.quantile(lp, 1 - q)) if q < 1.0 else float(min(lp)) - 1e-9
            e = quadrants(usable, CONF_KEYS["logprob"], tau)
            if e:
                e["target_coverage"] = q
            out["quadrant_sweep"]["logprob"].append(e)

    # ---- Figure 1: utility distribution per confidence bin (方案 §20) ----
    bins = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0001)]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, (cname, ckey) in zip(axes, CONF_KEYS.items()):
        h, n_, m_ = [], [], []
        labels = []
        for lo, hi in bins:
            sub = [r for r in usable
                   if isinstance(r.get(ckey), (int, float))
                   and not math.isnan(r[ckey]) and lo <= r[ckey] < hi]
            labels.append(f"{lo:.1f}-{min(hi,1.0):.1f}\n(n={len(sub)})")
            if sub:
                uu = [r["action_utility"] for r in sub]
                h.append(uu.count(1) / len(uu))
                n_.append(uu.count(0) / len(uu))
                m_.append(uu.count(-1) / len(uu))
            else:
                h.append(0); n_.append(0); m_.append(0)
        x = np.arange(len(bins))
        ax.bar(x, h, 0.6, label="helpful (U=+1)", color="#4c72b0")
        ax.bar(x, n_, 0.6, bottom=h, label="neutral (U=0)", color="#cccccc")
        ax.bar(x, m_, 0.6, bottom=np.array(h) + np.array(n_), label="harmful (U=-1)", color="#c44e52")
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8)
        ax.set_title(f"{cname} confidence bin"); ax.set_ylabel("share")
    axes[0].legend(fontsize=8)
    fig.suptitle("Fig 1: Action-level utility by confidence bin")
    fig.tight_layout(); fig.savefig(OUT_FIG / f"dirB_fig1_confidence_bins{args.tag}.png", dpi=150)
    plt.close(fig)

    # ---- Figure 2: confidence vs utility scatter (方案 §21) ----
    rng = np.random.default_rng(2026)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, (cname, ckey) in zip(axes, CONF_KEYS.items()):
        xs = [r.get(ckey) for r in usable]
        ys = [r["action_utility"] for r in usable]
        keep = [(a, b) for a, b in zip(xs, ys)
                if isinstance(a, (int, float)) and not math.isnan(a)]
        if keep:
            ax.scatter([p[0] for p in keep],
                       np.array([p[1] for p in keep]) + rng.uniform(-0.08, 0.08, len(keep)),
                       alpha=0.5, s=18)
        ax.set_yticks([-1, 0, 1]); ax.set_xlabel(f"{cname} confidence")
        ax.set_ylabel("action utility (jittered)")
    fig.suptitle("Fig 2: Prediction confidence vs planning utility")
    fig.tight_layout(); fig.savefig(OUT_FIG / f"dirB_fig2_conf_vs_utility{args.tag}.png", dpi=150)
    plt.close(fig)

    # ---- Figure 3: risk-coverage curves (WorldEvolver Fig.11) ----
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, (cname, _) in zip(axes, CONF_KEYS.items()):
        for mk in ["correctness_token_f1", "correctness_fact_f1", "correctness_cosine"]:
            rc = out["risk_coverage"][cname][mk]
            qs = sorted(k for k, v in rc.items() if v is not None)
            ax.plot(qs, [rc[q] for q in qs], marker="o", label=mk.replace("correctness_", ""))
        ax.set_xlabel("coverage (top-q by confidence)"); ax.set_ylabel("mean correctness")
        ax.set_title(cname)
    axes[0].legend(fontsize=8)
    fig.suptitle("Fig 3: Risk-coverage — does confidence rank correctness?")
    fig.tight_layout(); fig.savefig(OUT_FIG / f"dirB_fig3_risk_coverage{args.tag}.png", dpi=150)
    plt.close(fig)

    path = OUT_TAB / f"dirB_stage1_summary{args.tag}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # ---- console summary ----
    a = out["action_level"]
    print(f"\nn={out['n_usable']} usable states "
          f"(from {out['dataset']['n_episodes']} episodes, "
          f"expert-noop excluded={out['exclude_expert_noop']})")
    print(f"  ACR={a['ACR']:.1%}  AIR={a['AIR']:.1%}  AHR={a['AHR']:.1%}  "
          f"P(+1|changed)={a['P_improve_given_changed']:.1%}")
    print(f"  base matches expert={a['base_match_expert']:.1%}  "
          f"foresight matches expert={a['fore_match_expert']:.1%}")
    print("\n  confidence -> correctness (the instrument check):")
    for cname in CONF_KEYS:
        e = out["correlations"][cname]
        print(f"    {cname:12s} token_f1 rho={e['vs_correctness_token_f1']['spearman']:+.3f} "
              f"(p={e['vs_correctness_token_f1']['spearman_p']:.3f})  "
              f"fact_f1 rho={e['vs_correctness_fact_f1']['spearman']:+.3f} "
              f"(p={e['vs_correctness_fact_f1']['spearman_p']:.3f})")
    print("\n  confidence -> utility:")
    for cname in CONF_KEYS:
        v = out["correlations"][cname]["vs_utility"]
        print(f"    {cname:12s} pearson={v['pearson']:+.3f} spearman={v['spearman']:+.3f} "
              f"(p={v['spearman_p']:.3f})")
    print(f"\n-> {path}")
    print(f"-> {OUT_FIG}/dirB_fig1..3{args.tag}.png")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Stage 1 confidence-vs-utility analysis.")
    p.add_argument("--rows", default="action_utility.jsonl")
    p.add_argument("--tag", default="", help="suffix for output files, so runs on "
                   "different arms (weak / strongwm) do not overwrite each other")
    p.add_argument("--exclude_noop", action="store_true",
                   help="drop states where the expert action is look/inventory/examine")
    p.add_argument("--tau_sweep", type=float, nargs="*",
                   default=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    p.add_argument("--coverage_sweep", type=float, nargs="*",
                   default=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    return p


if __name__ == "__main__":
    os.chdir(ROOT)
    main(build_arg_parser().parse_args())
