"""Round 5 stage A (probe_feasibility/tables/preregistration_round5A.json): method matrix on dev460 x 2 reps.

  * method table for both planners (SR / PR / legal / gate rate / tokens)
  * pre-registered Holm families (4B primary, 4B secondary, 14B secondary) and the freeze-rule verdict
  * diagnosis quality: at gate steps of inv_wmrepair / post_wmrepair / inv_sreflect, agreement of the proposed
    first repair action with the environment-derived diagnosis (preconditions.diagnose); admissible lists come
    from --record_state rows, else from replaying the episode prefix

    $PY -m preexperiments.react_study.analyze_round5 [--diag_max 600]
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from collections import Counter, defaultdict

import numpy as np

from preexperiments.react_study.analyze_episodes import load_rows
from preexperiments.react_study.analyze_round3 import boot_p, holm
from preexperiments.react_study.common import ROOT, stage_dir

O = ROOT / "outputs" / "react_study"
PF = "probe_feasibility/raw/train/"
ARMS4 = {
    "none": "step0_protocol_v2_measurement/raw/train/dev_v2_c*_none__rep*.jsonl",
    "inv_resample": PF + "p4b_inv_resample_c*__rep*.jsonl",
    "inv_proj": PF + "p4b_inv_proj_c*__rep*.jsonl",
    "inv_fail": PF + "p4b_inv_fail_c*__rep*.jsonl",
    "inv_reflect": PF + "p4b_inv_reflect_c*__rep*.jsonl",
    "inv_sreflect": PF + "p4b_inv_sreflect_c*__rep*.jsonl",
    "inv_rules": PF + "p4b_inv_rules_c*__rep*.jsonl",
    "inv_state": PF + "p4b_inv_state_c*__rep*.jsonl",
    "inv_wmpred_wm4": PF + "p4b_inv_wmpred_wm4_c*__rep*.jsonl",
    "inv_wmpred_wm14": PF + "p4b_inv_wmpred_wm14_c*__rep*.jsonl",
    "wmrepair_wm4": PF + "p4b_inv_wmrepair_wm4_c*__rep*.jsonl",
    "wmrepair_wm14": PF + "p4b_inv_wmrepair_wm14_c*__rep*.jsonl",
    "post_wmrepair_wm4": PF + "p4b_post_wmrepair_wm4_c*__rep*.jsonl",
    "inv_repair": PF + "p4b_inv_repair_c*__rep*.jsonl",
}
ARMS14 = {
    "none": "dirE_larger_planner/raw/train/p14b_none_c*__rep*.jsonl",
    "inv_fail": PF + "p14b_inv_fail_c*__rep*.jsonl",
    "inv_reflect": PF + "p14b_inv_reflect_c*__rep*.jsonl",
    "inv_sreflect": PF + "p14b_inv_sreflect_c*__rep*.jsonl",
    "inv_rules": PF + "p14b_inv_rules_c*__rep*.jsonl",
    "inv_state": PF + "p14b_inv_state_c*__rep*.jsonl",
    "inv_wmpred_wm14": PF + "p14b_inv_wmpred_wm14_c*__rep*.jsonl",
    "wmrepair_wm14": PF + "p14b_inv_wmrepair_wm14_c*__rep*.jsonl",
    "inv_repair": PF + "p14b_inv_repair_c*__rep*.jsonl",
}
FAMILIES = [
    ("4B primary (Holm over 4)", ARMS4, [("wmrepair_wm14", "inv_reflect"), ("wmrepair_wm14", "inv_sreflect"),
                                        ("wmrepair_wm14", "inv_rules"), ("wmrepair_wm14", "inv_wmpred_wm14")]),
    ("4B secondary (Holm over 4)", ARMS4, [("wmrepair_wm4", "inv_sreflect"), ("wmrepair_wm4", "inv_wmpred_wm4"),
                                          ("post_wmrepair_wm4", "inv_fail"), ("post_wmrepair_wm4", "wmrepair_wm4")]),
    ("14B secondary (Holm over 3)", ARMS14, [("inv_state", "inv_fail"), ("inv_repair", "inv_state"),
                                            ("inv_sreflect", "inv_fail")]),
]


def load(src, games):
    S, rows = defaultdict(lambda: defaultdict(list)), defaultdict(list)
    for k, g in src.items():
        for r in load_rows(sorted(p for p in glob.glob(str(O / g)) if not p.endswith(".config.json"))):
            if r["gamefile"] in games:
                tok = sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())
                S[k][r["task_id"]].append((float(r["success"]), r["progress_rate"], tok, r["legal_action_rate"] or 0.0,
                                           r.get("n_gate_open", 0) / max(r["steps"], 1)))
                rows[k].append(r)
    return S, rows


def table(S, keys, tasks):
    m = lambda k, i: np.array([np.mean([x[i] for x in S[k][t][:2]]) for t in tasks])
    L = ["| arm | SR | PR | legal | gate open/step | tokens/task |", "|---|---:|---:|---:|---:|---:|"]
    for k in keys:
        L.append(f"| {k} | {100*m(k,0).mean():.1f}% | {100*m(k,1).mean():.1f}% | {m(k,3).mean():.2f} | "
                 f"{m(k,4).mean():.2f} | {m(k,2).mean()/1000:.1f}k |")
    return L, m


FIRST_STEP_RE = re.compile(r"first step\s*:\s*\"?([^\";\n]+)", re.IGNORECASE)


def diagnosis_quality(rows, arm, max_n, rng):
    """Agreement of the proposed repair with preconditions.diagnose at gate steps."""
    from preexperiments.common.alfworld_runner import extract_admissible, visible_actions
    from preexperiments.react_study.agent import replay
    from preexperiments.react_study.preconditions import diagnose
    items = []
    for r in rows:
        for i, s in enumerate(r["step_log"]):
            if s.get("gate_open"):
                items.append((r, i, s))
    rng.shuffle(items)
    items = items[:max_n]
    agree, given, oracle_has, cats = [], [], [], Counter()
    for r, i, s in items:
        hist = [(x["action"], x["next_observation"]) for x in r["step_log"][:i]]
        failed = s.get("post_failed_action") or s["baseline_action"]
        if s.get("post_failed_action"):
            hist = hist  # the failed action is the last element of hist already
            adm_hist = hist[:-1]
        else:
            adm_hist = hist
        adm = s.get("admissible_actions")
        if adm is None:
            env, obs, info, _h, done, _i = replay("train", r["gamefile"], [a for a, _ in hist])
            adm = visible_actions(extract_admissible(info))
        d = diagnose(failed, adm_hist if s.get("post_failed_action") else hist, adm)
        if arm.endswith("sreflect"):
            m = FIRST_STEP_RE.search(s.get("second_raw") or "")
            prop = m.group(1).strip().rstrip(".") if m else None
            prop = {a.lower(): a for a in adm}.get((prop or "").lower())
        else:
            prop = s.get("diag_repair")
        given.append(prop is not None)
        oracle_has.append(d["repair"] is not None)
        if d["repair"] is not None:
            agree.append(prop == d["repair"])
        cats[re.sub(r"\b[a-z]+ \d+\b", "X", d["reason"])[:40]] += 1
    return {"n_gate_steps": len(items), "repair_given": float(np.mean(given)) if given else None,
            "oracle_repair_exists": float(np.mean(oracle_has)) if oracle_has else None,
            "agree_with_oracle_when_it_exists": float(np.mean(agree)) if agree else None,
            "oracle_reason_categories": cats.most_common(6)}


def main(a):
    games = set(open(O / "step3_gating/raw/eval460_games.txt").read().split())
    rng = np.random.default_rng(2027)
    out, L = {"families": {}, "diagnosis": {}}, ["# Round 5 stage A: method matrix (dev460 x 2 reps)", ""]
    cache = {}
    for name, src in (("4B", ARMS4), ("14B", ARMS14)):
        S, rows = load(src, games)
        keys = [k for k in src if S[k]]
        tasks = sorted(set.intersection(*[set(t for t, v in S[k].items() if len(v) >= 2) for k in keys]))
        T, m = table(S, keys, tasks)
        cache[name] = (S, rows, keys, m)
        L += [f"## {name} planner ({len(tasks)} tasks)", ""] + T + [""]
        out[name] = {k: {"SR": float(m(k, 0).mean()), "PR": float(m(k, 1).mean()), "tokens": float(m(k, 2).mean())} for k in keys}
    f = lambda v: f"{100*v[0]:+.1f} [{100*v[1]:+.1f}, {100*v[2]:+.1f}] p={v[3]:.3f}" + (f" Holm={v[4]:.3f}" if len(v) > 4 else "")
    for fam, src, pairs in FAMILIES:
        S, rows, keys, m = cache["4B" if src is ARMS4 else "14B"]
        pairs = [(x, y) for x, y in pairs if x in keys and y in keys]
        vs = [list(boot_p(m(x, 1) - m(y, 1), rng)) for x, y in pairs]
        hs = holm(np.array([v[3] for v in vs])) if vs else []
        L += [f"## {fam}, PR", "", "| contrast | Δ pp [95% CI] | SR Δ (exploratory) |", "|---|---|---|"]
        for (x, y), v, h in zip(pairs, vs, hs):
            sr = list(boot_p(m(x, 0) - m(y, 0), rng))
            out["families"][f"{fam}:{x}-{y}:PR"] = v + [float(h)]
            out["families"][f"{fam}:{x}-{y}:SR"] = sr
            L.append(f"| {x} - {y} | {f(v + [float(h)])} | {f(sr)} |")
        L.append("")
    # freeze rule (4B primary)
    P = {k.split(":", 1)[1]: v for k, v in out["families"].items() if k.startswith("4B primary") and k.endswith(":PR")}
    c1, c2, c3 = P.get("wmrepair_wm14-inv_reflect:PR"), P.get("wmrepair_wm14-inv_sreflect:PR"), P.get("wmrepair_wm14-inv_rules:PR")
    verdict = "incomplete"
    if c1 and c2 and c3:
        S4, _r, _k, m4 = cache["4B"]
        sr_vs_rules = boot_p(m4("inv_sreflect", 1) - m4("inv_rules", 1), rng)
        rules_beat_both = c3[2] < 0 and sr_vs_rules[2] < 0
        out["families"]["aux:inv_sreflect-inv_rules:PR"] = list(sr_vs_rules)
        if rules_beat_both:
            verdict = "no method claim (rule cards beat both WM repair and structured reflection)"
        elif c1[4] < 0.05 and c2[1] > -0.02 and c3[1] > -0.02:
            verdict = "freeze inv_wmrepair (14B WM)"
        elif c2[2] < 0 or (c2[0] <= 0 and c2[4] >= 0.05):
            verdict = "freeze inv_sreflect"
        else:
            verdict = "ambiguous under the pre-registered rule: report all, decide on cost and stage-B robustness"
    out["freeze_verdict"] = verdict
    L += [f"**Freeze-rule verdict:** {verdict}", ""]
    L += ["## Diagnosis quality at gate steps (proposed first repair vs environment-derived diagnosis)", "",
          "| planner | arm | gate steps sampled | repair given | oracle repair exists | agree when it exists |", "|---|---|---:|---:|---:|---:|"]
    for name, arms in (("4B", ("wmrepair_wm4", "wmrepair_wm14", "post_wmrepair_wm4", "inv_sreflect")),
                       ("14B", ("wmrepair_wm14", "inv_sreflect"))):
        S, rows, keys, m = cache[name]
        for arm in arms:
            if arm in keys:
                q = diagnosis_quality(rows[arm], arm, a.diag_max, np.random.default_rng(7))
                out["diagnosis"][f"{name}:{arm}"] = q
                L.append(f"| {name} | {arm} | {q['n_gate_steps']} | {q['repair_given']:.2f} | {q['oracle_repair_exists']:.2f} | "
                         f"{(q['agree_with_oracle_when_it_exists'] or float('nan')):.2f} |")
    sd = stage_dir(38)
    (sd / "tables" / "round5A.json").write_text(json.dumps(out, indent=2, default=str))
    (sd / "tables" / "round5A.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--diag_max", type=int, default=600)
    main(ap.parse_args())
