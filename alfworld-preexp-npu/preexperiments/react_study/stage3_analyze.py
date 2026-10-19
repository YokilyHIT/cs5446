"""Stage 3c: analyse paired-branch utilities.

Answers the five stage-3 questions of the plan:
  1. share of U_W = +1 / 0 / -1 (and vs the U_noise floor)
  2. confidence vs prediction accuracy vs utility
  3. which agent-visible state features go with benefit / harm
  4. at equal usage, confidence-ranked vs random selection
  5. ex-post oracle selection vs always
plus the rethink control (U_R).

Outputs: tables/stage3_summary.{json,md}, tables/stage3_by_feature.csv,
figures/utility_coverage.png, tables/stage3_cases.md
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict

import numpy as np
from scipy.stats import mannwhitneyu, spearmanr

from preexperiments.react_study.common import stage_dir
from preexperiments.react_study.stats import mcnemar_exact

RNG_SEED = 2026


def dist(u, w=None):
    u = np.asarray(u)
    w = np.ones(len(u)) if w is None else np.asarray(w, float)
    W = w.sum()
    return {"n": int(len(u)), "pos": float(w[u > 0].sum() / W), "zero": float(w[u == 0].sum() / W),
            "neg": float(w[u < 0].sum() / W), "mean": float((w * u).sum() / W),
            "n_pos": int((u > 0).sum()), "n_neg": int((u < 0).sum())}


def cluster_boot_mean(u, tasks, n_boot=10000, seed=RNG_SEED):
    """Mean of u with CI from resampling TASKS (points within a task are correlated)."""
    by = defaultdict(list)
    for x, t in zip(u, tasks):
        by[t].append(x)
    keys = list(by)
    sums = np.array([sum(by[k]) for k in keys], float)
    cnts = np.array([len(by[k]) for k in keys], float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(keys), size=(n_boot, len(keys)))
    m = sums[idx].sum(1) / cnts[idx].sum(1)
    return float(np.mean(u)), float(np.quantile(m, .025)), float(np.quantile(m, .975))


def auroc(score, label):
    s1 = [s for s, l in zip(score, label) if l]
    s0 = [s for s, l in zip(score, label) if not l]
    if not s1 or not s0:
        return None
    return float(mannwhitneyu(s1, s0).statistic / (len(s1) * len(s0)))


def coverage_curve(score, u, qs):
    """Per-decision gain sum(U over top-q by score)/N; ties broken randomly."""
    rng = np.random.default_rng(RNG_SEED)
    score = np.asarray(score, float) + rng.uniform(0, 1e-9, len(score))
    order = np.argsort(-score)
    u = np.asarray(u, float)
    return [float(u[order[: int(round(q * len(u)))]].sum() / len(u)) for q in qs]


def main():
    sd = stage_dir(3)
    rows = [json.loads(l) for f in sorted((sd / "raw").glob("branches*.jsonl")) for l in open(f) if l.strip()]
    ok = [r for r in rows if r.get("replay_ok")]
    ok.sort(key=lambda r: r["point_id"])
    S = {"n_points": len(rows), "n_replay_ok": len(ok),
         "a_base_matches_log": sum(r["a_base_matches_log"] for r in ok),
         "b0_vs_b0r_identical_trajectory": sum(r["b0_actions_equal_b0r"] for r in ok)}
    UW = np.array([r["U_W"] for r in ok]); UR = np.array([r["U_R"] for r in ok])
    UN = np.array([r["U_noise"] for r in ok]); w = np.array([r["weight"] for r in ok])
    tasks = [r["task_id"] for r in ok]
    chg = np.array([r["fore_changed"] for r in ok]); rchg = np.array([r["re_changed"] for r in ok])
    conf = np.array([r["wm_confidence_logprob"] if r["wm_confidence_logprob"] is not None else np.nan
                     for r in ok])
    f1 = np.array([r["pred_f1"] for r in ok]); em = np.array([r["pred_em"] for r in ok])

    # Q1
    S["Q1"] = {
        "U_W": dist(UW), "U_W_visit_weighted": dist(UW, w), "U_R": dist(UR), "U_noise": dist(UN),
        "U_W_given_changed": dist(UW[chg]), "U_R_given_changed": dist(UR[rchg]),
        "fore_change_rate": float(chg.mean()), "rethink_change_rate": float(rchg.mean()),
        "Y0_rate": float(np.mean([r["Y0"] for r in ok])),
        "mean_U_W_cluster_ci": cluster_boot_mean(UW, tasks),
        "mean_U_R_cluster_ci": cluster_boot_mean(UR, tasks),
        "mean_U_noise_cluster_ci": cluster_boot_mean(UN, tasks),
        "sign_test_U_W_p": mcnemar_exact(int((UW < 0).sum()), int((UW > 0).sum())),
        "sign_test_U_R_p": mcnemar_exact(int((UR < 0).sum()), int((UR > 0).sum())),
        "nonzero_rate": {"U_W": float((UW != 0).mean()), "U_R": float((UR != 0).mean()),
                         "U_noise": float((UN != 0).mean())},
        "a_fore_admissible_when_changed": float(np.mean([r["a_fore_admissible"] for r in ok if r["fore_changed"]]))
        if chg.any() else None,
        "a_re_admissible_when_changed": float(np.mean([r["a_re_admissible"] for r in ok if r["re_changed"]]))
        if rchg.any() else None,
    }
    # Q2
    m = ~np.isnan(conf)
    S["Q2"] = {
        "n_with_conf": int(m.sum()),
        "pred_em_mean": float(em.mean()), "pred_f1_mean": float(f1.mean()),
        "spearman_conf_f1": float(spearmanr(conf[m], f1[m]).statistic),
        "auroc_conf_for_EM": auroc(conf[m], em[m] > 0.5),
        "auroc_conf_for_U_pos": auroc(conf[m], UW[m] > 0),
        "auroc_conf_for_U_neg": auroc(conf[m], UW[m] < 0),
        "auroc_conf_for_U_nonzero": auroc(conf[m], UW[m] != 0),
        "auroc_conf_for_changed": auroc(conf[m], chg[m]),
        "auroc_f1_for_U_pos": auroc(f1, UW > 0), "auroc_f1_for_U_neg": auroc(f1, UW < 0),
        "mean_U_by_em": {"em1": float(UW[em > .5].mean()) if (em > .5).any() else None,
                         "em0": float(UW[em <= .5].mean())},
    }
    # Q3: feature tables
    feats = []
    for r in ok:
        f = r["features"]
        feats.append({"stratum": r["stratum"], "phase": f["phase"], "action_type": f["action_type"],
                      "task_type": r["task_type"], "repeated": "yes" if f["repeat_count"] >= 1 else "no",
                      "no_progress": "yes" if f["no_progress_run"] >= 1 else "no",
                      "orig_episode_success": str(r["episode_success"]),
                      "conf_high(>0.9997)": "yes" if (r["wm_confidence_logprob"] or 0) > 0.9997 else "no",
                      "pred_em": "1" if r["pred_em"] > .5 else "0"})
    table = []
    for key in feats[0]:
        groups = defaultdict(list)
        for i, f in enumerate(feats):
            groups[f[key]].append(i)
        for val, idx in sorted(groups.items()):
            idx = np.array(idx)
            table.append({"feature": key, "value": val, "n": len(idx),
                          "change_rate": float(chg[idx].mean()),
                          "P(U_W=+1)": float((UW[idx] > 0).mean()), "P(U_W=-1)": float((UW[idx] < 0).mean()),
                          "mean_U_W": float(UW[idx].mean()), "mean_U_R": float(UR[idx].mean()),
                          "P(U_noise!=0)": float((UN[idx] != 0).mean())})
    S["Q3_table"] = table
    with open(sd / "tables" / "stage3_by_feature.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(table[0]))
        wr.writeheader(); wr.writerows(table)
    # Q4/Q5: utility-coverage
    qs = [round(x, 2) for x in np.linspace(0.05, 1.0, 20)]
    stuck = np.array([1.0 if r["stratum"] == "stuck" else 0.0 for r in ok])
    c0 = np.nan_to_num(conf, nan=0.0)
    curves = {
        "confidence (high first)": coverage_curve(c0, UW, qs),
        "confidence (low first)": coverage_curve(-c0, UW, qs),
        "random (expected)": [float(q * UW.mean()) for q in qs],
        "stuck rule": coverage_curve(stuck, UW, qs),
        "ex-post oracle": coverage_curve(UW, UW, qs),
    }
    S["Q4_Q5"] = {"coverage": qs, "curves": curves,
                  "always_gain": float(UW.mean()),
                  "oracle_gain": float(np.clip(UW, 0, None).sum() / len(UW)),
                  "oracle_usage": float((UW > 0).mean()),
                  "at_usage_0.276": {k: float(np.interp(0.276, qs, v)) for k, v in curves.items()},
                  "rethink_always_gain": float(UR.mean())}
    (sd / "tables" / "stage3_summary.json").write_text(json.dumps(S, indent=2, ensure_ascii=False))
    write_md(S, sd / "tables" / "stage3_summary.md")
    plot(qs, curves, sd / "figures" / "utility_coverage.png", len(ok))
    write_cases(ok, sd / "tables" / "stage3_cases.md")
    print((sd / "tables" / "stage3_summary.md").read_text())


def _p(x):
    return "—" if x is None else f"{100*x:.1f}%"


def write_md(S, path):
    q1, q2, q4 = S["Q1"], S["Q2"], S["Q4_Q5"]
    L = ["# Stage 3 paired-branch summary", "",
         f"Points: {S['n_points']} sampled, {S['n_replay_ok']} replayed exactly. "
         f"a_base reproduced the logged action at {S['a_base_matches_log']}/{S['n_replay_ok']}; "
         f"B0 and its exact repeat B0r produced identical trajectories at "
         f"{S['b0_vs_b0r_identical_trajectory']}/{S['n_replay_ok']}.", "",
         "## Q1 utility distribution", "",
         "| quantity | n | +1 | 0 | −1 | mean [95% task-cluster CI] | sign-test p |", "|---|---:|---:|---:|---:|---|---:|"]
    for name, key, ci, p in [("U_W (foresight)", "U_W", "mean_U_W_cluster_ci", q1["sign_test_U_W_p"]),
                             ("U_R (rethink)", "U_R", "mean_U_R_cluster_ci", q1["sign_test_U_R_p"]),
                             ("U_noise (B0r − B0)", "U_noise", "mean_U_noise_cluster_ci", None)]:
        d = q1[key]; c = q1[ci]
        L.append(f"| {name} | {d['n']} | {d['n_pos']} ({_p(d['pos'])}) | {_p(d['zero'])} | {d['n_neg']} ({_p(d['neg'])}) "
                 f"| {c[0]:+.3f} [{c[1]:+.3f}, {c[2]:+.3f}] | {'—' if p is None else f'{p:.3f}'} |")
    dv = q1["U_W_visit_weighted"]
    L += ["", f"Visit-distribution-weighted U_W: +1 {_p(dv['pos'])}, −1 {_p(dv['neg'])}, mean {dv['mean']:+.3f}.",
          f"Action changed by foresight at {_p(q1['fore_change_rate'])} of points; by rethink at {_p(q1['rethink_change_rate'])}.",
          f"Given a change: U_W +1 {_p(q1['U_W_given_changed']['pos'])}, −1 {_p(q1['U_W_given_changed']['neg'])} "
          f"(n={q1['U_W_given_changed']['n']}); U_R +1 {_p(q1['U_R_given_changed']['pos'])}, −1 {_p(q1['U_R_given_changed']['neg'])} "
          f"(n={q1['U_R_given_changed']['n']}).",
          f"Changed foresight action admissible: {_p(q1['a_fore_admissible_when_changed'])}; changed rethink action admissible: {_p(q1['a_re_admissible_when_changed'])}.",
          f"Non-zero rate: U_W {_p(q1['nonzero_rate']['U_W'])}, U_R {_p(q1['nonzero_rate']['U_R'])}, U_noise {_p(q1['nonzero_rate']['U_noise'])}.",
          f"Base branch success rate Y0: {_p(q1['Y0_rate'])}.", "",
          "## Q2 confidence vs accuracy vs utility", "",
          f"Prediction EM {_p(q2['pred_em_mean'])}, token-F1 {q2['pred_f1_mean']:.3f} (vs real next observation).", "",
          "| signal → target | AUROC |", "|---|---:|"]
    for k in ("auroc_conf_for_EM", "auroc_conf_for_changed", "auroc_conf_for_U_nonzero",
              "auroc_conf_for_U_pos", "auroc_conf_for_U_neg", "auroc_f1_for_U_pos", "auroc_f1_for_U_neg"):
        v = q2[k]
        L.append(f"| {k.replace('auroc_', '')} | {'—' if v is None else f'{v:.3f}'} |")
    L += ["", f"Spearman(confidence, F1) = {q2['spearman_conf_f1']:.3f}. Mean U_W when EM=1: "
          f"{q2['mean_U_by_em']['em1']}, EM=0: {q2['mean_U_by_em']['em0']:+.3f}.", "",
          "## Q3 by feature (see stage3_by_feature.csv for all)", "",
          "| feature | value | n | changed | P(U_W=+1) | P(U_W=−1) | mean U_W | mean U_R | P(U_noise≠0) |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for t in S["Q3_table"]:
        L.append(f"| {t['feature']} | {t['value']} | {t['n']} | {_p(t['change_rate'])} | {_p(t['P(U_W=+1)'])} | "
                 f"{_p(t['P(U_W=-1)'])} | {t['mean_U_W']:+.3f} | {t['mean_U_R']:+.3f} | {_p(t['P(U_noise!=0)'])} |")
    L += ["", "## Q4/Q5 utility–coverage (per-decision gain = ΣU over selected / N)", "",
          f"Always: {q4['always_gain']:+.4f}. Ex-post oracle: {q4['oracle_gain']:+.4f} at usage {_p(q4['oracle_usage'])}. "
          f"Rethink-always: {q4['rethink_always_gain']:+.4f}.", "",
          "| selector | gain at usage 27.6% |", "|---|---:|"]
    for k, v in q4["at_usage_0.276"].items():
        L.append(f"| {k} | {v:+.4f} |")
    L += ["", "Oracle is a diagnostic on these fixed states only, not a deployable bound."]
    path.write_text("\n".join(L) + "\n")


def plot(qs, curves, path, n):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cols = ["#2a78d6", "#eb6834", "#8a8984", "#1baf7a", "#6250d6"]
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=150)
    fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")
    for (k, v), c in zip(curves.items(), cols):
        ls = "--" if "random" in k else "-"
        ax.plot([100 * q for q in qs], v, ls, color=c, lw=2, label=k)
    ax.axhline(0, color="#c3c2b7", lw=1)
    ax.axvline(27.6, color="#c3c2b7", lw=1, ls=":")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e", labelsize=9)
    ax.grid(True, color="#ecebe7", lw=0.8)
    ax.set_xlabel("Usage: % of decision points given foresight", color="#52514e")
    ax.set_ylabel("Gain per decision (ΣU_W / N)", color="#52514e")
    ax.set_title(f"Utility–coverage on {n} on-policy train states (only 3 points have U_W≠0)", fontsize=10, loc="left")
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def write_cases(ok, path):
    L = ["# Stage 3 cases (U_W = +1 and U_W = −1)", ""]
    for sign, title in ((1, "Benefit (U_W=+1)"), (-1, "Harm (U_W=−1)")):
        L += [f"## {title}", ""]
        for r in [r for r in ok if r["U_W"] == sign][:12]:
            L += [f"### point {r['point_id']} · {r['task_type']} · t={r['t']} · stratum={r['stratum']} · "
                  f"conf={r['wm_confidence_logprob']} · EM={r['pred_em']} · U_noise={r['U_noise']}",
                  f"- a_base: `{r['a_base']}` → GT: {r['gt_next_obs'][:200]}",
                  f"- prediction: {(r['wm_prediction'] or '')[:200]}",
                  f"- a_fore: `{r['a_fore']}` (admissible={r['a_fore_admissible']})",
                  f"- base thought: {(r['base_raw'] or '')[:300]}",
                  f"- foresight thought: {(r['fore_raw'] or '')[:300]}", ""]
    path.write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
