"""Round 4 / Phase 2 analysis: same-state labels for keep / resample / foresight (gate G1).

For each config file glob (e.g. p2_4b, p2_14b_same) and metric (pr, success):

  1. Contrasts with task-clustered bootstrap CIs (points of one task are resampled together):
        g_R    = V_RT - V_base          R0 - base   (serving-noise resample)
        g_I4   = V_W4 - V_RT            g_I14 = V_W14 - V_RT
        g_O    = V_oracle - V_RT        g_OS  = V_oracle_struct - V_RT
        W - base for W4 / W14 / oracle / oracle_struct
  2. Action agreement (same first action as base / as RT).
  3. Heterogeneity: var_points(g) - mean continuation-noise variance of g (K rollouts per action).
  4. Generation noise on regen points: P(redrawn action != original), and the variance of V across draws.
  5. Predictability (pre-WM features only, task-grouped 5-fold CV ridge, repeated 20 splits):
        Spearman(g_hat, g), sign AUROC on g != 0, and the offline policy value of
        "foresight on the top-q predicted states, resample elsewhere" minus a same-rate random choice.

    $PY -m preexperiments.react_study.analyze_p2 --cfg p2_4b --cfg p2_14b_same
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict

import numpy as np

from preexperiments.react_study.common import OUT_ROOT, stage_dir

B = 5000
ACTION_TYPES = ("go to", "take", "move", "open", "close", "examine", "use", "heat", "cool", "clean",
                "look", "inventory", "check valid actions")
CONTRASTS = {  # name: (a, b) -> V_a - V_b
    "g_R (RT-base)": ("RT", "base"), "R0-base": ("R0", "base"),
    "g_I4 (W4-RT)": ("W4", "RT"), "g_I14 (W14-RT)": ("W14", "RT"),
    "g_O (oracle-RT)": ("oracle", "RT"), "g_OS (oracle_struct-RT)": ("oracle_struct", "RT"),
    "W4-base": ("W4", "base"), "W14-base": ("W14", "base"),
    "oracle-base": ("oracle", "base"), "oracle_struct-base": ("oracle_struct", "base"),
    "W14-W4": ("W14", "W4"), "oracle_struct-oracle": ("oracle_struct", "oracle"),
}
TARGETS = {"g_R": ("RT", "base"), "g_I4": ("W4", "RT"), "g_I14": ("W14", "RT"), "g_O": ("oracle", "RT"),
           "g_W4tot": ("W4", "base"), "g_W14tot": ("W14", "base")}


def load(cfg):
    if "+" in cfg:
        return [r for c in cfg.split("+") for r in load(c)]
    rows = []
    for st in (32, 34):  # Phase 2 (p2_*) and Phase 4 (p4_*) branch rows
        for f in sorted(glob.glob(str(stage_dir(st) / "raw" / f"{cfg}.shard*.jsonl"))):
            rows += [json.loads(l) for l in open(f) if l.strip()]
    rows = [r for r in rows if r.get("replay_ok")]
    sig = {}
    sf = OUT_ROOT / "dirB_planner_uncertainty" / "raw" / "signals.jsonl"
    for l in open(sf):
        s = json.loads(l)
        sig[s["point_id"]] = s
    for r in rows:  # reused 4B base actions carry no logprob; dirB computed it on the identical prompt
        if r.get("base_action_lp") is None and r.get("reused_prior") and r["point_id"] in sig:
            r["base_action_lp"] = sig[r["point_id"]]["planner_action_lp"]
    return rows


def V(r, arm, m):
    return r[f"P_{m}"][arm]


def cont_var(r, arm, m):
    """Sampling variance of V(arm) from its K continuations."""
    a = r["first_actions"][arm]
    xs = np.array([float(c["success"] if m == "success" else c[m]) for c in r["continuations"][a]])
    return xs.var(ddof=1) / len(xs) if len(xs) > 1 else 0.0


def g_noise_var(r, a, b, m):
    if r["first_actions"][a] == r["first_actions"][b]:
        return 0.0
    return cont_var(r, a, m) + cont_var(r, b, m)


def cluster_boot(vals, tasks, rng, stat=np.mean):
    vals, tasks = np.asarray(vals, float), np.asarray(tasks)
    ut = np.unique(tasks)
    idx = {t: np.where(tasks == t)[0] for t in ut}
    bs = []
    for _ in range(B):
        pick = rng.choice(ut, len(ut))
        ii = np.concatenate([idx[t] for t in pick])
        bs.append(stat(vals[ii]))
    lo, hi = np.quantile(bs, [0.025, 0.975])
    bs = np.asarray(bs)
    p = 2 * min((bs <= 0).mean(), (bs >= 0).mean())
    return float(stat(vals)), float(lo), float(hi), float(min(1.0, max(p, 1 / B)))


def features(r, two_stage=False):
    from preexperiments.react_study.router import row_features
    return row_features(r, two_stage)


def auroc(score, y):
    score, y = np.asarray(score), np.asarray(y).astype(bool)
    if y.all() or (~y).all():
        return float("nan")
    from scipy.stats import rankdata
    rk = rankdata(score)
    n1 = y.sum()
    return float((rk[y].sum() - n1 * (n1 + 1) / 2) / (n1 * (~y).sum()))


def cv_predict(X, y, tasks, rng, lam=10.0, folds=5):
    ut = np.unique(tasks)
    perm = rng.permutation(ut)
    fold_of = {t: i % folds for i, t in enumerate(perm)}
    f = np.array([fold_of[t] for t in tasks])
    pred = np.zeros(len(y))
    for k in range(folds):
        tr, te = f != k, f == k
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        Xt = (X[tr] - mu) / sd
        A = Xt.T @ Xt + lam * np.eye(X.shape[1])
        w = np.linalg.solve(A, Xt.T @ (y[tr] - y[tr].mean()))
        pred[te] = ((X[te] - mu) / sd) @ w + y[tr].mean()
    return pred


def predictability(rows, m, rng, n_rep=20):
    from scipy.stats import spearmanr
    X = np.stack([features(r) for r in rows])
    tasks = np.array([r["task_id"] for r in rows])
    out = {}
    for name, (a, b) in TARGETS.items():
        if any(a not in r["P_pr"] or b not in r["P_pr"] for r in rows):
            continue
        y = np.array([V(r, a, m) - V(r, b, m) for r in rows])
        rhos, aucs, pv = [], [], defaultdict(list)
        for _ in range(n_rep):
            p = cv_predict(X, y, tasks, rng)
            rhos.append(spearmanr(p, y).correlation if np.std(p) > 0 else 0.0)
            nz = y != 0
            aucs.append(auroc(p[nz], y[nz] > 0))
            for q in (0.2, 0.3, 0.5):
                k = max(1, int(round(q * len(y))))
                sel = np.zeros(len(y), bool)
                sel[np.argsort(-p)[:k]] = True
                pv[q].append((y * sel).mean() - q * y.mean())  # vs random selection at the same rate
        # CI for the policy value: cluster bootstrap over a single representative split
        p = cv_predict(X, y, tasks, rng)
        ci = {}
        for q in (0.2, 0.3, 0.5):
            k = max(1, int(round(q * len(y))))
            sel = np.zeros(len(y), bool)
            sel[np.argsort(-p)[:k]] = True
            per = y * sel - q * y  # per-point contribution; mean = policy value vs random
            ci[q] = cluster_boot(per, tasks, rng)
        out[name] = {"n": len(y), "mean": float(y.mean()), "frac_nonzero": float((y != 0).mean()),
                     "spearman_cv": float(np.nanmean(rhos)), "sign_auroc_cv": float(np.nanmean(aucs)),
                     "policy_value_vs_random": {str(q): float(np.mean(v)) for q, v in pv.items()},
                     "policy_value_ci_one_split": {str(q): ci[q] for q in ci}}
    return out


def router_offline(rows, m, W, rng, n_rep=20, qs=(0.2, 0.3, 0.5, 1.0), two_stage=False):
    """Offline value (vs always-keep) of choosing 0 / RT / W per state from pre-WM features.

    incremental: S_R = g_R_hat, S_W = g_R_hat + g_I_hat (two ridges); direct: S_R = g_R_hat, S_W = gW_hat
    (ridge on V_W - V_0). Budget q = fraction of states allowed a non-keep choice (top-q by max(S_R, S_W),
    only if that max > 0 when q = 1). Matched random = same 0/R/W proportions assigned at random
    (expected value). Also the 0-vs-W router (rank gW_hat) and its same-rate random."""
    X = np.stack([features(r, two_stage) for r in rows])
    tasks = np.array([r["task_id"] for r in rows])
    v0 = np.array([V(r, "base", m) for r in rows])
    gR = np.array([V(r, "RT", m) for r in rows]) - v0
    gW = np.array([V(r, W, m) for r in rows]) - v0
    gI = gW - gR
    res = defaultdict(lambda: defaultdict(list))
    eq_err = []
    per_split = []
    for rep in range(n_rep):
        seed = int(rng.integers(1 << 30))
        pR = cv_predict(X, gR, tasks, np.random.default_rng(seed))
        pI = cv_predict(X, gI, tasks, np.random.default_rng(seed))
        pW = cv_predict(X, gW, tasks, np.random.default_rng(seed))
        eq_err.append(float(np.max(np.abs(pR + pI - pW))))
        for name, SW in (("incremental", pR + pI), ("direct", pW)):
            for q in qs:
                best = np.maximum(SW, pR)
                k = int(round(q * len(rows)))
                act = np.zeros(len(rows), bool)
                order = np.argsort(-best)[:k]
                act[order] = True
                if q == 1.0:
                    act &= best > 0
                choseW = act & (SW >= pR)
                choseR = act & (SW < pR)
                val = (gW * choseW + gR * choseR)
                rand = choseW.mean() * gW.mean() + choseR.mean() * gR.mean()
                res[f"{name}/q={q}"]["value"].append(val.mean())
                res[f"{name}/q={q}"]["minus_matched_random"].append(val.mean() - rand)
                res[f"{name}/q={q}"]["fracW"].append(choseW.mean())
                res[f"{name}/q={q}"]["fracR"].append(choseR.mean())
                if rep == 0:
                    per_split.append((f"{name}/q={q}", val - (choseW.mean() * gW + choseR.mean() * gR)))
        for q in qs[:-1]:
            k = int(round(q * len(rows)))
            sel = np.zeros(len(rows), bool)
            sel[np.argsort(-pW)[:k]] = True
            res[f"keep_vs_W/q={q}"]["value"].append((gW * sel).mean())
            res[f"keep_vs_W/q={q}"]["minus_matched_random"].append((gW * sel).mean() - q * gW.mean())
            if rep == 0:
                per_split.append((f"keep_vs_W/q={q}", gW * sel - q * gW))
    out = {k: {kk: float(np.mean(vv)) for kk, vv in d.items()} for k, d in res.items()}
    for k, per in per_split:
        out[k]["ci_minus_random_one_split"] = cluster_boot(per, tasks, rng)[1:3]
    out["_ridge_additivity_max_abs_err"] = float(np.max(eq_err))
    out["_corr(g_I, -g_R)"] = float(np.corrcoef(gI, -gR)[0, 1])
    out["_oracle_best_of_3_value"] = float(np.maximum(np.maximum(gW, gR), 0).mean())
    out["_always_R"] = float(gR.mean())
    out["_always_W"] = float(gW.mean())
    return out


def analyze(cfg, rng):
    rows = load(cfg)
    res = {"cfg": cfg, "n_points": len(rows), "n_tasks": len({r["task_id"] for r in rows})}
    tasks = [r["task_id"] for r in rows]
    for m in ("pr", "success"):
        C = {}
        for name, (a, b) in CONTRASTS.items():
            ok = [r for r in rows if a in r[f"P_{m}"] and b in r[f"P_{m}"]]
            if not ok:
                continue
            g = [V(r, a, m) - V(r, b, m) for r in ok]
            mean, lo, hi, p = cluster_boot(g, [r["task_id"] for r in ok], rng)
            noise = float(np.mean([g_noise_var(r, a, b, m) for r in ok]))
            C[name] = {"n": len(ok), "mean": mean, "ci": [lo, hi], "p": p,
                       "frac_changed": float(np.mean([r["first_actions"][a] != r["first_actions"][b] for r in ok])),
                       "frac_pos": float(np.mean(np.array(g) > 0)), "frac_neg": float(np.mean(np.array(g) < 0)),
                       "var_total": float(np.var(g, ddof=1)), "var_noise": noise,
                       "heterogeneity_sd": float(np.sqrt(max(np.var(g, ddof=1) - noise, 0)))}
        res[m] = {"contrasts": C, "V_mean": {k: float(np.mean([V(r, k, m) for r in rows if k in r[f"P_{m}"]]))
                                             for k in ("base", "R0", "RT", "W4", "W14", "oracle", "oracle_struct")}}
        res[m]["predictability"] = predictability(rows, m, rng)
        res[m]["router_offline"] = {W: router_offline(rows, m, W, rng) for W in ("W4", "W14", "oracle")}
        res[m]["router_offline"].update({W + "+2stage": router_offline(rows, m, W, rng, two_stage=True)
                                         for W in ("W4", "W14")})
    # generation noise on regen points
    gen = {}
    for k in ("RT", "W4", "W14"):
        rs = [r for r in rows if r.get("regen") and f"{k}#1" in r["first_actions"]]
        if not rs:
            continue
        diff = [np.mean([r["first_actions"][f"{k}#{j}"] != r["first_actions"][k]
                         for j in (1, 2) if f"{k}#{j}" in r["first_actions"]]) for r in rs]
        sdv = [np.std([r["P_pr"][x] for x in [k] + [f"{k}#{j}" for j in (1, 2)] if x in r["P_pr"]]) for r in rs]
        gen[k] = {"n_points": len(rs), "p_redraw_differs": float(np.mean(diff)), "mean_sd_V_pr_across_draws": float(np.mean(sdv))}
    if any(r.get("regen") for r in rows):
        pf = [np.mean([r["predictions"][f"W4#{j}"]["prediction"] != r["predictions"]["W4"]["prediction"]
                       for j in (1, 2) if f"W4#{j}" in r["predictions"]]) for r in rows
              if r.get("regen") and "W4#1" in r.get("predictions", {})]
        gen["W4_prediction_text_differs"] = float(np.mean(pf)) if pf else None
    res["generation_noise"] = gen
    # WM accuracy on a_base (fixed state-action = a_base)
    acc = {}
    for k in ("W4", "W14"):
        ps = [r["predictions"][k] for r in rows if k in r.get("predictions", {})]
        acc[k] = {"n": len(ps), "em": float(np.mean([bool(p.get("em")) for p in ps])) if ps else None,
                  "f1": float(np.mean([p.get("f1") or 0 for p in ps])) if ps else None}
    res["wm_accuracy_on_a_base"] = acc
    return res


def md(results):
    L = ["# Phase 2: same-state 0 / R / W labels\n",
         "V = mean over K=8 continuations under the planner's own WM-free policy; CIs are task-clustered bootstrap.",
         "g_R = RT - base; g_I = W - RT (foresight vs no-information resample). Points = 127 unbiased step-0c states.\n"]
    for res in results:
        L.append(f"## {res['cfg']} ({res['n_points']} points, {res['n_tasks']} tasks)\n")
        for m in ("pr", "success"):
            L.append(f"### metric = {m}\n")
            L.append("V means: " + ", ".join(f"{k} {v:.3f}" for k, v in res[m]["V_mean"].items()) + "\n")
            L.append("| contrast | n | mean | 95% CI | p | changed | +/- | heterogeneity sd |")
            L.append("|---|---:|---:|---|---:|---:|---|---:|")
            for k, c in res[m]["contrasts"].items():
                L.append(f"| {k} | {c['n']} | {c['mean']:+.4f} | [{c['ci'][0]:+.4f}, {c['ci'][1]:+.4f}] | {c['p']:.3f} | "
                         f"{c['frac_changed']:.2f} | {c['frac_pos']:.2f}/{c['frac_neg']:.2f} | {c['heterogeneity_sd']:.3f} |")
            L.append("\nPredictability (pre-WM features, task-grouped 5-fold ridge CV, 20 splits):\n")
            L.append("| target | mean | nonzero | Spearman | sign AUROC | PV q=.2 | PV q=.3 | PV q=.5 | PV q=.3 CI (one split) |")
            L.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
            for k, c in res[m]["predictability"].items():
                pv, ci = c["policy_value_vs_random"], c["policy_value_ci_one_split"]["0.3"]
                L.append(f"| {k} | {c['mean']:+.4f} | {c['frac_nonzero']:.2f} | {c['spearman_cv']:+.3f} | {c['sign_auroc_cv']:.3f} | "
                         f"{pv['0.2']:+.4f} | {pv['0.3']:+.4f} | {pv['0.5']:+.4f} | [{ci[1]:+.4f}, {ci[2]:+.4f}] |")
            L.append("\nOffline 3-way router (CV, value = mean V(choice) - V(keep); 'rand' = same 0/R/W mix at random):\n")
            L.append("| W arm | router | value | minus matched random | CI (one split) | frac W | frac R |")
            L.append("|---|---|---:|---:|---|---:|---:|")
            for W, ro in res[m]["router_offline"].items():
                for k, c in ro.items():
                    if k.startswith("_"):
                        continue
                    ci = c.get("ci_minus_random_one_split", [float("nan")] * 2)
                    L.append(f"| {W} | {k} | {c['value']:+.4f} | {c['minus_matched_random']:+.4f} | "
                             f"[{ci[0]:+.4f}, {ci[1]:+.4f}] | {c.get('fracW', float('nan')):.2f} | {c.get('fracR', float('nan')):.2f} |")
                L.append(f"| {W} | diagnostics | always R {ro['_always_R']:+.4f}, always W {ro['_always_W']:+.4f}, "
                         f"best-of-3 oracle {ro['_oracle_best_of_3_value']:+.4f}, corr(g_I,-g_R) {ro['_corr(g_I, -g_R)']:+.2f}, "
                         f"ridge additivity err {ro['_ridge_additivity_max_abs_err']:.1e} | | | | |")
            L.append("")
        L.append("Generation noise: " + json.dumps(res["generation_noise"]) + "\n")
        L.append("WM accuracy on a_base: " + json.dumps(res["wm_accuracy_on_a_base"]) + "\n")
    return "\n".join(L)


def main(a):
    rng = np.random.default_rng(2026)
    results = [analyze(c, rng) for c in a.cfg]
    sd = stage_dir(32)
    tag = a.tag or "_".join(a.cfg)
    (sd / "tables" / f"p2_{tag}.json").write_text(json.dumps(results, indent=2))
    (sd / "tables" / f"p2_{tag}.md").write_text(md(results))
    print(md(results))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", action="append", required=True)
    ap.add_argument("--tag", default="")
    main(ap.parse_args())
