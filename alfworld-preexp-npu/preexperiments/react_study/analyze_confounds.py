"""Confound controls and follow-ups (p7_final/tables/preregistration_confounds.json, preregistration_followups.json).

4B planner, 14B WM / takeover model. Primary families on fresh_test600 x 3 (Holm within family, PR):
  confounds  C1 wmrepair_wm14 - inv_takeover, C2 wmrepair_wm14 - inv_wmpred_info, C3 wmrepair_reason - inv_fail
  follow-ups E1 inv_wmrepair_exec - wmrepair_wm14, E2 inv_wmrepair_mem - wmrepair_wm14
Also per-arm adoption of the suggested repair and repeated same-failure per episode; dev460 x 2 for reference.

    $PY -m preexperiments.react_study.analyze_confounds
"""
from __future__ import annotations

import glob
import json
from collections import Counter, defaultdict

import numpy as np

from preexperiments.react_study.analyze_episodes import load_rows
from preexperiments.react_study.analyze_round3 import boot_p, holm
from preexperiments.react_study.common import ROOT, stage_dir

R = ROOT / "outputs" / "react_study"
FRESH = {a: f"p7_final/raw/train/fresh_p4b_{a}_c*__rep*.jsonl" for a in
         ("none", "inv_fail", "inv_rules", "wmrepair_wm14", "inv_repair")}
FRESH.update({a: f"p7_final/raw/train/fresh_p4b_{a}_wm14_c*__rep*.jsonl" for a in
              ("inv_takeover", "inv_wmpred", "inv_wmpred_info", "inv_wmrepair_reason", "inv_wmrepair_action",
               "inv_wmrepair_exec", "inv_wmrepair_mem")})
PF = "probe_feasibility/raw/train/"
DEV = {"none": "step0_protocol_v2_measurement/raw/train/dev_v2_c*_none__rep*.jsonl",
       "inv_fail": PF + "p4b_inv_fail_c*__rep*.jsonl", "inv_rules": PF + "p4b_inv_rules_c*__rep*.jsonl",
       "inv_wmpred": PF + "p4b_inv_wmpred_wm14_c*__rep*.jsonl", "wmrepair_wm14": PF + "p4b_inv_wmrepair_wm14_c*__rep*.jsonl",
       "inv_repair": PF + "p4b_inv_repair_c*__rep*.jsonl"}
DEV.update({a: PF + f"p4b_{a}_wm14_c*__rep*.jsonl" for a in
            ("inv_takeover", "inv_wmpred_info", "inv_wmrepair_reason", "inv_wmrepair_action", "inv_wmrepair_exec", "inv_wmrepair_mem")})
FAMILIES = {"confounds": [("wmrepair_wm14", "inv_takeover"), ("wmrepair_wm14", "inv_wmpred_info"), ("inv_wmrepair_reason", "inv_fail")],
            "follow-ups": [("inv_wmrepair_exec", "wmrepair_wm14"), ("inv_wmrepair_mem", "wmrepair_wm14")]}
SECONDARY = [("inv_wmrepair_action", "inv_fail"), ("wmrepair_wm14", "inv_wmrepair_action"), ("wmrepair_wm14", "inv_wmrepair_reason"),
             ("inv_wmpred_info", "inv_wmpred"), ("inv_takeover", "inv_fail"), ("wmrepair_wm14", "inv_wmpred"),
             ("inv_wmrepair_exec", "inv_repair"), ("inv_wmrepair_mem", "inv_rules")]


def episode_metrics(r):
    seen = Counter(s["baseline_action"] for s in r["step_log"] if s.get("gate_open"))
    rp = [s for s in r["step_log"] if s.get("gate_open") and s.get("diag_repair")]
    return {"repeat": sum(v - 1 for v in seen.values() if v > 1),
            "gates": sum(1 for s in r["step_log"] if s.get("gate_open")),
            "adopt": (np.mean([s["second_action"] == s["diag_repair"] for s in rp]) if rp else float("nan"))}


