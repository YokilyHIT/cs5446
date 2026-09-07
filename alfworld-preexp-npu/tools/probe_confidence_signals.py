"""判别实验：三种"世界模型不确定性"度量，哪一种不是常数、哪一种与 planning utility 相关。

背景：预实验 B 的 148 个决策点里，模型自报置信度有 102 个恰好是 0.95，只出现 9 个不同取值。
τ_c 取中位数后评估集实际使用率 95.9%（目标 50%），confidence gate 退化成 "always foresight"。
这是分布性质而非样本量问题——102/148 的 95% 区间是 [61%, 76%]，扩大十倍中位数仍是 0.95。

所以在扩大规模之前先回答一个问题：**是"置信度"这个概念没用，还是"让模型口头报数字"
这个测量方式坏了？** 本脚本在已采集的决策点上并排测三种度量：

  1. verbalized —— 模型自报的 0..1 数字（现有做法，已知退化）
  2. logprob    —— 生成该预测时 token 的平均对数概率（模型的内在不确定性）
  3. consistency—— 同一状态下采样 K 次预测，两两语义相似度的均值（预测稳定性）

对每一种报告：不同取值个数、分位数、以及与已测得的 planning_gain 的 Spearman 相关。
只读 results/ 下已有文件 + 重新调用模型，不改变任何实验数据。

用法（需 vLLM 在跑）：
    python tools/probe_confidence_signals.py --n 60 --workers 12
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from preexperiments.common import prompts
from preexperiments.common.embeddings import Embedder, cosine_sim
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import load_yaml_config
from preexperiments.common.parallel import ordered_map
from preexperiments.world_model_utility._common import (
    parse_prediction_confidence,
    render_action_prefix_history,
)

CONFIG = "preexperiments/configs/preexperiment.yaml"
OUT_DIR = Path(__file__).resolve().parents[1] / "diagnostics"
SEED = 13
CONSISTENCY_SEEDS = [2001, 2002, 2003, 2004]


def _wm_prompt(dp, base_action):
    return prompts.WORLD_MODEL_PREDICTION_PROMPT.format(
        goal=dp["goal"],
        observation=dp["observation"],
        history=render_action_prefix_history(dp["action_prefix"]),
        base_action=base_action,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="抽多少个决策点")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--api_base", default=None, help="覆盖 vLLM 地址（双卡时指定另一张）")
    args = ap.parse_args()

    config = load_yaml_config(CONFIG)
    if args.api_base:
        config["model"]["api_base"] = args.api_base
    llm = load_client_from_config(config)
    embedder = Embedder(config)

    results_dir = config["paths"]["results_dir"]
    dps = {json.loads(l)["point_id"]: json.loads(l)
           for l in open(os.path.join(results_dir, "B_decision_points.jsonl"))}
    branches = [json.loads(l) for l in open(os.path.join(results_dir, "B_branches_raw.jsonl"))]

    # 优先取变道点：只有它们的 planning_gain 携带 gating 判别信息（规范 §27）
    changed = [r for r in branches if r["action_changed"]]
    others = [r for r in branches if not r["action_changed"]]
    picked = (changed + others)[: args.n]
    print(f"[probe] 取 {len(picked)} 个决策点（其中变道 "
          f"{sum(1 for r in picked if r['action_changed'])} 个）", flush=True)

    def measure(rec):
        dp = dps[rec["point_id"]]
        base_action = rec["base_action"]
        prompt = _wm_prompt(dp, base_action)

        # 1+2: 一次调用同时拿到自报置信度和 token logprob
        resp = llm.complete(prompt, seed=SEED, logprobs=True)
        pred, verbal = parse_prediction_confidence(resp.text)
        lp = resp.mean_logprob

        # 3: 重复采样，看预测有多稳定
        samples = []
        for s in CONSISTENCY_SEEDS:
            r = llm.complete(prompt, seed=s, temperature=0.7)
            p, _ = parse_prediction_confidence(r.text)
            if p:
                samples.append(p)
        if len(samples) >= 2:
            vecs = [embedder.encode_one(p) for p in samples]
            sims = [cosine_sim(a, b) for a, b in itertools.combinations(vecs, 2)]
            consistency = float(np.mean(sims))
        else:
            consistency = float("nan")

        return {
            "point_id": rec["point_id"],
            "action_changed": rec["action_changed"],
            "planning_gain": rec["planning_gain"],
            "verbalized": verbal,
            "logprob": lp,
            "prob": math.exp(lp) if lp is not None and not math.isnan(lp) else float("nan"),
            "consistency": consistency,
            "semantic_correctness": rec["semantic_correctness"],
        }

    rows = ordered_map(measure, picked, workers=args.workers,
                       label="probe", progress_every=10)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "confidence_signal_probe.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- 汇总 ----
    ch = [r for r in rows if r["action_changed"]]
    print("\n" + "=" * 76)
    print(f"{'度量':14s} {'不同取值':>8s} {'p10':>8s} {'中位':>8s} {'p90':>8s} "
          f"{'rho(变道点)':>12s} {'p':>7s}")
    for key, label in [("verbalized", "自报置信度"), ("prob", "logprob概率"),
                       ("consistency", "预测一致性"), ("semantic_correctness", "语义正确性")]:
        v = [r[key] for r in rows if r[key] == r[key]]
        vc = [(r[key], r["planning_gain"]) for r in ch if r[key] == r[key]]
        if len(vc) >= 3:
            rho, p = spearmanr([x[0] for x in vc], [x[1] for x in vc])
        else:
            rho = p = float("nan")
        print(f"{label:14s} {len(set(round(x, 4) for x in v)):8d} "
              f"{np.percentile(v, 10):8.3f} {np.median(v):8.3f} {np.percentile(v, 90):8.3f} "
              f"{rho:12.3f} {p:7.3f}")
    print("=" * 76)
    print("判读：'不同取值'越多、p10 与 p90 差距越大，说明该度量越有区分度；")
    print("      能同时做到有区分度 且 与 planning_gain 相关的，才适合当 gate。")
    print(f"-> {out}")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    main()
