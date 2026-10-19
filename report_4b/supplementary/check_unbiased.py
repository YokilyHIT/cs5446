"""Check the two new Step-0c tables, then rerun our D/N/P contrasts on the 127 unbiased points.

Consistency checks (pre-declared): per-rep table agrees with the per-task means, the dev-pool game list,
the published success/progress/step means and A/A flip counts; the point table agrees with
branch_points.jsonl; in_unbiased_subset equals "solvable by rep1"; 127 points / 81 tasks.
"""
import csv
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

# step0_protocol_v2_measurement folder of the team repo master (a26e7e4 holds raw/ and both new tables);
# an optional second path points at a different copy of the new tables.
old = Path(sys.argv[1])
new = Path(sys.argv[2]) if len(sys.argv) > 2 else old
rng = np.random.default_rng(2026)
ok = []


def check(name, cond, detail=""):
    ok.append(bool(cond))
    print(f"{'ok ' if cond else 'BAD'} {name}" + (f"  ({detail})" if detail else ""))


rep = list(csv.DictReader(open(new / "tables" / "per_task_per_rep_dev600.csv", encoding="utf-8")))
means = {r["task_id"]: r for r in csv.DictReader(open(old / "tables" / "per_task_dev600_v2.csv", encoding="utf-8"))}
games = {l.strip().split("/")[-2] for l in open(old / "raw" / "devpool600_games.txt", encoding="utf-8") if l.strip()}
ids = [r["task_id"] for r in rep]
check("600 unique tasks", len(rep) == 600 == len(set(ids)))
check("same task set as devpool600_games.txt", set(ids) == games)
check("100 tasks per type", set(np.unique([r["task_type"] for r in rep], return_counts=True)[1]) == {100})
f = lambda arm, k, cast=float: np.array([cast(r[f"{arm}_{k}"]) for r in rep])
for arm in ("none", "always"):
    s0, s1 = f(arm, "rep0_success", int), f(arm, "rep1_success", int)
    agree = all(abs((a + b) / 2 - float(means[t][f"{arm}_mean_success"])) < 1e-9 for a, b, t in zip(s0, s1, ids))
    check(f"{arm}: (rep0+rep1)/2 equals per_task_dev600_v2 mean", agree)
    print(f"    {arm}: SR rep0 {s0.mean():.4f} rep1 {s1.mean():.4f} | PR {f(arm, 'rep0_progress').mean():.4f} / "
          f"{f(arm, 'rep1_progress').mean():.4f} | steps {np.r_[f(arm, 'rep0_steps'), f(arm, 'rep1_steps')].mean():.2f} | "
          f"tasks whose success differs across reps {int((s0 != s1).sum())}")

pts = {json.loads(l)["point_id"]: json.loads(l) for l in open(old / "raw" / "branch_points.jsonl", encoding="utf-8")}
up = list(csv.DictReader(open(new / "tables" / "branch_k_unbiased_points.csv", encoding="utf-8")))
by_task = {r["task_id"]: r for r in rep}
check("200 points, ids match branch_points", len(up) == 200 and {int(r["point_id"]) for r in up} == set(pts))
check("task_id / t / group / stratum match branch_points",
      all(pts[int(r["point_id"])]["task_id"] == r["task_id"] and pts[int(r["point_id"])]["t"] == int(r["t"])
          and pts[int(r["point_id"])]["group"] == r["group"] and pts[int(r["point_id"])]["stratum"] == r["stratum"] for r in up))
check("rep outcomes match the per-rep table",
      all(r["none_rep0_success"] == by_task[r["task_id"]]["none_rep0_success"]
          and r["none_rep1_success"] == by_task[r["task_id"]]["none_rep1_success"] for r in up))
check("task_solve_rate equals mean of the two reps",
      all(abs(pts[int(r["point_id"])]["task_solve_rate"] - (int(r["none_rep0_success"]) + int(r["none_rep1_success"])) / 2) < 1e-9 for r in up))