def collect(src):
    S, M = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    for k, g in src.items():
        for r in load_rows(sorted(p for p in glob.glob(str(R / g)) if not p.endswith(".config.json"))):
            tok = sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())
            tok14 = sum(e["prompt_tokens"] + e["completion_tokens"] for role, e in r["cost"].items() if role == "wm_alt")
            S[k][r["task_id"]].append((float(r["success"]), r["progress_rate"], tok, tok14))
            for mk, v in episode_metrics(r).items():
                M[k][mk].append(v)
    return S, M


def main():
    f = lambda v: f"{100*v[0]:+.1f} [{100*v[1]:+.1f}, {100*v[2]:+.1f}] p={v[3]:.3f}" + (f" Holm={v[4]:.3f}" if len(v) > 4 else "")
    rng = np.random.default_rng(2029)
    out, L = {}, ["# Confound controls and follow-ups (4B planner, 14B WM / takeover model)", ""]
    for name, src in (("fresh600", FRESH), ("dev460", DEV)):
        S, M = collect(src)
        keys = [k for k in src if S[k]]
        nrep = min(min(len(v) for v in S[k].values()) for k in keys)
        tasks = sorted(set.intersection(*[set(S[k]) for k in keys]))
        m = lambda k, i: np.array([np.mean([x[i] for x in S[k][t][:nrep]]) for t in tasks])
        out[name] = {"n_tasks": len(tasks), "reps": nrep, "arms": {}, "families": {}, "secondary": {}}
        L += [f"## {name} ({len(tasks)} tasks x {nrep} reps)", "",
              "| arm | SR | PR | repeated same failure / ep | repair adopted | tokens/task (of which 14B) |",
              "|---|---:|---:|---:|---:|---:|"]
        for k in keys:
            mt = M[k]
            ad = np.nanmean(mt["adopt"]) if np.any(~np.isnan(mt["adopt"])) else float("nan")
            out[name]["arms"][k] = {"SR": float(m(k, 0).mean()), "PR": float(m(k, 1).mean()), "repeat": float(np.mean(mt["repeat"])),
                                    "adopt": float(ad), "tokens": float(m(k, 2).mean()), "tokens_14B": float(m(k, 3).mean())}
            a = out[name]["arms"][k]
            adopt = "-" if np.isnan(a["adopt"]) else "%.2f" % a["adopt"]
            L.append(f"| {k} | {100*a['SR']:.1f}% | {100*a['PR']:.1f}% | {a['repeat']:.2f} | {adopt} | "
                     f"{a['tokens']/1000:.1f}k ({a['tokens_14B']/1000:.1f}k) |")
        L.append("")
        for fam, pairs in FAMILIES.items():
            pairs = [(x, y) for x, y in pairs if x in keys and y in keys]
            vs = [list(boot_p(m(x, 1) - m(y, 1), rng)) for x, y in pairs]
            hs = holm(np.array([v[3] for v in vs])) if vs else []
            tag = "pre-registered primary, Holm" if name == "fresh600" else "dev reference, Holm within family"
            L += [f"### {fam} ({tag}), PR (SR exploratory)", "", "| contrast | ΔPR | ΔSR |", "|---|---|---|"]
            for (x, y), v, h in zip(pairs, vs, hs):
                sr = list(boot_p(m(x, 0) - m(y, 0), rng))
                out[name]["families"][f"{fam}:{x}-{y}"] = {"PR": v + [float(h)], "SR": sr}
                L.append(f"| {x} - {y} | {f(v + [float(h)])} | {f(sr)} |")
            L.append("")
        L += ["### Secondary (uncorrected)", "", "| contrast | ΔPR | ΔSR |", "|---|---|---|"]
        for x, y in SECONDARY:
            if x in keys and y in keys:
                vp, vs_ = list(boot_p(m(x, 1) - m(y, 1), rng)), list(boot_p(m(x, 0) - m(y, 0), rng))
                out[name]["secondary"][f"{x}-{y}"] = {"PR": vp, "SR": vs_}
                L.append(f"| {x} - {y} | {f(vp)} | {f(vs_)} |")
        L.append("")
    sd = stage_dir(37)
    (sd / "tables" / "confounds_followups.json").write_text(json.dumps(out, indent=2))
    (sd / "tables" / "confounds_followups.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
