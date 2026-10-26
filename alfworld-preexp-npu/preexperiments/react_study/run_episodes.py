"""Run one arm x one repeat over a split; streams JSONL, resumable.

    $PY -m preexperiments.react_study.run_episodes --stage 2 --arm always --rep 0

Output: outputs/react_study/<stage>/raw/<split>/<arm>__rep<k>.jsonl, one row
per episode (see agent.run_episode), plus a run-config JSON next to it.
Rows already present for a gamefile are skipped on restart.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path

from preexperiments.common.logging_utils import load_yaml_config
from preexperiments.common.parallel import ordered_map
from preexperiments.direction_b.pipeline import DirectionBPipeline
from preexperiments.failure_selection._common import extract_task_type
from preexperiments.react_study import agent as agent_mod
from preexperiments.react_study.agent import ARMS, list_games, run_episode
from preexperiments.react_study.common import MeteredLLM, stage_dir
from preexperiments.react_study.protocol_v2 import PipelineV2
from preexperiments.react_study.online_memory import OnlineEpisodicMemory


def select_games(games, n: int, seed: int, stratify: bool):
    if not n or n >= len(games):
        return games
    if not stratify:
        stride = len(games) / n
        return [games[int(i * stride)] for i in range(n)]
    import random
    rng = random.Random(seed)
    by = {}
    for g in games:
        by.setdefault(extract_task_type(g), []).append(g)
    types = sorted(by)
    out = []
    for i, t in enumerate(types):
        k = n // len(types) + (1 if i < n % len(types) else 0)
        out += sorted(rng.sample(by[t], min(k, len(by[t]))))
    return sorted(out)


def main(a: argparse.Namespace) -> None:
    agent_mod.WM_ROLE = a.wm_role
    if a.router:
        from preexperiments.react_study.router import Router
        agent_mod.ROUTER = Router(a.router)
    agent_mod.ROUTE_RAND_P = (a.route_pR, a.route_pW)
    config = load_yaml_config(a.config)
    db_cfg = {**config.get("direction_b", {}), "reasoning_mode": "react"}
    hist_len = config["sampling"].get("history_length", 50)

    games = list_games(a.split)
    if a.games_file:
        games = [g.strip() for g in Path(a.games_file).read_text().splitlines() if g.strip()]
    games = select_games(games, a.episodes, a.select_seed, a.stratify)

    d = stage_dir(a.stage) / "raw" / a.split
    d.mkdir(parents=True, exist_ok=True)
    name = f"{a.prefix}{a.arm}__rep{a.rep}"
    out = d / f"{name}.jsonl"
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            if line.strip():
                done.add(json.loads(line)["gamefile"])
    todo = [g for g in games if g not in done]

    run_cfg = {"arm": a.arm, "rep": a.rep, "split": a.split, "n_games": len(games),
               "max_steps": a.max_steps, "tau": a.tau, "p_gate": a.p_gate,
               "gate_seed": a.gate_seed, "workers": a.workers,
               "model": config["model"]["name"], "decoding": {
                   k: db_cfg.get(k) for k in ("temperature", "top_p", "seed",
                                              "max_tokens_action_react", "max_tokens_prediction")},
               "history_length": hist_len, "reasoning_mode": "react",
               "record_state": a.record_state, "protocol": a.protocol, "variant": a.variant,
               "second_call_when_closed": a.second_call_when_closed, "memory_mode": a.memory,
               "memory_init": a.memory_init, "k_me": a.k_me, "wm_role": a.wm_role, "router": a.router, "route_pR": a.route_pR, "route_pW": a.route_pW,
               "env": {k: os.environ.get(k, "") for k in ("PREEXP_API_BASES", "PREEXP_PLANNER_MODEL",
                       "PREEXP_PLANNER_BASES", "PREEXP_WM_ALT_MODEL", "PREEXP_WM_ALT_BASES")}}
    (d / f"{name}.config.json").write_text(json.dumps(run_cfg, indent=2))
    if a.write_games:
        (d / f"{a.prefix}games.txt").write_text("\n".join(games) + "\n")

    llm = MeteredLLM(config)
    pipe = PipelineV2(llm, db_cfg, variant=a.variant) if a.protocol == "v2" else DirectionBPipeline(llm, db_cfg)
    print(f"[run] {a.arm} rep{a.rep} split={a.split} games={len(games)} todo={len(todo)} "
          f"endpoints={len(llm.endpoints)} tau={a.tau} p={a.p_gate}", flush=True)

    memory = None
    if a.memory == "online":
        memory = (OnlineEpisodicMemory.load(Path(a.memory_init), k=a.k_me) if a.memory_init
                  else OnlineEpisodicMemory(k=a.k_me))
        print(f"[run] online episodic memory, initial entries={len(memory.entries)}", flush=True)
    lock = threading.Lock()

    def one(g):
        t0 = time.time()
        r = run_episode(pipe, split=a.split, gamefile=g, arm=a.arm, max_steps=a.max_steps,
                        tau=a.tau, p_gate=a.p_gate, gate_seed=a.gate_seed,
                        history_length=hist_len, record_state=a.record_state,
                        second_call_when_closed=a.second_call_when_closed, memory=memory)
        r["rep"] = a.rep
        if a.label:
            r["arm"] = a.label
        r["wall_s"] = time.time() - t0
        return r

    n_done = [0]

    def sink(_i, _g, r):
        with lock, open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n_done[0] += 1
            if memory is not None and n_done[0] % 25 == 0:
                memory.dump(d / f"{name}.memory.partial.jsonl")

    t0 = time.time()
    ordered_map(one, todo, workers=a.workers, label=f"{a.arm}/rep{a.rep}",
                progress_every=20, on_result=sink)
    if memory is not None:
        memory.dump(d / f"{name}.memory.jsonl")
    rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    sr = sum(r["success"] for r in rows) / max(len(rows), 1)
    print(f"[run] DONE {a.arm} rep{a.rep}: n={len(rows)} SR={sr:.2%} ({time.time()-t0:.0f}s)",
          flush=True)


def build_arg_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    p.add_argument("--stage", type=int, required=True)
    p.add_argument("--arm", required=True, choices=list(ARMS))
    p.add_argument("--rep", type=int, default=0)
    p.add_argument("--split", default="eval_in_distribution")
    p.add_argument("--episodes", type=int, default=0, help="0 = whole split")
    p.add_argument("--stratify", action="store_true", help="stratify --episodes by task type")
    p.add_argument("--select_seed", type=int, default=0)
    p.add_argument("--games_file", default="")
    p.add_argument("--write_games", action="store_true")
    p.add_argument("--max_steps", type=int, default=30)
    p.add_argument("--tau", type=float, default=0.9997)
    p.add_argument("--p_gate", type=float, default=0.25)
    p.add_argument("--gate_seed", type=int, default=2026)
    p.add_argument("--record_state", action="store_true")
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--protocol", default="v1", choices=["v1", "v2"])
    p.add_argument("--variant", default="query", choices=["query", "list"], help="v2 only")
    p.add_argument("--second_call_when_closed", action="store_true")
    p.add_argument("--prefix", default="", help="output file prefix, e.g. v2query_")
    p.add_argument("--label", default="", help="override the arm name written to rows (e.g. random_pre_p0.1)")
    p.add_argument("--memory", default="off", choices=["off", "online"])
    p.add_argument("--memory_init", default="", help="seed the online bank from a previous dump")
    p.add_argument("--k_me", type=int, default=5)
    p.add_argument("--router", default="", help="round 4: router model json for arm route")
    p.add_argument("--route_pR", type=float, default=0.0, help="route_rand: P(R)")
    p.add_argument("--route_pW", type=float, default=0.0, help="route_rand: P(W)")
    p.add_argument("--wm_role", default="wm", choices=["wm", "wm_alt"],
                   help="round 4: wm_alt routes WM calls to PREEXP_WM_ALT_* (e.g. Qwen3-14B)")
    return p


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
