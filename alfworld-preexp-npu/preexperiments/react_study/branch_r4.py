"""Round 4 / Phase 2: same-state paired labels for keep (0) / resample (R) / foresight (W).

Extends step-0c `branch_k.py` (unchanged, still reproduces round 2). At each replayed
decision point the FIRST action of every intervention is computed once:

    base           a_base                                   (planner, no block) -> V_0
    R0             same prompt, same decoding (T=0) again   (serving nondeterminism only)
    RT             same prompt, T=0.7, seed = _seed(task, t, 1)    -> V_R  (main R)
    W4             FORESIGHT_BLOCK(prediction of a_base by role "wm")      (Qwen3-4B WM)
    W14            FORESIGHT_BLOCK(prediction of a_base by role "wm_alt")  (Qwen3-14B WM)
    oracle         FORESIGHT_BLOCK(true next observation of a_base)        (diagnostic)
    oracle_struct  ORACLE_STRUCT_BLOCK(effect / progress verdict from the true obs)
                   (Plan-C probe: is a structured verdict more usable than raw text?)

The planner (4B or 14B) is whatever PREEXP_PLANNER_* routes to (unset = 4B); continuations
follow the WM-free `none` policy of that same planner (pi_m^0). Distinct first actions share
K continuations, so identical interventions have exactly equal value.

Reuse (`--prior`): for a 4B planner the round-2 step-0c rows already hold a_base, the 4B-WM
foresight action ("wm"), the oracle action and K=8 continuations per distinct action, all
produced by the same code path; they are reused verbatim and only new actions are rolled out.

Generation noise (`--regen N`, applied to points with point_id % regen_mod == 0): RT is redrawn
with seeds 2..N+1 and W4/W14 are recomputed N more times (WM prediction + foresight pass), each
as an extra key "RT#j" / "W4#j" / "W14#j" with its own continuations.

    $PY -m preexperiments.react_study.branch_r4 --points <file> --out <name>.jsonl \
        --prior 'outputs/react_study/step0_protocol_v2_measurement/raw/branch_k.shard*.jsonl'
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from preexperiments.common.alfworld_runner import extract_admissible, format_history, visible_actions
from preexperiments.common.logging_utils import load_yaml_config
from preexperiments.common.parallel import ordered_map
from preexperiments.direction_b.metrics import exact_match, token_f1
from preexperiments.direction_b.pipeline import FORESIGHT_BLOCK
from preexperiments.react_study.agent import RT_TEMPERATURE, _seed, replay, shadow_next_obs
from preexperiments.react_study.branch_k import continuation
from preexperiments.react_study.common import Meter, MeteredLLM, ROOT, set_meter, set_role, stage_dir
from preexperiments.react_study.progress import progress_rate
from preexperiments.react_study.protocol_v2 import PipelineV2, history_v2, init_room_obs

ORACLE_STRUCT_BLOCK = """
An environment check of the candidate action "{base_action}" says: {verdict}

