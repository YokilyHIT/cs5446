"""Step 0c: paired branching with K continuations per distinct first action.

Fixes the two measurement problems of stage 3:
  * binary single-rollout utility is drowned by serving noise  -> K rollouts
    per first action give P_hat(success) and mean progress;
  * most sampled states were hopeless (Y0 = 5.5%)              -> points are
    drawn mostly from tasks the agent solves at least sometimes.

At each decision point (replayed exactly), the first action of every
intervention is computed once:
    base      a_base                         (planner, no extra block)
    wm        a after FORESIGHT_BLOCK(WM prediction of a_base)
    oracle    a after FORESIGHT_BLOCK(true next observation of a_base)
    rethink   a after RETHINK_BLOCK
    loophint  a after LOOP_HINT_BLOCK (computed unconditionally here)
Interventions with the same first action share continuations, so a no-op
intervention has U = 0 exactly. Each distinct first action gets K
continuations under the `none` policy to max_steps.

    U_X      = P_hat(a_X) - P_hat(a_base)          (success)
    U_X^PR   = mean PR(a_X) - mean PR(a_base)      (AgentBoard progress)
    U_X^PR5  = same, progress measured only 5 steps after the decision
    A/A      = P_hat(first half of base rollouts) - P_hat(second half)
"""
from __future__ import annotations

import argparse
import json
import threading
import time

from preexperiments.common.alfworld_runner import extract_admissible, format_history, visible_actions
from preexperiments.common.logging_utils import load_yaml_config
from preexperiments.common.parallel import ordered_map
from preexperiments.direction_b.metrics import exact_match, token_f1
from preexperiments.direction_b.pipeline import FORESIGHT_BLOCK
from preexperiments.react_study.agent import (LOOP_HINT_BLOCK, RETHINK_BLOCK, replay, run_policy,
                                              shadow_next_obs)
from preexperiments.react_study.common import Meter, MeteredLLM, set_meter, set_role, stage_dir
from preexperiments.react_study.progress import progress_rate
from preexperiments.react_study.protocol_v2 import PipelineV2, history_v2, init_room_obs


def continuation(pipe, split, p, first_action, max_steps, hist_len, horizon=5):
    env, obs, info, history, done, init_obs = replay(split, p["gamefile"], p["prefix"])
    m = Meter()
    r = run_policy(pipe, env, obs, info, goal=p["goal"], task_id=p["task_id"], history=history,
                   start_step=p["t"], max_steps=max_steps, arm="none", tau=0, p_gate=0, gate_seed=0,
                   history_length=hist_len, meter=m, first_action=first_action,
                   init_obs=init_obs, task_type=p["task_type"], split=split, gamefile=p["gamefile"])
    prev_obs = [o for _, o in history]
    new_obs = [s["next_observation"] for s in r["steps"]]
    return {"success": r["success"], "n_steps": len(r["steps"]),
            "pr": progress_rate(p["gamefile"], prev_obs + new_obs, r["success"]),
            "pr_h5": progress_rate(p["gamefile"], prev_obs + new_obs[:horizon],
                                   r["success"] and len(new_obs) <= horizon),
            "actions": [s["action"] for s in r["steps"]],
            "tokens": sum(e["prompt_tokens"] + e["completion_tokens"] for e in m.total.values())}


