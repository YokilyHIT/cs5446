"""
Experiment B5-B6 (spec sections 24-25): for each decision point, restore the
exact ALFWorld state twice and run the two counterfactual branches:

  Branch 0 (base):      execute `base_action`, then continue with the base
                         ReAct planner to success/done/max_steps.
  Branch W (foresight):  execute `foresight_action`, then continue with the
                         base ReAct planner to success/done/max_steps.

`planning_gain = Y_W - Y_0 in {-1,0,+1}` is the paired, state-matched causal
comparison this whole experiment is built around -- it only has a valid
causal interpretation if both branches genuinely start from the identical
state, which is exactly what replay_state.restore_state() guarantees (see
its module docstring). Per spec section 39, if restore fails on more than
10% of points, this script raises instead of silently continuing: a state
mismatch means Delta_t has no causal interpretation and experiment B must
not proceed.
"""
from __future__ import annotations

import argparse
import os
from typing import Any, Dict, List, Tuple

from preexperiments.common.alfworld_runner import rollout
from preexperiments.common.embeddings import Embedder, cosine_sim
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import append_jsonl, ensure_dirs, load_yaml_config, new_run_id, read_jsonl_all
from preexperiments.common.parallel import add_workers_arg, ordered_map
from preexperiments.common.replay_state import StateRestoreError, restore_state
from preexperiments.world_model_utility._common import reset_output_file

_SEED = 13
_MAX_RESTORE_FAILURE_RATIO = 0.10


def _join(decision_points_path: str, foresight_path: str) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    decision_points = {r["point_id"]: r for r in read_jsonl_all(decision_points_path)}
    foresight = read_jsonl_all(foresight_path)
    if not foresight:
        raise RuntimeError(f"{foresight_path} contains no records; nothing to do.")

    joined = []
    for fr in foresight:
        dp = decision_points.get(fr["point_id"])
        if dp is None:
            print(
                f"[build_counterfactual_pairs] warning: point_id {fr['point_id']!r} in "
                f"{foresight_path} has no matching decision point, skipping."
            )
            continue
        joined.append((dp, fr))
    joined.sort(key=lambda pair: pair[0]["point_id"])
    return joined


