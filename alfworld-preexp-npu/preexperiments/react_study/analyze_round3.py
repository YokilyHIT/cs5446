"""Direction F: one paired analysis of all round-3 arms on the dev460 held-out tasks,
with Holm-corrected paired-bootstrap p-values, plus the dose-response figure (D).

Arms are read from the run files (row["arm"] = --label). Reference runs on the same
460 tasks: step0 none/always (2 reps), step3 random_pre (with identical-prompt second
call when closed = "random_pre_cc").

    $PY -m preexperiments.react_study.analyze_round3
"""
from __future__ import annotations

import glob
import json
from collections import defaultdict

import numpy as np

from preexperiments.react_study.analyze_episodes import load_rows
from preexperiments.react_study.common import ROOT, stage_dir

OUT = ROOT / "outputs" / "react_study"
B = 20000


def boot_p(d, rng):
    """Two-sided paired-bootstrap p-value for mean(d) != 0 (task resampling)."""
    d = np.asarray(d, float)
    m = d.mean()
    bs = d[rng.integers(0, len(d), (B, len(d)))].mean(1)
    lo, hi = np.quantile(bs, [0.025, 0.975])
    p = 2 * min((bs <= 0).mean(), (bs >= 0).mean())
    return float(m), float(lo), float(hi), float(min(1.0, max(p, 1.0 / B)))


def holm(ps):
    idx = np.argsort(ps)
    adj = np.empty(len(ps))
    run = 0.0
    for k, i in enumerate(idx):
        run = max(run, (len(ps) - k) * ps[i])
        adj[i] = min(1.0, run)
    return adj


