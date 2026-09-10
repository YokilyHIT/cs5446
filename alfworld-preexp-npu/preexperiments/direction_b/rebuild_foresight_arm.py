"""Recompute only the foresight arm of Stage 1 under the current framing.

Everything upstream of the foresight block is independent of it:

    a_base                    chosen with no foresight block at all
    ô_{t+1}, C_self, C_logprob  produced by the world model, which never sees it
    true o_{t+1}, correctness  obtained by executing a_base in the environment

Only `foresight_action` and the three fields derived from it change. So instead
of re-running the full pipeline -- whose environment-replay phase costs about an
hour for 500 states -- this rebuilds just the one arm and copies the rest of
each Stage 1 record through unchanged. That also makes the comparison exact:
the two runs share byte-identical baselines rather than merely equivalent ones.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config
from preexperiments.common.parallel import add_workers_arg, ordered_map
from preexperiments.direction_b.action_canonicalizer import action_utility, same_action
from preexperiments.direction_b.pipeline import DirectionBPipeline

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def main(args: argparse.Namespace) -> None:
    ensure_dirs(DATA_DIR)
    config = load_yaml_config(args.config)
    states = {json.loads(l)["state_id"]: json.loads(l)
              for l in open(DATA_DIR / args.states)}
    rows = [json.loads(l) for l in open(DATA_DIR / args.rows)]
    print(f"[rebuild] {len(rows)} rows; recomputing foresight arm only", flush=True)

    llm = load_client_from_config(config)
    pipe = DirectionBPipeline(llm, config.get("direction_b", {}))

    def run(r: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(r)
        if not r.get("wm_prediction"):
            return out  # nothing to show the planner; leave the record as-is
        st = states[r["state_id"]]
        a_base = r["baseline_action"]
        a_fore, forced, _ = pipe.foresight_action(st, a_base, r["wm_prediction"])
        expert = st["expert_action"]
        out.update({
            "foresight_action": a_fore,
            "baseline_changed": not same_action(a_base, a_fore),
            "fore_matches_expert": same_action(a_fore, expert),
            "action_utility": action_utility(a_base, a_fore, expert),
            "action_forced": bool(r.get("action_forced")) or bool(forced),
        })
        return out

    records = ordered_map(run, rows, workers=args.workers,
                          label="rebuild", progress_every=100)
    out_path = DATA_DIR / args.out
    with open(out_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[rebuild] wrote {len(records)} rows -> {out_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Recompute the foresight arm under the current framing.")
    p.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    p.add_argument("--states", default="sampled_states.jsonl")
    p.add_argument("--rows", default="action_utility.jsonl")
    p.add_argument("--out", default="action_utility_framingB.jsonl")
    add_workers_arg(p, default=16)
    return p


if __name__ == "__main__":
    os.chdir(ROOT)
    main(build_arg_parser().parse_args())
