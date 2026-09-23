"""置信度的"问法"对比：模型能不能估计自己预测的准确性？

动机。预实验 B 里 148 个决策点的自报置信度与实际预测准确性的相关是
**+0.034 (p=0.68)** —— 它没有测到它声称要测的东西。WorldEvolver 那条路线的整个
前提是 C_t = P(prediction correct)，所以这一步不成立的话，H1 的检验是无效的。

一个具体的怀疑对象是实现方式，而不是模型能力。研究方向文档 §8 把置信度定义成

    C_t = C_psi(h_t, a_t, ô_{t+1})

—— 把**已完成的预测**当作输入的独立估计器。而规范 §22 的实现是单次调用行内追加：
模型写完 "Prediction: ..." 之后在同一次前向生成里紧接着写 "Confidence: 0.95"，
没有任何机会审视自己刚写的东西。这更像在续写一个文本模式，不是在做评估。

本脚本固定同一条预测（用主实验存档的 wm_prediction），只改变"怎么问置信度"，
并用同一套真实 o_{t+1} 计算准确性，因此各变体的 rho 直接可比：

    A  行内自报        规范 §22 原文（不重跑，直接用存档值）
    B  独立评估调用    文档 §8 的 C_psi(h,a,ô) 字面实现
    C  频率化问法      "100 个类似情况里有几个会完全正确"
    D  离散档位        guided_choice 约束到五档
    E  token logprob   重新生成预测并取其平均 logprob（作对照）

判据只有一个：rho(置信度, 语义正确性)。
顺带验证存档的 semantic_correctness 是否算对（重新还原状态取真实 o_{t+1} 复算）。

用法：python tools/probe_confidence_elicitation.py --n 100 --workers 8
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from preexperiments.common import prompts
from preexperiments.common.embeddings import Embedder, cosine_sim
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import load_yaml_config
from preexperiments.common.parallel import ordered_map
from preexperiments.common.replay_state import StateRestoreError, restore_state
from preexperiments.world_model_utility._common import (
    parse_prediction_confidence,
    render_action_prefix_history,
)

CONFIG = "preexperiments/configs/preexperiment.yaml"
OUT_DIR = Path(__file__).resolve().parents[1] / "diagnostics"
SEED = 13

# --- B: 文档 §8 的 C_psi(h_t, a_t, ô_{t+1}) —— 预测作为输入，独立一次调用 ---
PROMPT_B = """You are evaluating a world model's prediction for an interactive household environment.

Current task:
{goal}

Current observation:
{observation}

Recent action-observation history:
{history}

Action that was taken:
{base_action}

The world model predicted this next observation:
{prediction}

Judge how likely it is that this prediction is correct about the important
state changes and preconditions.

Return only one decimal number between 0.0 and 1.0."""

# --- C: 频率化问法 ---
PROMPT_C = """You are evaluating a world model's prediction for an interactive household environment.

Current task:
{goal}

Current observation:
{observation}

Recent action-observation history:
{history}

Action that was taken:
{base_action}

The world model predicted this next observation:
{prediction}

Imagine 100 different situations just like this one. In how many of them would
this prediction turn out to be exactly right about what is observed next?

Return only an integer between 0 and 100."""

# --- D: 离散档位（guided_choice 约束）---
PROMPT_D = """You are evaluating a world model's prediction for an interactive household environment.

Current task:
{goal}

Current observation:
{observation}

Recent action-observation history:
{history}

Action that was taken:
{base_action}

The world model predicted this next observation:
{prediction}

How likely is this prediction to be correct?