def main():
    eval_tasks = None
    s3 = OUT / "step3_gating" / "raw"
    eval_games = set(open(s3 / "eval460_games.txt").read().split())
    paths = (glob.glob(str(OUT / "dirA_D_mechanism_dose/raw/train/*.jsonl"))
             + glob.glob(str(OUT / "dirC_interface/raw/train/*.jsonl"))
             + glob.glob(str(OUT / "dirB_planner_uncertainty/raw/train/*.jsonl"))
             + glob.glob(str(OUT / "step0_protocol_v2_measurement/raw/train/dev_v2_c*_none__rep*.jsonl"))
             + glob.glob(str(OUT / "step0_protocol_v2_measurement/raw/train/dev_v2_c*_always__rep*.jsonl"))
             + glob.glob(str(OUT / "step3_gating/raw/train/eval_v2_c*_random_pre__rep*.jsonl")))
    rows = [r for r in load_rows(sorted(p for p in paths if not p.endswith(".config.json")))
            if r["gamefile"] in eval_games]
    for r in rows:
        if r["arm"] == "random_pre" and "second_call" not in r:
            pass
    # step3 random_pre had the identical-prompt second call when closed
    for r in rows:
        if r["arm"] == "random_pre":
            r["arm"] = "random_pre_cc_p0.3"
    S = defaultdict(lambda: defaultdict(list))   # arm -> task -> [(succ, pr, tokens)]
    for r in rows:
        tok = sum(e["prompt_tokens"] + e["completion_tokens"] for e in r["cost"].values())
        S[r["arm"]][r["task_id"]].append((float(r["success"]), r["progress_rate"], tok,
                                          r.get("n_foresight_used", 0) / max(r["steps"], 1),
                                          sum(1 for s in r["step_log"] if s.get("second_action") is not None
                                              and s["second_action"] != s["baseline_action"]) / max(r["steps"], 1)))
    tasks = sorted(set.intersection(*[set(v) for v in S.values()]))
    arms = sorted(S, key=lambda a: (a != "none", a))
    rng = np.random.default_rng(2027)
    summ = {}
    for a in arms:
        per = [np.mean(S[a][t], axis=0) for t in tasks]
        per = np.array(per)
        summ[a] = {"n_tasks": len(tasks), "reps": int(np.mean([len(S[a][t]) for t in tasks])),
                   "SR": float(per[:, 0].mean()), "PR": float(per[:, 1].mean()),
                   "tokens_per_task": float(per[:, 2].mean()), "foresight_usage": float(per[:, 3].mean()),
                   "action_changed_frac": float(per[:, 4].mean())}
    comps = []
    for ref in ("none", "random_pre_nc_p0.3"):
        if ref not in S:
            continue
        for a in arms:
            if a == ref:
                continue
            for k, met in ((0, "SR"), (1, "PR")):
                d = [np.mean([x[k] for x in S[a][t]]) - np.mean([x[k] for x in S[ref][t]]) for t in tasks]
                m, lo, hi, p = boot_p(d, rng)
                comps.append({"arm": a, "ref": ref, "metric": met, "delta": m, "ci": [lo, hi], "p": p})
    adj = holm(np.array([c["p"] for c in comps]))
    for c, q in zip(comps, adj):
        c["p_holm"] = float(q)
    sd = stage_dir(24)
    (sd / "tables" / "round3_dev460.json").write_text(json.dumps({"summary": summ, "comparisons": comps}, indent=2))
    L = ["# Round 3 — all arms on the 460 held-out dev tasks", "",
         f"Paired task set: {len(tasks)} tasks. Holm correction over all {len(comps)} comparisons below.", "",
         "| arm | reps | SR | PR | WM usage | steps w/ changed action | tokens/task |", "|---|---:|---:|---:|---:|---:|---:|"]
    for a in arms:
        v = summ[a]
        L.append(f"| {a} | {v['reps']} | {100*v['SR']:.1f}% | {100*v['PR']:.1f}% | {100*v['foresight_usage']:.0f}% | "
                 f"{100*v['action_changed_frac']:.1f}% | {v['tokens_per_task']/1000:.1f}k |")
    for ref in ("none", "random_pre_nc_p0.3"):
        L += ["", f"## vs `{ref}`", "", "| arm | ΔSR [95% CI] | p (Holm) | ΔPR [95% CI] | p (Holm) |", "|---|---|---:|---|---:|"]
        for a in arms:
            cs = {c["metric"]: c for c in comps if c["arm"] == a and c["ref"] == ref}
            if not cs:
                continue
            f = lambda c: f"{100*c['delta']:+.1f} [{100*c['ci'][0]:+.1f}, {100*c['ci'][1]:+.1f}]"
            L.append(f"| {a} | {f(cs['SR'])} | {cs['SR']['p']:.3f} ({cs['SR']['p_holm']:.3f}) | {f(cs['PR'])} | "
                     f"{cs['PR']['p']:.3f} ({cs['PR']['p_holm']:.3f}) |")
    (sd / "tables" / "round3_dev460.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    dose_plot(summ, S, tasks, sd)


def dose_plot(summ, S, tasks, sd):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pts = [(0.0, "none")] + [(p, f"random_pre_nc_p{p}") for p in (0.1, 0.3, 0.5, 0.7)] + [(1.0, "always")]
    pts = [(p, a) for p, a in pts if a in S]
    rng = np.random.default_rng(0)
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=150)
    fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")
    for k, (name, col) in enumerate((("Δ success rate", "#2a78d6"), ("Δ progress rate", "#eb6834"))):
        xs, ys, lo, hi = [], [], [], []
        base = np.array([np.mean([x[k] for x in S["none"][t]]) for t in tasks])
        for p, a in pts:
            per = np.array([np.mean([x[k] for x in S[a][t]]) for t in tasks]) - base  # paired delta vs none
            bs = per[rng.integers(0, len(per), (4000, len(per)))].mean(1)
            xs.append(100 * p); ys.append(100 * per.mean())
            lo.append(100 * np.quantile(bs, .025)); hi.append(100 * np.quantile(bs, .975))
        ax.fill_between(xs, lo, hi, color=col, alpha=0.12, lw=0)
        ax.plot(xs, ys, "-o", color=col, lw=2, ms=6, mec="#fcfcfb", label=name)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.grid(True, color="#ecebe7", lw=0.8)
    ax.set_xticks([0, 10, 30, 50, 70, 100])
    ax.set_xlabel("Share of steps given WM foresight (random pre-call gate, no extra call)", color="#52514e")
    ax.axhline(0, color="#c3c2b7", lw=1)
    ax.set_ylabel("pp vs none (paired; band = 95% CI)", color="#52514e")
    ax.set_title("Dose-response of foresight usage — 460 held-out dev tasks, 2 reps", fontsize=10, loc="left")
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    fig.tight_layout(); fig.savefig(sd / "figures" / "dose_response_dev460.png"); plt.close(fig)


if __name__ == "__main__":
    main()
