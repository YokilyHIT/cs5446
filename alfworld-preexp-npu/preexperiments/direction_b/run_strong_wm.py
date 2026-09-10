"""The Strong-WM arm: rerun the world model with Episodic Memory (方案 §35.3).

Why the whole Stage 1 conclusion needs this arm. Our zero-shot world model
scores Token F1 53.3%, above every zero-shot row WorldEvolver reports, but their
full system reaches 76.8% and their `w/o MS` ablation -- Episodic Memory alone,
no semantic memory -- already reaches 72.6%. So everything measured so far
(Always-Foresight net -0.8%, Oracle headroom +1.4pp) was measured on a world
model reproducing their ABLATION, not their system. "Confidence does not
represent usefulness" is a much weaker claim if it only holds when the
prediction is half wrong.

The A/B is exact rather than merely matched. Both arms reuse, byte for byte:

    a_base                   the planner's no-foresight choice
    true o_{t+1}             obtained by executing a_base in the environment

so only the world-model prompt differs (one `## Retrieved similar past
transitions` block), and the foresight arm downstream differs only through the
prediction that block produces. No environment replay is needed here at all --
`true_next_observation` depends on a_base, which is unchanged.

Retrieval is causally filtered: see `episodic_memory.retrieve`. A state at
(episode e, step t) cannot see its own episode at step >= t.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from preexperiments.common.embeddings import Embedder
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config
from preexperiments.common.parallel import add_workers_arg, ordered_map
from preexperiments.direction_b import metrics
from preexperiments.direction_b.action_canonicalizer import action_utility, same_action
from preexperiments.direction_b.episodic_memory import EpisodicMemory
from preexperiments.direction_b.pipeline import DirectionBPipeline

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_TAB = ROOT / "outputs" / "tables"

_METRICS = ["exact_match", "token_f1", "fact_f1", "cosine"]


def _mean(xs: List[float]) -> float:
    xs = [x for x in xs if isinstance(x, (int, float)) and not math.isnan(x)]
    return sum(xs) / len(xs) if xs else float("nan")


def main(args: argparse.Namespace) -> None:
    ensure_dirs(DATA_DIR, OUT_TAB)
    config = load_yaml_config(args.config)

    states = {json.loads(l)["state_id"]: json.loads(l)
              for l in open(DATA_DIR / args.states)}
    rows = [json.loads(l) for l in open(DATA_DIR / args.rows)]
    memory = EpisodicMemory.load(DATA_DIR / args.bank, k=args.k)
    print(f"[strongwm] {len(rows)} rows, bank has {len(memory.entries)} transitions, "
          f"k_ME={args.k}", flush=True)

    llm = load_client_from_config(config)
    pipe = DirectionBPipeline(llm, config.get("direction_b", {}))
    embedder = Embedder(config)

    def run(r: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(r)
        st = states[r["state_id"]]
        a_base = r["baseline_action"]

        block = memory.render(a_base, episode_id=r.get("episode_id"),
                              step_id=int(r["step_id"]))
        hits = len(memory.retrieve(a_base, episode_id=r.get("episode_id"),
                                   step_id=int(r["step_id"])))
        pred = pipe.predict(st, a_base, memory_block=block)
        out.update(pred)
        out["memory_hits"] = hits

        # correctness against the SAME ground truth Stage 1 recorded
        o_next = r.get("true_next_observation")
        if o_next:
            corr = metrics.all_metrics(pred["wm_prediction"] or "", o_next, embedder=embedder)
            out.update({f"correctness_{k}": v for k, v in corr.items()})

        # foresight arm, identical framing B block as the Weak run
        if pred["wm_prediction"]:
            a_fore, forced, _ = pipe.foresight_action(st, a_base, pred["wm_prediction"])
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
                          label="strongwm", progress_every=100)
    out_path = DATA_DIR / args.out
    with open(out_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---------------- Weak vs Strong ----------------
    scored = [(w, s) for w, s in zip(rows, records) if w.get("true_next_observation")]
    print(f"\n=== world-model prediction quality (n={len(scored)}) ===")
    print(f"{'metric':14s} {'Weak (0-shot)':>14s} {'Strong (EM)':>13s} {'delta':>9s}")
    summary: Dict[str, Any] = {"n": len(scored), "k_ME": args.k,
                               "bank_size": len(memory.entries)}
    for m in _METRICS:
        w = _mean([x[0].get(f"correctness_{m}") for x in scored])
        s = _mean([x[1].get(f"correctness_{m}") for x in scored])
        summary[m] = {"weak": w, "strong": s, "delta": s - w}
        print(f"{m:14s} {w:>13.2%} {s:>12.2%} {(s-w)*100:>+7.2f}pp")

    hits = [r.get("memory_hits", 0) for r in records]
    summary["retrieval"] = {"mean_hits": _mean([float(h) for h in hits]),
                            "empty_rate": sum(h == 0 for h in hits) / len(hits)}
    print(f"\nretrieved transitions: mean {summary['retrieval']['mean_hits']:.2f}/{args.k}, "
          f"empty (falls back to 0-shot) {summary['retrieval']['empty_rate']:.1%}")

    # action-level, non-noop, so it is directly comparable to Stage 1's table
    nn = [(w, s) for w, s in zip(rows, records) if not w["expert_is_noop"]]
    print(f"\n=== action level, non-noop (n={len(nn)}) ===")
    print(f"{'arm':10s} {'ACR':>7s} {'AIR':>7s} {'AHR':>7s} {'net':>8s} {'fore==expert':>13s}")
    for name, idx in (("Weak", 0), ("Strong", 1)):
        sub = [x[idx] for x in nn if x[idx].get("action_utility") is not None]
        u = [r["action_utility"] for r in sub]
        air, ahr = u.count(1) / len(u), u.count(-1) / len(u)
        acr = sum(r["baseline_changed"] for r in sub) / len(sub)
        hit = sum(r["fore_matches_expert"] for r in sub) / len(sub)
        summary[f"action_{name.lower()}"] = {"n": len(sub), "ACR": acr, "AIR": air,
                                             "AHR": ahr, "net": air - ahr,
                                             "fore_match_expert": hit}
        print(f"{name:10s} {acr:>6.1%} {air:>6.1%} {ahr:>6.1%} {air-ahr:>7.1%} {hit:>12.1%}")
    base_hit = sum(x[0]["base_matches_expert"] for x in nn) / len(nn)
    summary["base_match_expert"] = base_hit
    print(f"{'(no fore)':10s} {'-':>6s} {'-':>6s} {'-':>6s} {'-':>7s} {base_hit:>12.1%}")

    with open(OUT_TAB / "dirB_strong_wm.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n-> {out_path}\n-> {OUT_TAB / 'dirB_strong_wm.json'}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Strong-WM arm: world model + Episodic Memory.")
    p.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    p.add_argument("--states", default="sampled_states.jsonl")
    p.add_argument("--rows", default="action_utility_framingB.jsonl")
    p.add_argument("--bank", default="transition_bank.jsonl")
    p.add_argument("--k", type=int, default=5, help="k_ME (paper default 5)")
    p.add_argument("--out", default="action_utility_strongwm.jsonl")
    add_workers_arg(p, default=16)
    return p


if __name__ == "__main__":
    os.chdir(ROOT)
    main(build_arg_parser().parse_args())
