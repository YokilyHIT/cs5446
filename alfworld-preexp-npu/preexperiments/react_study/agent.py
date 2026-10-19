"""ReAct agent loop with six decision arms and per-step cost logging.

Arms (all share the same ReAct planner, WM, prompts, parser and step budget):

    none         a_base every step
    rethink      a_base, then a second ReAct pass shown only "you proposed
                 a_base, reconsider" -- same prompt shape as foresight minus
                 the prediction. Controls for "one more reasoning call".
    always       WM predicts o_{t+1} for a_base; second pass with prediction
    selective    WM always called; prediction used iff C_logprob > tau
                 (post-hoc confidence filter, WorldEvolver style)
    random_post  WM always called; prediction used iff u_t < p
                 (post-hoc random filter: same generation cost as selective)
    random_pre   iff u_t < p, call WM and use the prediction; otherwise no WM
                 call at all (pre-call random gate: saves WM cost)

u_t = gate_uniform(gate_seed, task_id, step) -- deterministic, so random_pre
and random_post draw the same u_t at the same (task, step).

`run_policy` is reusable from an arbitrary mid-episode state (stage 3
branches), so the stage-2 episodes and stage-3 continuations are produced by
literally the same code path.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from preexperiments.common.alfworld_runner import (
    _ENV_LOCK,
    _import_alfred_tw_env,
    _load_alfworld_config,
    extract_admissible,
    extract_task_id,
    extract_won,
    format_history,
    visible_actions,
)
from preexperiments.direction_b.pipeline import FORESIGHT_BLOCK, DirectionBPipeline
from preexperiments.failure_selection._common import extract_goal, extract_task_type
from preexperiments.react_study.common import Meter, gate_uniform, set_meter, set_role, sum_costs
from preexperiments.react_study.protocol_v2 import CHECK_VALID, history_v2, init_room_obs

import threading

ARMS = ("none", "rethink", "always", "selective", "random_post", "random_pre", "oracle", "loop_hint",
        "gate_stuck", "gate_learned")

# Same layout as FORESIGHT_BLOCK, prediction removed. Keeps the second pass's
# prompt length/shape close to the foresight pass so "rethink" isolates the
# value of the prediction's CONTENT from the value of a second ReAct call.
RETHINK_BLOCK = """
You previously proposed executing "{base_action}" in this state.
Before committing, reconsider whether it is the best next action.

You are still at the current state described above.
"""

# loop_hint (step 1b): a WM-free loop breaker. Fires only when the cheap,
# agent-visible stuck rule fires (same rule as stage-3 `stuck` stratum, applied
# to the candidate a_base), then asks the planner again with this note.
LOOP_HINT_BLOCK = """
Note: you have already executed "{base_action}" {n_repeat} time(s) in this episode, and
{n_nothing} of your last 5 actions produced "Nothing happens.". Repeating an action that
gave no new information is unlikely to help. Reconsider before committing.

