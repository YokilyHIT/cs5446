"""Round 4 / Phase 1: WM capability on a FIXED set of (state, action) pairs.

Pairs = every distinct first action produced at the Phase-2 states (base / R / W / oracle arms,
both planners), so the comparison between WMs never mixes in a planner's action distribution.
For each pair the true next observation comes from a shadow env (replay + step); each WM
("wm" = Qwen3-4B-Instruct-2507, "wm_alt" = Qwen3-14B, thinking off) predicts it once, with
the identical WM prompt (direction_b WORLD_MODEL_PROMPT, no memory).

Metrics: exact match, token F1, effect classification (predicted vs true "Nothing happens"),
progress classification (does the predicted / true observation complete a new subgoal, using
the AgentBoard progress patterns), reported overall and by action type.

    $PY -m preexperiments.react_study.wm_capability_r4 --branch_cfg p2_4b --branch_cfg p2_14b_same
"""
from __future__ import annotations

import argparse
import glob
import json
import threading
from collections import defaultdict

import numpy as np

from preexperiments.common.alfworld_runner import extract_admissible, format_history, visible_actions
from preexperiments.common.logging_utils import load_yaml_config
from preexperiments.common.parallel import ordered_map
from preexperiments.direction_b.metrics import exact_match, token_f1
from preexperiments.react_study.agent import pseudo_or_env_step, replay
from preexperiments.react_study.analyze_p2 import ACTION_TYPES
from preexperiments.react_study.common import MeteredLLM, OUT_ROOT, set_role, stage_dir
from preexperiments.react_study.progress import progress_rate
from preexperiments.react_study.protocol_v2 import CHECK_VALID, PipelineV2, history_v2, init_room_obs


def atype(a):
    for t in ACTION_TYPES:
        if a.startswith(t):
            return t
    return "other"


def build_pairs(cfgs):
    pts = {json.loads(l)["point_id"]: json.loads(l)
           for l in open(OUT_ROOT / "step0_protocol_v2_measurement" / "raw" / "branch_points.jsonl")}
    pairs = {}
    for cfg in cfgs:
        for f in glob.glob(str(stage_dir(32) / "raw" / f"{cfg}.shard*.jsonl")):
            for l in open(f):
                r = json.loads(l)
                if not r.get("replay_ok"):
                    continue
                for arm, act in r["first_actions"].items():
                    if act == CHECK_VALID:
                        continue
                    key = (r["point_id"], act)
                    pairs.setdefault(key, {"point_id": r["point_id"], "action": act, "sources": set()})
                    pairs[key]["sources"].add(f"{cfg}:{arm.split('#')[0]}")
    out = []
    for (pid, act), v in sorted(pairs.items()):
        v["sources"] = sorted(v["sources"])
        v["point"] = pts[pid]
        out.append(v)
    return out


def run_pair(pipe, split, hist_len, q):
    p = q["point"]
    env, obs, info, history, done, init_obs = replay(split, p["gamefile"], p["prefix"])
    if obs != p["observation"] or done:
        return {"point_id": q["point_id"], "action": q["action"], "replay_ok": False}
    adm = visible_actions(extract_admissible(info))
    state = {"goal": p["goal"], "task_type": p["task_type"],
             "history": format_history(history, max_turns=hist_len),
             "history_v2": history_v2(init_room_obs(init_obs), history),
             "current_observation": obs, "admissible_actions": adm}
    gt, _d, _i = pseudo_or_env_step(env, q["action"], adm, info)
    prev = [o for _, o in history]
    base_pr = progress_rate(p["gamefile"], prev, False)
    out = {"point_id": q["point_id"], "task_id": p["task_id"], "action": q["action"], "sources": q["sources"],
           "action_type": atype(q["action"]), "admissible": q["action"] in adm, "replay_ok": True, "gt": gt,
           "gt_nothing": "nothing happens" in gt.lower(),
           "gt_progress": progress_rate(p["gamefile"], prev + [gt], False) > base_pr}
    for role in ("wm", "wm_alt"):
        set_role(role)
        pr = pipe.predict(state, q["action"])
        txt = pr["wm_prediction"] or ""
        out[role] = {"prediction": txt, "em": exact_match(txt, gt), "f1": token_f1(txt, gt),
                     "nothing": "nothing happens" in txt.lower(),
                     "progress": progress_rate(p["gamefile"], prev + [txt], False) > base_pr,
                     "confidence_logprob": pr["wm_confidence_logprob"]
                     if pr["wm_confidence_logprob"] == pr["wm_confidence_logprob"] else None}
    return out


