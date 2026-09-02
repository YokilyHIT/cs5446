#!/usr/bin/env python
"""
Phase 0 (spec section 39's decision gate): measure the TRUE no-memory
baseline success rate on `eval_in_distribution` before deciding whether any
remedy (raise max_episode_steps, switch prompt_style) is warranted.

Why this exists: a handful of ad-hoc episodes give contradictory, tiny-sample
evidence about "is the model even capable of this task" (e.g. 1/5 succeeding
in one run, 1/2 in another) -- nowhere near enough to tell whether spec
section 39's remedies are needed or would just be wasted compute. This script
only measures; it changes no experiment parameter on disk.

  - 30 tasks sampled evenly-strided over the full eval_in_distribution pool
    (same deterministic rule as evaluate_topk_vs_all.py::_select_eval_subset
    and collect_decision_points.py, covering all six task families).
  - seed=13, no-memory, no lesson -- the exact same rollout() path
    collect_failures.py / collect_decision_points.py use.
  - Each episode additionally records "looping" evidence: the longest run of
    the same action repeated back to back, and the single most-common action
    and its count -- a model stuck cycling among a handful of actions looks
    very different from one that explores broadly and still fails.

Real-hardware result recorded once (Ascend 910B3, Qwen3-4B-Instruct-2507,
seed=13, this repo's fixed 30-task subset): spec prompt / 30 steps = 10.0%
success (23% of episodes looping); spec prompt / 50 steps = 13.3% (27%
looping, 62% more compute for +1 success -- max_episode_steps was ruled out
as the bottleneck); AdaMEM's <think> no-memory prompt / 30 steps = 26.7% (10%
looping) -- see CHANGELOG entry VALID-3 and README_NPU_SETUP.md.

Output: <output_dir>/baseline_<tag>.jsonl + a terminal summary.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

from preexperiments.common.alfworld_runner import (
    ALFWorldEnvAdapter,
    build_single_game_adapter,
    extract_task_id,
    reset_and_attach,
    rollout,
)
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import load_yaml_config, new_run_id
from preexperiments.failure_selection._common import extract_goal, extract_task_type

PROJECT_ROOT = Path(__file__).resolve().parents[1]
N_EPISODES = 30
SEED = 13


def longest_consecutive_run(actions: List[str]) -> int:
    """Longest run of the same action repeated back to back -- the most
    direct evidence of a stuck-looping episode."""
    best = cur = 0
    prev = None
    for a in actions:
        cur = cur + 1 if a == prev else 1
        prev = a
        best = max(best, cur)
    return best


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(PROJECT_ROOT / "preexperiments/configs/preexperiment.yaml"))
    parser.add_argument("--output_dir", default=str(PROJECT_ROOT / "diagnostics"))
    parser.add_argument("--max_steps", type=int, default=None, help="Override sampling.max_episode_steps (spec section 39 remedy #2).")
    parser.add_argument("--tag", default="30")
    parser.add_argument(
        "--workers", type=int, default=1,
        help="Run this many episodes concurrently. vLLM batches concurrent requests -- "
             "measured 37 tok/s single-stream vs 513 tok/s at 16-way concurrency with "
             "near-zero per-request latency penalty.",
    )
    parser.add_argument(
        "--prompt_style", default=None,
        help='Override sampling.prompt_style: "spec" or "adamem_think" (spec section 39 remedy #3).',
    )
    return parser


def main(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"baseline_{args.tag}.jsonl"
    if out_path.exists():
        out_path.unlink()

    config = load_yaml_config(args.config)
    if args.max_steps:
        config["sampling"]["max_episode_steps"] = args.max_steps
    if args.prompt_style:
        config["sampling"]["prompt_style"] = args.prompt_style
    split = config["splits"]["evaluation"]
    max_steps = config["sampling"]["max_episode_steps"]
    llm = load_client_from_config(config)

    all_games = sorted(ALFWorldEnvAdapter(config, split).game_files)
    n = len(all_games)
    if n <= N_EPISODES:
        chosen = list(all_games)
    else:
        stride = n / N_EPISODES
        chosen = [all_games[int(i * stride)] for i in range(N_EPISODES)]

    print(
        f"[baseline] split={split} pool={n} chosen={len(chosen)} "
        f"max_episode_steps={max_steps} seed={SEED} "
        f"prompt_style={config['sampling'].get('prompt_style', 'spec')}",
        flush=True,
    )

    t0 = time.time()
    rows: List[Dict[str, Any]] = []
    write_lock = threading.Lock()
    done = [0]

    def run_one(gf: str) -> Dict[str, Any]:
        adapter = build_single_game_adapter(config, split, gf)
        obs, info = reset_and_attach(adapter)
        goal = extract_goal(obs, info)
        result = rollout(
            adapter,
            llm=llm,
            config=config,
            run_id=new_run_id("base0"),
            task_id=extract_task_id(gf),
            game_id_or_path=gf,
            split=split,
            seed=SEED,
            goal=goal,
            observation=obs,
            lesson=None,
        )
        actions = [r["action"] for r in result.step_records]
        counts = Counter(actions)
        top_action, top_n = counts.most_common(1)[0] if counts else ("", 0)
        row = {
            "task_id": extract_task_id(gf),
            "task_type": extract_task_type(gf),
            "goal": goal,
            "success": bool(result.success),
            "steps": result.steps,
            "forced_actions": sum(1 for r in result.step_records if r.get("action_forced")),
            "longest_repeat_run": longest_consecutive_run(actions),
            "most_common_action": top_action,
            "most_common_action_count": top_n,
            "distinct_actions": len(counts),
        }
        with write_lock:
            rows.append(row)
            done[0] += 1
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(
                f"  [{done[0]:2d}/{len(chosen)}] {row['task_type'][:30]:32s} "
                f"success={str(row['success']):5s} steps={row['steps']:2d} "
                f"forced={row['forced_actions']:2d} maxrun={row['longest_repeat_run']:2d} "
                f"({time.time() - t0:.0f}s)",
                flush=True,
            )
        return row

    if args.workers > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(run_one, chosen))
    else:
        for gf in chosen:
            run_one(gf)

    total = len(rows)
    succ = sum(r["success"] for r in rows)
    steps_sum = sum(r["steps"] for r in rows)
    forced_sum = sum(r["forced_actions"] for r in rows)
    looped = [r for r in rows if r["longest_repeat_run"] >= 5]
    timeout_fail = [r for r in rows if not r["success"] and r["steps"] >= max_steps]

    print("\n" + "=" * 68)
    print(f"baseline success rate : {succ}/{total} = {succ / total:.1%}")
    print(f"forced-action rate    : {forced_sum}/{steps_sum} = {forced_sum / max(steps_sum, 1):.1%}")
    print(f"mean steps            : {steps_sum / total:.1f}")
    print(f"looping episodes      : {len(looped)}/{total} = {len(looped) / total:.1%} (same action repeated >=5x in a row)")
    print(f"failed by timeout     : {len(timeout_fail)}/{total}")
    print("-" * 68)
    print(f"{'task_type':34s} {'success':>9s} {'mean_steps':>11s} {'loop':>6s}")
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_type.setdefault(r["task_type"], []).append(r)
    for tt, rs in sorted(by_type.items()):
        s = sum(x["success"] for x in rs)
        lp = sum(1 for x in rs if x["longest_repeat_run"] >= 5)
        print(f"{tt[:34]:34s} {s}/{len(rs):<7d} {sum(x['steps'] for x in rs) / len(rs):>11.1f} {lp:>6d}")
    print("=" * 68)
    print(f"-> {out_path}")


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
