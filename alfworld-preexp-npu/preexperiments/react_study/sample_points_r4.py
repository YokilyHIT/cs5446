"""Round 4 state sampling (Phase 2b / Phase 4 / Phase 6): decision points from `none` runs.

Outcome-selection-safe version of step-0c sampling (`sample_points_v2.py`): states are drawn
from the rep-0 trajectory, but a task's group is decided ONLY by the independent rep-1 run
    solvable : rep-1 succeeded         unsolved : rep-1 failed
(step 0c's "unbiased subset" = exactly this rule for the solvable group). Within a group,
task types are round-robined, at most `per_task` states per task, steps t <= max_t.

    $PY -m preexperiments.react_study.sample_points_r4 --runs 'r4_common/raw/train/p14b_branch140_none__rep{rep}.jsonl' \
        --n_solvable 104 --n_unsolved 26 --out p14b_branch140_points.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict

from preexperiments.react_study.common import OUT_ROOT, stage_dir
from preexperiments.react_study.stage3_sample_points import features


def main(a):
    reps = {}
    for rep in (0, 1):
        reps[rep] = {}
        for l in open(OUT_ROOT / a.runs.format(rep=rep)):
            r = json.loads(l)
            reps[rep][r["task_id"]] = r
    tasks = sorted(set(reps[0]) & set(reps[1]))
    cands = defaultdict(list)
    for t in tasks:
        e, grp = reps[0][t], ("solvable" if reps[1][t]["success"] else "unsolved")
        steps = e["step_log"]
        for i in range(min(len(steps), a.max_t + 1)):
            f = features(steps, i)
            obs = steps[i].get("observation") or (e["initial_observation"] if i == 0 else steps[i - 1]["next_observation"])
            cands[grp].append({"task_id": t, "gamefile": e["gamefile"], "task_type": e["task_type"], "goal": e["goal"],
                               "group": grp, "unbiased_group": grp,
                               "task_solve_rate": (reps[0][t]["success"] + reps[1][t]["success"]) / 2,
                               "stratum": "stuck" if (f["repeat_count"] >= 2 or f["nothing_last5"] >= 2) else "normal",
                               "features": f, "t": i, "prefix": [s["action"] for s in steps[:i]], "observation": obs,
                               "logged_baseline_action": steps[i]["baseline_action"]})
    rng = random.Random(a.seed)
    chosen = []
    for grp, n in (("solvable", a.n_solvable), ("unsolved", a.n_unsolved)):
        pool = cands[grp]
        rng.shuffle(pool)
        by = defaultdict(list)
        for c in pool:
            by[c["task_type"]].append(c)
        per, got = Counter(), []
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
        c["point_id"] = a.id_offset + i
        c["weight"] = 1.0
    sd = stage_dir(a.stage)
    with open(sd / "raw" / a.out, "w") as f:
        for c in chosen:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    design = {"runs": a.runs, "n_tasks": len(tasks),
              "n_solvable_tasks_rep1": sum(reps[1][t]["success"] for t in tasks),
              "candidates": {g: len(v) for g, v in cands.items()},
              "chosen": dict(Counter(c["group"] for c in chosen)),
              "chosen_stratum": {f"{g}/{s}": n for (g, s), n in Counter((c["group"], c["stratum"]) for c in chosen).items()},
              "chosen_task_type": dict(Counter(c["task_type"] for c in chosen)),
              "n_distinct_tasks": len({c["task_id"] for c in chosen}), "seed": a.seed, "id_offset": a.id_offset}
    (sd / "tables" / a.out.replace(".jsonl", "_design.json")).write_text(json.dumps(design, indent=2))
    print(json.dumps(design, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, default=32)
    ap.add_argument("--runs", required=True, help="path under outputs/react_study with {rep}")
    ap.add_argument("--n_solvable", type=int, required=True)
    ap.add_argument("--n_unsolved", type=int, required=True)
    ap.add_argument("--per_task", type=int, default=2)
    ap.add_argument("--max_t", type=int, default=25)
    ap.add_argument("--seed", type=int, default=2028)
    ap.add_argument("--id_offset", type=int, default=0)
    ap.add_argument("--out", required=True)
    main(ap.parse_args())
