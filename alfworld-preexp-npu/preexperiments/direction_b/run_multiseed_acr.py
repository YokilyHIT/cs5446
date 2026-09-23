"""方案 §41: multi-seed replication of the Action Change Rate.

Stage 1 measured ACR = 13.3% at temperature 0, and with U^action non-zero on
only 14 of 353 states the four-quadrant analysis lost its resolution. Two very
different explanations fit that observation equally well:

    (a) foresight genuinely carries little decision-relevant information, so
        the planner is right not to change its action  -> bad news for the
        direction itself;
    (b) deterministic decoding over-anchors the planner on whatever it answered
        the first time, so the low ACR is an artefact of the measurement setup.

Raising the temperature and watching ACR go up would NOT distinguish them: at
T > 0 the two planner calls differ partly because of sampling noise, whether or
not foresight is present. This script therefore runs a control arm.

    foresight arm : a_base(seed s)   vs  a_fore(seed s, same stored prediction)
    noise arm     : a_base(seed s)   vs  a_base2(seed s + 1000)   [no foresight]

    ACR_foresight - ACR_noise  =  the part of the change actually attributable
                                  to having seen the prediction.

Two details that keep the comparison honest:
  * The world-model prediction is REUSED from Stage 1 rather than regenerated
    per seed, so the foresight content is held fixed and only the planner's
    sampling varies. Regenerating it would confound planner sensitivity with
    world-model variability.
  * At temperature 0 the noise arm is the determinism check the pipeline never
    had: ACR_noise should come out at ~0, which is what licenses reading the
    whole of Stage 1's 13.3% as a genuine foresight effect.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config
from preexperiments.common.parallel import add_workers_arg, ordered_map
from preexperiments.direction_b.action_canonicalizer import action_utility, same_action
from preexperiments.direction_b.pipeline import DirectionBPipeline

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_TAB = ROOT / "outputs" / "tables"
NOISE_SEED_OFFSET = 1000


def main(args: argparse.Namespace) -> None:
    ensure_dirs(DATA_DIR, OUT_TAB)
    config = load_yaml_config(args.config)
    db_cfg = dict(config.get("direction_b", {}))

    states = {json.loads(l)["state_id"]: json.loads(l)
              for l in open(DATA_DIR / args.states)}
    rows = [json.loads(l) for l in open(DATA_DIR / args.rows)]
    # Only states whose Stage-1 prediction parsed: without a stored prediction
    # there is no fixed foresight content to re-show.
    rows = [r for r in rows if r.get("wm_prediction")]
    if args.exclude_noop:
        rows = [r for r in rows if not r["expert_is_noop"]]
    if args.limit:
        rows = rows[: args.limit]
    print(f"[multiseed] {len(rows)} states, temps={args.temps}, seeds={args.seeds}", flush=True)

    llm = load_client_from_config(config)
    out_records: List[Dict[str, Any]] = []

    for temp in args.temps:
        for seed in args.seeds:
            cfg = {**db_cfg, "temperature": temp, "seed": seed}
            pipe = DirectionBPipeline(llm, cfg)
            noise_pipe = DirectionBPipeline(llm, {**cfg, "seed": seed + NOISE_SEED_OFFSET})

            def run(r: Dict[str, Any], _pipe=pipe, _npipe=noise_pipe,
                    _t=temp, _s=seed) -> Dict[str, Any]:
                st = states[r["state_id"]]
                state = {**st, "admissible_actions": st["admissible_actions"]}
                a_base, _, _ = _pipe.baseline_action(state)
                a_base2, _, _ = _npipe.baseline_action(state)          # noise arm
                a_fore, _, _ = _pipe.foresight_action(                  # foresight arm
                    state, a_base, r["wm_prediction"])
                expert = st["expert_action"]
                return {
                    "state_id": r["state_id"],
                    "temperature": _t,
                    "seed": _s,
                    "baseline_action": a_base,
                    "baseline_action_noise": a_base2,
                    "foresight_action": a_fore,
                    "changed_by_foresight": not same_action(a_base, a_fore),
                    "changed_by_noise": not same_action(a_base, a_base2),
                    "action_utility": action_utility(a_base, a_fore, expert),
                    "base_matches_expert": same_action(a_base, expert),
                    "fore_matches_expert": same_action(a_fore, expert),
                }

            recs = ordered_map(run, rows, workers=args.workers,
                               label=f"T={temp} seed={seed}", progress_every=100)
            out_records.extend(recs)

    out_path = DATA_DIR / args.out
    with open(out_path, "w", encoding="utf-8") as f:
        for r in out_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- summary: mean +- std across seeds, per temperature (方案 §41) ----
    summary = {}
    print(f"\n{'temp':>6s} {'ACR_fore':>18s} {'ACR_noise':>18s} {'净效应':>16s} "
          f"{'AIR':>14s} {'AHR':>14s}")
    for temp in args.temps:
        per_seed = []
        for seed in args.seeds:
            sub = [r for r in out_records if r["temperature"] == temp and r["seed"] == seed]
            if not sub:
                continue
            u = [r["action_utility"] for r in sub]
            per_seed.append({
                "seed": seed,
                "acr_foresight": sum(r["changed_by_foresight"] for r in sub) / len(sub),
                "acr_noise": sum(r["changed_by_noise"] for r in sub) / len(sub),
                "air": u.count(1) / len(u),
                "ahr": u.count(-1) / len(u),
                "n": len(sub),
            })
        if not per_seed:
            continue
        agg = lambda k: (float(np.mean([p[k] for p in per_seed])),  # noqa: E731
                         float(np.std([p[k] for p in per_seed])))
        af_m, af_s = agg("acr_foresight")
        an_m, an_s = agg("acr_noise")
        ai_m, ai_s = agg("air")
        ah_m, ah_s = agg("ahr")
        summary[str(temp)] = {"per_seed": per_seed,
                              "acr_foresight_mean": af_m, "acr_foresight_std": af_s,
                              "acr_noise_mean": an_m, "acr_noise_std": an_s,
                              "net_effect": af_m - an_m,
                              "air_mean": ai_m, "air_std": ai_s,
                              "ahr_mean": ah_m, "ahr_std": ah_s}
        print(f"{temp:>6.1f} {af_m:>10.1%}±{af_s:<6.1%} {an_m:>10.1%}±{an_s:<6.1%} "
              f"{af_m - an_m:>15.1%} {ai_m:>8.1%}±{ai_s:<4.1%} {ah_m:>8.1%}±{ah_s:<4.1%}")

    path = OUT_TAB / "dirB_multiseed_acr.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"temps": args.temps, "seeds": args.seeds,
                   "n_states": len(rows), "summary": summary}, f, indent=2)
    print(f"\n净效应 = ACR_foresight - ACR_noise，即真正归因于'看到预测'的部分")
    print(f"-> {out_path}\n-> {path}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="方案 §41 multi-seed ACR replication with a noise-floor control.")
    p.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    p.add_argument("--states", default="sampled_states.jsonl")
    p.add_argument("--rows", default="action_utility.jsonl")
    p.add_argument("--out", default="multiseed_acr.jsonl")
    p.add_argument("--temps", type=float, nargs="*", default=[0.0, 0.3, 0.7])
    p.add_argument("--seeds", type=int, nargs="*", default=[101, 102, 103])
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--exclude_noop", action="store_true")
    add_workers_arg(p, default=16)
    return p


if __name__ == "__main__":
    os.chdir(ROOT)
    main(build_arg_parser().parse_args())
