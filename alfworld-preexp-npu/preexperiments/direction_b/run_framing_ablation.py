"""Ablation: does the HARM from foresight come from how the imagined future is framed?

Stage 1 found foresight to be net negative (AHR 3.4% vs AIR 0.6%), and reading
the U = -1 cases showed one mechanism over and over:

    base   = 'open drawer 1'          <- already the expert action
    pred   = "You open the drawer 1. In it, you see a bowl."   <- correct
    fore   = 'examine drawer 1'       <- acts as if the drawer were already open
    expert = 'open drawer 1'

    base   = 'move egg 1 to microwave 1'
    pred   = "You arrive at microwave 1. In it, you see a cup 1 and an egg 1."
    fore   = 'heat egg 1 with microwave 1'   <- skips ahead one step

The planner appears to read the predicted observation as something that HAS
happened, and then picks the action that would follow it -- so an *accurate*
prediction is precisely what makes it skip a step. That would explain all three
oddities at once: the 3:1 harm-to-help ratio, the zero confidence-utility
correlation despite confidence tracking correctness (rho = +0.37), and the fact
that raising temperature changed nothing.

But that reading has an alternative: the wording may simply be too weak for a
4B model, in which case "foresight is net harmful" is a statement about our
prompt rather than about foresight. This script separates the two by re-running
the identical states with progressively more explicit framing, holding
everything else fixed:

    a_base and the world-model prediction are REUSED from Stage 1, so the only
    thing that varies across arms is the wording of the block. Temperature 0 and
    the same seed, so any difference is not sampling noise.

If AHR falls as the framing strengthens, the Stage 1 conclusion has to be
restated as "foresight's value depends on how the imagined future is
presented"; if it does not move, the mechanism is not about wording.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config
from preexperiments.common.parallel import add_workers_arg, ordered_map
from preexperiments.direction_b.action_canonicalizer import action_utility, same_action
from preexperiments.direction_b.pipeline import DirectionBPipeline

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_TAB = ROOT / "outputs" / "tables"

# A: exactly what Stage 1 used.
FRAMING_A = """
A world model predicts that executing "{base_action}" would lead to this next
observation:
{prediction}
"""

# B: A plus one explicit sentence that the prediction has not occurred.
FRAMING_B = """
A world model predicts that executing "{base_action}" would lead to this next
observation:
{prediction}

This has NOT happened yet. You are still at the current state described above.
"""

# C: hypothetical framing throughout -- the prediction is labelled as imagined,
# the current state is restated as unchanged, and the question is put in the
# present tense.
FRAMING_C = """
Before acting, you imagined what WOULD happen if you executed "{base_action}":

    [IMAGINED, NOT YET EXECUTED]
    {prediction}

Nothing above has actually happened. No action has been taken. You are still in
the current state and the current observation is unchanged.

Using that imagined outcome only as a hint about whether "{base_action}" is a
good idea, decide what to do NOW.
"""

FRAMINGS = {"A_current": FRAMING_A, "B_not_happened": FRAMING_B, "C_hypothetical": FRAMING_C}


def main(args: argparse.Namespace) -> None:
    ensure_dirs(DATA_DIR, OUT_TAB)
    config = load_yaml_config(args.config)
    db_cfg = config.get("direction_b", {})

    states = {json.loads(l)["state_id"]: json.loads(l)
              for l in open(DATA_DIR / args.states)}
    rows = [json.loads(l) for l in open(DATA_DIR / args.rows)]
    rows = [r for r in rows if r.get("wm_prediction")]
    if args.exclude_noop:
        rows = [r for r in rows if not r["expert_is_noop"]]
    if args.limit:
        rows = rows[: args.limit]
    print(f"[framing] {len(rows)} states x {len(FRAMINGS)} framings "
          f"(a_base and predictions reused from Stage 1)", flush=True)

    llm = load_client_from_config(config)
    pipe = DirectionBPipeline(llm, db_cfg)
    out: List[Dict[str, Any]] = []

    for name, template in FRAMINGS.items():
        def run(r: Dict[str, Any], _tpl=template, _name=name) -> Dict[str, Any]:
            st = states[r["state_id"]]
            a_base = r["baseline_action"]          # reused: identical across arms
            block = _tpl.format(base_action=a_base, prediction=r["wm_prediction"])
            a_fore, forced, _ = pipe._choose(
                pipe._action_prompt(st, block), st["admissible_actions"])
            expert = st["expert_action"]
            return {
                "state_id": r["state_id"],
                "framing": _name,
                "baseline_action": a_base,
                "foresight_action": a_fore,
                "changed": not same_action(a_base, a_fore),
                "action_utility": action_utility(a_base, a_fore, expert),
                "base_matches_expert": same_action(a_base, expert),
                "fore_matches_expert": same_action(a_fore, expert),
                "action_forced": bool(forced),
            }

        out.extend(ordered_map(run, rows, workers=args.workers,
                               label=name, progress_every=100))

    path = DATA_DIR / args.out
    with open(path, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = {}
    base_hit = sum(r["base_matches_expert"] for r in out if r["framing"] == "A_current")
    n = len([r for r in out if r["framing"] == "A_current"])
    print(f"\nbaseline 命中 expert（三臂相同）: {base_hit}/{n} = {base_hit/n:.1%}\n")
    print(f"{'framing':18s} {'ACR':>8s} {'AIR':>8s} {'AHR':>8s} {'净(AIR-AHR)':>12s} "
          f"{'fore命中expert':>14s}")
    for name in FRAMINGS:
        sub = [r for r in out if r["framing"] == name]
        u = [r["action_utility"] for r in sub]
        air, ahr = u.count(1) / len(u), u.count(-1) / len(u)
        hit = sum(r["fore_matches_expert"] for r in sub) / len(sub)
        summary[name] = {"n": len(sub), "ACR": sum(r["changed"] for r in sub) / len(sub),
                         "AIR": air, "AHR": ahr, "net": air - ahr,
                         "fore_match_expert": hit,
                         "U_dist": dict(Counter(u))}
        s = summary[name]
        print(f"{name:18s} {s['ACR']:>7.1%} {air:>7.1%} {ahr:>7.1%} {air-ahr:>11.1%} "
              f"{hit:>13.1%}")

    with open(OUT_TAB / "dirB_framing_ablation.json", "w", encoding="utf-8") as f:
        json.dump({"n_states": n, "summary": summary}, f, indent=2, ensure_ascii=False)
    print(f"\n-> {path}\n-> {OUT_TAB / 'dirB_framing_ablation.json'}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Foresight framing ablation.")
    p.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    p.add_argument("--states", default="sampled_states.jsonl")
    p.add_argument("--rows", default="action_utility.jsonl")
    p.add_argument("--out", default="framing_ablation.jsonl")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--exclude_noop", action="store_true")
    add_workers_arg(p, default=16)
    return p


if __name__ == "__main__":
    os.chdir(ROOT)
    main(build_arg_parser().parse_args())
