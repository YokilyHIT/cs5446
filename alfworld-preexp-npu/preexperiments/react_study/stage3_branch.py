"""Stage 3b: paired counterfactual branches from each sampled decision point.

For every point (task, t, action prefix):

  1. Replay the prefix in a fresh env; assert the observation equals the one
     logged at collection time (otherwise the point is dropped and counted).
  2. At that state, with the SAME ReAct prompt/decoding as stage 2:
       a_base  = planner(state)
       pred    = WM(state, a_base)    (+ logprob confidence)
       a_fore  = planner(state + FORESIGHT_BLOCK(pred))
       a_re    = planner(state + RETHINK_BLOCK)
  3. Branches, each executing its first action and then continuing with the
     `none` policy until step max_steps (same remaining budget for all):
       B0    first action a_base
       B0r   first action a_base again, fresh env (noise floor: identical
             intervention, so any Y difference is serving nondeterminism)
       BW    first action a_fore   (shares B0's outcome if a_fore == a_base)
       BR    first action a_re     (shares B0's outcome if a_re == a_base)
  4. U_W = Y_W - Y_0,  U_R = Y_R - Y_0,  U_noise = Y_0r - Y_0.

The prediction is NOT kept in the continuation's context: the intervention is
exactly "one step of foresight at t".
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from pathlib import Path

from preexperiments.common.alfworld_runner import extract_admissible, format_history, visible_actions
from preexperiments.common.logging_utils import load_yaml_config
from preexperiments.common.parallel import ordered_map
from preexperiments.direction_b.metrics import exact_match, token_f1
from preexperiments.direction_b.pipeline import FORESIGHT_BLOCK, DirectionBPipeline
from preexperiments.react_study.agent import RETHINK_BLOCK, replay, run_policy
from preexperiments.react_study.common import Meter, MeteredLLM, set_meter, set_role, stage_dir


def branch(pipe, split, p, first_action, max_steps, hist_len):
    env, obs, info, history, done, _init = replay(split, p["gamefile"], p["prefix"])
    m = Meter()
    r = run_policy(pipe, env, obs, info, goal=p["goal"], task_id=p["task_id"], history=history,
                   start_step=p["t"], max_steps=max_steps, arm="none", tau=0, p_gate=0,
                   gate_seed=0, history_length=hist_len, meter=m, first_action=first_action)
    return {"success": r["success"], "done": r["done"], "n_steps": len(r["steps"]),
            "first_next_obs": r["steps"][0]["next_observation"] if r["steps"] else None,
            "actions": [s["action"] for s in r["steps"]], "cost": m.total}


def run_point(pipe, split, p, max_steps, hist_len):
    t0 = time.time()
    env, obs, info, history, done, _init = replay(split, p["gamefile"], p["prefix"])
    if obs != p["observation"] or done:
        return {"point_id": p["point_id"], "replay_ok": False}
    admissible = visible_actions(extract_admissible(info))
    state = {"goal": p["goal"], "history": format_history(history, max_turns=hist_len),
             "current_observation": obs, "admissible_actions": admissible}
    m = Meter()
    set_meter(m)
    set_role("planner_base")
    a_base, fb, _, db = pipe._dispatch_choose(state, "")
    set_role("wm")
    pred = pipe.predict(state, a_base)
    set_role("planner_second")
    a_fore, ff, _, df = (pipe._dispatch_choose(
        state, FORESIGHT_BLOCK.format(base_action=a_base, prediction=pred["wm_prediction"]))
        if pred["wm_prediction"] else (a_base, fb, 0, {"raw_response": None}))
    a_re, fr, _, dr = pipe._dispatch_choose(state, RETHINK_BLOCK.format(base_action=a_base))
    set_meter(None)
    decision_cost = m.total

    b0 = branch(pipe, split, p, a_base, max_steps, hist_len)
    b0r = branch(pipe, split, p, a_base, max_steps, hist_len)
    bw = b0 if a_fore == a_base else branch(pipe, split, p, a_fore, max_steps, hist_len)
    br = b0 if a_re == a_base else branch(pipe, split, p, a_re, max_steps, hist_len)
    gt = b0["first_next_obs"] or ""
    conf = pred["wm_confidence_logprob"]
    return {
        "point_id": p["point_id"], "replay_ok": True,
        "a_base": a_base, "a_base_matches_log": a_base == p["logged_baseline_action"],
        "a_base_admissible": a_base in admissible, "base_raw": db["raw_response"],
        "wm_prediction": pred["wm_prediction"], "wm_raw": pred["wm_raw_response"],
        "wm_confidence_logprob": conf if conf == conf else None,
        "wm_confidence_self_report": pred["wm_confidence_self_report"],
        "gt_next_obs": gt,
        "pred_em": exact_match(pred["wm_prediction"] or "", gt),
        "pred_f1": token_f1(pred["wm_prediction"] or "", gt),
        "a_fore": a_fore, "fore_raw": df["raw_response"], "fore_changed": a_fore != a_base,
        "a_fore_admissible": a_fore in admissible,
        "a_re": a_re, "re_raw": dr["raw_response"], "re_changed": a_re != a_base,
        "a_re_admissible": a_re in admissible,
        "Y0": b0["success"], "Y0r": b0r["success"], "YW": bw["success"], "YR": br["success"],
        "U_W": int(bw["success"]) - int(b0["success"]),
        "U_R": int(br["success"]) - int(b0["success"]),
        "U_noise": int(b0r["success"]) - int(b0["success"]),
        "b0_actions_equal_b0r": b0["actions"] == b0r["actions"],
        "branches": {"B0": b0, "B0r": b0r, "BW": None if bw is b0 else bw,
                     "BR": None if br is b0 else br},
        "decision_cost": decision_cost, "wall_s": time.time() - t0,
    }


def main(a):
    config = load_yaml_config(a.config)
    db_cfg = {**config.get("direction_b", {}), "reasoning_mode": "react"}
    hist_len = config["sampling"].get("history_length", 50)
    sd = stage_dir(3)
    points = [json.loads(l) for l in open(sd / "raw" / "decision_points.jsonl") if l.strip()]
    if a.limit:
        points = points[: a.limit]
    # TextWorld calls are serialised by one in-process lock, so throughput
    # comes from running several processes, each on a shard of the points.
    points = [p for p in points if p["point_id"] % a.n_shards == a.shard]
    out = sd / "raw" / (a.out if a.n_shards == 1 else a.out.replace(".jsonl", f".shard{a.shard}.jsonl"))
    done = set()
    for f in (sd / "raw").glob(a.out.replace(".jsonl", "*.jsonl")):
        done |= {json.loads(l)["point_id"] for l in open(f) if l.strip()}
    todo = [p for p in points if p["point_id"] not in done]
    pipe = DirectionBPipeline(MeteredLLM(config), db_cfg)
    print(f"[branch] points={len(points)} todo={len(todo)}", flush=True)
    lock = threading.Lock()

    def sink(_i, p, r):
        r.update({k: p[k] for k in ("task_id", "task_type", "t", "stratum", "weight",
                                    "features", "episode_success")})
        with lock, open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ordered_map(lambda p: run_point(pipe, "train", p, a.max_steps, hist_len), todo,
                workers=a.workers, label="branch", progress_every=10, on_result=sink)
    print("[branch] DONE", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    ap.add_argument("--max_steps", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--out", default="branches.jsonl")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n_shards", type=int, default=1)
    main(ap.parse_args())
