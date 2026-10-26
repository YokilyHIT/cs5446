"""Round 5 stage B: frozen evaluation (p7_final/tables/preregistration_round5_final.json).

fresh_test600 (3 reps) and unseen134 (5 reps), 4B and 14B planners. Primary (4B, fresh600):
H1 PR(frozen) - PR(inv_fail), H3 SR(frozen) - SR(none) (two-sided, Holm over 2); H2 non-inferiority of
PR(frozen) - PR(inv_rules), margin -2 pp (95% CI lower bound). Everything else is secondary.

    $PY -m preexperiments.react_study.analyze_final [--set fresh600|unseen134]
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict

import numpy as np

from preexperiments.react_study.analyze_episodes import load_rows
from preexperiments.react_study.analyze_round3 import boot_p, holm
from preexperiments.react_study.common import ROOT, stage_dir

O = ROOT / "outputs" / "react_study" / "p7_final" / "raw"
ARMS = {"4B": ["none", "inv_fail", "inv_reflect", "inv_sreflect", "inv_rules", "wmrepair_wm4", "wmrepair_wm14", "inv_repair"],
        "14B": ["none", "inv_fail", "inv_reflect", "inv_sreflect", "inv_rules", "wmrepair_wm14", "inv_repair"]}
FROZEN = "wmrepair_wm14"
SETS = {"fresh600": ("train", "fresh_"), "unseen134": ("eval_out_of_distribution", "unseen_")}


def main(a):
    split, pre = SETS[a.set]
    rng = np.random.default_rng(2028)
    out, L = {"set": a.set}, [f"# Round 5 final evaluation: {a.set}", ""]
    f = lambda v: f"{100*v[0]:+.1f} [{100*v[1]:+.1f}, {100*v[2]:+.1f}] p={v[3]:.3f}" + (f" Holm={v[4]:.3f}" if len(v) > 4 else "")
    for pl, arms in ARMS.items():
        S = defaultdict(lambda: defaultdict(list))
        for arm in arms:
            for r in load_rows(sorted(p for p in glob.glob(str(O / split / f"{pre}p{pl.lower()}_{arm}_c*__rep*.jsonl"))
                                      if not p.endswith(".config.json"))):
                tok = sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())
                S[arm][r["task_id"]].append((float(r["success"]), r["progress_rate"], tok, r["legal_action_rate"] or 0.0))
        keys = [k for k in arms if S[k]]
        if not keys:
            continue
        nrep = min(min(len(v) for v in S[k].values()) for k in keys)
        tasks = sorted(set.intersection(*[set(S[k]) for k in keys]))
        m = lambda k, i: np.array([np.mean([x[i] for x in S[k][t][:nrep]]) for t in tasks])
        L += [f"## {pl} planner ({len(tasks)} tasks x {nrep} reps)", "",
              "| arm | SR | PR | legal | tokens/task |", "|---|---:|---:|---:|---:|"]
        out[pl] = {"n_tasks": len(tasks), "reps": nrep, "arms": {}, "contrasts": {}}
        for k in keys:
            out[pl]["arms"][k] = {"SR": float(m(k, 0).mean()), "PR": float(m(k, 1).mean()), "tokens": float(m(k, 2).mean())}
            L.append(f"| {k}{' (frozen)' if k == FROZEN else ''} | {100*m(k,0).mean():.1f}% | {100*m(k,1).mean():.1f}% | "
                     f"{m(k,3).mean():.2f} | {m(k,2).mean()/1000:.1f}k |")
        L.append("")
        if FROZEN in keys and pl == "4B" and a.set == "fresh600":
            h1 = list(boot_p(m(FROZEN, 1) - m("inv_fail", 1), rng))
            h3 = list(boot_p(m(FROZEN, 0) - m("none", 0), rng))
            hs = holm(np.array([h1[3], h3[3]]))
            h2 = list(boot_p(m(FROZEN, 1) - m("inv_rules", 1), rng))
            out["primary"] = {"H1 PR frozen-inv_fail": h1 + [float(hs[0])], "H3 SR frozen-none": h3 + [float(hs[1])],
                              "H2 PR frozen-inv_rules (NI, margin -2pp)": h2 + [bool(h2[1] > -0.02)]}
            L += ["### Pre-registered primary (4B, fresh600)", "",
                  f"* H1 PR(frozen) - PR(inv_fail): {f(h1 + [float(hs[0])])}",
                  f"* H3 SR(frozen) - SR(none): {f(h3 + [float(hs[1])])}",
                  f"* H2 non-inferiority PR(frozen) - PR(inv_rules): {f(h2)} -> "
                  f"{'NON-INFERIOR' if h2[1] > -0.02 else 'not shown non-inferior'} (margin -2 pp)", ""]
        L += [f"### Secondary contrasts ({pl}, uncorrected)", "", "| contrast | ΔSR | ΔPR |", "|---|---|---|"]
        for x, y in [(FROZEN, "none"), (FROZEN, "inv_fail"), (FROZEN, "inv_reflect"), (FROZEN, "inv_sreflect"),
                     (FROZEN, "inv_rules"), ("wmrepair_wm4", "inv_fail"), ("wmrepair_wm4", FROZEN), ("inv_rules", "inv_fail"),
                     ("inv_repair", FROZEN), ("inv_fail", "none"), ("inv_reflect", "inv_fail"), ("inv_sreflect", "inv_fail")]:
            if x in keys and y in keys:
                vs, vp = list(boot_p(m(x, 0) - m(y, 0), rng)), list(boot_p(m(x, 1) - m(y, 1), rng))
                out[pl]["contrasts"][f"{x}-{y}"] = {"SR": vs, "PR": vp}
                L.append(f"| {x} - {y} | {f(vs)} | {f(vp)} |")
        L.append("")
    sd = stage_dir(37)
    (sd / "tables" / f"final_{a.set}.json").write_text(json.dumps(out, indent=2))
    (sd / "tables" / f"final_{a.set}.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="fresh600", choices=list(SETS))
    main(ap.parse_args())