You are still at the current state described above.
"""

_TLS = threading.local()


def _wrapper(split: str):
    w = getattr(_TLS, "wrapper", None)
    if w is None or getattr(_TLS, "split", None) != split:
        AlfredTWEnv = _import_alfred_tw_env()
        with _ENV_LOCK:
            w = AlfredTWEnv(copy.deepcopy(_load_alfworld_config()), train_eval=split)
        _TLS.wrapper, _TLS.split = w, split
    return w


def list_games(split: str) -> List[str]:
    AlfredTWEnv = _import_alfred_tw_env()
    with _ENV_LOCK:
        w0 = AlfredTWEnv(copy.deepcopy(_load_alfworld_config()), train_eval=split)
    return sorted(w0.game_files)


def make_env(split: str, gamefile: str):
    w = _wrapper(split)
    with _ENV_LOCK:
        w.game_files = [gamefile]
        if hasattr(w, "num_games"):
            w.num_games = 1
        env = w.init_env(batch_size=1)
        obs, info = env.reset()
    return env, obs[0], info


def env_step(env, action: str) -> Tuple[str, bool, Dict[str, Any]]:
    with _ENV_LOCK:
        nxt, _, dones, info = env.step([action])
    return nxt[0], bool(dones[0]), info


def replay(split: str, gamefile: str, prefix: List[str]):
    """Fresh env, replay `prefix` verbatim. Returns env, obs, info, history, done."""
    env, obs, info = make_env(split, gamefile)
    init_obs = obs
    history: List[Tuple[str, str]] = []
    done = False
    for a in prefix:
        obs, done, info = pseudo_or_env_step(env, a, visible_actions(extract_admissible(info)), info)
        history.append((a, obs))
        if done:
            break
    return env, obs, info, history, done, init_obs


def shadow_next_obs(split: str, gamefile: str, prefix: List[str], action: str) -> str:
    """True o_{t+1} of `action` at the state reached by `prefix` (fresh env + replay)."""
    env, obs, info, _h, done, _i = replay(split, gamefile, prefix)
    if done:
        return obs
    nxt, _d, _info = pseudo_or_env_step(env, action, visible_actions(extract_admissible(info)), info)
    return nxt


def pseudo_or_env_step(env, action: str, admissible: List[str], info):
    """`check valid actions` (protocol v2) answers from the admissible list and
    does not step the env; everything else is a real env step."""
    if action == CHECK_VALID:
        return "Choose an action from these valid actions: " + ", ".join(admissible), False, info
    return env_step(env, action)


def decide(pipe: DirectionBPipeline, state: Dict[str, Any], arm: str, *,
           task_id: str, step: int, tau: float, p_gate: float, gate_seed: int,
           second_call_when_closed: bool = False, gt_fn=None,
           recent: Optional[List[Tuple[str, str]]] = None, memory=None) -> Dict[str, Any]:
    """One decision under `arm`. Pure w.r.t. the env (does not step it);
    `gt_fn(a)` (oracle arm only) returns the true next observation of `a`
    from a shadow env."""
    set_role("planner_base")
    a_base, forced, _tok, diag = pipe._dispatch_choose(state, "")
    rec: Dict[str, Any] = {
        "baseline_action": a_base, "base_forced": bool(forced), "base_raw": diag["raw_response"],
        "action": a_base, "action_forced": bool(forced),
        "wm_called": False, "foresight_used": False, "rethink_used": False,
        "wm_prediction": None, "wm_confidence_logprob": None, "gate_u": None,
        "second_action": None, "second_raw": None,
    }
    if arm == "none":
        return rec

    if arm == "rethink":
        set_role("planner_second")
        a2, f2, _t, d2 = pipe._dispatch_choose(state, RETHINK_BLOCK.format(base_action=a_base))
        rec.update(action=a2, action_forced=bool(f2), second_action=a2,
                   second_raw=d2["raw_response"], rethink_used=True)
        return rec

    if arm == "loop_hint":
        recent = recent or []
        n_rep = sum(1 for a, _ in recent if a == a_base)
        n_noth = sum(1 for _, o in recent[-5:] if "Nothing happens" in o)
        rec.update(loop_detected=bool(n_rep >= 2 or n_noth >= 2))
        if rec["loop_detected"]:
            set_role("planner_second")
            a2, f2, _t, d2 = pipe._dispatch_choose(state, LOOP_HINT_BLOCK.format(
                base_action=a_base, n_repeat=n_rep, n_nothing=n_noth))
            rec.update(action=a2, action_forced=bool(f2), second_action=a2,
                       second_raw=d2["raw_response"], rethink_used=True)
        return rec

    if arm == "oracle":
        gt = gt_fn(a_base)
        rec.update(wm_prediction=gt, oracle=True)
        set_role("planner_second")
        block = FORESIGHT_BLOCK.format(base_action=a_base, prediction=gt)
        a2, f2, _t, d2 = pipe._dispatch_choose(state, block)
        rec.update(action=a2, action_forced=bool(f2), second_action=a2,
                   second_raw=d2["raw_response"], foresight_used=True)
        return rec

    u = gate_uniform(gate_seed, task_id, step)
    rec["gate_u"] = u
    if arm == "random_pre" and not (u < p_gate):
        return _closed(pipe, state, rec, second_call_when_closed)  # closed before any WM call
    if arm in ("gate_stuck", "gate_learned"):  # step 3 pre-call gates (agent-visible features only)
        from preexperiments.react_study.gate import is_stuck, learned_open
        g = (is_stuck(recent or [], a_base) if arm == "gate_stuck"
             else learned_open(recent or [], a_base, state["admissible_actions"], step))
        rec["gate_open"] = bool(g)
        if not g:
            return _closed(pipe, state, rec, second_call_when_closed)

    set_role("wm")
    block = memory.render(a_base) if memory is not None else ""
    pred = pipe.predict(state, a_base, memory_block=block)
    rec["wm_memory_hits"] = block.count("Transition ") if block else 0
    conf = pred["wm_confidence_logprob"]
    rec.update(wm_called=True, wm_prediction=pred["wm_prediction"],
               wm_confidence_logprob=(conf if conf == conf else None))
    if not pred["wm_prediction"]:
        return _closed(pipe, state, rec, second_call_when_closed)
    if arm in ("always", "random_pre", "gate_stuck", "gate_learned"):
        use = True
    elif arm == "selective":
        use = conf == conf and conf > tau
    elif arm == "random_post":
        use = u < p_gate
    else:
        raise ValueError(arm)
    if use:
        set_role("planner_second")
        block = FORESIGHT_BLOCK.format(base_action=a_base, prediction=pred["wm_prediction"])
        a2, f2, _t, d2 = pipe._dispatch_choose(state, block)
        rec.update(action=a2, action_forced=bool(f2), second_action=a2,
                   second_raw=d2["raw_response"], foresight_used=True)
        return rec
    return _closed(pipe, state, rec, second_call_when_closed)


def _closed(pipe, state, rec, second_call_when_closed):
    """Gate closed. WorldEvolver (Alg. 1) still re-samples a^(1) ~ pi(.|s_t, F_t=empty),
    i.e. a second planner call with no foresight; v1 simply keeps a_base."""
    if second_call_when_closed:
        set_role("planner_second")
        a2, f2, _t, d2 = pipe._dispatch_choose(state, "")
        rec.update(action=a2, action_forced=bool(f2), second_action=a2,
                   second_raw=d2["raw_response"], closed_second_call=True)
    return rec


def run_policy(pipe: DirectionBPipeline, env, obs: str, info: Dict[str, Any], *,
               goal: str, task_id: str, history: List[Tuple[str, str]], start_step: int,
               max_steps: int, arm: str, tau: float, p_gate: float, gate_seed: int,
               history_length: int, meter: Meter, record_state: bool = False,
               first_action: Optional[str] = None, init_obs: str = "", task_type: str = "",
               second_call_when_closed: bool = False, split: str = "",
               gamefile: str = "", memory=None) -> Dict[str, Any]:
    """Run `arm` from the given env state until done or step == max_steps.

    `first_action`, if given, is executed at start_step instead of asking the
    policy (stage-3 branches whose first action was already decided)."""
    steps: List[Dict[str, Any]] = []
    done = success = False
    history = list(history)
    set_meter(meter)
    # oracle arm: an incrementally-synced shadow env. gt_fn steps it with
    # a_base; if the executed action is also a_base the shadow is already at
    # s_{t+1}, otherwise it is rebuilt by replay on the next query. Equivalent
    # to a fresh replay per step, minus the O(T^2) env cost.
    shadow = {"env": None, "info": None, "pos": None}

    def gt_fn_inc(a, prefix):
        if shadow["env"] is None or shadow["pos"] != tuple(prefix):
            e, _o, inf, _h, d, _i = replay(split, gamefile, list(prefix))
            if d:
                shadow["env"] = None
                return _o
            shadow.update(env=e, info=inf, pos=tuple(prefix))
        nxt, _d, inf = pseudo_or_env_step(shadow["env"], a, visible_actions(extract_admissible(shadow["info"])),
                                          shadow["info"])
        shadow.update(info=inf, pos=tuple(prefix) + (a,))
        if _d:
            shadow["env"] = None
        return nxt
    for step in range(start_step, max_steps):
        admissible = visible_actions(extract_admissible(info))
        if not admissible:
            break
        state = {"goal": goal, "task_type": task_type,
                 "history": format_history(history, max_turns=history_length),
                 "history_v2": history_v2(init_room_obs(init_obs), history),
                 "current_observation": obs, "admissible_actions": admissible}
        if first_action is not None and step == start_step:
            rec = {"action": first_action, "injected": True}
        else:
            prefix = [a for a, _ in history]
            gt_fn = (lambda a, _p=prefix: gt_fn_inc(a, _p)) if arm == "oracle" else None
            rec = decide(pipe, state, arm, task_id=task_id, step=step,
                         tau=tau, p_gate=p_gate, gate_seed=gate_seed,
                         second_call_when_closed=second_call_when_closed,
                         gt_fn=gt_fn, recent=history, memory=memory)
        next_obs, done, info = pseudo_or_env_step(env, rec["action"], admissible, info)
        success = extract_won(info) if done else False
        if memory is not None and rec["action"] != CHECK_VALID:
            memory.add(obs, rec["action"], next_obs, task_id, step)
        rec.update(step=step, action_admissible=(rec["action"] in admissible or rec["action"] == CHECK_VALID),
                   next_observation=next_obs, cost=meter.pop_step())
        if record_state:
            rec.update(observation=obs, admissible_actions=admissible)
        steps.append(rec)
        history.append((rec["action"], next_obs))
        obs = next_obs
        if done:
            break
    set_meter(None)
    return {"steps": steps, "done": bool(done), "success": bool(success),
            "final_step": (steps[-1]["step"] + 1) if steps else start_step}


def run_episode(pipe: DirectionBPipeline, *, split: str, gamefile: str, arm: str,
                max_steps: int, tau: float, p_gate: float, gate_seed: int,
                history_length: int, record_state: bool = False,
                second_call_when_closed: bool = False, memory=None) -> Dict[str, Any]:
    env, obs, info = make_env(split, gamefile)
    goal = extract_goal(obs, info)
    task_id = extract_task_id(gamefile)
    meter = Meter()
    res = run_policy(pipe, env, obs, info, goal=goal, task_id=task_id, history=[],
                     start_step=0, max_steps=max_steps, arm=arm, tau=tau, p_gate=p_gate,
                     gate_seed=gate_seed, history_length=history_length, meter=meter,
                     record_state=record_state, init_obs=obs, task_type=extract_task_type(gamefile),
                     second_call_when_closed=second_call_when_closed, split=split, gamefile=gamefile,
                     memory=memory)
    steps = res["steps"]
    n = len(steps)
    return {
        "arm": arm, "gamefile": gamefile, "task_id": task_id,
        "task_type": extract_task_type(gamefile), "goal": goal,
        "initial_observation": obs,
        "success": res["success"], "done": res["done"], "steps": n,
        "n_wm_calls": sum(s.get("wm_called", False) for s in steps),
        "n_foresight_used": sum(s.get("foresight_used", False) for s in steps),
        "n_rethink_used": sum(s.get("rethink_used", False) for s in steps),
        "n_action_changed": sum(1 for s in steps if s.get("second_action") is not None
                                and s["second_action"] != s["baseline_action"]),
        "legal_action_rate": (sum(s["action_admissible"] for s in steps) / n) if n else None,
        "cost": meter.total,
        "step_log": steps,
    }
