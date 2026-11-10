"""Round 5 offline analyses on fresh_test600 x 3 reps (no new runs).

  3. Where the gain comes from: per failure category (environment-derived reason of the failing action, from
     the history only) -- local outcome of the intervention (executed action admissible; same failed action
     proposed again later in the episode) -- and per task type (SR), plus the subgoal funnel.
  4. Does a wrong diagnosis hurt? WM reason text mapped to the same categories; confusion matrix vs the
     environment-derived category; local outcomes and episode SR for correct vs incorrect diagnoses;
     repair-action agreement with the environment-derived repair.
  5. Capability: the same breakdowns for the 14B planner (where rule cards beat WM repair).

    $PY -m preexperiments.react_study.deep_analysis
"""
from __future__ import annotations

import glob
import json
import re
from collections import Counter, defaultdict

import numpy as np

from preexperiments.react_study.common import ROOT, stage_dir
from preexperiments.react_study import preconditions as _PC
from preexperiments.react_study.preconditions import diagnose
from preexperiments.react_study.progress import _parse, subgoals_for

O = ROOT / "outputs" / "react_study" / "p7_final" / "raw" / "train"
ARMS = {"4B": ["none", "inv_fail", "inv_rules", "wmrepair_wm14", "inv_repair"],
        "14B": ["none", "inv_fail", "inv_rules", "wmrepair_wm14", "inv_repair"]}
CATS = ["not_at", "already_at", "holding_other", "not_holding", "closed", "absent", "open_state", "other"]


class _All:
    def __contains__(self, x):
        return True


# diagnose() does `adm = set(admissible)`; the fresh600 logs carry no admissible lists, so for the analysis
# the environment-derived repair is accepted whatever it is. preconditions.py itself is part of the frozen
# method (hash in the pre-registration) and is not modified: only the name `set` in its namespace is shadowed.
import builtins as _bi


def _set(*a):
    return a[0] if a and isinstance(a[0], _All) else _bi.set(*a)


_PC.set = _set


def oracle_cat(reason):
    r = reason.lower()
    if "already at" in r:
        return "already_at"
    if "already holding" in r:
        return "holding_other"
    if "not holding" in r or "must be holding" in r:
        return "not_holding"
    if "is closed" in r:
        return "closed"
    if "already open" in r or "already closed" in r:
        return "open_state"
    if "not at the" in r or "must be at" in r:
        return "not_at"
    if "there is no" in r:
        return "absent"
    return "other"


def wm_cat(reason):
    r = (reason or "").lower()
    if re.search(r"already (at|in|located at|standing at)", r):
        return "already_at"
    if re.search(r"already (holding|carrying)|carry only one|hands? (are|is) (full|occupied)|holding (the |a )?\w+ already", r):
        return "holding_other"
    if re.search(r"not (holding|carrying)|must be (holding|carrying)|need(s)? to (take|pick|hold)|not in (your |the )?inventory|first take|have to (take|pick)", r):
        return "not_holding"
    if re.search(r"\bclosed\b|needs? to be opened|must (first )?(be )?open", r):
        return "closed"
    if re.search(r"not (at|in|near) (the )?(current )?(location|\w+ \d)|must be at|need(s)? to (go|be at|move to)|not (currently )?(at|accessible|reachable)|go to", r):
        return "not_at"
    if re.search(r"\bno \w+|not present|does not exist|not available|isn't (in|on|there)|is not (in|on|there)|not found", r):
        return "absent"
    return "other"


def load(pl, arm):
    rows = []
    for f in sorted(glob.glob(str(O / f"fresh_p{pl.lower()}_{arm}_c*__rep*.jsonl"))):
        rows += [json.loads(l) for l in open(f)]
    return rows


def gate_steps(rows):
    """Yield (row, step_index, step, history, oracle diagnosis) for every gate step."""
    for r in rows:
        hist = []
        for i, s in enumerate(r["step_log"]):
            if s.get("gate_open"):
                d = diagnose(s["baseline_action"], hist, _All())
                yield r, i, s, hist, d
            hist.append((s["action"], s["next_observation"]))