sub = [r for r in up if r["in_unbiased_subset"] == "1"]
check("in_unbiased_subset == solvable by rep1", all((r["in_unbiased_subset"] == "1") == (r["none_rep1_success"] == "1") for r in up))
check("127 points / 81 tasks", len(sub) == 127 and len({r["task_id"] for r in sub}) == 81,
      f"{len(sub)} points, {len({r['task_id'] for r in sub})} tasks")
solv = [r for r in up if r["group"] == "solvable"]
print(f"    solvable points from rep0 trajectories that succeeded: {sum(r['none_rep0_success'] == '1' for r in solv)}/{len(solv)}")
print(f"    checks passed: {sum(ok)}/{len(ok)}")

# ---------- D/N/P contrasts on the unbiased subset ----------
keep = {int(r["point_id"]) for r in sub}
rows = [json.loads(l) for fn in sorted(glob.glob(str(old / "raw" / "branch_k.shard*.jsonl"))) for l in open(fn, encoding="utf-8")]
rows = [r for r in rows if r.get("replay_ok") and r["point_id"] in keep]
tasks = [r["task_id"] for r in rows]


def est(r, arm, metric):
    x = np.array([float(c["success"]) if metric == "success" else float(c["pr"]) for c in r["continuations"][r["first_actions"][arm]]])
    return x.mean(), x.var(ddof=1) / len(x)


def ci(values):
    by = defaultdict(list)
    for v, t in zip(values, tasks):
        by[t].append(v)
    g = list(by.values()); s = np.array([sum(x) for x in g]); n = np.array([len(x) for x in g])
    idx = rng.integers(0, len(g), size=(10000, len(g)))
    b = s[idx].sum(1) / n[idx].sum(1)
    return np.mean(values), np.percentile(b, 2.5), np.percentile(b, 97.5)


conf = np.array([r["wm_confidence_logprob"] for r in rows]); em = np.array([r["pred_em"] for r in rows])
print(f"\n# D/N/P on the unbiased subset: {len(rows)} points, {len(set(tasks))} tasks")
for metric in ("success", "pr"):
    print(f"  metric={metric}")
    for name, (a, b) in {"vs base: wm (P-D)": ("wm", "base"), "vs base: oracle": ("oracle", "base"),
                         "vs base: rethink (N-D)": ("rethink", "base"), "vs base: loophint": ("loophint", "base"),
                         "information P-N": ("wm", "rethink"), "perfect info P*-N": ("oracle", "rethink")}.items():
        u, noise, ch = [], [], []
        for r in rows:
            (ma, va), (mb, vb) = est(r, a, metric), est(r, b, metric)
            c = r["first_actions"][a] != r["first_actions"][b]
            u.append(ma - mb if c else 0.0); noise.append(va + vb if c else 0.0); ch.append(c)
        u, noise, ch = map(np.array, (u, noise, ch))
        m, lo, hi = ci(u)
        ratio = u[ch].var(ddof=1) / noise[ch].mean() if ch.sum() > 2 and noise[ch].mean() > 0 else float("nan")
        rho = spearmanr(conf[ch], u[ch]).statistic if ch.sum() > 5 else float("nan")
        extra = f"  EM=1 {u[em > .5].mean():+.3f} EM=0 {u[em <= .5].mean():+.3f}" if name.startswith("information") else ""
        print(f"    {name:24s} changed {ch.mean():4.0%}  mean {m:+.3f} [{lo:+.3f}, {hi:+.3f}]  excess-var {ratio:5.2f}"
              f"  rho(conf,U|changed) {rho:+.3f} (n={ch.sum()}){extra}")
U = {k: np.array([est(r, a, "success")[0] - est(r, b, "success")[0] for r in rows])
     for k, (a, b) in {"admission": ("wm", "base"), "info": ("wm", "rethink"), "revision": ("rethink", "base")}.items()}
top = conf >= np.median(conf)
print("  G (success):", {k: round(0.25 * (v[top].mean() - v[~top].mean()), 4) for k, v in U.items()})
print("  rank corr conf-EM %.3f, conf-F1 %.3f" % (spearmanr(conf, em).statistic, spearmanr(conf, [r["pred_f1"] for r in rows]).statistic))
