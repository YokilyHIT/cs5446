"""Round 4 / Phase 4: keep (0) / resample (R) / foresight (W) router.

One feature map for offline training (branch rows) and online routing (agent arm `route`):
only information available BEFORE any WM call -- the step-0c agent-visible features
(stage3_sample_points.features), the base action's action-line logprob, whether a_base is
admissible, and its verb. Optional stage-2 features (`--two_stage`) add the outcome of the
R draw itself (RT != a_base, RT verb): the R draw costs one planner call, which a router that
may choose R pays anyway.

Scores (ridge; with identical features/penalty the incremental form g_R + g_I equals a direct
ridge on V_W - V_0, so only one is fitted and the equivalence is reported, not claimed as a gain):
    S_0 = 0,  S_R = g_R_hat - lam * C_R,  S_W = g_W_hat - lam * C_W,   choice = argmax, ties -> cheaper.
lam is chosen on a calibration split so that the non-keep rate hits a target budget.

    $PY -m preexperiments.react_study.router train --cfg p4_4b_label --cfg p2_4b --W W14 --out router_4b.json
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

ACTION_TYPES = ("go to", "take", "move", "open", "close", "examine", "use", "heat", "cool", "clean",
                "look", "inventory", "check valid actions")


def verb_onehot(a: str) -> List[float]:
    return [float(a.startswith(t)) for t in ACTION_TYPES]


def feat_vector(f: Dict[str, Any], base_lp: Optional[float], a_base: str, base_adm: bool,
                rt: Optional[str] = None) -> np.ndarray:
    lp = float(base_lp) if base_lp is not None and base_lp == base_lp else 0.0
    x = [np.log1p(-lp * 1e3), float(lp < -1e-3), f.get("step", 0) / 30, f.get("repeat_count", 0),
         f.get("nothing_last5", 0), f.get("no_progress_run", 0), f.get("n_distinct_last5", 0),
         f.get("n_locations_visited", 0), f.get("n_admissible", 0) / 30, float(base_adm)]
    x += verb_onehot(a_base)
    if rt is not None:
        x += [float(rt != a_base)] + verb_onehot(rt)
    return np.array(x, float)


def online_fdict(history: Sequence[Tuple[str, str]], a_base: str, admissible: Sequence[str], step: int,
                 base_forced: bool) -> Dict[str, Any]:
    """Same dict as stage3_sample_points.features(steps, t) from the live history."""
    from preexperiments.react_study.stage3_sample_points import features
    steps = [{"action": a, "next_observation": o} for a, o in history]
    steps.append({"baseline_action": a_base, "base_forced": base_forced, "admissible_actions": list(admissible)})
    f = features(steps, len(history))
    f["step"] = step
    return f


def row_features(r: Dict[str, Any], two_stage: bool = False) -> np.ndarray:
    a = r["first_actions"]["base"]
    return feat_vector(r.get("features") or {}, r.get("base_action_lp"), a, r["first_admissible"]["base"],
                       rt=r["first_actions"]["RT"] if two_stage else None)


def ridge_fit(X, y, lam):
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xt = (X - mu) / sd
    w = np.linalg.solve(Xt.T @ Xt + lam * np.eye(X.shape[1]), Xt.T @ (y - y.mean()))
    return {"mu": mu.tolist(), "sd": sd.tolist(), "w": w.tolist(), "b": float(y.mean()), "lam": lam}


def ridge_pred(m, X):
    return ((np.atleast_2d(X) - np.array(m["mu"])) / np.array(m["sd"])) @ np.array(m["w"]) + m["b"]


class Router:
    def __init__(self, path: str):
        self.m = json.load(open(path))

    def scores(self, x: np.ndarray) -> Tuple[float, float]:
        sR = float(ridge_pred(self.m["gR"], x)[0]) - self.m["lambda"] * self.m["C_R"]
        sW = float(ridge_pred(self.m["gW"], x)[0]) - self.m["lambda"] * self.m["C_W"]
        return sR, sW

    def choose(self, x: np.ndarray) -> Tuple[str, float, float]:
        sR, sW = self.scores(x)
        if max(sR, sW) <= 0:
            return "0", sR, sW
        return ("R" if sR >= sW else "W"), sR, sW  # tie -> cheaper (R)


def choose_offline(sR, sW):
    act = np.maximum(sR, sW) > 0
    return act & (sW > sR), act & (sW <= sR)


# ------------------------------------------------------------------ training
def load_rows(cfgs: List[str]):
    from preexperiments.react_study.analyze_p2 import load
    rows = []
    for c in cfgs:
        rows += load(c)
    return rows


def main_train(a):
    rows = load_rows(a.cfg)
    V = lambda r, k: r[f"P_{a.metric}"][k]
    rows = [r for r in rows if a.W in r[f"P_{a.metric}"] and "RT" in r[f"P_{a.metric}"]]
    X = np.stack([row_features(r, a.two_stage) for r in rows])
    gR = np.array([V(r, "RT") - V(r, "base") for r in rows])
    gW = np.array([V(r, a.W) - V(r, "base") for r in rows])
    tasks = np.array([r["task_id"] for r in rows])
    # calibration split by task (held out from the fit used for lambda selection)
    rng = np.random.default_rng(a.seed)
    ut = rng.permutation(np.unique(tasks))
    cal = np.isin(tasks, ut[: int(len(ut) * a.cal_frac)])
    mR, mW = ridge_fit(X[~cal], gR[~cal], a.lam), ridge_fit(X[~cal], gW[~cal], a.lam)
    cost = json.load(open(a.costs)) if a.costs else {"C_R": 1.0, "C_W": 2.0}
    pR, pW = ridge_pred(mR, X[cal]), ridge_pred(mW, X[cal])
    best, lam_star = None, 0.0
    for lam in np.linspace(0, 0.05, 501):
        wW, wR = choose_offline(pR - lam * cost["C_R"], pW - lam * cost["C_W"])
        rate = (wW | wR).mean()
        if best is None or abs(rate - a.budget) < best:
            best, lam_star = abs(rate - a.budget), float(lam)
    model = {"gR": ridge_fit(X, gR, a.lam), "gW": ridge_fit(X, gW, a.lam), "lambda": lam_star,
             "C_R": cost["C_R"], "C_W": cost["C_W"], "W": a.W, "metric": a.metric, "two_stage": a.two_stage,
             "budget": a.budget, "n_rows": len(rows), "n_tasks": int(len(np.unique(tasks))), "cfgs": a.cfg,
             "feature_note": "router.feat_vector"}
    wW, wR = choose_offline(ridge_pred(model["gR"], X) - lam_star * cost["C_R"],
                            ridge_pred(model["gW"], X) - lam_star * cost["C_W"])
    model["train_rates"] = {"W": float(wW.mean()), "R": float(wR.mean())}
    json.dump(model, open(a.out, "w"), indent=2)
    print(json.dumps({k: v for k, v in model.items() if k not in ("gR", "gW")}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--cfg", action="append", required=True)
    t.add_argument("--W", default="W14")
    t.add_argument("--metric", default="pr")
    t.add_argument("--lam", type=float, default=10.0)
    t.add_argument("--budget", type=float, default=0.3, help="target non-keep rate on the calibration split")
    t.add_argument("--cal_frac", type=float, default=0.25)
    t.add_argument("--costs", default="")
    t.add_argument("--two_stage", action="store_true")
    t.add_argument("--seed", type=int, default=2026)
    t.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "train":
        main_train(a)
