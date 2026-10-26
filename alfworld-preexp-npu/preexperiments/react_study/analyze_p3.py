"""Round 4 / Phase 3: full-task 2x2 mechanism matrix (planner 4B/14B x {none, R, R0, W4, W14, oracle_r30}).

dev460 x 2 reps; every intervention arm opens on the same random 30% of steps (gate_seed 2027,
NC when closed), so W - R isolates foresight content from "a second, different action".
Primary family (tables/preregistration_p3.json): W4-R, W14-R, oracle_r30-R on PR for each planner,
Holm-corrected. Everything else is exploratory.

    $PY -m preexperiments.react_study.analyze_p3
"""
from __future__ import annotations

import glob
import json
from collections import defaultdict

import numpy as np

from preexperiments.react_study.analyze_episodes import load_rows
from preexperiments.react_study.analyze_round3 import boot_p, holm
from preexperiments.react_study.common import ROOT, stage_dir

O = ROOT / "outputs" / "react_study"
P3 = "p3_mechanism_matrix/raw/train/"
SRC = {
    ("4B", "none"): "step0_protocol_v2_measurement/raw/train/dev_v2_c*_none__rep*.jsonl",
    ("4B", "always"): "step0_protocol_v2_measurement/raw/train/dev_v2_c*_always__rep*.jsonl",
    ("4B", "oracle_every"): "step1_upper_bound_controls/raw/train/dev_v2_o*_oracle__rep*.jsonl",
    ("4B", "W4"): "dirA_D_mechanism_dose/raw/train/random_pre_nc_p0.3_c*__rep*.jsonl",
    ("4B", "R"): P3 + "p4b_RT_r30_c*__rep*.jsonl",
    ("4B", "R0"): P3 + "p4b_R0_r30_c*__rep*.jsonl",
    ("4B", "W14"): P3 + "p4b_W14_r30_c*__rep*.jsonl",
    ("4B", "oracle_r30"): P3 + "p4b_oracle_r30_c*__rep*.jsonl",
    ("14B", "none"): "dirE_larger_planner/raw/train/p14b_none_c*__rep*.jsonl",
    ("14B", "always"): "dirE_larger_planner/raw/train/p14b_always_c*__rep*.jsonl",
    ("14B", "oracle_every"): "dirE_larger_planner/raw/train/p14b_oracle_*__rep*.jsonl",
    ("14B", "W4"): "dirE_larger_planner/raw/train/p14b_random_c*__rep*.jsonl",
    ("14B", "R"): P3 + "p14b_RT_r30_c*__rep*.jsonl",
    ("14B", "W14"): P3 + "p14b_W14_r30_c*__rep*.jsonl",
    ("14B", "oracle_r30"): P3 + "p14b_oracle_r30_c*__rep*.jsonl",
}
PRIMARY = [(pl, a, "R") for pl in ("4B", "14B") for a in ("W4", "W14", "oracle_r30")]


def main():
    games = set(open(O / "step3_gating/raw/eval460_games.txt").read().split())
    S = defaultdict(lambda: defaultdict(list))
    for key, g in SRC.items():
        for r in load_rows(sorted(p for p in glob.glob(str(O / g)) if not p.endswith(".config.json"))):
            if r["gamefile"] in games:
                tok = sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())
                S[key][r["task_id"]].append((float(r["success"]), r["progress_rate"], tok,
                                             r.get("n_action_changed", 0) / max(r["steps"], 1)))
    keys = [k for k in SRC if S[k]]
    tasks = sorted(set.intersection(*[set(t for t, v in S[k].items() if len(v) >= 2) for k in keys]))
    rng = np.random.default_rng(2027)
    m = lambda key, k: np.array([np.mean([x[k] for x in S[key][t][:2]]) for t in tasks])
    out = {"n_tasks": len(tasks), "arms": {}, "primary": {}, "exploratory": {}}
    for key in keys:
        out["arms"]["/".join(key)] = {"SR": float(m(key, 0).mean()), "PR": float(m(key, 1).mean()),
                                      "tokens": float(m(key, 2).mean()), "changed_per_step": float(m(key, 3).mean())}
    prim = [(pl, a, b) for pl, a, b in PRIMARY if (pl, a) in keys and (pl, b) in keys]
    ps = []
    for pl, a, b in prim:
        v = boot_p(m((pl, a), 1) - m((pl, b), 1), rng)
        out["primary"][f"{pl}:{a}-{b}:PR"] = list(v)
        ps.append(v[3])
    for (k, v), h in zip(list(out["primary"].items()), holm(np.array(ps)) if ps else []):
        out["primary"][k] = v + [float(h)]
    expl = []
    for pl in ("4B", "14B"):
        for a, b in (("R", "none"), ("R0", "none"), ("W4", "none"), ("W14", "none"), ("oracle_r30", "none"),
                     ("W14", "W4"), ("oracle_r30", "W4"), ("R0", "R"), ("always", "none"), ("oracle_every", "none")):
            expl.append((pl, a, b))
    for pl, a, b in expl:
        if (pl, a) in keys and (pl, b) in keys:
            for k, met in ((0, "SR"), (1, "PR")):
                out["exploratory"][f"{pl}:{a}-{b}:{met}"] = list(boot_p(m((pl, a), k) - m((pl, b), k), rng))
    for pl in ("4B", "14B"):
        for a in ("W4", "W14", "oracle_r30"):
            if (pl, a) in keys and (pl, "R") in keys:
                out["exploratory"][f"{pl}:{a}-R:SR"] = list(boot_p(m((pl, a), 0) - m((pl, "R"), 0), rng))
    for a in ("W4", "W14", "oracle_r30", "R"):
        ref = "R" if a != "R" else "none"
        if all((pl, x) in keys for pl in ("4B", "14B") for x in (a, ref)):
            for k, met in ((0, "SR"), (1, "PR")):
                g4 = m(("4B", a), k) - m(("4B", ref), k)
                g14 = m(("14B", a), k) - m(("14B", ref), k)
                out["exploratory"][f"interaction(14B-4B):{a}-{ref}:{met}"] = list(boot_p(g14 - g4, rng))
    sd = stage_dir(33)
    (sd / "tables" / "p3_matrix.json").write_text(json.dumps(out, indent=2))
    f = lambda v: f"{100*v[0]:+.1f} [{100*v[1]:+.1f}, {100*v[2]:+.1f}] p={v[3]:.3f}" + (f" Holm={v[4]:.3f}" if len(v) > 4 else "")
    L = [f"# Phase 3: full-task mechanism matrix, {len(tasks)} dev460 tasks x 2 reps", "",
         "| planner | arm | SR | PR | tokens/task | changed actions/step |", "|---|---|---:|---:|---:|---:|"]
    for key in keys:
        v = out["arms"]["/".join(key)]
        L.append(f"| {key[0]} | {key[1]} | {100*v['SR']:.1f}% | {100*v['PR']:.1f}% | {v['tokens']/1000:.1f}k | {v['changed_per_step']:.3f} |")
    L += ["", "## Primary (pre-registered, Holm over 6)", "", "| contrast | Δ (pp) [95% CI] |", "|---|---|"]
    L += [f"| {k} | {f(v)} |" for k, v in out["primary"].items()]
    L += ["", "## Exploratory (uncorrected)", "", "| contrast | Δ (pp) [95% CI] |", "|---|---|"]
    L += [f"| {k} | {f(v)} |" for k, v in sorted(out["exploratory"].items())]
    (sd / "tables" / "p3_matrix.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
