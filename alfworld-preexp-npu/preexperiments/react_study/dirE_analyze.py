"""Direction E: does a stronger planner (Qwen3-14B, thinking off) use foresight better?

Same 460 held-out dev tasks, same protocol v2, same Qwen3-4B WM. 4B-planner rows come from
step0 (none/always), step1 (oracle) and dirA (random_pre_nc_p0.3).
"""
from __future__ import annotations

import glob
import json
from collections import defaultdict

import numpy as np

from preexperiments.react_study.analyze_episodes import load_rows
from preexperiments.react_study.analyze_round3 import boot_p
from preexperiments.react_study.common import ROOT, stage_dir

O = ROOT / "outputs" / "react_study"


def main():
    games = set(open(O / "step3_gating/raw/eval460_games.txt").read().split())
    src = {
        ("4B", "none"): "step0_protocol_v2_measurement/raw/train/dev_v2_c*_none__rep*.jsonl",
        ("4B", "always"): "step0_protocol_v2_measurement/raw/train/dev_v2_c*_always__rep*.jsonl",
        ("4B", "oracle"): "step1_upper_bound_controls/raw/train/dev_v2_o*_oracle__rep*.jsonl",
        ("4B", "random_pre_nc_p0.3"): "dirA_D_mechanism_dose/raw/train/random_pre_nc_p0.3_c*__rep*.jsonl",
        ("14B", "none"): "dirE_larger_planner/raw/train/p14b_none_c*__rep*.jsonl",
        ("14B", "always"): "dirE_larger_planner/raw/train/p14b_always_c*__rep*.jsonl",
        ("14B", "oracle"): "dirE_larger_planner/raw/train/p14b_oracle_*__rep*.jsonl",
        ("14B", "random_pre_nc_p0.3"): "dirE_larger_planner/raw/train/p14b_random_c*__rep*.jsonl",
    }
    S = defaultdict(lambda: defaultdict(list))
    for key, g in src.items():
        for r in load_rows(sorted(glob.glob(str(O / g)))):
            if r["gamefile"] in games:
                tok = sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())
                S[key][r["task_id"]].append((float(r["success"]), r["progress_rate"], tok,
                                             r["legal_action_rate"] or 0.0))
    tasks = sorted(set.intersection(*[set(v) for v in S.values()]))
    rng = np.random.default_rng(2027)
    m = lambda key, k: np.array([np.mean([x[k] for x in S[key][t]]) for t in tasks])
    out = {"n_tasks": len(tasks), "arms": {}, "deltas": {}}
    for key in src:
        out["arms"]["/".join(key)] = {"reps": int(np.mean([len(S[key][t]) for t in tasks])),
                                      "SR": float(m(key, 0).mean()), "PR": float(m(key, 1).mean()),
                                      "tokens": float(m(key, 2).mean()), "legal": float(m(key, 3).mean())}
    for pl in ("4B", "14B"):
        for arm, ref in (("always", "none"), ("random_pre_nc_p0.3", "none"), ("oracle", "none"), ("oracle", "always")):
            for k, met in ((0, "SR"), (1, "PR")):
                d, lo, hi, p = boot_p(m((pl, arm), k) - m((pl, ref), k), rng)
                out["deltas"][f"{pl}:{arm}-{ref}:{met}"] = [d, lo, hi, p]
    for arm in ("none", "always", "oracle", "random_pre_nc_p0.3"):
        for k, met in ((0, "SR"), (1, "PR")):
            d, lo, hi, p = boot_p(m(("14B", arm), k) - m(("4B", arm), k), rng)
            out["deltas"][f"14B-4B:{arm}:{met}"] = [d, lo, hi, p]
    # interaction: does the foresight gain grow with planner size?
    for arm in ("always", "oracle", "random_pre_nc_p0.3"):
        for k, met in ((0, "SR"), (1, "PR")):
            g14 = m(("14B", arm), k) - m(("14B", "none"), k)
            g4 = m(("4B", arm), k) - m(("4B", "none"), k)
            d, lo, hi, p = boot_p(g14 - g4, rng)
            out["deltas"][f"gain14-gain4:{arm}:{met}"] = [d, lo, hi, p]
    sd = stage_dir(23)
    (sd / "tables" / "planner_4b_vs_14b.json").write_text(json.dumps(out, indent=2))
    f = lambda v: f"{100*v[0]:+.1f} [{100*v[1]:+.1f}, {100*v[2]:+.1f}] (p={v[3]:.3f})"
    L = [f"# Direction E: 4B vs 14B planner (WM = 4B), {len(tasks)} held-out dev tasks", "",
         "| planner | arm | reps | SR | PR | legal | tokens/task |", "|---|---|---:|---:|---:|---:|---:|"]
    for key in src:
        v = out["arms"]["/".join(key)]
        L.append(f"| {key[0]} | {key[1]} | {v['reps']} | {100*v['SR']:.1f}% | {100*v['PR']:.1f}% | "
                 f"{100*v['legal']:.1f}% | {v['tokens']/1000:.1f}k |")
    L += ["", "| contrast | ΔSR | ΔPR |", "|---|---|---|"]
    names = sorted({k.rsplit(":", 1)[0] for k in out["deltas"]})
    for n in names:
        L.append(f"| {n} | {f(out['deltas'][n + ':SR'])} | {f(out['deltas'][n + ':PR'])} |")
    (sd / "tables" / "planner_4b_vs_14b.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