def bal_acc(pred, y):
    pred, y = np.asarray(pred, bool), np.asarray(y, bool)
    tpr = (pred & y).sum() / max(y.sum(), 1)
    tnr = (~pred & ~y).sum() / max((~y).sum(), 1)
    return float((tpr + tnr) / 2)


def summarize(rows, rng):
    rows = [r for r in rows if r.get("replay_ok")]
    tasks = np.array([r["task_id"] for r in rows])
    ut = np.unique(tasks)
    idx = {t: np.where(tasks == t)[0] for t in ut}

    def stats(rs):
        s = {"n": len(rs), "gt_nothing_rate": float(np.mean([r["gt_nothing"] for r in rs])),
             "gt_progress_rate": float(np.mean([r["gt_progress"] for r in rs]))}
        for role, name in (("wm", "4B"), ("wm_alt", "14B")):
            s[name] = {"em": float(np.mean([r[role]["em"] for r in rs])),
                       "f1": float(np.mean([r[role]["f1"] for r in rs])),
                       "effect_bal_acc": bal_acc([r[role]["nothing"] for r in rs], [r["gt_nothing"] for r in rs]),
                       "progress_bal_acc": bal_acc([r[role]["progress"] for r in rs], [r["gt_progress"] for r in rs])}
        return s

    res = {"overall": stats(rows)}
    # paired task-cluster bootstrap for 14B - 4B differences
    diffs = {}
    for k, f in (("em", lambda r, w: float(r[w]["em"])), ("f1", lambda r, w: r[w]["f1"]),
                 ("effect_correct", lambda r, w: float(r[w]["nothing"] == r["gt_nothing"])),
                 ("progress_correct", lambda r, w: float(r[w]["progress"] == r["gt_progress"]))):
        d = np.array([f(r, "wm_alt") - f(r, "wm") for r in rows])
        bs = [d[np.concatenate([idx[t] for t in rng.choice(ut, len(ut))])].mean() for _ in range(5000)]
        diffs[k] = {"mean_14B_minus_4B": float(d.mean()), "ci": [float(np.quantile(bs, .025)), float(np.quantile(bs, .975))]}
    res["diff_14B_minus_4B"] = diffs
    by = defaultdict(list)
    for r in rows:
        by[r["action_type"]].append(r)
    res["by_action_type"] = {k: stats(v) for k, v in sorted(by.items()) if len(v) >= 10}
    return res


def main(a):
    config = load_yaml_config(a.config)
    hist_len = config["sampling"].get("history_length", 50)
    pairs = build_pairs(a.branch_cfg)
    sd = stage_dir(31)
    out = sd / "raw" / "wm_capability.jsonl"
    done = set()
    if out.exists():
        done = {(json.loads(l)["point_id"], json.loads(l)["action"]) for l in open(out) if l.strip()}
    todo = [q for q in pairs if (q["point_id"], q["action"]) not in done]
    print(f"[p1] pairs={len(pairs)} todo={len(todo)}", flush=True)
    pipe = PipelineV2(MeteredLLM(config), config.get("direction_b", {}), variant="list")
    lock = threading.Lock()

    def sink(_i, _q, r):
        with lock, open(out, "a") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ordered_map(lambda q: run_pair(pipe, "train", hist_len, q), todo, workers=a.workers, label="p1",
                progress_every=50, on_result=sink)
    rows = [json.loads(l) for l in open(out) if l.strip()]
    res = summarize(rows, np.random.default_rng(2026))
    (sd / "tables" / "wm_capability.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    ap.add_argument("--branch_cfg", action="append", required=True)
    ap.add_argument("--workers", type=int, default=24)
    main(ap.parse_args())