Answer with exactly one of: very low, low, medium, high, very high"""

BINS = ["very low", "low", "medium", "high", "very high"]
BIN_VALUE = {b: v for b, v in zip(BINS, [0.1, 0.3, 0.5, 0.7, 0.9])}
_NUM = re.compile(r"-?\d*\.?\d+")


def _num(text, lo=0.0, hi=1.0, scale=1.0):
    m = _NUM.search(text or "")
    if not m:
        return float("nan")
    try:
        return max(lo, min(hi, float(m.group(0)) / scale))
    except ValueError:
        return float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    config = load_yaml_config(CONFIG)
    llm = load_client_from_config(config)
    embedder = Embedder(config)
    split = config["splits"]["evaluation"]
    results_dir = config["paths"]["results_dir"]

    dps = {json.loads(l)["point_id"]: json.loads(l)
           for l in open(os.path.join(results_dir, "B_decision_points.jsonl"))}
    branches = [json.loads(l) for l in open(os.path.join(results_dir, "B_branches_raw.jsonl"))]
    branches = [r for r in branches if r["wm_prediction"].strip()][: args.n]
    print(f"[elicit] {len(branches)} 个决策点，固定存档预测，只改变置信度问法", flush=True)

    def one(rec):
        dp = dps[rec["point_id"]]
        pred = rec["wm_prediction"]
        fields = dict(
            goal=dp["goal"],
            observation=dp["observation"],
            history=render_action_prefix_history(dp["action_prefix"]),
            base_action=rec["base_action"],
            prediction=pred,
        )

        # 还原状态取真实 o_{t+1}，作为所有变体共用的准确性标签
        try:
            st = restore_state(
                config=config, split=split,
                game_id_or_path=dp["game_id_or_path"],
                action_prefix=dp["action_prefix"],
                expected_observation=dp.get("restore_observation", dp["observation"]),
                strict=True,
            )
            o_next, _, _, _ = st.adapter.step(rec["base_action"])
            sem = cosine_sim(embedder.encode_one(pred), embedder.encode_one(o_next))
        except StateRestoreError:
            return None

        b = _num(llm.complete(PROMPT_B.format(**fields), seed=SEED, max_tokens=8).text)
        c = _num(llm.complete(PROMPT_C.format(**fields), seed=SEED, max_tokens=8).text,
                 lo=0.0, hi=1.0, scale=100.0)
        d_raw = llm.complete(PROMPT_D.format(**fields), seed=SEED,
                             choices=BINS, max_tokens=8).text.strip().lower()
        d = BIN_VALUE.get(d_raw, float("nan"))

        # E: 重新生成预测并取平均 logprob；用它自己的预测算自己的准确性
        e_resp = llm.complete(
            prompts.WORLD_MODEL_PREDICTION_PROMPT.format(
                goal=fields["goal"], observation=fields["observation"],
                history=fields["history"], base_action=fields["base_action"]),
            seed=SEED, logprobs=True)
        e_pred, _ = parse_prediction_confidence(e_resp.text)
        e_prob = math.exp(e_resp.mean_logprob) if not math.isnan(e_resp.mean_logprob) else float("nan")
        e_sem = (cosine_sim(embedder.encode_one(e_pred), embedder.encode_one(o_next))
                 if e_pred else float("nan"))

        return {
            "point_id": rec["point_id"],
            "sem_true": sem,
            "sem_archived": rec["semantic_correctness"],
            "A_inline": rec["self_confidence"],
            "B_separate": b,
            "C_frequency": c,
            "D_bins": d,
            "D_bin_label": d_raw,
            "E_logprob_prob": e_prob,
            "E_sem": e_sem,
            "planning_gain": rec["planning_gain"],
            "action_changed": rec["action_changed"],
        }

    rows = [r for r in ordered_map(one, branches, workers=args.workers,
                                   label="elicit", progress_every=10) if r]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "confidence_elicitation_probe.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # --- 先验证存档的 semantic_correctness ---
    a = [r["sem_archived"] for r in rows]
    t = [r["sem_true"] for r in rows]
    print(f"\n=== 存档 semantic_correctness 校验（n={len(rows)}）===")
    print(f"  与重新还原复算值的相关 = {spearmanr(a, t)[0]:+.3f}，"
          f"平均绝对差 {np.mean(np.abs(np.array(a) - np.array(t))):.4f}")

    def report(key, label, sem_key="sem_true"):
        v = [(r[key], r[sem_key]) for r in rows if r[key] == r[key] and r[sem_key] == r[sem_key]]
        if len(v) < 5:
            print(f"{label:16s}  样本不足 ({len(v)})")
            return
        x = [p[0] for p in v]
        rho, p = spearmanr(x, [p[1] for p in v])
        print(f"{label:16s} n={len(v):3d}  取值数={len(set(round(z,4) for z in x)):3d}  "
              f"p10={np.percentile(x,10):.2f} 中位={np.median(x):.2f} p90={np.percentile(x,90):.2f}  "
              f"rho(准确性)={rho:+.3f}  p={p:.4f}")

    print(f"\n=== 判据：rho(置信度, 语义正确性) —— 能否测到它声称要测的东西 ===")
    report("A_inline", "A 行内自报")
    report("B_separate", "B 独立评估")
    report("C_frequency", "C 频率化")
    report("D_bins", "D 离散档位")
    report("E_logprob_prob", "E token logprob", sem_key="E_sem")

    print(f"\n=== 附：各变体与 planning_gain 的相关（仅变道点）===")
    ch = [r for r in rows if r["action_changed"]]
    for key, label in [("A_inline", "A 行内自报"), ("B_separate", "B 独立评估"),
                       ("C_frequency", "C 频率化"), ("D_bins", "D 离散档位")]:
        v = [(r[key], r["planning_gain"]) for r in ch if r[key] == r[key]]
        if len(v) >= 5:
            rho, p = spearmanr([x[0] for x in v], [x[1] for x in v])
            print(f"  {label:16s} n={len(v):2d}  rho={rho:+.3f}  p={p:.3f}")
    print(f"\n-> {out}")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    main()
