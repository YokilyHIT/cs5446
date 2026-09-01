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
import os
from collections import Counter
from typing import Any, Dict

from preexperiments.common import prompts
from preexperiments.common.alfworld_runner import choose_action, format_admissible, ground_action
from preexperiments.common.llm_client import load_client_from_config
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


def _process_point(llm, dp: Dict[str, Any]) -> Dict[str, Any]:
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
    )

    # B3: world-model prediction + self confidence.
    wm_prompt = prompts.WORLD_MODEL_PREDICTION_PROMPT.format(
        goal=goal,
        observation=observation,
        history=history_text,
        base_action=base_action,
    )
    wm_resp = llm.complete(wm_prompt, seed=_BASE_SEED)
    wm_prediction, self_confidence = parse_prediction_confidence(wm_resp.text)

    # B4: foresight-conditioned re-planning at the same state.
    foresight_prompt = prompts.FORESIGHT_CONDITIONED_ACTION_PROMPT.format(
        goal=goal,
        observation=observation,
        admissible_actions=format_admissible(admissible_actions),
        base_action=base_action,
        predicted_next_observation=wm_prediction,
    )
    foresight_resp = llm.complete(foresight_prompt, seed=_BASE_SEED)
    foresight_action, _ = ground_action(foresight_resp.text, admissible_actions)
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

    reset_output_file(output_path)
    llm = load_client_from_config(config)

    for i, dp in enumerate(decision_points):
        record = _process_point(llm, dp)
        append_jsonl(output_path, record)
        if (i + 1) % 10 == 0 or (i + 1) == len(decision_points):
            print(f"[generate_foresight] processed {i + 1}/{len(decision_points)}")

    print(f"[generate_foresight] decision_points={len(decision_points)}\n  -> {output_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="B2-B4, B11: base action, world-model prediction, foresight action, ambiguity."
    )
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
