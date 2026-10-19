"""Step 3: pre-call utility gates (decide BEFORE any WM call, agent-visible only).

Features at decision step t (history = executed (action, obs) pairs, a_base,
admissible list) -- the same quantities as stage-3/step-0c `features()`:
    base_admissible, repeat_count, nothing_last5, no_progress_run, step,
    n_distinct_last5, n_admissible, action-type one-hot.

Learned gate: ridge regression of U_PR(wm) (step-0c K-continuation utility)
on these features, trained on the UNBIASED step-0c subset (tasks solvable by
rep1, states from rep0). Threshold = the score quantile giving `usage` on the
training points. `fit()` also reports leave-task-out CV Spearman so the gate's
predictive power is known before any episode is run.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
from scipy.stats import spearmanr

from preexperiments.react_study.stage3_sample_points import action_type

ACTION_TYPES = ("go_to", "take", "move", "open", "close", "use", "heat", "cool", "clean", "examine",
                "look", "inventory", "other")
ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = ROOT / "outputs" / "react_study" / "step3_gating" / "tables" / "learned_gate.json"


def featurize(history: Sequence[Tuple[str, str]], a_base: str, admissible: Sequence[str], step: int) -> np.ndarray:
    acts = [a for a, _ in history]
    nothing = ["Nothing happens" in o for _, o in history]
    run = 0
    for x in reversed(nothing):
        if not x:
            break
        run += 1
    at = action_type(a_base)
    at = "move" if a_base.startswith("move") else at
    onehot = [1.0 if at == t else 0.0 for t in ACTION_TYPES]
    return np.array([float(a_base in admissible), acts.count(a_base), sum(nothing[-5:]), run, step / 30.0,
                     len(set(acts[-5:])), len(admissible) / 50.0] + onehot, float)


def is_stuck(history, a_base) -> bool:
    return sum(1 for a, _ in history if a == a_base) >= 2 or sum("Nothing happens" in o for _, o in history[-5:]) >= 2


def _training_rows(step0_dir: Path):
    rep = {}
    for f in glob.glob(str(step0_dir / "raw" / "train" / "dev_v2_c*_none__rep*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            rep[(r["task_id"], r["rep"])] = r
    pts = {json.loads(l)["point_id"]: json.loads(l) for l in open(step0_dir / "raw" / "branch_points.jsonl")}
    X, y, tasks = [], [], []
    for f in glob.glob(str(step0_dir / "raw" / "branch_k.shard*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            if not r.get("replay_ok") or not rep[(r["task_id"], 1)]["success"]:
                continue  # unbiased subset only
            p = pts[r["point_id"]]
            traj = rep[(r["task_id"], 0)]["step_log"]
            hist = [(s["action"], s["next_observation"]) for s in traj[: p["t"]]]
            X.append(featurize(hist, r["first_actions"]["base"], traj[p["t"]]["admissible_actions"], p["t"]))
            y.append(r["U_pr"]["wm"])
            tasks.append(r["task_id"])
    return np.array(X), np.array(y), tasks


def _ridge(X, y, lam):
    mu, sd = X.mean(0), X.std(0) + 1e-8
    Z = (X - mu) / sd
    w = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    return mu, sd, w, y.mean()


def fit(step0_dir: Path, usage: float = 0.3, lam: float = 10.0) -> Dict:
    X, y, tasks = _training_rows(step0_dir)
    # leave-task-out CV
    uniq = sorted(set(tasks))
    pred = np.zeros(len(y))
    for t in uniq:
        te = np.array([x == t for x in tasks])
        mu, sd, w, b = _ridge(X[~te], y[~te], lam)
        pred[te] = ((X[te] - mu) / sd) @ w + b
    cv = spearmanr(pred, y).statistic
    k = max(1, int(round(usage * len(y))))
    top = np.argsort(-pred)[:k]
    mu, sd, w, b = _ridge(X, y, lam)
    score = ((X - mu) / sd) @ w + b
    thr = float(np.quantile(score, 1 - usage))
    model = {"mu": mu.tolist(), "sd": sd.tolist(), "w": w.tolist(), "b": float(b), "threshold": thr,
             "usage_target": usage, "lambda": lam, "n_train": int(len(y)), "n_tasks": len(uniq),
             "cv_spearman_leave_task_out": float(cv),
             "cv_gain_at_usage": float(y[top].sum() / len(y)), "always_gain": float(y.mean()),
             "random_gain_at_usage": float(usage * y.mean()),
             "oracle_gain_at_usage": float(np.sort(y)[::-1][:k].sum() / len(y)),
             "features": ["base_admissible", "repeat_count", "nothing_last5", "no_progress_run", "step/30",
                          "n_distinct_last5", "n_admissible/50"] + [f"at_{t}" for t in ACTION_TYPES]}
    GATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GATE_PATH.write_text(json.dumps(model, indent=2))
    return model


_MODEL = None


def learned_score(history, a_base, admissible, step) -> float:
    global _MODEL
    if _MODEL is None:
        _MODEL = json.loads(GATE_PATH.read_text())
    x = featurize(history, a_base, admissible, step)
    return float(((x - np.array(_MODEL["mu"])) / np.array(_MODEL["sd"])) @ np.array(_MODEL["w"]) + _MODEL["b"])


def learned_open(history, a_base, admissible, step) -> bool:
    if _MODEL is None:
        learned_score(history, a_base, admissible, step)
    return learned_score(history, a_base, admissible, step) > _MODEL["threshold"]


if __name__ == "__main__":
    m = fit(ROOT / "outputs" / "react_study" / "step0_protocol_v2_measurement")
    print(json.dumps({k: v for k, v in m.items() if k not in ("mu", "sd", "w")}, indent=2))


_UNC = None


def planner_uncertain(diag) -> bool:
    """Direction B gate: open when the planner's own action-token logprob is below the
    30%-usage threshold calibrated on the step-0c states (dirB_planner_uncertainty)."""
    global _UNC
    if _UNC is None:
        _UNC = json.loads((ROOT / "outputs" / "react_study" / "dirB_planner_uncertainty" / "tables" /
                           "gate_unc_calibration.json").read_text())["action_lp_threshold"]
    lp = diag.get("action_lp", float("nan"))
    return lp == lp and lp < _UNC