def run_point(pipe, split, p, K, max_steps, hist_len):
    t0 = time.time()
    env, obs, info, history, done, init_obs = replay(split, p["gamefile"], p["prefix"])
    if obs != p["observation"] or done:
        return {"point_id": p["point_id"], "replay_ok": False}
    adm = visible_actions(extract_admissible(info))
    state = {"goal": p["goal"], "task_type": p["task_type"],
             "history": format_history(history, max_turns=hist_len),
             "history_v2": history_v2(init_room_obs(init_obs), history),
             "current_observation": obs, "admissible_actions": adm}
    m = Meter()
    set_meter(m)
    set_role("planner_base")
    a_base, _f, _t, d0 = pipe._dispatch_choose(state, "")
    set_role("wm")
    pred = pipe.predict(state, a_base)
    gt = shadow_next_obs(split, p["gamefile"], p["prefix"], a_base)
    set_role("planner_second")
    first, raws = {"base": a_base}, {"base": d0["raw_response"]}
    blocks = {
        "wm": FORESIGHT_BLOCK.format(base_action=a_base, prediction=pred["wm_prediction"])
        if pred["wm_prediction"] else None,
        "oracle": FORESIGHT_BLOCK.format(base_action=a_base, prediction=gt),
        "rethink": RETHINK_BLOCK.format(base_action=a_base),
        "loophint": LOOP_HINT_BLOCK.format(
            base_action=a_base, n_repeat=sum(1 for a, _ in history if a == a_base),
            n_nothing=sum(1 for _, o in history[-5:] if "Nothing happens" in o)),
    }
    for k, b in blocks.items():
        if b is None:
            first[k], raws[k] = a_base, None
            continue
        a, _f, _t, d = pipe._dispatch_choose(state, b)
        first[k], raws[k] = a, d["raw_response"]
    set_meter(None)

    conts = {}
    for a in dict.fromkeys(first.values()):
        conts[a] = [continuation(pipe, split, p, a, max_steps, hist_len) for _ in range(K)]

    def stat(a, key):
        xs = [c[key] for c in conts[a]]
        return sum(xs) / len(xs)

    out = {"point_id": p["point_id"], "replay_ok": True, "K": K,
           "first_actions": first, "raws": raws,
           "first_admissible": {k: (v in adm or v == "check valid actions") for k, v in first.items()},
           "wm_prediction": pred["wm_prediction"], "gt_next_obs": gt,
           "wm_confidence_logprob": pred["wm_confidence_logprob"]
           if pred["wm_confidence_logprob"] == pred["wm_confidence_logprob"] else None,
           "pred_em": exact_match(pred["wm_prediction"] or "", gt),
           "pred_f1": token_f1(pred["wm_prediction"] or "", gt),
           "a_base_matches_log": a_base == p["logged_baseline_action"],
           "decision_cost": m.total, "wall_s": None}
    for key in ("success", "pr", "pr_h5"):
        out[f"P_{key}"] = {k: stat(a, key) for k, a in first.items()}
        out[f"U_{key}"] = {k: stat(a, key) - stat(a_base, key) for k, a in first.items() if k != "base"}
    base = conts[a_base]
    h = K // 2
    out["AA_success"] = (sum(c["success"] for c in base[:h]) / h) - (sum(c["success"] for c in base[h:2 * h]) / h)
    out["AA_pr"] = (sum(c["pr"] for c in base[:h]) / h) - (sum(c["pr"] for c in base[h:2 * h]) / h)
    out["continuations"] = {a: [{k: c[k] for k in ("success", "n_steps", "pr", "pr_h5", "tokens", "actions")}
                                for c in cs] for a, cs in conts.items()}
    out["wall_s"] = time.time() - t0
    return out


def main(a):
    config = load_yaml_config(a.config)
    db_cfg = config.get("direction_b", {})
    hist_len = config["sampling"].get("history_length", 50)
    sd = stage_dir(a.stage)
    points = [json.loads(l) for l in open(sd / "raw" / a.points) if l.strip()]
    points = [p for p in points if p["point_id"] % a.n_shards == a.shard]
    out = sd / "raw" / a.out.replace(".jsonl", f".shard{a.shard}.jsonl")
    done = set()
    for f in (sd / "raw").glob(a.out.replace(".jsonl", ".shard*.jsonl")):
        done |= {json.loads(l)["point_id"] for l in open(f) if l.strip()}
    todo = [p for p in points if p["point_id"] not in done]
    pipe = PipelineV2(MeteredLLM(config), db_cfg, variant=a.variant)
    print(f"[branch_k] shard {a.shard}/{a.n_shards} points={len(points)} todo={len(todo)} K={a.K}", flush=True)
    lock = threading.Lock()

    def sink(_i, p, r):
        r.update({k: p.get(k) for k in ("task_id", "task_type", "t", "stratum", "weight", "features",
                                         "task_solve_rate")})
        with lock, open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ordered_map(lambda p: run_point(pipe, a.split, p, a.K, a.max_steps, hist_len), todo,
                workers=a.workers, label=f"branch_k{a.shard}", progress_every=5, on_result=sink)
    print("[branch_k] DONE", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    ap.add_argument("--stage", type=int, default=10)
    ap.add_argument("--split", default="train")
    ap.add_argument("--points", default="branch_points.jsonl")
    ap.add_argument("--out", default="branch_k.jsonl")
    ap.add_argument("--variant", default="query")
    ap.add_argument("--K", type=int, default=8)
    ap.add_argument("--max_steps", type=int, default=30)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n_shards", type=int, default=1)
    main(ap.parse_args())
