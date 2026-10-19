"""Step 0a/0b: noise floor and power analysis from paired episode runs.

For a pair of (arm, rep) runs on the same tasks, the per-task difference d_t
(success or progress) has sd s. A paired test at alpha=.05 with 80% power
needs  N = ((z_.975 + z_.8) * s / delta)^2  tasks for a true effect delta,
when each arm is run `reps` times and averaged (s computed on rep-averaged
differences if several reps are given).

    $PY -m preexperiments.react_study.power --stage 10 --glob '...' --pairs none:none always:none
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict

import numpy as np

from preexperiments.react_study.analyze_episodes import load_rows
from preexperiments.react_study.common import stage_dir

Z = 1.959964 + 0.841621


def main(a):
    rows = load_rows(sorted(sum((glob.glob(g) for g in a.glob), [])))
    S = defaultdict(lambda: defaultdict(dict))  # arm -> rep -> task -> (succ, pr)
    for r in rows:
        S[r["arm"]][r["rep"]][r["task_id"]] = (float(r["success"]), r["progress_rate"])
    out = {}
    for pair in a.pairs:
        x, y = pair.split(":")
        if x == y:  # A/A: rep0 vs rep1 of the same arm
            reps = sorted(S[x])
            A, B = S[x][reps[0]], S[x][reps[1]]
            tasks = sorted(set(A) & set(B))
            dS = np.array([B[t][0] - A[t][0] for t in tasks]); dP = np.array([B[t][1] - A[t][1] for t in tasks])
            k = 1
        else:
            reps = sorted(set(S[x]) & set(S[y]))
            tasks = sorted(set.intersection(*[set(S[x][r]) & set(S[y][r]) for r in reps]))
            dS = np.array([np.mean([S[x][r][t][0] - S[y][r][t][0] for r in reps]) for t in tasks])
            dP = np.array([np.mean([S[x][r][t][1] - S[y][r][t][1] for r in reps]) for t in tasks])
            k = len(reps)
        res = {"n_tasks": len(tasks), "reps_averaged": k}
        for name, d in (("success", dS), ("progress", dP)):
            sd = float(d.std(ddof=1))
            res[name] = {"mean_diff": float(d.mean()), "sd_task_diff": sd,
                         "se": sd / np.sqrt(len(d)),
                         "discordant_frac": float((d != 0).mean()),
                         "N_needed": {f"{int(delta*100)}pp": int(np.ceil((Z * sd / delta) ** 2))
                                      for delta in (0.02, 0.03, 0.05)}}
        out[pair] = res
    sd = stage_dir(a.stage)
    (sd / "tables" / f"power_{a.tag}.json").write_text(json.dumps(out, indent=2))
    for p, r in out.items():
        print(p, json.dumps(r))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, default=10)
    ap.add_argument("--glob", nargs="+", required=True)
    ap.add_argument("--pairs", nargs="+", required=True)
    ap.add_argument("--tag", required=True)
    main(ap.parse_args())
