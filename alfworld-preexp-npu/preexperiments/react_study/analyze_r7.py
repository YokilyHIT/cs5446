"""Round 7: rule-verified WM repair (r7_hybrid/tables/preregistration_r7.json).
Stage A on dev460 x 2 (selection), stage B on fresh600 x 3 (Holm over H1-H3 per planner, PR primary).

    $PY -m preexperiments.react_study.analyze_r7            # stage A
    $PY -m preexperiments.react_study.analyze_r7 --fresh    # stage B
"""
from __future__ import annotations

import glob
import json
from collections import defaultdict

import numpy as np

from preexperiments.react_study.analyze_episodes import load_rows
from preexperiments.react_study.analyze_round3 import B, boot_p, holm
from preexperiments.react_study.common import ROOT, stage_dir
from preexperiments.react_study.hybrid_r7 import rule_cat, wm_cat
from preexperiments.react_study.preconditions import diagnose

R = ROOT / "outputs" / "react_study"
OLD = {"inv_fail": "inv_fail", "inv_rules": "inv_rules", "frozen": "inv_wmrepair_wm14", "inv_repair": "inv_repair"}
NEW = ["inv_rpms", "wmrules_concat", "wmverify", "wmverify_learned"]


def files(pl, k):
    if k in OLD:
        g = R / "probe_feasibility/raw/train" / f"{pl}_{OLD[k]}_c*__rep*.jsonl"
    else:
        g = R / "r7_hybrid/raw/train" / f"{pl}_{k}_c*__rep*.jsonl"
    return sorted(p for p in glob.glob(str(g)) if not p.endswith(".config.json"))


def check_stats(rows):
    n = re = agree1 = agree2 = cov = 0
    for r in rows:
        h = []
        for s in r["step_log"]:
            if s.get("gate_open") and s.get("first_reason") is not None:
                c = rule_cat(diagnose(s["baseline_action"], h, s.get("admissible_actions") or [])["reason"])
                n += 1
                if c not in ("other", "absent"):
                    cov += 1
                    agree1 += wm_cat(s["first_reason"]) == c
                    agree2 += wm_cat(s["diag_reason"]) == c
                v = s.get("verify")
                re += bool(v and not v["ok"])
            h.append((s["action"], s["next_observation"]))
    return {"gate_steps": n, "reask_rate": re / max(n, 1), "cat_agree_before": agree1 / max(cov, 1),
            "cat_agree_after": agree2 / max(cov, 1)}


