"""Build the (observation, action, next_observation) bank behind Episodic Memory.

WorldEvolver grows this bank online: after each executed step it appends the
triple it just observed, so by mid-run the world model has hundreds of real
transitions to retrieve from. Our diagnostic scores a fixed set of pre-sampled
states rather than running an agent, so the bank has to be materialised up
front -- but from the same source, expert trajectories in the ALFWorld train
split.

This walks the identical games `sample_states.py` walks, using the identical
stride selection, so `episode_id` and `step_id` line up exactly with
`sampled_states.jsonl`. That alignment is what makes the causal filter in
`episodic_memory.retrieve()` possible: a state sampled at step t can be told to
ignore transitions from its own episode at step >= t, which is precisely
WorldEvolver's "records are appended only after execution" guarantee, while
still keeping the earlier same-episode experience their method does use.

`--extra` walks additional games beyond the sampled 100. Those episodes contain
no evaluated state at all, so they enlarge the bank with zero leakage risk;
they exist because the paper's own k_ME ablation (Exact Match +16.8/+23.5 going
from k=1 to k=5) says retrieval depth matters, and depth needs a bank to draw
from.

No LLM is involved. This is pure environment walking.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from preexperiments.common.alfworld_runner import _ENV_LOCK, extract_task_id
from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config
from preexperiments.direction_b.sample_states import _build_train_env_wrapper, _expert_action
from preexperiments.failure_selection._common import extract_goal, extract_task_type

OUT_DIR = Path(__file__).resolve().parents[2] / "data"


def main(args: argparse.Namespace) -> None:
    ensure_dirs(OUT_DIR)
    out_path = OUT_DIR / args.out
    if out_path.exists():
        out_path.unlink()

    config = load_yaml_config(args.config)
    max_steps = config["sampling"]["max_episode_steps"]

    wrapper = _build_train_env_wrapper()
    all_games = sorted(wrapper.game_files)

    # --- identical selection to sample_states.py, so episode_ids match ---
    n_ep = min(args.episodes, len(all_games))
    stride = len(all_games) / n_ep
    chosen = [(f"E{i:04d}", all_games[int(i * stride)]) for i in range(n_ep)]
    sampled = {g for _, g in chosen}

    # --- extra episodes: any other game, ids that cannot collide ---
    if args.extra > 0:
        rest = [g for g in all_games if g not in sampled]
        s2 = len(rest) / min(args.extra, len(rest))
        chosen += [(f"X{i:04d}", rest[int(i * s2)])
                   for i in range(min(args.extra, len(rest)))]

    print(f"[bank] walking {len(chosen)} expert trajectories "
          f"({n_ep} aligned + {len(chosen) - n_ep} extra)", flush=True)

    t0, total = time.time(), 0
    for ep_i, (ep_id, gamefile) in enumerate(chosen):
        with _ENV_LOCK:
            wrapper.game_files = [gamefile]
            if hasattr(wrapper, "num_games"):
                wrapper.num_games = 1
            env = wrapper.init_env(batch_size=1)
            raw_obs, info = env.reset()
        obs = raw_obs[0]
        goal = extract_goal(obs, info)

        rows: List[Dict[str, Any]] = []
        done = False
        for step in range(max_steps):
            if done:
                break
            expert = _expert_action(info)
            if not expert:
                break
            with _ENV_LOCK:
                nxt, _, dones, info = env.step([expert])
            nxt_obs, done = nxt[0], bool(dones[0])
            rows.append({
                "episode_id": ep_id,
                "step_id": step,
                "task_id": extract_task_id(gamefile),
                "task_type": extract_task_type(gamefile),
                "goal": goal,
                "observation": obs,
                "action": expert,
                "next_observation": nxt_obs,
            })
            obs = nxt_obs

        with open(out_path, "a", encoding="utf-8") as f:
            for r in rows:
                total += 1
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        if (ep_i + 1) % 20 == 0 or ep_i + 1 == len(chosen):
            print(f"[bank] {ep_i+1}/{len(chosen)} episodes, {total} transitions, "
                  f"{time.time()-t0:.0f}s", flush=True)

    print(f"[bank] done: {total} transitions -> {out_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build the episodic-memory transition bank.")
    p.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    p.add_argument("--episodes", type=int, default=100,
                   help="episodes aligned 1:1 with sampled_states.jsonl")
    p.add_argument("--extra", type=int, default=100,
                   help="additional episodes containing no evaluated state")
    p.add_argument("--out", default="transition_bank.jsonl")
    return p


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[2])
    main(build_arg_parser().parse_args())