def local_outcomes(r, i, s):
    later = [x["baseline_action"] for x in r["step_log"][i + 1:] if x.get("gate_open")]
    return {"exec_admissible": float(bool(s.get("action_admissible"))),
            "recurs": float(s["baseline_action"] in later)}


def funnel(rows):
    seen = picked = succ = 0
    for r in rows:
        sg = subgoals_for(r["gamefile"])
        obs = [x["next_observation"] for x in r["step_log"]]
        body = lambda o: o[o.find(". ") + 2:] if o.startswith("You arrive at loc ") else o
        seen += r["success"] or any(re.search(sg[0], body(o)) for o in obs)
        picked += r["success"] or any(re.search(sg[1], body(o)) for o in obs)
        succ += r["success"]
    n = len(rows)
    return {"seen": seen / n, "picked": picked / n, "success": succ / n, "P(success|picked)": succ / max(picked, 1)}


def main():
    out, L = {}, ["# Round 5 offline analyses (fresh_test600 x 3 reps)", ""]
    for pl, arms in ARMS.items():
        data = {a: load(pl, a) for a in arms}
        data = {a: v for a, v in data.items() if v}
        out[pl] = {}
        # ---- task type SR and funnel
        L += [f"## {pl} planner", "", "### SR by task type", "",
              "| task type | " + " | ".join(data) + " |", "|---|" + "---:|" * len(data)]
        tts = sorted({_parse(r["gamefile"])[0] for r in next(iter(data.values()))})
        tsr = {a: {tt: float(np.mean([r["success"] for r in v if _parse(r["gamefile"])[0] == tt])) for tt in tts}
               for a, v in data.items()}
        for tt in tts:
            L.append(f"| {tt} | " + " | ".join(f"{100*tsr[a][tt]:.1f}" for a in data) + " |")
        out[pl]["sr_by_task_type"] = tsr
        L += ["", "### Subgoal funnel", "", "| arm | saw target | picked | success | P(success|picked) |", "|---|---:|---:|---:|---:|"]
        out[pl]["funnel"] = {}
        for a, v in data.items():
            f = funnel(v)
            out[pl]["funnel"][a] = f
            L.append(f"| {a} | {f['seen']:.2f} | {f['picked']:.2f} | {f['success']:.3f} | {f['P(success|picked)']:.2f} |")
        # ---- per failure category local outcomes
        L += ["", "### Failure categories at gate steps (environment-derived reason, from history only)", "",
              "Cells: share of gate steps / executed action admissible / same failed action proposed again later.", "",
              "| category | " + " | ".join(a for a in data if a != "none") + " |", "|---|" + "---|" * (len(data) - 1)]
        cat_stats = {}
        for a, v in data.items():
            if a == "none":
                continue
            agg = defaultdict(lambda: defaultdict(list))
            n = 0
            for r, i, s, hist, d in gate_steps(v):
                c = oracle_cat(d["reason"])
                lo = local_outcomes(r, i, s)
                for k, x in lo.items():
                    agg[c][k].append(x)
                n += 1
            cat_stats[a] = {c: {"share": len(agg[c]["recurs"]) / max(n, 1),
                                "exec_admissible": float(np.mean(agg[c]["exec_admissible"])) if agg[c]["recurs"] else None,
                                "recurs": float(np.mean(agg[c]["recurs"])) if agg[c]["recurs"] else None} for c in CATS}
            cat_stats[a]["_n_gate_steps"] = n
        out[pl]["categories"] = cat_stats
        for c in CATS:
            cells = []
            for a in data:
                if a == "none":
                    continue
                x = cat_stats[a][c]
                cells.append("-" if x["recurs"] is None else f"{x['share']:.2f} / {x['exec_admissible']:.2f} / {x['recurs']:.2f}")
            if any(cl != "-" for cl in cells):
                L.append(f"| {c} | " + " | ".join(cells) + " |")
        L.append("| gate steps | " + " | ".join(str(cat_stats[a]["_n_gate_steps"]) for a in data if a != "none") + " |")
        # ---- diagnosis correctness (WM repair arm)
        if "wmrepair_wm14" in data:
            conf = Counter()
            by = defaultdict(lambda: defaultdict(list))
            rep_agree, ep_correct = [], defaultdict(list)
            for r, i, s, hist, d in gate_steps(data["wmrepair_wm14"]):
                oc, wc = oracle_cat(d["reason"]), wm_cat(s.get("diag_reason"))
                conf[(oc, wc)] += 1
                ok = oc == wc
                lo = local_outcomes(r, i, s)
                for k, x in lo.items():
                    by[ok][k].append(x)
                adopted = s.get("diag_repair") is not None and s.get("second_action") == s.get("diag_repair")
                by[ok]["adopted"].append(float(adopted))
                if d["repair"] and s.get("diag_repair"):
                    rep_agree.append(float(d["repair"] == s["diag_repair"]))
                ep_correct[(r["task_id"], r["rep"], r["gamefile"])].append((ok, r["success"]))
            ep = [(np.mean([o for o, _ in v]), v[0][1]) for v in ep_correct.values()]
            hi = [s for m, s in ep if m >= 0.5]
            lo_ = [s for m, s in ep if m < 0.5]
            diag = {"category_agreement": sum(v for (a, b), v in conf.items() if a == b) / max(sum(conf.values()), 1),
                    "repair_action_agreement_when_both_exist": float(np.mean(rep_agree)) if rep_agree else None,
                    "local_correct": {k: float(np.mean(x)) for k, x in by[True].items()},
                    "local_incorrect": {k: float(np.mean(x)) for k, x in by[False].items()},
                    "n_correct": len(by[True]["recurs"]), "n_incorrect": len(by[False]["recurs"]),
                    "episode_SR_mostly_correct": float(np.mean(hi)) if hi else None, "n_ep_mostly_correct": len(hi),
                    "episode_SR_mostly_incorrect": float(np.mean(lo_)) if lo_ else None, "n_ep_mostly_incorrect": len(lo_),
                    "confusion": {f"{a}->{b}": v for (a, b), v in conf.most_common()}}
            out[pl]["diagnosis"] = diag
            L += ["", "### WM diagnosis vs environment-derived diagnosis (wmrepair_wm14)", "",
                  f"* category agreement: {diag['category_agreement']:.2f}; repair-action agreement (both exist): "
                  f"{(diag['repair_action_agreement_when_both_exist'] or float('nan')):.2f}",
                  f"* correct diagnosis (n={diag['n_correct']}): executed admissible {diag['local_correct']['exec_admissible']:.2f}, "
                  f"recurs {diag['local_correct']['recurs']:.2f}, repair adopted {diag['local_correct']['adopted']:.2f}",
                  f"* incorrect diagnosis (n={diag['n_incorrect']}): executed admissible {diag['local_incorrect']['exec_admissible']:.2f}, "
                  f"recurs {diag['local_incorrect']['recurs']:.2f}, repair adopted {diag['local_incorrect']['adopted']:.2f}",
                  f"* episodes with mostly correct diagnoses: SR {100*(diag['episode_SR_mostly_correct'] or 0):.1f}% "
                  f"(n={diag['n_ep_mostly_correct']}); mostly incorrect: SR {100*(diag['episode_SR_mostly_incorrect'] or 0):.1f}% "
                  f"(n={diag['n_ep_mostly_incorrect']}) -- correlational", "",
                  "Most frequent (environment category -> WM category): " +
                  ", ".join(f"{k} {v}" for k, v in list(diag["confusion"].items())[:10]), ""]
        L.append("")
    sd = stage_dir(39)
    (sd / "tables" / "deep_analysis.json").write_text(json.dumps(out, indent=2))
    (sd / "tables" / "deep_analysis.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
