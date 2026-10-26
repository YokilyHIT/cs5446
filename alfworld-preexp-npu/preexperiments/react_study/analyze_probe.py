"""Round 4 feasibility probes (tables/preregistration_probe.json): 4B planner, dev460 x 2 reps.

Arms intervene only when a_base is not admissible: inv_resample (no information), inv_fail (bare
failure notice), inv_repair (environment-derived precondition diagnosis + admissible repair; oracle
upper bound of a repair-type WM), inv_proj (admissibility projection, no WM). References: none,
always (4B WM every step), oracle_every (true next obs every step).

    $PY -m preexperiments.react_study.analyze_probe
"""
from __future__ import annotations

import glob
import json
import re
from collections import defaultdict

import numpy as np

from preexperiments.react_study.analyze_episodes import load_rows
from preexperiments.react_study.analyze_round3 import boot_p, holm
from preexperiments.react_study.common import ROOT, stage_dir
from preexperiments.react_study.progress import subgoals_for

O = ROOT / "outputs" / "react_study"
SRC = {
    "none": "step0_protocol_v2_measurement/raw/train/dev_v2_c*_none__rep*.jsonl",
    "always": "step0_protocol_v2_measurement/raw/train/dev_v2_c*_always__rep*.jsonl",
    "oracle_every": "step1_upper_bound_controls/raw/train/dev_v2_o*_oracle__rep*.jsonl",
    **{a: f"probe_feasibility/raw/train/p4b_{a}_c*__rep*.jsonl" for a in ("inv_resample", "inv_fail", "inv_repair", "inv_proj")},
    "wmrepair_wm4": "probe_feasibility/raw/train/p4b_inv_wmrepair_wm4_c*__rep*.jsonl",
    "wmrepair_wm14": "probe_feasibility/raw/train/p4b_inv_wmrepair_wm14_c*__rep*.jsonl",
}
SRC14 = {
    "none": "dirE_larger_planner/raw/train/p14b_none_c*__rep*.jsonl",
    # (dirE 14B oracle_every covers only part of dev460 with 2 reps in this glob; left out so the
    #  14B family uses all 460 tasks)
    "R_r30": "p3_mechanism_matrix/raw/train/p14b_RT_r30_c*__rep*.jsonl",
    "inv_fail": "probe_feasibility/raw/train/p14b_inv_fail_c*__rep*.jsonl",
    "inv_repair": "probe_feasibility/raw/train/p14b_inv_repair_c*__rep*.jsonl",
    "wmrepair_wm14": "probe_feasibility/raw/train/p14b_inv_wmrepair_wm14_c*__rep*.jsonl",
}
PRIMARY = [("inv_repair", "inv_fail"), ("inv_repair", "inv_proj"), ("inv_proj", "none")]
# preregistration_wmrepair.json
FAMILIES = {"4B wmrepair (Holm over 3)": ("4B", [("wmrepair_wm14", "inv_fail"), ("wmrepair_wm4", "inv_fail"),
                                                  ("inv_repair", "wmrepair_wm14")]),
            "14B planner (Holm over 2)": ("14B", [("inv_repair", "none"), ("wmrepair_wm14", "inv_fail")])}


def funnel(r):
    sg = subgoals_for(r["gamefile"])
    obs = [s["next_observation"] for s in r["step_log"]]
    hit = [r["success"] or any(re.search(p, o[o.find(". ") + 2:] if o.startswith("You arrive at loc ") else o) for o in obs)
           for p in sg[:2]]
    return float(hit[0]), float(hit[1])


def collect(src, games):
    S = defaultdict(lambda: defaultdict(list))
    for k, g in src.items():
        for r in load_rows(sorted(p for p in glob.glob(str(O / g)) if not p.endswith(".config.json"))):
            if r["gamefile"] in games:
                tok = sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())
                seen, picked = funnel(r)
                rep = [s for s in r["step_log"] if s.get("gate_open") and "diag_repair" in s]
                S[k][r["task_id"]].append((float(r["success"]), r["progress_rate"], tok, r["legal_action_rate"] or 0.0,
                                           r.get("n_gate_open", 0) / max(r["steps"], 1), seen, picked,
                                           (sum(bool(s["diag_repair"]) for s in rep) / len(rep)) if rep else float("nan")))
    return S


