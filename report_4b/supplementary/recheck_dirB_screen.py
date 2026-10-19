"""Recompute the direction-B offline signal screen (AUROC / Spearman) from committed per-state data.

    python -I recheck_dirB_screen.py <team repo>/alfworld-preexp-npu/outputs/react_study

Inputs: dirB_planner_uncertainty/raw/signals.jsonl (per-state signals), step0 raw/branch_k.shard*.jsonl
(U_pr(wm) labels from K = 8 continuations) and step0 tables/branch_k_unbiased_points.csv (127-point subset).
Sign convention as published: a higher score opens the gate; low logprob or low confidence opens it, so the
logprob and confidence columns are AUROCs of the *negated* value. The target is observed PR utility of wm.
Published reference: dirB_planner_uncertainty/tables/offline_signal_screen.md (first four numeric columns).

Section 1 reproduces the stored labels as published. Section 2 (added after CODEX_REVIEW.md) applies two label
fixes separately and together: N1, a floating-point residual |U| < 1e-9 treated as zero (point 76), and N3,
the legal pseudo-action "check valid actions" not counted as inadmissible (point 166).
"""
import csv
import glob
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

react = Path(sys.argv[1])
step0 = react / "step0_protocol_v2_measurement"
sig = {}
for line in open(react / "dirB_planner_uncertainty" / "raw" / "signals.jsonl", encoding="utf-8"):
    r = json.loads(line)
    sig[r["point_id"]] = r
U, U_sr, BASE = {}, {}, {}
for f in glob.glob(str(step0 / "raw" / "branch_k.shard*.jsonl")):
    for line in open(f, encoding="utf-8"):
        r = json.loads(line)
        if r.get("replay_ok"):
            U[r["point_id"]] = r["U_pr"]["wm"]
            U_sr[r["point_id"]] = r["U_success"]["wm"]
            BASE[r["point_id"]] = r["first_actions"]["base"]
unbiased = {int(r["point_id"]) for r in csv.DictReader(open(step0 / "tables" / "branch_k_unbiased_points.csv", encoding="utf-8"))
            if r["in_unbiased_subset"] == "1"}

LOW_OPENS = {"planner_action_lp", "planner_full_lp", "wm_confidence"}
SIGNALS = ["planner_action_lp", "planner_full_lp", "sample_disagree", "sample_n_distinct", "base_inadmissible",
           "wm_predicts_failure", "wm_changes_action", "wm_confidence"]
CHECK_VALID = "check valid actions"


def auroc(score, label):
    m = ~np.isnan(score)
    s1, s0 = score[m & label], score[m & ~label]
    if len(s1) == 0 or len(s0) == 0:
        return float("nan")
    diff = s1[:, None] - s0[None, :]
    return float(((diff > 0).sum() + 0.5 * (diff == 0).sum()) / diff.size)


def table(pids, fix_zero=False, fix_pseudo=False):
    u = np.array([0.0 if fix_zero and abs(U[p]) < 1e-9 else U[p] for p in pids])
    out = {}
    for s in SIGNALS:
        x = np.array([float(sig[p][s]) if sig[p].get(s) is not None else np.nan for p in pids])
        if s == "base_inadmissible" and fix_pseudo:
            x = np.array([0.0 if BASE[p] == CHECK_VALID else v for p, v in zip(pids, x)])
        sc = -x if s in LOW_OPENS else x
        m = ~np.isnan(sc)
        out[s] = (auroc(sc, u > 0), auroc(sc, u < 0), auroc(sc, u != 0), spearmanr(sc[m], u[m]).statistic)
    return u, out


def show(title, pids, **fixes):
    u, out = table(pids, **fixes)
    sr = np.array([U_sr[p] for p in pids])
    print(f"## {title} (n={len(pids)}; PR target U>0 {int((u > 0).sum())}, U<0 {int((u < 0).sum())}, U!=0 {int((u != 0).sum())};"
          f" success target U>0 {int((sr > 0).sum())}, U<0 {int((sr < 0).sum())})")
    print(f"  {'signal':22s} AUROC U>0  AUROC U<0  AUROC U!=0  Spearman")
    for s in SIGNALS:
        a, b, c, rho = out[s]
        print(f"  {s:22s} {a:9.3f} {b:10.3f} {c:11.3f} {rho:+9.3f}")
    return out


SETS = {"unbiased": sorted(p for p in sig if p in unbiased and p in U), "all": sorted(p for p in sig if p in U)}
print("# Section 1: stored labels, as published")
stored = {name: show(name, pids) for name, pids in SETS.items()}
print("\n# Section 2: label fixes (N1 zero residual, N3 legal pseudo-action), separately and together")
print("  points with 0 < |U_pr(wm)| < 1e-9:", [p for p in U if U[p] != 0 and abs(U[p]) < 1e-9])
print("  points whose base action is the legal pseudo-action:", [p for p in SETS["all"] if BASE[p] == CHECK_VALID],
      "| flagged base_inadmissible:", [p for p in SETS["all"] if BASE[p] == CHECK_VALID and sig[p].get("base_inadmissible") == 1.0])
for name, pids in SETS.items():
    for label, fixes in (("N1 only", {"fix_zero": True}), ("N3 only", {"fix_pseudo": True}),
                         ("N1 + N3", {"fix_zero": True, "fix_pseudo": True})):
        _, out = table(pids, **fixes)
        changed = [s for s in SIGNALS if any(abs(x - y) > 1e-12 for x, y in zip(out[s], stored[name][s]))]
        if not changed:
            print(f"  {name}, {label}: no change")
            continue
        show(f"{name}, {label}", pids, **fixes)