def _run_branches(
    *,
    config: Dict[str, Any],
    llm,
    embedder: Embedder,
    split: str,
    dp: Dict[str, Any],
    fr: Dict[str, Any],
) -> Dict[str, Any]:
    task_id = dp["task_id"]
    game_id_or_path = dp["game_id_or_path"]
    action_prefix = dp["action_prefix"]
    observation = dp["observation"]
    # What the env actually emits at this state -- equals `observation` except
    # at step 0, where the goal sentence was stripped for prompting. See
    # collect_decision_points.py::raw_state_obs. Falls back to `observation`
    # for decision-point files written before that field existed.
    restore_observation = dp.get("restore_observation", observation)
    goal = dp["goal"]
    step = dp["step"]
    base_action = fr["base_action"]
    foresight_action = fr["foresight_action"]

    # Both branches get the SAME step budget counted from the decision point,
    # rather than sharing the global episode cap. With decision points now
    # spread across the whole episode (steps 0..29 observed), the old
    # "max_episode_steps - t" budget left a point at step 29 with one step per
    # branch: both fail, Delta_t = 0, and that 0 says nothing about foresight --
    # only that neither branch was given room to finish. Identical budgets keep
    # the paired comparison valid.
    branch_budget = config["experiment_b"].get(
        "branch_rollout_budget", config["sampling"]["max_episode_steps"]
    )

    restored0 = restore_state(
        config=config,
        split=split,
        game_id_or_path=game_id_or_path,
        action_prefix=action_prefix,
        expected_observation=restore_observation,
        strict=True,
    )

    # B5 semantic correctness + Branch 0's first step are the same
    # execution of `base_action` -- do not run it twice.
    o_next_true, done0, success0, info0 = restored0.adapter.step(base_action)
    restored0.adapter._last_info = info0
    semantic_correctness = cosine_sim(
        embedder.encode_one(fr["wm_prediction"]), embedder.encode_one(o_next_true)
    )

    if done0:
        y0 = success0
    else:
        result0 = rollout(
            restored0.adapter,
            llm=llm,
            config=config,
            run_id=new_run_id("B0"),
            task_id=task_id,
            game_id_or_path=game_id_or_path,
            split=split,
            seed=_SEED,
            goal=goal,
            observation=o_next_true,
            history=[(base_action, o_next_true)],
            start_step=step + 1,
            # Branch 0 already spent one step executing base_action above, so
            # it resumes at step+1 and stops at the same absolute index as
            # Branch W: both get exactly `branch_budget` steps from the
            # decision point.
            max_steps=step + branch_budget,
            lesson=None,
        )
        y0 = result0.success

    if not fr["action_changed"]:
        # a_t^(W) == a_t^(0): Branch W would execute the identical action from
        # the identical restored state and then continue with the identical
        # planner, so Y_W == Y_0 by construction and Delta_t == 0. Asserting
        # that is strictly better than measuring it, for two reasons:
        #   * Correctness. vLLM's batched sampling is not reproducible under
        #     concurrency (same prompt + same seed diverges when the batch
        #     composition differs -- verified on this host). Re-running the
        #     identical branch could therefore split into Delta_t = +-1 purely
        #     from batch numerics, manufacturing mismatch signal in exactly the
        #     statistic experiment B reports.
        #   * Cost. Unchanged points are typically the majority, and this
        #     halves their rollout cost.
        yw = y0
    else:
        # Branch W needs a fresh, second restore -- Branch 0 already advanced
        # the first restored env and cannot be reused for the counterfactual.
        restoredw = restore_state(
            config=config,
            split=split,
            game_id_or_path=game_id_or_path,
            action_prefix=action_prefix,
            expected_observation=restore_observation,
            strict=True,
        )
        resultw = rollout(
            restoredw.adapter,
            llm=llm,
            config=config,
            run_id=new_run_id("BW"),
            task_id=task_id,
            game_id_or_path=game_id_or_path,
            split=split,
            seed=_SEED,
            goal=goal,
            observation=observation,
            history=[],
            start_step=step,
            max_steps=step + branch_budget,
            forced_first_action=foresight_action,
            lesson=None,
        )
        yw = resultw.success

    return {
        "point_id": dp["point_id"],
        "task_id": task_id,
        "step": step,
        "base_action": base_action,
        "foresight_action": foresight_action,
        "action_changed": fr["action_changed"],
        "wm_prediction": fr["wm_prediction"],
        "self_confidence": fr["self_confidence"],
        # 预注册的替代信号，见 generate_foresight.py 顶部注释
        "confidence_separate": fr.get("confidence_separate", float("nan")),
        "logprob_prob": fr.get("logprob_prob", float("nan")),
        "base_action_is_noop": fr.get("base_action_is_noop", None),
        "semantic_correctness": semantic_correctness,
        "base_success": bool(y0),
        "foresight_success": bool(yw),
        "planning_gain": int(yw) - int(y0),
        "ambiguity": fr["ambiguity"],
    }


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    results_dir = config["paths"]["results_dir"]
    ensure_dirs(results_dir)

    dp_path = os.path.join(results_dir, "B_decision_points.jsonl")
    fr_path = os.path.join(results_dir, "B_foresight_raw.jsonl")
    out_path = os.path.join(results_dir, "B_branches_raw.jsonl")
    fail_path = os.path.join(results_dir, "B_restore_failures.jsonl")

    for p in (dp_path, fr_path):
        if not os.path.exists(p):
            raise FileNotFoundError(f"missing input file {p}, run the earlier experiment B scripts first.")

    joined = _join(dp_path, fr_path)
    if args.max_points is not None:
        joined = joined[: args.max_points]

    reset_output_file(out_path)
    reset_output_file(fail_path)

    split = config["splits"]["evaluation"]
    llm = load_client_from_config(config)
    embedder = Embedder(config)

    n_total = len(joined)

    def run_pair(pair):
        dp, fr = pair
        try:
            return ("ok", _run_branches(config=config, llm=llm, embedder=embedder,
                                        split=split, dp=dp, fr=fr))
        except StateRestoreError as e:
            # Caught per-point rather than allowed to propagate: a handful of
            # unrestorable points is expected and is what the fail_ratio check
            # below exists to judge, so one of them must not kill the pool and
            # discard every other point's rollouts.
            return ("restore_failed", {
                "point_id": dp["point_id"],
                "task_id": dp["task_id"],
                "game_id_or_path": dp["game_id_or_path"],
                "error": str(e),
            })

    outcomes = ordered_map(run_pair, joined, workers=args.workers,
                           label="build_counterfactual_pairs", progress_every=5)

    n_written = n_failed = 0
    for status, payload in outcomes:
        if status == "ok":
            append_jsonl(out_path, payload)
            n_written += 1
        else:
            append_jsonl(fail_path, payload)
            n_failed += 1
            print(f"[build_counterfactual_pairs] WARNING: restore failed for "
                  f"{payload['point_id']}: {payload['error']}")

    fail_ratio = (n_failed / n_total) if n_total else 0.0
    print(
        f"[build_counterfactual_pairs] total={n_total} written={n_written} failed={n_failed} "
        f"fail_ratio={fail_ratio:.3f}\n  -> {out_path}\n  -> {fail_path}"
    )

    if n_total > 0 and fail_ratio > _MAX_RESTORE_FAILURE_RATIO:
        raise RuntimeError(
            f"restore_state failed on {n_failed}/{n_total} ({fail_ratio:.1%}) decision points, "
            f"exceeding the {_MAX_RESTORE_FAILURE_RATIO:.0%} hard limit. Per spec section 39, "
            f"deterministic replay failing at this rate means Delta_t has no causal "
            f"interpretation and experiment B must not proceed -- fix restore_state()/its "
            f"assumptions (see scripts/inspect_alfworld_api.py) before re-running."
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="B5-B6: restore each decision point twice and run the Branch0/BranchW counterfactual rollouts."
    )
    parser.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    parser.add_argument(
        "--max_points",
        type=int,
        default=None,
        help="Process only the first N decision points (by point_id); for cheap smoke tests.",
    )
    add_workers_arg(parser)
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