def main():
    rng = np.random.default_rng(2034)
    out, L = {}, ["# Round 7 stage A: rule-verified WM repair (dev460 x 2)", ""]
    for pl in ("p4b", "p14b"):
        S, rows = defaultdict(lambda: defaultdict(list)), {}
        for k in list(OLD) + NEW:
            rows[k] = load_rows(files(pl, k))
            for r in rows[k]:
                c = r["cost"].get("wm_alt", {})
                S[k][r["task_id"]].append((float(r["success"]), r["progress_rate"], c.get("calls", 0),
                                           sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())))
        keys = [k for k in list(OLD) + NEW if S[k]]
        tasks = sorted(set.intersection(*[set(S[k]) for k in keys]))
        m = lambda k, i: np.array([np.mean([x[i] for x in S[k][t][:2]]) for t in tasks])
        out[pl] = {"n_tasks": len(tasks), "arms": {}, "contrasts": {}}
        L += [f"## {pl[1:].upper()} planner ({len(tasks)} tasks x 2)", "",
              "| arm | SR | PR | 14B calls / ep | tokens / ep | re-ask rate | reason agrees with rules (before -> after) |",
              "|---|---:|---:|---:|---:|---:|---|"]
        for k in keys:
            v = {"SR": float(m(k, 0).mean()), "PR": float(m(k, 1).mean()), "calls14": float(m(k, 2).mean()),
                 "tokens": float(m(k, 3).mean())}
            extra = ""
            if k in ("wmverify", "wmverify_learned"):
                cs = check_stats(rows[k])
                v.update(cs)
                extra = f"{100*cs['reask_rate']:.0f}% | {100*cs['cat_agree_before']:.0f}% -> {100*cs['cat_agree_after']:.0f}%"
            else:
                extra = "- | -"
            out[pl]["arms"][k] = v
            L.append(f"| {k} | {100*v['SR']:.1f} | {100*v['PR']:.1f} | {v['calls14']:.1f} | {v['tokens']/1000:.1f}k | {extra} |")
        L += ["", "| contrast | dPR | dSR |", "|---|---|---|"]
        f = lambda v: f"{100*v[0]:+.1f} [{100*v[1]:+.1f}, {100*v[2]:+.1f}] p={v[3]:.3f}"
        for x in ("wmverify", "wmverify_learned", "wmrules_concat"):
            for y in ("frozen", "wmrules_concat", "inv_rpms"):
                if x == y or (x == "wmrules_concat" and y == "wmrules_concat"):
                    continue
                pr, sr = list(boot_p(m(x, 1) - m(y, 1), rng)), list(boot_p(m(x, 0) - m(y, 0), rng))
                out[pl]["contrasts"][f"{x}-{y}"] = {"PR": pr, "SR": sr}
                L.append(f"| {x} - {y} | {f(pr)} | {f(sr)} |")
        L.append("")
    sel = {}
    for v in ("wmverify", "wmverify_learned"):
        sel[v] = all(out[pl]["arms"][v]["PR"] > out[pl]["arms"]["frozen"]["PR"] and
                     out[pl]["arms"][v]["PR"] > out[pl]["arms"]["wmrules_concat"]["PR"] for pl in ("p4b", "p14b"))
    out["selection"] = sel
    L += ["## Pre-registered selection rule (dev PR above frozen AND concat for both planners)", "",
          *[f"* {v}: {'qualifies' if q else 'does not qualify'}" for v, q in sel.items()], ""]
    sd = stage_dir(41)
    (sd / "tables" / "dev_r7.json").write_text(json.dumps(out, indent=2))
    (sd / "tables" / "dev_r7.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


FRESH = {"none": "p7_final", "inv_fail": "p7_final", "inv_rules": "p7_final", "wmrepair_wm14": "p7_final",
         "inv_repair": "p7_final", "inv_rpms": "r6_baselines", "wmrules_concat": "r7_hybrid", "wmverify": "r7_hybrid"}
NAME = {"wmrepair_wm14": "frozen", "inv_rpms": "RPMS-style", "wmrules_concat": "concat", "wmverify": "verify (hand rules)"}


def ni_p(d, rng, margin=0.02):
    """One-sided paired-bootstrap p for mean(d) > -margin."""
    d = np.asarray(d, float) + margin
    bs = d[rng.integers(0, len(d), (B, len(d)))].mean(1)
    return float(max((bs <= 0).mean(), 1.0 / B))


def main_fresh():
    rng = np.random.default_rng(2035)
    out, L = {}, ["# Round 7 stage B: rule-verified WM repair on fresh600 x 3 (pre-registered)", ""]
    f = lambda v: f"{100*v[0]:+.1f} [{100*v[1]:+.1f}, {100*v[2]:+.1f}]"
    for pl in ("p4b", "p14b"):
        S, rows = defaultdict(lambda: defaultdict(list)), {}
        for k, d in FRESH.items():
            g = R / d / "raw/train" / f"fresh_{pl}_{k}_c*__rep*.jsonl"
            rows[k] = load_rows(sorted(p for p in glob.glob(str(g)) if not p.endswith(".config.json") and ".memory" not in p))
            for r in rows[k]:
                c = r["cost"].get("wm_alt", {})
                S[k][r["task_id"]].append((float(r["success"]), r["progress_rate"], c.get("calls", 0),
                                           sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())))
        keys = [k for k in FRESH if S[k]]
        nrep = min(min(len(v) for v in S[k].values()) for k in keys)
        tasks = sorted(set.intersection(*[set(S[k]) for k in keys]))
        m = lambda k, i: np.array([np.mean([x[i] for x in S[k][t][:nrep]]) for t in tasks])
        out[pl] = {"n_tasks": len(tasks), "reps": nrep, "arms": {}, "hypotheses": {}}
        L += [f"## {pl[1:].upper()} planner ({len(tasks)} tasks x {nrep} reps)", "",
              "| arm | SR | PR | 14B calls / ep | tokens / ep |", "|---|---:|---:|---:|---:|"]
        for k in keys:
            v = {"SR": float(m(k, 0).mean()), "PR": float(m(k, 1).mean()), "calls14": float(m(k, 2).mean()),
                 "tokens": float(m(k, 3).mean())}
            if k == "wmverify":
                v.update(check_stats(rows[k]))
            out[pl]["arms"][k] = v
            L.append(f"| {NAME.get(k, k)} | {100*v['SR']:.1f} | {100*v['PR']:.1f} | {v['calls14']:.1f} | {v['tokens']/1000:.1f}k |")
        if "reask_rate" in out[pl]["arms"].get("wmverify", {}):
            v = out[pl]["arms"]["wmverify"]
            L += ["", f"Check: re-ask on {100*v['reask_rate']:.0f}% of gate steps; reason agrees with the rule category "
                      f"{100*v['cat_agree_before']:.0f}% -> {100*v['cat_agree_after']:.0f}% after the re-ask."]
        H = [("H1", "wmverify", "wmrepair_wm14", "sup"), ("H2", "wmverify", "wmrules_concat", "sup"),
             ("H3", "wmverify", "inv_rpms", "ni")]
        res = []
        for h, x, y, kind in H:
            d = m(x, 1) - m(y, 1)
            pr = list(boot_p(d, rng))
            res.append((h, x, y, kind, pr, ni_p(d, rng) if kind == "ni" else pr[3], list(boot_p(m(x, 0) - m(y, 0), rng))))
        adj = holm(np.array([r[5] for r in res]))
        L += ["", "| hypothesis | dPR [95% CI] | test p | Holm | holds | dSR [95% CI] |", "|---|---|---:|---:|---|---|"]
        for (h, x, y, kind, pr, p, sr), a in zip(res, adj):
            ok = bool(a < 0.05 and (pr[0] > 0 if kind == "sup" else True))
            out[pl]["hypotheses"][h] = {"contrast": f"{x}-{y}", "kind": kind, "PR": pr, "p": p, "holm": float(a),
                                        "holds": ok, "SR": sr}
            lab = f"{h}: verify - {NAME[y]}" + (" (non-inferior, -2 pp)" if kind == "ni" else " (> 0)")
            L.append(f"| {lab} | {f(pr)} | {p:.4f} | {a:.4f} | {'yes' if ok else 'no'} | {f(sr)} p={sr[3]:.3f} |")
        L.append("")
    sd = stage_dir(41)
    (sd / "tables" / "fresh_r7.json").write_text(json.dumps(out, indent=2))
    (sd / "tables" / "fresh_r7.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    import sys
    main_fresh() if "--fresh" in sys.argv else main()