This has NOT happened yet. You are still at the current state described above.
"""

ALL_ARMS = ("base", "R0", "RT", "W4", "W14", "oracle", "oracle_struct")
WM_ROLE_OF = {"W4": "wm", "W14": "wm_alt"}


def struct_verdict(gamefile, prev_obs, gt):
    if "nothing happens" in gt.lower():
        return 'it would have no effect ("Nothing happens.").'
    if progress_rate(gamefile, prev_obs + [gt], False) > progress_rate(gamefile, prev_obs, False):
        return "it would succeed and complete a part of the task."
    return "it would succeed (the state would change), but it would not yet complete any part of the task."


def load_prior(pattern):
    prior = {}
    for f in sorted(glob.glob(pattern)) if pattern else []:
        for l in open(f):
            if l.strip():
                r = json.loads(l)
                if r.get("replay_ok"):
                    prior[r["point_id"]] = r
    return prior


def run_point(pipe, split, p, a):
    t0 = time.time()
    env, obs, info, history, done, init_obs = replay(split, p["gamefile"], p["prefix"])
    if obs != p["observation"] or done:
        return {"point_id": p["point_id"], "replay_ok": False}
    adm = visible_actions(extract_admissible(info))
    state = {"goal": p["goal"], "task_type": p["task_type"],
             "history": format_history(history, max_turns=a.hist_len),
             "history_v2": history_v2(init_room_obs(init_obs), history),
             "current_observation": obs, "admissible_actions": adm}
    prev_obs = [o for _, o in history]
    pr = a.prior_rows.get(p["point_id"]) if a.prior_rows else None
    arms = a.arm_list
    m = Meter()
    set_meter(m)
    first, raws, preds = {}, {}, {}
    base_lp = None
    if pr is not None:
        first["base"], raws["base"] = pr["first_actions"]["base"], pr["raws"].get("base")
        base_lp = None
    else:
        set_role("planner_base")
        first["base"], _f, _t, d0 = pipe._dispatch_choose(state, "")
        raws["base"], base_lp = d0["raw_response"], d0.get("action_lp")
    a_base = first["base"]
    gt = shadow_next_obs(split, p["gamefile"], p["prefix"], a_base)

    def foresight(block):
        set_role("planner_second")
        act, _f, _t, d = pipe._dispatch_choose(state, block)
        return act, d["raw_response"]

    def wm_arm(key, role):
        set_role(role)
        pred = pipe.predict(state, a_base)
        preds[key] = {"prediction": pred["wm_prediction"],
                      "confidence_logprob": pred["wm_confidence_logprob"]
                      if pred["wm_confidence_logprob"] == pred["wm_confidence_logprob"] else None,
                      "em": exact_match(pred["wm_prediction"] or "", gt),
                      "f1": token_f1(pred["wm_prediction"] or "", gt)}
        if not pred["wm_prediction"]:
            return a_base, None
        return foresight(FORESIGHT_BLOCK.format(base_action=a_base, prediction=pred["wm_prediction"]))

    for k in arms:
        if k == "base":
            continue
        if pr is not None and k == "W4" and "wm" in pr["first_actions"]:
            first[k], raws[k] = pr["first_actions"]["wm"], pr["raws"].get("wm")
            preds[k] = {"prediction": pr.get("wm_prediction"), "confidence_logprob": pr.get("wm_confidence_logprob"),
                        "em": pr.get("pred_em"), "f1": pr.get("pred_f1"), "reused": True}
        elif pr is not None and k == "oracle" and "oracle" in pr["first_actions"]:
            first[k], raws[k] = pr["first_actions"]["oracle"], pr["raws"].get("oracle")
        elif k == "R0":
            set_role("planner_second")
            act, _f, _t, d = pipe._dispatch_choose(state, "")
            first[k], raws[k] = act, d["raw_response"]
        elif k == "RT":
            set_role("planner_second")
            first[k], _f, raws[k] = pipe.sample_action(state, "", RT_TEMPERATURE, _seed(p["task_id"], p["t"], 1))
        elif k in WM_ROLE_OF:
            first[k], raws[k] = wm_arm(k, WM_ROLE_OF[k])
        elif k == "oracle":
            first[k], raws[k] = foresight(FORESIGHT_BLOCK.format(base_action=a_base, prediction=gt))
        elif k == "oracle_struct":
            v = struct_verdict(p["gamefile"], prev_obs, gt)
            first[k], raws[k] = foresight(ORACLE_STRUCT_BLOCK.format(base_action=a_base, verdict=v))
            preds[k] = {"verdict": v}
        else:
            raise ValueError(k)
    regen = a.regen and p["point_id"] % a.regen_mod == 0
    if regen:
        for j in range(1, a.regen + 1):
            if "RT" in arms:
                set_role("planner_second")
                first[f"RT#{j}"], _f, raws[f"RT#{j}"] = pipe.sample_action(
                    state, "", RT_TEMPERATURE, _seed(p["task_id"], p["t"], 1 + j))
            for k in ("W4", "W14"):
                if k in arms:
                    first[f"{k}#{j}"], raws[f"{k}#{j}"] = wm_arm(f"{k}#{j}", WM_ROLE_OF[k])
    set_meter(None)

    conts = {}
    if pr is not None:
        for act, cs in pr["continuations"].items():
            if len(cs) >= a.K:
                conts[act] = cs[:a.K]
    todo = [x for x in dict.fromkeys(first.values()) if x not in conts]
    jobs = [(x, i) for x in todo for i in range(a.K)]

    def one(job):
        c = continuation(pipe, split, p, job[0], a.max_steps, a.hist_len)
        return job[0], {k: c[k] for k in ("success", "n_steps", "pr", "pr_h5", "tokens", "actions")}
    # one long-lived pool (threads cache their own AlfredTWEnv wrapper; a pool per point would rebuild them)
    for act, c in a.pool.map(one, jobs):
        conts.setdefault(act, []).append(c)

    def stat(x, key):
        xs = [c[key] for c in conts[x]]
        return sum(xs) / len(xs)

    out = {"point_id": p["point_id"], "replay_ok": True, "K": a.K, "regen": bool(regen),
           "first_actions": first, "raws": raws, "predictions": preds, "gt_next_obs": gt,
           "base_action_lp": base_lp,
           "first_admissible": {k: (v in adm or v == "check valid actions") for k, v in first.items()},
           "reused_prior": pr is not None, "n_new_actions": len(todo),
           "decision_cost": m.total}
    for key in ("success", "pr", "pr_h5"):
        out[f"P_{key}"] = {k: stat(x, key) for k, x in first.items()}
    out["continuations"] = conts
    out["wall_s"] = time.time() - t0
    return out


def main(a):
    config = load_yaml_config(a.config)
    db_cfg = config.get("direction_b", {})
    a.hist_len = config["sampling"].get("history_length", 50)
    a.arm_list = [x for x in a.arms.split(",") if x]
    assert a.arm_list[0] == "base" and set(a.arm_list) <= set(ALL_ARMS), a.arm_list
    sd = stage_dir(a.stage)
    pts_path = Path(a.points) if os.path.isabs(a.points) or Path(a.points).exists() else sd / "raw" / a.points
    points = [json.loads(l) for l in open(pts_path) if l.strip()]
    if a.only_ids:
        keep = {int(x) for x in Path(a.only_ids).read_text().split()}
        points = [p for p in points if p["point_id"] in keep]
    points = [p for p in points if p["point_id"] % a.n_shards == a.shard]
    if a.prior and os.environ.get("PREEXP_PLANNER_BASES", "").strip():
        raise SystemExit("--prior rows were produced by the 4B planner; do not reuse them with another planner")
    a.prior_rows = load_prior(str(ROOT / a.prior)) if a.prior else {}
    a.pool = ThreadPoolExecutor(max_workers=a.cont_workers * a.workers)
    out = sd / "raw" / a.out.replace(".jsonl", f".shard{a.shard}.jsonl")
    done = set()
    for f in (sd / "raw").glob(a.out.replace(".jsonl", ".shard*.jsonl")):
        done |= {json.loads(l)["point_id"] for l in open(f) if l.strip()}
    todo = [p for p in points if p["point_id"] not in done]
    pipe = PipelineV2(MeteredLLM(config), db_cfg, variant=a.variant)
    cfg = {k: v for k, v in vars(a).items() if k not in ("prior_rows", "pool")}
    cfg["env"] = {k: os.environ.get(k, "") for k in ("PREEXP_API_BASES", "PREEXP_PLANNER_MODEL", "PREEXP_PLANNER_BASES",
                                                    "PREEXP_WM_ALT_MODEL", "PREEXP_WM_ALT_BASES")}
    (sd / "raw" / a.out.replace(".jsonl", f".shard{a.shard}.config.json")).write_text(json.dumps(cfg, indent=2))
    print(f"[branch_r4] shard {a.shard}/{a.n_shards} points={len(points)} todo={len(todo)} K={a.K} "
          f"arms={a.arm_list} prior={len(a.prior_rows)}", flush=True)
    lock = threading.Lock()

    def sink(_i, p, r):
        r.update({k: p.get(k) for k in ("task_id", "task_type", "t", "group", "stratum", "features",
                                         "task_solve_rate", "gamefile", "unbiased_group")})
        with lock, open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ordered_map(lambda p: run_point(pipe, a.split, p, a), todo,
                workers=a.workers, label=f"branch_r4/{a.shard}", progress_every=2, on_result=sink)
    print("[branch_r4] DONE", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    ap.add_argument("--stage", type=int, default=32)
    ap.add_argument("--split", default="train")
    ap.add_argument("--points", required=True)
    ap.add_argument("--only_ids", default="", help="file with point_ids to keep (e.g. unbiased subset)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--prior", default="", help="glob (repo-relative) of round-2 branch_k rows to reuse (4B only)")
    ap.add_argument("--arms", default=",".join(ALL_ARMS))
    ap.add_argument("--variant", default="list")
    ap.add_argument("--K", type=int, default=8)
    ap.add_argument("--max_steps", type=int, default=30)
    ap.add_argument("--regen", type=int, default=0)
    ap.add_argument("--regen_mod", type=int, default=4)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--cont_workers", type=int, default=4)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n_shards", type=int, default=1)
    main(ap.parse_args())
