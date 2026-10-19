"""Analyse step-0c K-continuation branches (branch_k.py output).

Key quantities per intervention X in {wm, oracle, rethink, loophint}:
  * change rate (first action != a_base)
  * mean U (success / progress / 5-step progress) with task-clustered CI
  * excess variance: Var_obs(U_X | changed) vs the binomial/sampling noise
    variance expected from K continuations on each side. Excess > 0 means
    states genuinely differ in how much X helps -> selection space exists.
  * A/A check: the base action's K rollouts split in halves.
  * confidence / prediction accuracy vs U; utility-coverage curves.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np
from scipy.stats import mannwhitneyu, spearmanr

from preexperiments.react_study.common import stage_dir
from preexperiments.react_study.stage3_analyze import cluster_boot_mean

IV = ("wm", "oracle", "rethink", "loophint")


def auroc(score, label):
    s1 = [s for s, l in zip(score, label) if l]
    s0 = [s for s, l in zip(score, label) if not l]
    if len(s1) < 3 or len(s0) < 3:
        return None
    return float(mannwhitneyu(s1, s0).statistic / (len(s1) * len(s0)))


def noise_var(r, x, key):
    """Sampling variance of U_X = mean_K(a_X) - mean_K(a_base) for one point."""
    conts = r["continuations"]
    a0, ax = r["first_actions"]["base"], r["first_actions"][x]
    v = 0.0
    for a in (a0, ax):
        xs = np.array([c[key] for c in conts[a]], float)
        v += xs.var(ddof=1) / len(xs) if len(xs) > 1 else 0.0
    return v


def coverage(score, u, qs, seed=2027):
    rng = np.random.default_rng(seed)
    score = np.asarray(score, float) + rng.uniform(0, 1e-9, len(score))
    order = np.argsort(-score)
    u = np.asarray(u, float)
    return [float(u[order[: int(round(q * len(u)))]].sum() / len(u)) for q in qs]


def main(a):
    sd = stage_dir(a.stage)
    rows = [json.loads(l) for f in sorted((sd / "raw").glob("branch_k.shard*.jsonl")) for l in open(f) if l.strip()]
    pts = {json.loads(l)["point_id"]: json.loads(l) for l in open(sd / "raw" / "branch_points.jsonl")}
    ok = [r for r in rows if r.get("replay_ok")]
    for r in ok:
        r["group"] = pts[r["point_id"]]["group"]
    S = {"n_points": len(rows), "n_replay_ok": len(ok),
         "a_base_matches_log": int(sum(r["a_base_matches_log"] for r in ok)),
         "K": ok[0]["K"] if ok else None}
    res = {}
    for grp in ("all", "solvable", "unsolved"):
        R = [r for r in ok if grp == "all" or r["group"] == grp]
        if not R:
            continue
        g = {"n": len(R), "P_base_success": float(np.mean([r["P_success"]["base"] for r in R])),
             "P_base_pr": float(np.mean([r["P_pr"]["base"] for r in R]))}
        for key in ("success", "pr", "pr_h5"):
            aa = np.array([r["AA_success"] if key == "success" else r["AA_pr"] for r in R]) if key != "pr_h5" else None
            if aa is not None:
                g[f"AA_{key}"] = {"mean": float(aa.mean()), "var": float(aa.var(ddof=1))}
        for x in IV:
            chg = np.array([r["first_actions"][x] != r["first_actions"]["base"] for r in R])
            e = {"change_rate": float(chg.mean())}
            for key in ("success", "pr", "pr_h5"):
                u = np.array([r[f"U_{key}"][x] for r in R])
                tasks = [r["task_id"] for r in R]
                m, lo, hi = cluster_boot_mean(u, tasks)
                ent = {"mean": m, "ci": [lo, hi]}
                if chg.sum() >= 3:
                    uc = u[chg]
                    nv = np.array([noise_var(r, x, key) for r, c in zip(R, chg) if c])
                    ent.update({"mean_given_changed": float(uc.mean()), "var_obs_changed": float(uc.var(ddof=1)),
                                "var_noise_changed": float(nv.mean()),
                                "excess_var_ratio": float(uc.var(ddof=1) / nv.mean()) if nv.mean() > 0 else None,
                                "frac_pos_beyond_2se": float(np.mean(uc > 2 * np.sqrt(nv))),
                                "frac_neg_beyond_2se": float(np.mean(uc < -2 * np.sqrt(nv)))})
                e[key] = ent
            g[x] = e
        res[grp] = g
    S["groups"] = res
    # confidence / accuracy vs utility (solvable group, wm intervention)
    R = [r for r in ok if r["group"] == "solvable"]
    conf = np.array([r["wm_confidence_logprob"] if r["wm_confidence_logprob"] is not None else np.nan for r in R])
    em = np.array([r["pred_em"] for r in R]); f1 = np.array([r["pred_f1"] for r in R])
    uw = np.array([r["U_pr"]["wm"] for r in R]); uo = np.array([r["U_pr"]["oracle"] for r in R])
    chg = np.array([r["first_actions"]["wm"] != r["first_actions"]["base"] for r in R])
    m = ~np.isnan(conf)
    S["confidence"] = {
        "auroc_conf_for_EM": auroc(conf[m], em[m] > .5),
        "spearman_conf_f1": float(spearmanr(conf[m], f1[m]).statistic),
        "spearman_conf_Uwm_pr_changed": float(spearmanr(conf[m & chg], uw[m & chg]).statistic) if (m & chg).sum() > 5 else None,
        "auroc_conf_for_Uwm_pr_pos": auroc(conf[m & chg], uw[m & chg] > 0),
        "auroc_conf_for_Uwm_pr_neg": auroc(conf[m & chg], uw[m & chg] < 0),
        "pred_em_mean": float(em.mean()), "pred_f1_mean": float(f1.mean()),
        "mean_Uwm_pr_when_EM1": float(uw[em > .5].mean()) if (em > .5).any() else None,
        "mean_Uwm_pr_when_EM0": float(uw[em <= .5].mean()) if (em <= .5).any() else None,
        "mean_Uoracle_pr": float(uo.mean()),
    }
    # features
    feat = defaultdict(lambda: defaultdict(list))
    for r in R:
        f = r["features"]
        for k, v in (("stratum", r["stratum"]), ("phase", f["phase"]), ("action_type", f["action_type"]),
                     ("task_type", r["task_type"]), ("repeated", f["repeat_count"] >= 1)):
            feat[k][str(v)].append(r)
    S["by_feature_solvable"] = {
        k: {v: {"n": len(rs), **{f"U_pr_{x}": float(np.mean([r["U_pr"][x] for r in rs])) for x in IV},
                **{f"chg_{x}": float(np.mean([r["first_actions"][x] != r["first_actions"]["base"] for r in rs])) for x in IV}}
            for v, rs in vs.items()} for k, vs in feat.items()}
    # coverage on solvable, U_pr of wm
    qs = [round(x, 2) for x in np.linspace(0.05, 1.0, 20)]
    stuck = np.array([1.0 if r["stratum"] == "stuck" else 0.0 for r in R])
    c0 = np.nan_to_num(conf, nan=0.0)
    S["coverage_wm_pr"] = {"q": qs, "confidence_high": coverage(c0, uw, qs), "confidence_low": coverage(-c0, uw, qs),
                           "stuck_rule": coverage(stuck, uw, qs), "random": [float(q * uw.mean()) for q in qs],
                           "ex_post_oracle": coverage(uw, uw, qs)}
    (sd / "tables" / "branch_k_summary.json").write_text(json.dumps(S, indent=2))
    write_md(S, sd / "tables" / "branch_k_summary.md")
    plot(S, sd / "figures" / "branch_k_coverage_wm_pr.png")
    print((sd / "tables" / "branch_k_summary.md").read_text())


def _c(e):
    return f"{e['mean']:+.3f} [{e['ci'][0]:+.3f}, {e['ci'][1]:+.3f}]"


def write_md(S, path):
    L = [f"# Step 0c: K={S['K']} continuation branches", "",
         f"{S['n_replay_ok']}/{S['n_points']} points replayed; a_base reproduced log at {S['a_base_matches_log']}.", ""]
    for grp, g in S["groups"].items():
        L += [f"## group: {grp} (n={g['n']}; P_base success {g['P_base_success']:.3f}, PR {g['P_base_pr']:.3f})", "",
              f"A/A (half-vs-half of base rollouts): success var {g['AA_success']['var']:.4f}, PR var {g['AA_pr']['var']:.4f}", "",
              "| intervention | changed | U success [CI] | U PR [CI] | U PR@5 [CI] | PR excess-var ratio (changed) | PR +beyond 2SE | PR −beyond 2SE |",
              "|---|---:|---|---|---|---:|---:|---:|"]
        for x in IV:
            e = g[x]; p = e["pr"]
            L.append(f"| {x} | {100*e['change_rate']:.0f}% | {_c(e['success'])} | {_c(p)} | {_c(e['pr_h5'])} | "
                     f"{p.get('excess_var_ratio') and round(p['excess_var_ratio'], 2)} | "
                     f"{p.get('frac_pos_beyond_2se', 0)*100:.0f}% | {p.get('frac_neg_beyond_2se', 0)*100:.0f}% |")
        L.append("")
    c = S["confidence"]
    L += ["## Confidence vs accuracy vs utility (solvable, wm)", "", "```", json.dumps(c, indent=1), "```", "",
          "## Coverage (solvable, U_PR of wm) at usage ≈ 30%", ""]
    cv = S["coverage_wm_pr"]
    i = cv["q"].index(0.3) if 0.3 in cv["q"] else 5
    for k in ("confidence_high", "confidence_low", "stuck_rule", "random", "ex_post_oracle"):
        L.append(f"- {k}: {cv[k][i]:+.4f}  (always: {cv[k][-1]:+.4f})")
    path.write_text("\n".join(L) + "\n")


def plot(S, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cv = S["coverage_wm_pr"]
    cols = {"confidence_high": "#2a78d6", "confidence_low": "#eb6834", "random": "#8a8984",
            "stuck_rule": "#1baf7a", "ex_post_oracle": "#6250d6"}
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=150)
    fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")
    for k, c in cols.items():
        ax.plot([100 * q for q in cv["q"]], cv[k], "--" if k == "random" else "-", color=c, lw=2, label=k)
    ax.axhline(0, color="#c3c2b7", lw=1)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.grid(True, color="#ecebe7", lw=0.8)
    ax.set_xlabel("Usage: % of decision points given WM foresight", color="#52514e")
    ax.set_ylabel("Gain per decision (Σ U_PR / N)", color="#52514e")
    ax.set_title("Utility–coverage, solvable states, K-rollout progress utility", fontsize=10, loc="left")
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, default=10)
    main(ap.parse_args())
