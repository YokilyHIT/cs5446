"""Action-sequence agreement between two episode JSONL files (same arm).

Used in stage 1 to check (a) new instrumented code vs the legacy Sep-14 run,
(b) rep0 vs rep1 of the same arm (serving nondeterminism at temperature 0).

    $PY -m preexperiments.react_study.compare_trajectories A.jsonl B.jsonl --arm none --out x.json
"""
from __future__ import annotations

import argparse
import json


def load(p, arm):
    out = {}
    for line in open(p, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            if r["arm"] == arm:
                out[r["task_id"]] = r
    return out


def main(a):
    A, B = load(a.a, a.arm), load(a.b, a.arm)
    tasks = sorted(set(A) & set(B))
    per = []
    for t in tasks:
        sa = [s["action"] for s in A[t]["step_log"]]
        sb = [s["action"] for s in B[t]["step_log"]]
        k = 0
        while k < min(len(sa), len(sb)) and sa[k] == sb[k]:
            k += 1
        per.append({"task_id": t, "identical": sa == sb, "first_divergence_step": None if sa == sb else k,
                    "len_a": len(sa), "len_b": len(sb),
                    "success_a": A[t]["success"], "success_b": B[t]["success"]})
    res = {"a": a.a, "b": a.b, "arm": a.arm, "n_tasks": len(tasks),
           "n_identical_trajectories": sum(p["identical"] for p in per),
           "n_success_disagree": sum(p["success_a"] != p["success_b"] for p in per),
           "first_divergence_steps": sorted(p["first_divergence_step"] for p in per
                                            if p["first_divergence_step"] is not None),
           "per_task": per}
    if a.out:
        json.dump(res, open(a.out, "w"), indent=2)
    print({k: v for k, v in res.items() if k != "per_task"})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("a"); p.add_argument("b")
    p.add_argument("--arm", required=True)
    p.add_argument("--out", default="")
    main(p.parse_args())
