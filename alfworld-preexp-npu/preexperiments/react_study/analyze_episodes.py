"""Summarise episode JSONL (new react_study rows or legacy direction_b rows).

    $PY -m preexperiments.react_study.analyze_episodes --stage 2 \
        --raw_glob 'outputs/react_study/stage2_baselines/raw/eval_in_distribution/*.jsonl' --tag dev140

Writes tables/summary_<tag>.{json,md}, tables/per_task_<tag>.csv and
figures/sr_vs_tokens_<tag>.png into the stage directory.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from preexperiments.react_study.common import ROLES, stage_dir
from preexperiments.react_study.progress import progress_rate
from preexperiments.react_study.stats import discordant, mcnemar_exact, paired_task_diff

ARM_ORDER = ["none", "rethink", "loop_hint", "always", "always_em", "oracle", "selective", "selective_nomem", "selective_em", "random_post", "random_pre", "gate_stuck", "gate_learned"]


def load_rows(paths: List[str]) -> List[Dict[str, Any]]:
    rows = []
    for p in paths:
        if p.endswith(".config.json"):
            continue
        for line in open(p, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                r.setdefault("rep", 0)
                r["progress_rate"] = progress_rate(r["gamefile"], [s["next_observation"] for s in r["step_log"]
                                                                   if "next_observation" in s], r["success"]) \
                    if r["step_log"] and "next_observation" in r["step_log"][0] else None
                rows.append(r)
    return rows


def episode_cost(r: Dict[str, Any]) -> Dict[str, float]:
    c = r.get("cost")
    if c is None:
        return {}
    out = {"tokens_in": 0, "tokens_out": 0, "llm_latency_s": 0.0, "llm_calls": 0, "failed_calls": 0}
    for role in ROLES:
        e = c.get(role, {})
        out[f"{role}_calls"] = e.get("calls", 0)
        out[f"{role}_tokens_in"] = e.get("prompt_tokens", 0)
        out[f"{role}_tokens_out"] = e.get("completion_tokens", 0)
        out["tokens_in"] += e.get("prompt_tokens", 0)
        out["tokens_out"] += e.get("completion_tokens", 0)
        out["llm_latency_s"] += e.get("latency_s", 0.0)
        out["llm_calls"] += e.get("calls", 0)
        out["failed_calls"] += e.get("failed_calls", 0)
    out["tokens_total"] = out["tokens_in"] + out["tokens_out"]
    return out


def arm_rep_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    steps = sum(r["steps"] for r in rows)
    m: Dict[str, Any] = {
        "n": n,
        "success_rate": sum(r["success"] for r in rows) / n,
        "n_success": sum(r["success"] for r in rows),
        "mean_steps": steps / n,
    }
    if rows[0].get("progress_rate") is not None:
        m["progress_rate"] = float(np.mean([r["progress_rate"] for r in rows]))
    m["check_valid_rate"] = sum(s["action"] == "check valid actions" for r in rows for s in r["step_log"]) / steps
    m["loop_hint_fire_rate"] = sum(bool(s.get("loop_detected")) for r in rows for s in r["step_log"]) / steps
    used = sum(r.get("n_foresight_used", 0) for r in rows)
    wm = sum(r.get("n_wm_calls", r.get("n_world_model_calls", 0)) for r in rows)
    m["foresight_usage_step_level"] = used / steps if steps else 0.0
    m["wm_calls_total"] = wm
    m["wm_calls_per_task"] = wm / n
    second = [s for r in rows for s in r["step_log"] if s.get("second_action") is not None]
    m["second_pass_steps"] = len(second)
    m["action_change_rate_given_second_pass"] = (
        sum(s["second_action"] != s["baseline_action"] for s in second) / len(second)
        if second else None)
    if "legal_action_rate" in rows[0]:
        m["legal_action_rate"] = (sum(s["action_admissible"] for r in rows for s in r["step_log"])
                                  / steps if steps else None)
    costs = [episode_cost(r) for r in rows]
    if costs and costs[0]:
        for k in costs[0]:
            m[f"{k}_per_task"] = float(np.mean([c[k] for c in costs]))
        m["wall_s_per_task"] = float(np.mean([r.get("wall_s", np.nan) for r in rows]))
    return m


def main(a: argparse.Namespace) -> None:
    paths = sorted(glob.glob(a.raw_glob))
    rows = load_rows(paths)
    if a.arms:
        rows = [r for r in rows if r["arm"] in a.arms]
    sd = stage_dir(a.stage)

    by = defaultdict(lambda: defaultdict(list))  # arm -> rep -> rows
    for r in rows:
        by[r["arm"]][r["rep"]].append(r)
    arms = [x for x in ARM_ORDER if x in by] + sorted(set(by) - set(ARM_ORDER))

    # Restrict every arm/rep to the tasks common to all of them, so all SRs are paired.
    common = None
    for arm in arms:
        for rep, rs in by[arm].items():
            s = {r["task_id"] for r in rs}
            common = s if common is None else common & s
    common = common or set()

    summary: Dict[str, Any] = {"tag": a.tag, "inputs": paths, "n_common_tasks": len(common),
                               "ref_arm": a.ref, "arms": {}}
    succ = {}  # arm -> task -> [success per rep]
    prog = {}  # arm -> task -> [progress per rep]
    for arm in arms:
        reps = {}
        succ[arm] = defaultdict(list)
        prog[arm] = defaultdict(list)
        for rep, rs in sorted(by[arm].items()):
            rs = [r for r in rs if r["task_id"] in common]
            reps[rep] = arm_rep_metrics(rs)
            for r in rs:
                succ[arm][r["task_id"]].append(float(r["success"]))
                if r.get("progress_rate") is not None:
                    prog[arm][r["task_id"]].append(r["progress_rate"])
        srs = [v["success_rate"] for v in reps.values()]
        agg = {"n_reps": len(reps), "sr_mean": float(np.mean(srs)),
               "sr_min": float(np.min(srs)), "sr_max": float(np.max(srs)),
               "sr_std": float(np.std(srs, ddof=1)) if len(srs) > 1 else 0.0}
        for k in reps[next(iter(reps))]:
            vals = [v[k] for v in reps.values() if isinstance(v.get(k), (int, float))]
            if vals and k not in ("n",):
                agg.setdefault("mean_over_reps", {})[k] = float(np.mean(vals))
        summary["arms"][arm] = {"per_rep": reps, "aggregate": agg}

    # per-task-type SR (mean over reps)
    ttype = {r["task_id"]: r["task_type"] for r in rows}
    types = sorted(set(ttype[t] for t in common))
    summary["sr_by_task_type"] = {
        arm: {tt: float(np.mean([np.mean(succ[arm][t]) for t in common if ttype[t] == tt]))
              for tt in types} for arm in arms}
    summary["n_by_task_type"] = {tt: sum(1 for t in common if ttype[t] == tt) for tt in types}

    # paired comparisons vs ref
    if a.ref in by:
        comp = {}
        for arm in arms:
            if arm == a.ref:
                continue
            c = paired_task_diff(succ[a.ref], succ[arm])
            per_rep = {}
            for rep in sorted(set(by[arm]) & set(by[a.ref])):
                ra = {r["task_id"]: r["success"] for r in by[a.ref][rep] if r["task_id"] in common}
                rb = {r["task_id"]: r["success"] for r in by[arm][rep] if r["task_id"] in common}
                b_, c_ = discordant(ra, rb)
                per_rep[rep] = {"ref_only": b_, "arm_only": c_, "mcnemar_p": mcnemar_exact(b_, c_)}
            c["per_rep"] = per_rep
            if prog[arm] and prog[a.ref]:
                c["progress_delta"] = paired_task_diff(prog[a.ref], prog[arm])
            comp[arm] = c
        summary["vs_ref"] = comp

    # repeat stability: for each arm, fraction of tasks whose outcome differs across reps
    stab = {}
    for arm in arms:
        if len(by[arm]) > 1:
            flips = [t for t in common if len(set(succ[arm][t])) > 1]
            stab[arm] = {"n_tasks_outcome_varies_across_reps": len(flips),
                         "frac": len(flips) / len(common)}
    summary["repeat_stability"] = stab

    tab = sd / "tables"
    (tab / f"summary_{a.tag}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    with open(tab / f"per_task_{a.tag}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "task_type"] + [f"{arm}_mean_success" for arm in arms])
        for t in sorted(common):
            w.writerow([t, ttype[t]] + [f"{np.mean(succ[arm][t]):.3f}" for arm in arms])
    write_md(summary, arms, tab / f"summary_{a.tag}.md")
    plot(summary, arms, sd / "figures" / f"sr_vs_tokens_{a.tag}.png", a.ref)
    print((tab / f"summary_{a.tag}.md").read_text())


def _f(x, pct=False, nd=1):
    if x is None or (isinstance(x, float) and x != x):
        return "—"
    return f"{100*x:.{nd}f}%" if pct else (f"{x:,.0f}" if abs(x) >= 100 else f"{x:.{nd+1}f}")


def _pd(vs):
    if not vs or "progress_delta" not in vs:
        return "—"
    p = vs["progress_delta"]
    return f"{100*p['delta']:+.1f} [{100*p['ci_low']:+.1f}, {100*p['ci_high']:+.1f}]"


def write_md(s: Dict[str, Any], arms: List[str], path: Path) -> None:
    L = [f"# Episode summary: {s['tag']}", "",
         f"Paired task set: {s['n_common_tasks']} tasks. Reference arm: `{s['ref_arm']}`.", "",
         "| arm | reps | SR mean | SR range | ΔSR vs ref [95% CI] | McNemar p (per rep) | PR | ΔPR vs ref [95% CI] | steps | legal | usage | Δaction | WM calls/task | planner calls/task | tokens in/task | tokens out/task | LLM s/task |",
         "|---|---:|---:|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for arm in arms:
        ag = s["arms"][arm]["aggregate"]
        mo = ag.get("mean_over_reps", {})
        vs = s.get("vs_ref", {}).get(arm)
        d = (f"{100*vs['delta']:+.1f} [{100*vs['ci_low']:+.1f}, {100*vs['ci_high']:+.1f}]" if vs else "—")
        ps = (", ".join(f"{v['mcnemar_p']:.2f} ({v['ref_only']}/{v['arm_only']})"
                        for v in vs["per_rep"].values()) if vs else "—")
        planner = (mo.get("planner_base_calls_per_task", 0) + mo.get("planner_second_calls_per_task", 0)
                   if "planner_base_calls_per_task" in mo else None)
        L.append(
            f"| {arm} | {ag['n_reps']} | {_f(ag['sr_mean'], True)} | {_f(ag['sr_min'], True)}–{_f(ag['sr_max'], True)} "
            f"| {d} | {ps} | {_f(mo.get('progress_rate'), True)} | {_pd(vs)} | {_f(mo.get('mean_steps'))} | {_f(mo.get('legal_action_rate'), True)} "
            f"| {_f(mo.get('foresight_usage_step_level'), True)} | {_f(mo.get('action_change_rate_given_second_pass'), True)} "
            f"| {_f(mo.get('wm_calls_per_task'))} | {_f(planner)} | {_f(mo.get('tokens_in_per_task'))} "
            f"| {_f(mo.get('tokens_out_per_task'))} | {_f(mo.get('llm_latency_s_per_task'))} |")
    L += ["", "McNemar cell format: p (ref-only successes / arm-only successes). "
          "ΔSR CI: task-level bootstrap of per-task mean success over reps (10k resamples). "
          "usage = steps where a WM prediction was shown to the planner / all steps. "
          "Δaction = second-pass action ≠ a_base, among steps with a second pass.", ""]
    if s.get("repeat_stability"):
        L += ["## Repeat stability", "", "| arm | tasks whose success differs across reps |", "|---|---:|"]
        for arm, v in s["repeat_stability"].items():
            L.append(f"| {arm} | {v['n_tasks_outcome_varies_across_reps']} ({100*v['frac']:.1f}%) |")
        L.append("")
    L += ["## SR by task type (mean over reps)", "",
          "| task type | n | " + " | ".join(arms) + " |", "|---|---:|" + "---:|" * len(arms)]
    for tt, n in s["n_by_task_type"].items():
        L.append(f"| {tt} | {n} | " + " | ".join(_f(s["sr_by_task_type"][a][tt], True) for a in arms) + " |")
    path.write_text("\n".join(L) + "\n")


def plot(s: Dict[str, Any], arms: List[str], path: Path, ref: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pts = []
    for arm in arms:
        ag = s["arms"][arm]["aggregate"]
        x = ag.get("mean_over_reps", {}).get("tokens_total_per_task")
        if x is None:
            return  # legacy rows have no cost fields
        pts.append((arm, x, ag["sr_mean"], ag["sr_min"], ag["sr_max"]))
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=150)
    fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")
    for arm, x, y, lo, hi in pts:
        col = "#8a8984" if arm == ref else "#2a78d6"
        ax.errorbar(x / 1000, 100 * y, yerr=[[100 * (y - lo)], [100 * (hi - y)]], fmt="o",
                    color=col, ms=8, mec="#fcfcfb", mew=2, elinewidth=2, capsize=0, zorder=3)
        dx, ha = (-8, "right") if arm == "rethink" else (8, "left")
        ax.annotate(arm, (x / 1000, 100 * y), xytext=(dx, 6), textcoords="offset points",
                    fontsize=9, color="#0b0b0b", ha=ha)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e", labelsize=9)
    ax.grid(True, color="#ecebe7", lw=0.8, zorder=0)
    ax.set_xlabel("LLM tokens per task (input + output, thousands)", color="#52514e", fontsize=10)
    ax.set_ylabel("Success rate (%)", color="#52514e", fontsize=10)
    ax.set_title(f"Success rate vs cost — {s['tag']} ({s['n_common_tasks']} tasks; bars = range over reps)",
                 fontsize=10, color="#0b0b0b", loc="left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def build_arg_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=int, required=True)
    p.add_argument("--raw_glob", required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--ref", default="none")
    p.add_argument("--arms", nargs="*", default=None)
    return p


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
