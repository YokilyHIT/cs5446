"""Round 4 failure analysis on dev460 x 2 reps (4B / 14B planner, `none`; 4B oracle_every for contrast).

Outputs (outputs/react_study/failure_analysis/tables/failure_analysis.{md,json}):
  1. action validity: share of executed actions not in the admissible list (although v2-list shows it),
     "Nothing happens." per step, repeated actions per step, failures ending in a loop
     (last 10 actions <= 4 distinct)
  2. subgoal funnel (AgentBoard subgoals: see target -> pick it up -> success)
  3. post-pick failures by task type
  4. heat / cool / clean attempts: at the appliance or not, admissible or not, outcome

    $PY -m preexperiments.react_study.failure_analysis
"""
from __future__ import annotations

import glob
import json
import re
from collections import Counter, defaultdict

import numpy as np

from preexperiments.react_study.analyze_episodes import load_rows
from preexperiments.react_study.common import ROOT, stage_dir
from preexperiments.react_study.progress import _parse, subgoals_for

O = ROOT / "outputs" / "react_study"
SRC = {"4B none": "step0_protocol_v2_measurement/raw/train/dev_v2_c*_none__rep*.jsonl",
       "4B oracle_every": "step1_upper_bound_controls/raw/train/dev_v2_o*_oracle__rep*.jsonl",
       "14B none": "dirE_larger_planner/raw/train/p14b_none_c*__rep*.jsonl"}
APP = {"pick_heat_then_place_in_recep": "microwave", "pick_cool_then_place_in_recep": "fridge",
       "pick_clean_then_place_in_recep": "sinkbasin"}


def obs_body(o):
    return o[o.find(". ") + 2:] if o.startswith("You arrive at loc ") else o


def main():
    games = set(open(O / "step3_gating/raw/eval460_games.txt").read().split())
    out, L = {}, ["# Failure analysis (dev460 x 2 reps, protocol v2-list)", ""]
    L += ["## 1. Action validity and loops", "",
          "| run | episodes | SR | inadmissible actions | 'Nothing happens'/step | repeated action/step | failures ending in a loop |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    funnel_rows, post_rows, hcc_rows = [], [], []
    for name, g in SRC.items():
        R = [r for r in load_rows(sorted(p for p in glob.glob(str(O / g)) if not p.endswith(".config.json")))
             if r["gamefile"] in games]
        fail = [r for r in R if not r["success"]]
        loopy = lambda r: len(r["step_log"]) >= 10 and len({s["action"] for s in r["step_log"][-10:]}) <= 4
        v = {"n": len(R), "SR": float(np.mean([r["success"] for r in R])),
             "inadmissible": 1 - float(np.mean([r["legal_action_rate"] for r in R if r["legal_action_rate"] is not None])),
             "nothing_per_step": float(np.mean([np.mean(["Nothing happens" in s["next_observation"] for s in r["step_log"]]) for r in R])),
             "repeat_per_step": float(np.mean([np.mean([s["action"] in {x["action"] for x in r["step_log"][:i]}
                                                         for i, s in enumerate(r["step_log"])]) for r in R])),
             "fail_loop_ending": float(np.mean([loopy(r) for r in fail]))}
        L.append(f"| {name} | {v['n']} | {100*v['SR']:.1f}% | {100*v['inadmissible']:.1f}% | {v['nothing_per_step']:.3f} | "
                 f"{v['repeat_per_step']:.3f} | {v['fail_loop_ending']:.2f} |")
        # funnel
        seen = picked = 0
        post = defaultdict(lambda: [0, 0])
        hcc = Counter()
        for r in R:
            sg = subgoals_for(r["gamefile"])
            obs = [s["next_observation"] for s in r["step_log"]]
            pi = next((i for i, o in enumerate(obs) if re.search(sg[1], obs_body(o))), None)
            s_ok = r["success"] or any(re.search(sg[0], obs_body(o)) for o in obs)
            p_ok = r["success"] or pi is not None
            seen += s_ok
            picked += p_ok
            tt, _o, _r = _parse(r["gamefile"])
            if p_ok:
                post[tt][0] += 1
                post[tt][1] += (not r["success"])
            loc = None
            for s in r["step_log"]:
                a, o = s["action"], s["next_observation"]
                m = re.match(r"(heat|cool|clean) (.+?) with (.+)$", a)
                if m:
                    hcc[(m.group(1), "at appliance" if loc == m.group(3) else "away",
                         "admissible" if s["action_admissible"] else "NOT admissible",
                         "ok" if "Nothing happens" not in o else "nothing happens")] += 1
                if a.startswith("go to ") and "Nothing happens" not in o:
                    loc = a[6:]
        n, nsucc = len(R), sum(r["success"] for r in R)
        v["funnel"] = {"seen": seen / n, "picked": picked / n, "success": nsucc / n,
                       "P(pick|seen)": picked / seen, "P(success|picked)": nsucc / picked}
        v["post_pick_fail_by_type"] = {k: {"picked": a, "fail_after_pick": b / a} for k, (a, b) in sorted(post.items())}
        tot = sum(hcc.values())
        v["heat_cool_clean"] = {"attempts": tot, "inadmissible_share": sum(c for k, c in hcc.items() if k[2] == "NOT admissible") / max(tot, 1),
                                "cells": {" / ".join(k): c for k, c in hcc.most_common()}}
        out[name] = v
        funnel_rows.append((name, v["funnel"]))
        post_rows.append((name, v["post_pick_fail_by_type"]))
        hcc_rows.append((name, v["heat_cool_clean"]))
    L += ["", "## 2. Subgoal funnel (AgentBoard subgoals)", "",
          "| run | saw target | picked it up | success | P(pick | seen) | P(success | picked) |", "|---|---:|---:|---:|---:|---:|"]
    for name, f in funnel_rows:
        L.append(f"| {name} | {f['seen']:.2f} | {f['picked']:.2f} | {f['success']:.3f} | {f['P(pick|seen)']:.2f} | {f['P(success|picked)']:.2f} |")
    L += ["", "## 3. Failure after picking the target, by task type", "", "| run | task type | episodes that picked | failed after pick |", "|---|---|---:|---:|"]
    for name, d in post_rows:
        for k, x in d.items():
            L.append(f"| {name} | {k} | {x['picked']} | {x['fail_after_pick']:.2f} |")
    L += ["", "## 4. heat / cool / clean attempts", ""]
    for name, h in hcc_rows:
        L.append(f"**{name}**: {h['attempts']} attempts, {100*h['inadmissible_share']:.0f}% not admissible")
        L += [f"* {k}: {c}" for k, c in list(h["cells"].items())[:8]] + [""]
    sd = stage_dir(39)
    (sd / "tables" / "failure_analysis.json").write_text(json.dumps(out, indent=2))
    (sd / "tables" / "failure_analysis.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
