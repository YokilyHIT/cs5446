"""Step 0c sampling: decision points from dev-pool `none` runs (record_state).

    solvable tasks  : `none` succeeded in >= 1 of the input repeats
    unsolved tasks  : never succeeded (contrast group)

Candidates: steps t <= max_t of rep-0 trajectories. Per group, the stuck /
normal mix is sampled at the candidate proportion (no oversampling this
time, so the unweighted mean is the visit-distribution mean within group),
with at most `per_task` points per task and task types round-robined.
"""
from __future__ import annotations

import argparse
import glob
import json
import random
from collections import Counter, defaultdict

from preexperiments.react_study.common import stage_dir
from preexperiments.react_study.stage3_sample_points import features


def main(a):
    sd = stage_dir(a.stage)
    reps = defaultdict(dict)
    for f in sorted(glob.glob(str(sd / "raw" / "train" / a.runs_glob))):
        for l in open(f):
            r = json.loads(l)
            reps[r["task_id"]][r["rep"]] = r
    solve = {t: sum(r["success"] for r in d.values()) / len(d) for t, d in reps.items()}
    cands = defaultdict(list)
    for t, d in reps.items():
        e = d[min(d)]
        steps = e["step_log"]
        grp = "solvable" if solve[t] > 0 else "unsolved"
        for i in range(min(len(steps), a.max_t + 1)):
            f = features(steps, i)
            stuck = f["repeat_count"] >= 2 or f["nothing_last5"] >= 2
            cands[grp].append({"task_id": t, "gamefile": e["gamefile"], "task_type": e["task_type"],
                               "goal": e["goal"], "group": grp, "task_solve_rate": solve[t],
                               "stratum": "stuck" if stuck else "normal", "features": f, "t": i,
                               "prefix": [s["action"] for s in steps[:i]],
                               "observation": steps[i]["observation"],
                               "logged_baseline_action": steps[i]["baseline_action"]})
    rng = random.Random(a.seed)
    chosen = []
    for grp, n in (("solvable", a.n_solvable), ("unsolved", a.n_unsolved)):
        pool = cands[grp]
        rng.shuffle(pool)
        by = defaultdict(list)
        for c in pool:
            by[c["task_type"]].append(c)
        per = Counter()
        got = []
        while len(got) < n and any(by.values()):
            for tt in sorted(by):
                while by[tt]:
                    c = by[tt].pop()
                    if per[c["task_id"]] < a.per_task:
                        per[c["task_id"]] += 1
                        got.append(c)
                        break
                if len(got) >= n:
                    break
        chosen += got
    chosen.sort(key=lambda c: (c["group"], c["task_id"], c["t"]))
    for i, c in enumerate(chosen):
        c["point_id"] = i
        c["weight"] = 1.0
    with open(sd / "raw" / a.out, "w") as f:
        for c in chosen:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    design = {"n_tasks": len(reps), "n_solvable_tasks": sum(v > 0 for v in solve.values()),
              "candidates": {g: len(v) for g, v in cands.items()},
              "candidate_stuck_frac": {g: sum(c["stratum"] == "stuck" for c in v) / max(len(v), 1)
                                       for g, v in cands.items()},
              "chosen": dict(Counter(c["group"] for c in chosen)),
              "chosen_stratum": dict(Counter((c["group"], c["stratum"]) for c in chosen).items()
                                     .__iter__()) if False else
              {f"{g}/{s}": n for (g, s), n in Counter((c["group"], c["stratum"]) for c in chosen).items()},
              "chosen_task_type": dict(Counter(c["task_type"] for c in chosen)),
              "n_distinct_tasks": len({c["task_id"] for c in chosen}), "seed": a.seed}
    (sd / "tables" / "branch_sampling_design.json").write_text(json.dumps(design, indent=2))
    print(json.dumps(design, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, default=10)
    ap.add_argument("--runs_glob", default="dev_v2_none__rep*.jsonl")
    ap.add_argument("--n_solvable", type=int, default=160)
    ap.add_argument("--n_unsolved", type=int, default=40)
    ap.add_argument("--per_task", type=int, default=2)
    ap.add_argument("--max_t", type=int, default=25)
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--out", default="branch_points.jsonl")
    main(ap.parse_args())
