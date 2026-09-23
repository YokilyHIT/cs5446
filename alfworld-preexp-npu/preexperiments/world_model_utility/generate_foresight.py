"""
Experiment B2-B4 (spec sections 21-23) + B11 (spec section 31): for each
decision point collected by collect_decision_points.py, at the SAME state
(no env interaction here, this script never touches ALFWorld):

  B2  base action from the ordinary base ReAct planner.
  B3  world-model prediction of the next observation + self-reported
      confidence, conditioned on the base action.
  B4  a foresight-conditioned re-planning call that may keep or change the
      base action given the world model's prediction.
  B11 action-ambiguity: resample the base planner 4 more times at this same
      state (varying only `seed`) to estimate how often the base planner
      itself disagrees with its own action choice.
"""
from __future__ import annotations

import argparse
import math
import os
import re
from collections import Counter
from typing import Any, Dict

from preexperiments.common import prompts

# 研究方向文档 §8 把置信度定义成 C_psi(h_t, a_t, ô_{t+1}) —— 一个把**已完成的预测**
# 当作输入的独立估计器。规范 §22 则把它实现成单次调用行内追加（写完 Prediction 之后
# 紧接着写 Confidence），模型没有机会审视自己刚写的东西。
# 实测：行内写法 148 个点里 102 个恰好报 0.95（只有 9 个不同取值），
# 与实际预测准确性的相关 +0.034 (p=0.68)；改成下面这个独立调用后分布散开到 0.30–0.90。
# 两个都记录：self_confidence 保持规范合规，confidence_separate 用于检验文档的 H1。
CONFIDENCE_SEPARATE_PROMPT = """You are evaluating a world model's prediction for an interactive household environment.

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

# 上一轮事后发现：真正预测 Delta 的不是预测的属性，而是"被替换掉的动作值不值钱"
# （空动作被打断净 +2，实质动作被打断净 -1，在标定/评估两半都复现）。
# 这一轮把它作为预注册字段记录，而不是再事后从数据里挖。
_NOOP_VERBS = {"inventory", "look", "examine", "help"}
from preexperiments.common.alfworld_runner import (
    choose_action,
    decide_action_from_prompt,
    format_admissible,
)
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.parallel import add_workers_arg, ordered_map
from preexperiments.common.logging_utils import append_jsonl, ensure_dirs, load_yaml_config, read_jsonl_all
from preexperiments.world_model_utility._common import (
    parse_prediction_confidence,
    render_action_prefix_history,
    reset_output_file,
)

_BASE_SEED = 13
# Fixed, deliberately disjoint from the experiment's config seeds [13,37,73]
# so this resampling stays orthogonal to any per-seed-sweep comparison.
_AMBIGUITY_SEEDS = [1001, 1002, 1003, 1004]


def _process_point(llm, dp: Dict[str, Any], sampling_cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Both the base action (B2) and the foresight-conditioned action (B4) must
    # be produced by the IDENTICAL mechanism, so `action_changed` isolates the
    # single variable experiment B is about: whether seeing the world model's
    # prediction changed the plan. Reading these from the config rather than
    # letting them default is what keeps them in step with the branch rollouts
    # in build_counterfactual_pairs.py, which get them from rollout().
    style = sampling_cfg.get("prompt_style", "spec")
    adamem_max_tokens = sampling_cfg.get("adamem_max_tokens", 512)
    history_length = sampling_cfg.get("history_length", 50)
    goal = dp["goal"]
    observation = dp["observation"]
    admissible_actions = dp["admissible_actions"]
    action_prefix = dp["action_prefix"]
    history_text = render_action_prefix_history(action_prefix)

    # B2: base action. `history=[]` here is a documented simplification --
    # the decision point only stores flat action strings, not the matching
    # intermediate observations, and `observation` already reflects the true
    # current state after all prior actions, which is what matters for
    # choosing the next one.
    base_action, _, _, _ = choose_action(
        llm,
        goal=goal,
        observation=observation,
        history=[],
        admissible_actions=admissible_actions,
        seed=_BASE_SEED,
        lesson=None,
        prompt_style=style,
        adamem_max_tokens=adamem_max_tokens,
        history_length=history_length,
    )

    # B3: world-model prediction + self confidence.
    wm_prompt = prompts.WORLD_MODEL_PREDICTION_PROMPT.format(
        goal=goal,
        observation=observation,
        history=history_text,
        base_action=base_action,
    )
    wm_resp = llm.complete(wm_prompt, seed=_BASE_SEED, logprobs=True)
    wm_prediction, self_confidence = parse_prediction_confidence(wm_resp.text)
    logprob_prob = (math.exp(wm_resp.mean_logprob)
                    if not math.isnan(wm_resp.mean_logprob) else float("nan"))

    # 文档 §8 的 C_psi(h, a, ô)：预测作为输入，独立一次调用
    conf_sep_resp = llm.complete(
        CONFIDENCE_SEPARATE_PROMPT.format(
            goal=goal, observation=observation, history=history_text,
            base_action=base_action, prediction=wm_prediction),
        seed=_BASE_SEED, max_tokens=8)
    m = re.search(r"-?\d*\.?\d+", conf_sep_resp.text or "")
    confidence_separate = max(0.0, min(1.0, float(m.group(0)))) if m else float("nan")

    # B4: foresight-conditioned re-planning at the same state.
    foresight_prompt = prompts.FORESIGHT_CONDITIONED_ACTION_PROMPT.format(
        goal=goal,
        observation=observation,
        admissible_actions=format_admissible(admissible_actions),
        base_action=base_action,
        predicted_next_observation=wm_prediction,
    )
    # Goes through the SAME decision mechanism as the base action above: the
    # guided_choice constraint, and -- under prompt_style="adamem_think" -- the
    # same <think> reasoning scaffold. The spec's fixed prompt text is
    # reproduced verbatim; only the scaffold around it is shared. Without this,
    # a_t^(0) would come from a two-call reasoning pipeline and a_t^(W) from a
    # single bare call, so D_t would conflate "the prediction changed the plan"
    # with "the model got to reason".
    foresight_action, _, _, _ = decide_action_from_prompt(
        llm,
        foresight_prompt,
        admissible_actions,
        seed=_BASE_SEED,
        prompt_style=style,
        adamem_max_tokens=adamem_max_tokens,
        # 注意：不传 history_length —— decide_action_from_prompt 接收的是已渲染好的
        # 提示词，历史长度在渲染时（choose_action / 上面的 foresight_prompt）就已确定。
    )
    action_changed = foresight_action != base_action

    # B11: action ambiguity via 4 independently-seeded base-planner resamples.
    ambiguity_samples = []
    for seed in _AMBIGUITY_SEEDS:
        sample_action, _, _, _ = choose_action(
            llm,
            goal=goal,
            observation=observation,
            history=[],
            admissible_actions=admissible_actions,
            seed=seed,
            lesson=None,
            prompt_style=style,
            adamem_max_tokens=adamem_max_tokens,
            history_length=history_length,
        )
        ambiguity_samples.append(sample_action)
    counts = Counter(ambiguity_samples)
    ambiguity = 1.0 - max(counts.values()) / len(ambiguity_samples)

    return {
        "point_id": dp["point_id"],
        "task_id": dp["task_id"],
        "game_id_or_path": dp["game_id_or_path"],
        "step": dp["step"],
        "goal": goal,
        "base_action": base_action,
        "wm_prediction": wm_prediction,
        "self_confidence": self_confidence,
        "confidence_separate": confidence_separate,
        "logprob_prob": logprob_prob,
        "base_action_is_noop": base_action.split()[0] in _NOOP_VERBS if base_action else False,
        "foresight_action": foresight_action,
        "action_changed": action_changed,
        "ambiguity": ambiguity,
        "ambiguity_samples": ambiguity_samples,
    }


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    ensure_dirs(results_dir)

    dp_path = os.path.join(results_dir, "B_decision_points.jsonl")
    output_path = os.path.join(results_dir, "B_foresight_raw.jsonl")

    if not os.path.exists(dp_path):
        raise FileNotFoundError(f"missing input file {dp_path}, run collect_decision_points.py first.")

    decision_points = read_jsonl_all(dp_path)
    if not decision_points:
        raise RuntimeError(f"{dp_path} contains no decision points; nothing to do.")
    if args.max_points is not None:
        # Smoke-test cap: each decision point costs 7 LLM calls here (base
        # action + world model + foresight re-plan + 4 ambiguity resamples),
        # so an uncapped run on the full 150 points is ~1000 calls -- far too
        # expensive for a pre-flight check.
        decision_points = decision_points[: args.max_points]

    reset_output_file(output_path)
    llm = load_client_from_config(config)

    records = ordered_map(
        lambda dp: _process_point(llm, dp, config["sampling"]),
        decision_points,
        workers=args.workers,
        label="generate_foresight",
        progress_every=10,
    )
    for record in records:
        append_jsonl(output_path, record)

    print(f"[generate_foresight] decision_points={len(decision_points)}\n  -> {output_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="B2-B4, B11: base action, world-model prediction, foresight action, ambiguity."
    )
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    parser.add_argument(
        "--max_points",
        type=int,
        default=None,
        help="Process only the first N decision points (by file order); for cheap smoke tests.",
    )
    add_workers_arg(parser)
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
