"""Episode-level reproduction of WorldEvolver's Selective Foresight comparison.

Everything reported for direction two so far has been ACTION-level: does the
chosen action equal the expert's action at a sampled state. That is the quantity
single-step expert labels support, but it is not the quantity WorldEvolver
reports, and the two are not interchangeable -- picking a better next action
does not have to finish more tasks. This script closes that gap by running whole
episodes and measuring what their Table reports: task success rate.

Three arms, run over the SAME games with the SAME planner:

    none        a_base every step                       (No Foresight)
    always      world model on a_base, then a_fore      (Always Foresight)
    selective   a_fore only when C_logprob > tau        (Selective Foresight)

`tau` is NOT tuned here. It is fixed to the value Stage 3 selected on the
train-split state set, and then applied unchanged to these held-out evaluation
episodes -- otherwise "selective beats always" would just be the gate fitting
its own test set.

Evaluation split is `eval_in_distribution` (ALFWorld valid_seen, 140 games);
WorldEvolver evaluates on AgentBoard's 134-task ALFWorld subset. Same benchmark
family and the same 30-step cap, but not literally the same task list, so
absolute numbers are comparable only loosely -- the arm-to-arm DELTA is the
quantity this script exists to produce.

The planner is DirectionBPipeline, i.e. the identical prompt/decoding used for
every action-level number (temperature 0, top_p 0.5, guided_choice over the
admissible set). It deliberately is NOT the `adamem_think` ReAct planner
experiments A/B used at temperature 0.7: mixing the two would make the episode
numbers incomparable with the action-level ones they are meant to explain.

Parallelism: each worker thread owns its own AlfredTWEnv wrapper, so no thread
mutates another's `game_files`; the global _ENV_LOCK still serialises the
TextWorld calls themselves, which are not thread-safe.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import threading
import time
from pathlib import Path
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
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config
from preexperiments.common.parallel import add_workers_arg, ordered_map
from preexperiments.direction_b.episodic_memory import EpisodicMemory
from preexperiments.direction_b.pipeline import DirectionBPipeline
from preexperiments.failure_selection._common import extract_goal, extract_task_type

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_TAB = ROOT / "outputs" / "tables"

ARMS = ("none", "always", "selective")

# One AlfredTWEnv wrapper per worker thread (see module docstring).
_TLS = threading.local()


def _wrapper(split: str):
    w = getattr(_TLS, "wrapper", None)
    if w is None or getattr(_TLS, "split", None) != split:
        AlfredTWEnv = _import_alfred_tw_env()
        with _ENV_LOCK:
            w = AlfredTWEnv(copy.deepcopy(_load_alfworld_config()), train_eval=split)
        _TLS.wrapper, _TLS.split = w, split
    return w


def _make_env(split: str, gamefile: str):
    w = _wrapper(split)
    with _ENV_LOCK:
        w.game_files = [gamefile]
        if hasattr(w, "num_games"):
            w.num_games = 1
        env = w.init_env(batch_size=1)
        obs, info = env.reset()
    return env, obs[0], info


def run_episode(
    pipe: DirectionBPipeline,
    memory: Optional[EpisodicMemory],
    *,
    arm: str,
    split: str,
    gamefile: str,
    max_steps: int,
    tau: float,
    history_length: int,
) -> Dict[str, Any]:
    env, obs, info = _make_env(split, gamefile)
    goal = extract_goal(obs, info)

    history: List[Tuple[str, str]] = []
    steps: List[Dict[str, Any]] = []
    done = success = False
    n_foresight = n_wm = 0

    for step in range(max_steps):
        admissible = visible_actions(extract_admissible(info))
        if not admissible:
            break
        state = {
            "goal": goal,
            "history": format_history(history, max_turns=history_length),
            "current_observation": obs,
            "admissible_actions": admissible,
        }

        a_base, forced, _ = pipe.baseline_action(state)
        action, conf, used = a_base, float("nan"), False

        if arm != "none":
            block = memory.render(a_base) if memory is not None else ""
            pred = pipe.predict(state, a_base, memory_block=block)
            n_wm += 1
            conf = pred["wm_confidence_logprob"]
            if pred["wm_prediction"]:
                # `always` uses foresight unconditionally; `selective` only when
                # the world model is confident. A NaN confidence (parse failure)
                # must not pass the gate, hence the explicit `conf == conf`.
                used = arm == "always" or (conf == conf and conf > tau)
                if used:
                    a_fore, f2, _ = pipe.foresight_action(state, a_base, pred["wm_prediction"])
                    action, forced = a_fore, forced or f2
                    n_foresight += 1

        with _ENV_LOCK:
            nxt, _, dones, info = env.step([action])
        next_obs, done = nxt[0], bool(dones[0])
        success = extract_won(info) if done else False

        steps.append({"step": step, "action": action, "baseline_action": a_base,
                      "foresight_used": used, "wm_confidence_logprob": conf,
                      "action_forced": bool(forced)})
        history.append((action, next_obs))
        obs = next_obs
        if done:
            break

    return {
        "arm": arm,
        "gamefile": gamefile,
        "task_id": extract_task_id(gamefile),
        "task_type": extract_task_type(gamefile),
        "goal": goal,
        "success": bool(success),
        "done": bool(done),
        "steps": len(steps),
        "n_world_model_calls": n_wm,
        "n_foresight_used": n_foresight,
        "foresight_usage": (n_foresight / len(steps)) if steps else 0.0,
        "step_log": steps,
    }


def main(args: argparse.Namespace) -> None:
    ensure_dirs(DATA_DIR, OUT_TAB)
    config = load_yaml_config(args.config)
    db_cfg = config.get("direction_b", {})
    split = args.split
    history_length = config["sampling"].get("history_length", 50)

    memory = None
    if args.memory:
        memory = EpisodicMemory.load(DATA_DIR / args.bank, k=args.k)

    # Enumerate the split once, in the main thread, so every arm sees the same
    # games in the same order.
    AlfredTWEnv = _import_alfred_tw_env()
    with _ENV_LOCK:
        w0 = AlfredTWEnv(copy.deepcopy(_load_alfworld_config()), train_eval=split)
    games = sorted(w0.game_files)
    if args.episodes:
        stride = len(games) / min(args.episodes, len(games))
        games = [games[int(i * stride)] for i in range(min(args.episodes, len(games)))]
    del w0

    print(f"[episode] split={split} games={len(games)} arms={args.arms} "
          f"max_steps={args.max_steps} tau={args.tau} "
          f"memory={'on' if memory else 'off'}", flush=True)

    llm = load_client_from_config(config)
    pipe = DirectionBPipeline(llm, db_cfg)

    out_path = DATA_DIR / args.out
    all_rows: List[Dict[str, Any]] = []
    for arm in args.arms:
        t0 = time.time()

        def one(g: str, _arm=arm) -> Dict[str, Any]:
            return run_episode(pipe, memory, arm=_arm, split=split, gamefile=g,
                               max_steps=args.max_steps, tau=args.tau,
                               history_length=history_length)

        rows = ordered_map(one, games, workers=args.workers,
                           label=arm, progress_every=20)
        sr = sum(r["success"] for r in rows) / len(rows)
        print(f"[episode] {arm:10s} success={sr:.2%}  "
              f"mean_steps={sum(r['steps'] for r in rows)/len(rows):.1f}  "
              f"({time.time()-t0:.0f}s)", flush=True)
        all_rows.extend(rows)
        with open(out_path, "w", encoding="utf-8") as f:
            for r in all_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---------------- summary ----------------
    print(f"\n{'arm':12s} {'SuccessRate':>12s} {'MeanSteps':>10s} {'ForesightUsage':>15s} "
          f"{'WM calls':>9s}")
    print("-" * 62)
    summary: Dict[str, Any] = {"split": split, "n_games": len(games),
                               "max_steps": args.max_steps, "tau": args.tau,
                               "memory": bool(memory), "k_ME": args.k,
                               "model": config["model"]["name"],
                               "temperature": db_cfg.get("temperature"),
                               "arms": {}}
    for arm in args.arms:
        rows = [r for r in all_rows if r["arm"] == arm]
        n = len(rows)
        sr = sum(r["success"] for r in rows) / n
        e = {"n": n, "success_rate": sr,
             "mean_steps": sum(r["steps"] for r in rows) / n,
             "foresight_usage": sum(r["foresight_usage"] for r in rows) / n,
             "wm_calls": sum(r["n_world_model_calls"] for r in rows)}
        summary["arms"][arm] = e
        print(f"{arm:12s} {sr:>11.2%} {e['mean_steps']:>10.1f} "
              f"{e['foresight_usage']:>14.1%} {e['wm_calls']:>9d}")
    if {"none", "always", "selective"} <= set(args.arms):
        a = summary["arms"]
        summary["selective_minus_always"] = (a["selective"]["success_rate"]
                                             - a["always"]["success_rate"])
        summary["selective_minus_none"] = (a["selective"]["success_rate"]
                                           - a["none"]["success_rate"])
        print(f"\n选择性 - 总是   = {summary['selective_minus_always']:+.2%}")
        print(f"选择性 - 无     = {summary['selective_minus_none']:+.2%}")

    with open(OUT_TAB / f"dirB_episode_level{args.tag}.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n-> {out_path}\n-> {OUT_TAB / ('dirB_episode_level' + args.tag + '.json')}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Episode-level No/Always/Selective foresight.")
    p.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    p.add_argument("--split", default="eval_in_distribution")
    p.add_argument("--episodes", type=int, default=0, help="0 = the whole split")
    p.add_argument("--max_steps", type=int, default=30, help="WorldEvolver/AgentBoard use 30")
    p.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    p.add_argument("--tau", type=float, default=0.9990,
                   help="logprob-confidence threshold; default = the value Stage 3 "
                        "selected on the train-split states, applied unchanged here")
    p.add_argument("--memory", action="store_true", help="Strong WM (Episodic Memory)")
    p.add_argument("--bank", default="transition_bank.jsonl")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--out", default="episode_level.jsonl")
    p.add_argument("--tag", default="")
    add_workers_arg(p, default=8)
    return p


if __name__ == "__main__":
    os.chdir(ROOT)
    main(build_arg_parser().parse_args())
