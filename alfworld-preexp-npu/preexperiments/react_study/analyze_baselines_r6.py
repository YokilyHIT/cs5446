"""Round 6: frozen method vs recent-work baselines on fresh600 x 3 (r6_baselines/tables/preregistration_baselines.json).

Per planner: table of SR / PR / 14B calls and tokens per episode; Holm family over frozen - {walle, walle_rules,
inv_rpms, expel, inv_expel} on PR; non-inferiority check (95% CI lower bound > -2 pp); SR versions secondary.

    $PY -m preexperiments.react_study.analyze_baselines_r6
"""
from __future__ import annotations

import glob
import json
from collections import defaultdict

import numpy as np

from preexperiments.react_study.analyze_episodes import load_rows
from preexperiments.react_study.analyze_round3 import boot_p, holm
from preexperiments.react_study.common import ROOT, stage_dir

R = ROOT / "outputs" / "react_study"
REF = ["none", "inv_fail", "inv_rules", "wmrepair_wm14", "inv_repair"]
NEW = ["walle", "walle_rules", "inv_rpms", "expel", "inv_expel"]
SEL = ["selective", "selective_em"]   # WorldEvolver-style confidence gate, separate family (preregistration_selective.json)
FROZEN = "wmrepair_wm14"


def src(pl, arm):
    if arm in REF:
        return R / "p7_final/raw/train" / f"fresh_{pl}_{arm}_c*__rep*.jsonl"
    return R / "r6_baselines/raw/train" / f"fresh_{pl}_{arm}_c*__rep*.jsonl"


def main():
    f = lambda v: f"{100*v[0]:+.1f} [{100*v[1]:+.1f}, {100*v[2]:+.1f}] p={v[3]:.3f}" + (f" Holm={v[4]:.3f}" if len(v) > 4 else "")
    rng = np.random.default_rng(2032)
    out, L = {}, ["# Frozen method vs recent-work baselines (fresh600 x 3, aligned models and tasks)", ""]
    for pl in ("p4b", "p14b"):
        S = defaultdict(lambda: defaultdict(list))
        for arm in REF + NEW + SEL:
            for r in load_rows(sorted(p for p in glob.glob(str(src(pl, arm))) if not p.endswith(".config.json") and ".memory" not in p)):
                tok = sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())
                c14 = r["cost"].get("wm_alt", {})
                S[arm][r["task_id"]].append((float(r["success"]), r["progress_rate"], tok,
                                             c14.get("calls", 0), c14.get("prompt_tokens", 0) + c14.get("completion_tokens", 0)))
        keys = [k for k in REF + NEW + SEL if S[k]]
        nrep = min(min(len(v) for v in S[k].values()) for k in keys)
        tasks = sorted(set.intersection(*[set(S[k]) for k in keys]))
        m = lambda k, i: np.array([np.mean([x[i] for x in S[k][t][:nrep]]) for t in tasks])
        out[pl] = {"n_tasks": len(tasks), "reps": nrep, "arms": {}, "primary": {}}
        L += [f"## {pl[1:].upper()} planner ({len(tasks)} tasks x {nrep} reps)", "",
              "| arm | SR | PR | 14B calls / ep | tokens / ep (14B) |", "|---|---:|---:|---:|---:|"]
        for k in keys:
            v = {"SR": float(m(k, 0).mean()), "PR": float(m(k, 1).mean()), "tokens": float(m(k, 2).mean()),
                 "calls14": float(m(k, 3).mean()), "tokens14": float(m(k, 4).mean())}
            out[pl]["arms"][k] = v
            L.append(f"| {k}{' (frozen)' if k == FROZEN else ''} | {100*v['SR']:.1f}% | {100*v['PR']:.1f}% | {v['calls14']:.1f} | "
                     f"{v['tokens']/1000:.1f}k ({v['tokens14']/1000:.1f}k) |")
        for fam, members in (("recent-method baselines", NEW), ("WorldEvolver-style confidence gate", SEL)):
            pairs = [(FROZEN, b) for b in members if b in keys]
            if not pairs:
                continue
            vs = [list(boot_p(m(x, 1) - m(y, 1), rng)) for x, y in pairs]
            hs = holm(np.array([v[3] for v in vs]))
            L += ["", f"### Pre-registered family: {fam} (Holm over {len(pairs)}), PR; SR exploratory", "",
                  "| contrast | ΔPR | non-inferior (−2 pp) | ΔSR |", "|---|---|---|---|"]
            for (x, y), v, h in zip(pairs, vs, hs):
                sr = list(boot_p(m(x, 0) - m(y, 0), rng))
                out[pl]["primary"][f"{x}-{y}"] = {"PR": v + [float(h)], "SR": sr, "noninferior": bool(v[1] > -0.02), "family": fam}
                L.append(f"| {x} - {y} | {f(v + [float(h)])} | {'yes' if v[1] > -0.02 else 'no'} | {f(sr)} |")
        L.append("")
    sd = stage_dir(40)
    (sd / "tables" / "baselines_fresh600.json").write_text(json.dumps(out, indent=2))
    (sd / "tables" / "baselines_fresh600.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
