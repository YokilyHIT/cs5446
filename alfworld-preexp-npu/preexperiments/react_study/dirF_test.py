"""Direction F: pre-registered hypotheses on unseen 134 (tables/preregistration.json) + exploratory table."""
from __future__ import annotations

import glob
import json
from collections import defaultdict

import numpy as np

from preexperiments.react_study.analyze_episodes import load_rows
from preexperiments.react_study.analyze_round3 import boot_p, holm
from preexperiments.react_study.common import ROOT, stage_dir

O = ROOT / "outputs" / "react_study"


def main():
    p = (glob.glob(str(O / "dirF_final_eval/raw/eval_out_of_distribution/unseen_*rep*.jsonl"))
         + glob.glob(str(O / "step4_unseen_test/raw/compare/*.jsonl")))
    rows = load_rows(sorted(x for x in p if not x.endswith((".config.json", ".memory.jsonl"))))
    for r in rows:
        if r["arm"] == "random_pre" and "posthoc_random_pre" in r.get("_src", ""):
            pass
    S = defaultdict(lambda: defaultdict(list))
    for r in rows:
        arm = r["arm"]
        if arm == "random_pre":
            arm = "random_pre_cc_p0.3"  # step-4 post-hoc control had the closed-gate second call
        tok = sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())
        S[arm][r["task_id"]].append((float(r["success"]), r["progress_rate"], tok))
    tasks = sorted(set.intersection(*[set(v) for v in S.values()]))
    rng = np.random.default_rng(2027)

    def delta(a, b, k):
        return [np.mean([x[k] for x in S[a][t]]) - np.mean([x[k] for x in S[b][t]]) for t in tasks]

    H = [("H1_B", "gate_unc", "random_pre_nc_p0.3", 1), ("H2_C", "fore_topk_p0.3", "random_pre_nc_p0.3", 1),
         ("H3_A", "explore_stuck", "none", 0)]
    res = []
    for name, a, b, k in H:
        m, lo, hi, pv = boot_p(delta(a, b, k), rng)
        res.append({"hyp": name, "arm": a, "ref": b, "metric": "PR" if k else "SR", "delta": m, "ci": [lo, hi], "p": pv})
    for r_, q in zip(res, holm(np.array([r["p"] for r in res]))):
        r_["p_holm"] = float(q)
    summ = {a: {"reps": int(np.mean([len(S[a][t]) for t in tasks])),
                "SR": float(np.mean([np.mean([x[0] for x in S[a][t]]) for t in tasks])),
                "PR": float(np.mean([np.mean([x[1] for x in S[a][t]]) for t in tasks])),
                "tokens": float(np.mean([np.mean([x[2] for x in S[a][t]]) for t in tasks]))} for a in S}
    expl = []
    for a in sorted(S):
        if a == "none":
            continue
        for k, met in ((0, "SR"), (1, "PR")):
            m, lo, hi, pv = boot_p(delta(a, "none", k), rng)
            expl.append({"arm": a, "metric": met, "delta": m, "ci": [lo, hi], "p": pv})
    sd = stage_dir(24)
    (sd / "tables" / "unseen_final.json").write_text(json.dumps({"n_tasks": len(tasks), "preregistered": res,
                                                                "summary": summ, "exploratory_vs_none": expl}, indent=2))
    L = [f"# Direction F — unseen 134 (n_tasks={len(tasks)})", "", "## Pre-registered (Holm over 3)", "",
         "| hypothesis | contrast | metric | Δ [95% CI] | p | p_holm |", "|---|---|---|---|---:|---:|"]
    for r in res:
        L.append(f"| {r['hyp']} | {r['arm']} − {r['ref']} | {r['metric']} | {100*r['delta']:+.1f} "
                 f"[{100*r['ci'][0]:+.1f}, {100*r['ci'][1]:+.1f}] | {r['p']:.3f} | {r['p_holm']:.3f} |")
    L += ["", "## All arms (exploratory, vs none, uncorrected)", "",
          "| arm | reps | SR | ΔSR [CI] | PR | ΔPR [CI] | tokens/task |", "|---|---:|---:|---|---:|---|---:|"]
    e = {(x["arm"], x["metric"]): x for x in expl}
    f = lambda x: f"{100*x['delta']:+.1f} [{100*x['ci'][0]:+.1f}, {100*x['ci'][1]:+.1f}]"
    for a in sorted(S, key=lambda a: (a != "none", -summ[a]["PR"])):
        v = summ[a]
        L.append(f"| {a} | {v['reps']} | {100*v['SR']:.1f}% | {f(e[(a,'SR')]) if a != 'none' else '—'} | "
                 f"{100*v['PR']:.1f}% | {f(e[(a,'PR')]) if a != 'none' else '—'} | {v['tokens']/1000:.1f}k |")
    (sd / "tables" / "unseen_final.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