def main():
    games = set(open(O / "step3_gating/raw/eval460_games.txt").read().split())
    S = defaultdict(lambda: defaultdict(list))
    for k, g in SRC.items():
        for r in load_rows(sorted(p for p in glob.glob(str(O / g)) if not p.endswith(".config.json"))):
            if r["gamefile"] in games:
                tok = sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())
                seen, picked = funnel(r)
                S[k][r["task_id"]].append((float(r["success"]), r["progress_rate"], tok, r["legal_action_rate"] or 0.0,
                                           r.get("n_gate_open", 0) / max(r["steps"], 1), seen, picked))
    keys = [k for k in SRC if S[k]]
    tasks = sorted(set.intersection(*[set(t for t, v in S[k].items() if len(v) >= 2) for k in keys]))
    m = lambda k, i: np.array([np.mean([x[i] for x in S[k][t][:2]]) for t in tasks])
    rng = np.random.default_rng(2027)
    out = {"n_tasks": len(tasks), "arms": {}, "primary": {}, "exploratory": {}}
    for k in keys:
        out["arms"][k] = {n: float(m(k, i).mean()) for i, n in enumerate(("SR", "PR", "tokens", "legal", "open_rate", "seen", "picked"))}
    prim = [(a, b) for a, b in PRIMARY if a in keys and b in keys]
    vs = [list(boot_p(m(a, 1) - m(b, 1), rng)) for a, b in prim]
    for (a, b), v, h in zip(prim, vs, holm(np.array([v[3] for v in vs])) if vs else []):
        out["primary"][f"{a}-{b}:PR"] = v + [float(h)]
    for a in keys:
        for b in ("none", "inv_resample", "inv_fail", "oracle_every"):
            if a != b and b in keys:
                for i, met in ((0, "SR"), (1, "PR")):
                    out["exploratory"][f"{a}-{b}:{met}"] = list(boot_p(m(a, i) - m(b, i), rng))
    sd = stage_dir(38)
    (sd / "tables" / "probe_4b.json").write_text(json.dumps(out, indent=2))
    f = lambda v: f"{100*v[0]:+.1f} [{100*v[1]:+.1f}, {100*v[2]:+.1f}] p={v[3]:.3f}" + (f" Holm={v[4]:.3f}" if len(v) > 4 else "")
    L = [f"# Feasibility probes, 4B planner, {len(tasks)} dev460 tasks x 2 reps", "",
         "| arm | SR | PR | legal | gate open/step | seen target | picked | tokens/task |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k in keys:
        v = out["arms"][k]
        L.append(f"| {k} | {100*v['SR']:.1f}% | {100*v['PR']:.1f}% | {v['legal']:.2f} | {v['open_rate']:.2f} | {v['seen']:.2f} | {v['picked']:.2f} | {v['tokens']/1000:.1f}k |")
    L += ["", "## Primary (pre-registered, Holm over 3)", "", "| contrast | Δ pp [95% CI] |", "|---|---|"]
    L += [f"| {k} | {f(v)} |" for k, v in out["primary"].items()]
    L += ["", "## Exploratory", "", "| contrast | Δ pp [95% CI] |", "|---|---|"]
    L += [f"| {k} | {f(v)} |" for k, v in sorted(out["exploratory"].items())]
    (sd / "tables" / "probe_4b.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    # ---- real-WM repair families (preregistration_wmrepair.json)
    L2, out2 = ["# Real-WM repair (no rules) vs oracle repair, dev460 x 2 reps", ""], {}
    for fam, (pl, pairs) in FAMILIES.items():
        S2 = collect(SRC if pl == "4B" else SRC14, games)
        ks = [k for k in (SRC if pl == "4B" else SRC14) if S2[k]]
        T = sorted(set.intersection(*[set(t for t, v in S2[k].items() if len(v) >= 2) for k in ks]))
        mm = lambda k, i: np.array([np.nanmean([x[i] for x in S2[k][t][:2]]) for t in T])
        L2 += [f"## {pl} planner arms ({len(T)} tasks)", "",
               "| arm | SR | PR | legal | gate open/step | repair given | tokens/task |", "|---|---:|---:|---:|---:|---:|---:|"]
        for k in ks:
            rg = np.nanmean([x[7] for t in T for x in S2[k][t][:2]]) if k.startswith(("inv_rep", "wmrep")) else float("nan")
            L2.append(f"| {k} | {100*mm(k,0).mean():.1f}% | {100*mm(k,1).mean():.1f}% | {mm(k,3).mean():.2f} | {mm(k,4).mean():.2f} | "
                      f"{rg:.2f} | {mm(k,2).mean()/1000:.1f}k |")
        vs = [list(boot_p(mm(a, 1) - mm(b, 1), rng)) for a, b in pairs]
        hs = holm(np.array([v[3] for v in vs]))
        L2 += ["", f"### {fam}, PR", "", "| contrast | Δ pp [95% CI] |", "|---|---|"]
        for (a, b), v, h in zip(pairs, vs, hs):
            out2[f"{pl}:{a}-{b}:PR"] = v + [float(h)]
            L2.append(f"| {a} - {b} | {f(v + [float(h)])} |")
        L2 += ["", "Exploratory SR:", ""]
        for a, b in pairs + [(x, "none") for x in ks if x != "none"]:
            v = boot_p(mm(a, 0) - mm(b, 0), rng)
            out2[f"{pl}:{a}-{b}:SR"] = list(v)
            L2.append(f"* {a} - {b}: {f(list(v))}")
        L2.append("")
    (sd / "tables" / "wmrepair.json").write_text(json.dumps(out2, indent=2))
    (sd / "tables" / "wmrepair.md").write_text("\n".join(L2) + "\n")
    print("\n".join(L2))


if __name__ == "__main__":
    main()
