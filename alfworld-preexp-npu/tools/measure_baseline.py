"""阶段 0：测准无记忆基线在 eval_in_distribution 上的真实成功率。

为什么需要这一步：目前关于"模型到底行不行"的证据全是极小样本且互相矛盾
（5 个 episode 是 1/5，2 个 episode 是 1/2）。而规范 §39 要求的补救动作
（加步数上限 / 换 AdaMEM 提示词）该不该做，完全取决于这个数——如果真实成功率
本来就有 25% 以上，那任何对实验设计的改动都是多余的干预。

本脚本只做测量，不改变任何实验参数：
  - 从 140 个 eval 任务里等距抽 30 个（六类任务都覆盖到，与
    evaluate_topk_vs_all.py::_select_eval_subset 同一规则，完全确定性）
  - seed=13，无记忆、无教训，与 collect_failures / collect_decision_points
    使用的完全是同一条 rollout 路径
  - 每个 episode 额外记录"打转"证据：某个动作连续重复的最长次数、
    以及出现次数最多的动作及其次数

输出 diagnostics/baseline_30.jsonl + 终端汇总。
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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

import argparse

N_EPISODES = 30
SEED = 13
OUT_DIR = Path(__file__).resolve().parents[1] / "diagnostics"
CONFIG = "preexperiments/configs/preexperiment.yaml"


def longest_consecutive_run(actions):
    """最长的"连续重复同一个动作"的长度 —— 卡死打转最直接的证据。"""
    best = cur = 0
    prev = None
    for a in actions:
        cur = cur + 1 if a == prev else 1
        prev = a
        best = max(best, cur)
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max_steps", type=int, default=None,
                    help="覆盖 sampling.max_episode_steps，用于验证规范 §39 第②条")
    ap.add_argument("--tag", default="30")
    ap.add_argument("--workers", type=int, default=1,
                    help="并发跑多少个 episode。vLLM 会把并发请求批处理："
                         "实测单路 37 tok/s、16 路 513 tok/s，而单请求延迟几乎不变。")
    ap.add_argument("--prompt_style", default=None,
                    help='覆盖 sampling.prompt_style："spec" 或 "adamem_think"（规范 §39 第③条）')
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"baseline_{args.tag}.jsonl"
    if out_path.exists():
        out_path.unlink()

    config = load_yaml_config(CONFIG)
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

    print(f"[baseline] split={split} pool={n} chosen={len(chosen)} "
          f"max_episode_steps={max_steps} seed={SEED} "
          f"prompt_style={config['sampling'].get('prompt_style', 'spec')}", flush=True)

    t0 = time.time()
    rows = []
    write_lock = threading.Lock()
    done = [0]

    def run_one(gf):
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
            print(f"  [{done[0]:2d}/{len(chosen)}] {row['task_type'][:30]:32s} "
                  f"success={str(row['success']):5s} steps={row['steps']:2d} "
                  f"forced={row['forced_actions']:2d} maxrun={row['longest_repeat_run']:2d} "
                  f"({time.time() - t0:.0f}s)", flush=True)
        return row

    if args.workers > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(run_one, chosen))
    else:
        for gf in chosen:
            run_one(gf)

    # ---- 汇总 ----
    total = len(rows)
    succ = sum(r["success"] for r in rows)
    steps_sum = sum(r["steps"] for r in rows)
    forced_sum = sum(r["forced_actions"] for r in rows)
    # "打转"判据：同一个动作连续重复 >= 5 次
    looped = [r for r in rows if r["longest_repeat_run"] >= 5]
    timeout_fail = [r for r in rows if not r["success"] and r["steps"] >= max_steps]

    print("\n" + "=" * 68)
    print(f"基线成功率      : {succ}/{total} = {succ / total:.1%}")
    print(f"强制动作率      : {forced_sum}/{steps_sum} = {forced_sum / max(steps_sum, 1):.1%}")
    print(f"平均步数        : {steps_sum / total:.1f}")
    print(f"打转 episode    : {len(looped)}/{total} = {len(looped) / total:.1%} (同一动作连续重复>=5次)")
    print(f"耗尽步数而失败  : {len(timeout_fail)}/{total}")
    print("-" * 68)
    print(f"{'task_type':34s} {'成功率':>9s} {'平均步数':>9s} {'打转':>6s}")
    by_type = {}
    for r in rows:
        by_type.setdefault(r["task_type"], []).append(r)
    for tt, rs in sorted(by_type.items()):
        s = sum(x["success"] for x in rs)
        lp = sum(1 for x in rs if x["longest_repeat_run"] >= 5)
        print(f"{tt[:34]:34s} {s}/{len(rs):<7d} {sum(x['steps'] for x in rs) / len(rs):>9.1f} {lp:>6d}")
    print("=" * 68)
    print(f"-> {out_path}")


if __name__ == "__main__":
    # 以仓库根目录为 cwd，好让 CONFIG 的相对路径成立
    os.chdir(Path(__file__).resolve().parents[1])
    main()
