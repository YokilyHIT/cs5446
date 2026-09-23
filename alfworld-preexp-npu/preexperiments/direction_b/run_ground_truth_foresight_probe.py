"""Ground-truth foresight probe: does foresight still cause a skip when the
"prediction" it is shown is not a world-model guess but the environment's own
real next observation?

Motivation (follow-up to the framing ablation in run_framing_ablation.py):
that script showed the harm from foresight does not go away by rewording the
block, and the U=-1 cases read as the planner treating an ACCURATE prediction
as something that has already happened, then choosing the action that would
follow it -- e.g.

    base   = 'open drawer 1'
    pred   = "You open the drawer 1. In it, you see a bowl."   (correct)
    fore   = 'examine drawer 1'      <- acts as if the drawer were open already

If that reading is right, the mechanism should be even easier to trigger with
a GROUND-TRUTH next observation than with the world model's (sometimes wrong)
guess -- there is no prediction error left to hide behind. This script tests
exactly that, and does it under both reasoning modes pipeline.py now supports
(direct / react), to check whether switching to WorldEvolver's own free-form
ReAct format changes the picture.

Procedure, per sampled state (holding a_base fixed, reused from Stage 1 --
same discipline as run_framing_ablation.py):

    1. preexperiments.common.replay_state.restore_state rebuilds the EXACT
       ALFWorld state at the decision point, in its own independent adapter
       (a fresh env instance untouched by anything else in this script or by
       the planner call in step 3) -- this is the ONLY sanctioned way to get
       back to that state (see replay_state.py's module docstring).
    2. That independent env executes a_base for real, producing the TRUE next
       observation o_true and the admissible actions available after it. This
       is ground truth, not a world-model prediction.
    3. o_true is handed to the Planner AT THE ORIGINAL, UN-ADVANCED state h_t,
       using the identical FORESIGHT_BLOCK wording pipeline.py already uses
       ("This has NOT happened yet..."), under EACH reasoning mode in turn.
       The planner's own state is never advanced -- it only ever sees h_t plus
       the foresight block, exactly like every other foresight call in this
       codebase.
    4. a_fore is compared to a_base and to the expert action, AND to whether
       it looks like a skip: `skip_like` is true when a_fore differs from
       a_base, is NOT a legal action at h_t, but IS a legal action at the
       state AFTER a_base has actually been executed -- i.e. it only makes
       sense if the world had already moved past h_t. This is a LOWER BOUND,
       not a complete detector -- see `_skip_like`'s docstring: ALFWorld
       usually offers "examine X" unconditionally, so the flagship example
       quoted above (open drawer 1 -> examine drawer 1) will typically NOT
       trip it even though it is exactly this pattern.

Every prompt, raw LLM response, and piece of environment feedback is saved so
the qualitative cases can be re-read the same way the Stage 1 U=-1 cases were
-- `skip_like` narrows down where to look, it does not replace doing so.

A `restore_state` mismatch (StateRestoreError) is NOT silently skipped: it is
recorded as its own row (row_type="restore_error", with the raised message) so
a state whose replay cannot be trusted is visible in the output rather than
missing from it, while letting the batch continue past a single bad state --
unlike the mandatory unit test (spec section 37, test 3), this script is an
exploratory diagnostic over many states, not the single correctness gate that
must halt experiment B on any mismatch.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from preexperiments.common.alfworld_runner import extract_admissible
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config
from preexperiments.common.parallel import add_workers_arg, ordered_map
from preexperiments.common.replay_state import StateRestoreError, restore_state
from preexperiments.direction_b.action_canonicalizer import action_utility, same_action
from preexperiments.direction_b.pipeline import DirectionBPipeline

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_TAB = ROOT / "outputs" / "tables"

MODES = ("direct", "react")


def _replay_one(config: Dict[str, Any], split: str, state: Dict[str, Any], a_base: str) -> Dict[str, Any]:
    """Phase 1: independent env, real a_base execution -> ground-truth o_true.

    Serial by design (see module docstring): build_single_game_adapter
    re-enumerates the whole split per call, so this is I/O-heavy regardless of
    thread count, and every TextWorld call is globally lock-serialised anyway
    (alfworld_runner._ENV_LOCK).
    """
    try:
        restored = restore_state(
            config=config,
            split=split,
            game_id_or_path=state["gamefile"],
            action_prefix=state["action_prefix"],
            expected_observation=state["current_observation"],
            strict=True,
        )
    except StateRestoreError as e:
        return {"state_id": state["state_id"], "row_type": "restore_error", "error": str(e)}

    if a_base not in restored.admissible_actions:
        return {
            "state_id": state["state_id"],
            "row_type": "restore_error",
            "error": (
                f"baseline_action {a_base!r} is not admissible after restore "
                f"(admissible={restored.admissible_actions}); the recorded "
                f"action_utility row and the restored env have drifted apart."
            ),
        }

    next_obs, done, success, info2 = restored.adapter.step(a_base)
    return {
        "state_id": state["state_id"],
        "row_type": "episode_ended" if done else "ok",
        "baseline_action": a_base,
        "true_next_observation": next_obs,
        "done": done,
        "success": success,
        "admissible_before": list(state["admissible_actions"]),
        "admissible_after": [] if done else extract_admissible(info2),
    }


def _skip_like(a_base: str, a_fore: str, admissible_before: List[str], admissible_after: List[str]) -> bool:
    """Code-checkable version of "acts as if the predicted step already
    happened": a_fore differs from a_base, is not legal at h_t, but IS legal
    at the state that comes after a_base actually executes.

    This is a LOWER BOUND on the skip phenomenon, not a complete detector, and
    it is worth being explicit about why: it only fires for actions gated on
    physical state (e.g. "take bowl 1 from drawer 1", "heat egg 1 with
    microwave 1" -- only admissible once the drawer is open / the agent has
    arrived). ALFWorld's admissible-command list generally offers "examine X"
    / "look" unconditionally regardless of whether a receptacle is open, so
    the flagship example quoted in this module's docstring (open drawer 1 ->
    examine drawer 1) is IN `admissible_before` and will NOT be flagged by
    this function even though it is exactly the skip pattern being probed.
    That is why every prompt/raw response is saved: `skip_like` narrows down
    where to look, it does not replace reading the cases, the same way Stage
    1's U=-1 cases were read manually rather than auto-classified.
    """
    if same_action(a_base, a_fore):
        return False
    if a_fore in admissible_before:
        return False
    return a_fore in admissible_after


def main(args: argparse.Namespace) -> None:
    ensure_dirs(DATA_DIR, OUT_TAB)
    config = load_yaml_config(args.config)
    db_cfg = config.get("direction_b", {})
    split = config["splits"]["experience"]  # sampled states come from the train split

    states = {json.loads(l)["state_id"]: json.loads(l)
              for l in open(DATA_DIR / args.states)}
    rows = [json.loads(l) for l in open(DATA_DIR / args.rows)]
    rows = [r for r in rows if r.get("baseline_action")]
    if args.exclude_noop:
        rows = [r for r in rows if not r["expert_is_noop"]]
    if args.limit:
        rows = rows[: args.limit]
    modes = args.modes or list(MODES)
    print(f"[gt_foresight_probe] {len(rows)} states x {len(modes)} reasoning modes "
          f"(a_base reused from Stage 1; foresight prediction = ground truth, not WM)",
          flush=True)

    # ---- Phase 1: independent-env ground truth, serial (see docstring) ----
    replayed: List[Dict[str, Any]] = []
    for i, r in enumerate(rows):
        st = states[r["state_id"]]
        replayed.append(_replay_one(config, split, st, r["baseline_action"]))
        if (i + 1) % 20 == 0 or i + 1 == len(rows):
            print(f"[gt_foresight_probe] replay {i+1}/{len(rows)}", flush=True)

    ok_pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = [
        (r, rep) for r, rep in zip(rows, replayed) if rep["row_type"] == "ok"
    ]
    n_restore_err = sum(rep["row_type"] == "restore_error" for rep in replayed)
    n_ended = sum(rep["row_type"] == "episode_ended" for rep in replayed)
    print(f"[gt_foresight_probe] {len(ok_pairs)}/{len(rows)} states replayed cleanly "
          f"({n_restore_err} restore errors, {n_ended} ended on a_base)", flush=True)

    # ---- Phase 2: LLM foresight calls, parallel, one pipeline per mode ----
    llm = load_client_from_config(config)
    pipes = {m: DirectionBPipeline(llm, {**db_cfg, "reasoning_mode": m}) for m in modes}

    def run(pair: Tuple[Dict[str, Any], Dict[str, Any]]) -> List[Dict[str, Any]]:
        r, rep = pair
        st = states[r["state_id"]]
        a_base = rep["baseline_action"]
        expert = st["expert_action"]
        out_rows = []
        for mode in modes:
            a_fore, forced, _tokens, diag = pipes[mode].foresight_action_ex(
                st, a_base, rep["true_next_observation"])
            out_rows.append({
                "state_id": r["state_id"],
                "row_type": "probe",
                "reasoning_mode": mode,
                "episode_id": st["episode_id"],
                "task_type": st["task_type"],
                "step_id": st["step_id"],
                "expert_action": expert,
                "baseline_action": a_base,
                "true_next_observation": rep["true_next_observation"],
                "foresight_action": a_fore,
                "action_forced": bool(forced),
                "action_matched_admissible": bool(diag["matched"]),
                "changed": not same_action(a_base, a_fore),
                "base_matches_expert": same_action(a_base, expert),
                "fore_matches_expert": same_action(a_fore, expert),
                "action_utility": action_utility(a_base, a_fore, expert),
                "skip_like": _skip_like(a_base, a_fore, rep["admissible_before"], rep["admissible_after"]),
                "foresight_prompt": diag["prompt"],
                "foresight_raw_response": diag["raw_response"],
            })
        return out_rows

    probe_groups = ordered_map(run, ok_pairs, workers=args.workers,
                               label="foresight", progress_every=50)
    probe_rows = [row for group in probe_groups for row in group]

    out_path = DATA_DIR / args.out
    with open(out_path, "w", encoding="utf-8") as f:
        for rep in replayed:
            f.write(json.dumps(rep, ensure_ascii=False) + "\n")
        for row in probe_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ---- summary, per reasoning mode ----
    summary: Dict[str, Any] = {
        "n_states": len(rows), "n_replayed_ok": len(ok_pairs),
        "n_restore_error": n_restore_err, "n_episode_ended_on_base": n_ended,
        "modes": {},
    }
    print(f"\n{'mode':10s} {'n':>5s} {'ACR':>8s} {'AIR':>8s} {'AHR':>8s} {'net':>8s} "
          f"{'skip_like>=':>11s} {'fore==expert':>13s} {'forced':>8s}")
    for mode in modes:
        sub = [r for r in probe_rows if r["reasoning_mode"] == mode]
        if not sub:
            continue
        u = [r["action_utility"] for r in sub]
        acr = sum(r["changed"] for r in sub) / len(sub)
        air, ahr = u.count(1) / len(u), u.count(-1) / len(u)
        skip_rate = sum(r["skip_like"] for r in sub) / len(sub)
        hit = sum(r["fore_matches_expert"] for r in sub) / len(sub)
        forced_rate = sum(r["action_forced"] for r in sub) / len(sub)
        summary["modes"][mode] = {
            "n": len(sub), "ACR": acr, "AIR": air, "AHR": ahr, "net": air - ahr,
            "skip_like_rate": skip_rate, "fore_match_expert": hit,
            "action_forced_rate": forced_rate,
        }
        print(f"{mode:10s} {len(sub):>5d} {acr:>7.1%} {air:>7.1%} {ahr:>7.1%} "
              f"{air - ahr:>7.1%} {skip_rate:>10.1%} {hit:>12.1%} {forced_rate:>7.1%}")

    with open(OUT_TAB / "dirB_ground_truth_foresight_probe.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n-> {out_path}\n-> {OUT_TAB / 'dirB_ground_truth_foresight_probe.json'}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Ground-truth foresight probe: does an ACCURATE (real env, "
                    "not world-model) next observation still cause the planner "
                    "to skip a step, under direct vs react reasoning?")
    p.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    p.add_argument("--states", default="sampled_states.jsonl")
    p.add_argument("--rows", default="action_utility.jsonl")
    p.add_argument("--out", default="ground_truth_foresight_probe.jsonl")
    p.add_argument("--modes", nargs="+", choices=list(MODES), default=None,
                   help="default: both direct and react")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--exclude_noop", action="store_true")
    add_workers_arg(p, default=8)
    return p


if __name__ == "__main__":
    os.chdir(ROOT)
    main(build_arg_parser().parse_args())
