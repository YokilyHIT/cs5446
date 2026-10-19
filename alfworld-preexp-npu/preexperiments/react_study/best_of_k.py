"""Best-of-k success (AgentBoard / WorldEvolver style) with cumulative cost.

For arms whose repeats are independent (no memory), best-of-k is averaged over
all k-subsets of the available repeats. For sequential-attempt arms (memory
carried across attempts) the natural order is used: attempts 1..k.
Cost is the cumulative tokens of all k attempts (every attempt is paid for,
even after a success, as in AgentBoard's L trials).

    $PY -m preexperiments.react_study.best_of_k --stage 14 --glob '...' --sequential selective_em --tag unseen
"""
from __future__ import annotations

import argparse
import glob
import itertools
import json
from collections import defaultdict

import numpy as np

from preexperiments.react_study.common import stage_dir


def main(a):
    S = defaultdict(lambda: defaultdict(dict))  # arm -> task -> rep -> (succ, tokens)
    for f in sorted(sum((glob.glob(g) for g in a.glob), [])):
        if f.endswith((".config.json", ".memory.jsonl", ".partial.jsonl")):
            continue
        for l in open(f):
            r = json.loads(l)
            tok = sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())
            S[r["arm"]][r["task_id"]][r["rep"]] = (float(r["success"]), tok)
    out = {}
    for arm, T in S.items():
        reps = sorted(set.intersection(*[set(v) for v in T.values()]))
        tasks = sorted(T)
        curve = []
        for k in range(1, len(reps) + 1):
            subs = [tuple(reps[:k])] if arm in a.sequential else list(itertools.combinations(reps, k))
            sr = np.mean([np.mean([max(T[t][r][0] for r in s) for t in tasks]) for s in subs])
            tok = np.mean([np.mean([sum(T[t][r][1] for r in s) for t in tasks]) for s in subs])
            curve.append({"k": k, "best_of_k_sr": float(sr), "cum_tokens_per_task": float(tok)})
        out[arm] = {"n_tasks": len(tasks), "reps": reps, "sequential": arm in a.sequential, "curve": curve}
    sd = stage_dir(a.stage)
    (sd / "tables" / f"best_of_k_{a.tag}.json").write_text(json.dumps(out, indent=2))
    for arm, v in out.items():
        print(arm, " ".join(f"k{c['k']}={100*c['best_of_k_sr']:.1f}%({c['cum_tokens_per_task']/1000:.0f}k)" for c in v["curve"]))
    plot(out, sd / "figures" / f"best_of_k_{a.tag}.png")


def plot(out, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cols = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=150)
    fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")
    for (arm, v), c in zip(sorted(out.items()), cols):
        ks = [x["k"] for x in v["curve"]]
        ax.plot(ks, [100 * x["best_of_k_sr"] for x in v["curve"]], "-o", color=c, lw=2, ms=6, mec="#fcfcfb", label=arm)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.grid(True, color="#ecebe7", lw=0.8)
    ax.set_xticks(range(1, 1 + max(len(v["curve"]) for v in out.values())))
    ax.set_xlabel("k attempts", color="#52514e"); ax.set_ylabel("best-of-k success rate (%)", color="#52514e")
    ax.set_title("Best-of-k success (cumulative cost in tables/best_of_k_*.json)", fontsize=10, loc="left")
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, required=True)
    ap.add_argument("--glob", nargs="+", required=True)
    ap.add_argument("--sequential", nargs="*", default=[])
    ap.add_argument("--tag", required=True)
    main(ap.parse_args())
