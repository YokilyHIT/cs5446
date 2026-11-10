"""Round 6: calibrate the WorldEvolver-style confidence gate for the 14B world model.

The round-1/2 threshold (tau = 0.99943) was calibrated for the 4B world model. Here the frozen Qwen3-14B world model
(role wm_alt, same WORLD_MODEL_PROMPT, no memory) predicts the next observation of the planner's proposed action
(`baseline_action`) on states sampled from that planner's label-pool `none` runs (training-split tasks disjoint
from fresh600). tau = the (1 - usage) quantile of the confidence exp(mean token logprob of the prediction), so the
prediction is shown on about `usage` of steps -- the same 30% target as in round 1/2. Test data are not used.

    $PY -m preexperiments.react_study.calib_selective_r6
"""
from __future__ import annotations

import argparse
import json
import random

import numpy as np

from preexperiments.common.alfworld_runner import format_history
from preexperiments.common.logging_utils import load_yaml_config
from preexperiments.common.parallel import ordered_map
from preexperiments.react_study.common import MeteredLLM, OUT_ROOT, set_role, stage_dir
from preexperiments.react_study.protocol_v2 import CHECK_VALID, PipelineV2


def states(pl):
    out = []
    for rep in (0, 1):
        for l in open(OUT_ROOT / f"r4_common/raw/train/{pl}_label_none__rep{rep}.jsonl"):
            r = json.loads(l)
            hist = []
            for s in r["step_log"]:
                if s["baseline_action"] != CHECK_VALID:
                    out.append({"goal": r["goal"], "hist": list(hist), "obs": s["observation"], "a": s["baseline_action"],
                                "adm": s.get("admissible_actions", [])})
                hist.append((s["action"], s["next_observation"]))
    return out


def main(a):
    config = load_yaml_config(a.config)
    pipe = PipelineV2(MeteredLLM(config), config.get("direction_b", {}), variant="list")
    rng = random.Random(2033)
    res = {"usage_target": a.usage, "wm": "Qwen/Qwen3-14B (wm_alt, thinking off)"}
    for pl in ("p4b", "p14b"):
        xs = states(pl)
        rng.shuffle(xs)
        xs = xs[:a.n]

        def one(x):
            set_role("wm_alt")
            st = {"goal": x["goal"], "history": format_history(x["hist"], max_turns=50), "current_observation": x["obs"],
                  "admissible_actions": x["adm"]}
            c = pipe.predict(st, x["a"])["wm_confidence_logprob"]
            return c if c == c else None
        conf = [c for c in ordered_map(one, xs, workers=a.workers, label=f"calib/{pl}", progress_every=200) if c is not None]
        tau = float(np.quantile(conf, 1 - a.usage))
        res[pl] = {"n": len(conf), "tau": tau, "quantiles": {str(q): float(np.quantile(conf, q)) for q in (0.1, 0.3, 0.5, 0.7, 0.9)}}
        print(f"[calib] {pl}: n={len(conf)} tau(usage {a.usage})={tau:.6f}", flush=True)
    json.dump(res, open(stage_dir(40) / "tables" / "selective_calibration.json", "w"), indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    ap.add_argument("--n", type=int, default=800)
    ap.add_argument("--usage", type=float, default=0.3)
    ap.add_argument("--workers", type=int, default=32)
    main(ap.parse_args())
