"""Stage 1: Action-Level Diagnostic (方案 §17, §18).

For every sampled expert state:

    1. Planner            -> a_base
    2. World Model        -> ô_{t+1}, C_self, C_logprob
    3. Planner + foresight-> a_fore
    4. Compare both to the expert action a*
    5. U^action = 1[a_fore == a*] - 1[a_base == a*]   in {-1, 0, +1}

Prediction correctness is stored SEPARATELY from confidence (方案 §10), against
the true next observation obtained by actually executing a_base in a forked
copy of the environment. Four correctness metrics are recorded -- Exact Match,
Token F1, Fact-F1, cosine -- because WorldEvolver validates its confidence
against Exact Match and Token F1, and because the previous round relied on
cosine alone, which has almost no dynamic range on ALFWorld's templated
observations (two unrelated observations already score a median 0.399).

Note on what is NOT done here, per 方案 §4 / §35.2: no adaptive horizon (the
world model predicts exactly one step), no utility estimator, no change to the
planner, no LLM judge.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from preexperiments.common.alfworld_runner import (
    _ENV_LOCK,
    _import_alfred_tw_env,
    _load_alfworld_config,
    visible_actions,
)
from preexperiments.common.embeddings import Embedder
from preexperiments.common.llm_client import load_client_from_config
from preexperiments.common.logging_utils import ensure_dirs, load_yaml_config
from preexperiments.common.parallel import add_workers_arg, ordered_map
from preexperiments.direction_b import metrics
from preexperiments.direction_b.action_canonicalizer import action_utility, same_action
from preexperiments.direction_b.pipeline import DirectionBPipeline

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class ExpertEnvPool:
    """Replays an expert prefix to reach a sampled state, then executes one
    action to observe the TRUE next observation.

    Built in **dqn** mode, not dagger. Sampling needed dagger because that is
    the only mode attaching ALFWorld's AlfredExpert wrapper and exposing
    `extra.expert_plan`; replay does not, because the expert action is already
    stored in the sampled state. Keeping dagger here would re-run the handcoded
    expert planner on every replayed step for nothing -- and with the global
    TextWorld lock held that was the dominant cost (measured end-to-end at ~7
    LLM requests/minute before this change).

    The train env is built once (~66s) and `game_files` is reassigned per
    state; TextWorld is not thread-safe, so every call into it is serialised
    behind alfworld_runner._ENV_LOCK. That is why the caller runs all LLM work
    in a fully-parallel phase first, and only then walks the environment.
    """

    def __init__(self):
        cfg = copy.deepcopy(_load_alfworld_config())
        cfg["general"]["training_method"] = "dqn"
        AlfredTWEnv = _import_alfred_tw_env()
        with _ENV_LOCK:
            self.wrapper = AlfredTWEnv(cfg, train_eval="train")
        # One registered env per gamefile, reused across that episode's states.
        # `init_env()` re-runs textworld.gym.register_games + make, which is the
        # expensive part; the five states sampled from one episode all share a
        # gamefile, so registering once per episode instead of once per state
        # removes 4 of every 5 registrations. The replay itself still has to be
        # redone per state -- TextWorld has no cheap way to rewind a step.
        self._env_cache_key: Optional[str] = None
        self._env_cache = None

    def _env_for(self, gamefile: str):
        if self._env_cache_key != gamefile:
            self.wrapper.game_files = [gamefile]
            if hasattr(self.wrapper, "num_games"):
                self.wrapper.num_games = 1
            self._env_cache = self.wrapper.init_env(batch_size=1)
            self._env_cache_key = gamefile
        return self._env_cache

    def true_next_observation(self, state: Dict[str, Any], action: str) -> str:
        with _ENV_LOCK:
            env = self._env_for(state["gamefile"])
            obs, info = env.reset()
            for a in state["action_prefix"]:
                obs, _, dones, info = env.step([a])
                if dones[0]:
                    return ""
            nxt, _, _, _ = env.step([action])
        return nxt[0]


def main(args: argparse.Namespace) -> None:
    config = load_yaml_config(args.config)
    db_cfg = config.get("direction_b", {})
    ensure_dirs(DATA_DIR)

    states = [json.loads(l) for l in open(DATA_DIR / args.states)]
    if args.limit:
        states = states[: args.limit]
    print(f"[action_level] {len(states)} states "
          f"(expert-noop: {sum(s['expert_is_noop'] for s in states)})", flush=True)

    llm = load_client_from_config(config)
    pipe = DirectionBPipeline(llm, db_cfg)
    embedder = Embedder(config)
    pool = ExpertEnvPool()

    # ---- Phase 1: every LLM call, fully parallel (touches no environment) ----
    def llm_phase(state: Dict[str, Any]):
        admissible = visible_actions(state["admissible_actions"])
        state = {**state, "admissible_actions": admissible}

        a_base, base_forced, _ = pipe.baseline_action(state)
        wm = pipe.predict(state, a_base)
        prediction = wm["wm_prediction"]

        if prediction is None:
            # Parse failure: no foresight to show, so a_fore is undefined.
            # Recorded and excluded downstream rather than silently defaulted.
            a_fore, fore_forced = None, None
        else:
            a_fore, fore_forced, _ = pipe.foresight_action(state, a_base, prediction)

        expert = state["expert_action"]
        rec = {
            "state_id": state["state_id"],
            "episode_id": state["episode_id"],
            "task_type": state["task_type"],
            "goal": state["goal"],
            "step_id": state["step_id"],
            "expert_action": expert,
            "expert_is_noop": state["expert_is_noop"],
            "baseline_action": a_base,
            "foresight_action": a_fore,
            "baseline_changed": (a_fore is not None and not same_action(a_base, a_fore)),
            "base_matches_expert": same_action(a_base, expert),
            "fore_matches_expert": (same_action(a_fore, expert) if a_fore else None),
            "action_utility": (action_utility(a_base, a_fore, expert) if a_fore else None),
            "n_admissible": len(admissible),
            "action_forced": bool(base_forced) or bool(fore_forced),
            **{k: v for k, v in wm.items() if k != "wm_raw_response"},
        }
        return rec, state

    pairs = ordered_map(llm_phase, states, workers=args.workers,
                        label="llm_phase", progress_every=20)

    # ---- Phase 2: environment replay, serial (TextWorld is not thread-safe) --
    # Grouped by gamefile and replayed shortest-prefix-first so that states from
    # the same episode reuse one registered env rather than re-registering per
    # state.
    records: List[Dict[str, Any]] = []
    by_game: Dict[str, List[int]] = {}
    for i, (_, st) in enumerate(pairs):
        by_game.setdefault(st["gamefile"], []).append(i)
    done = 0
    for _, idxs in by_game.items():
        idxs.sort(key=lambda i: len(pairs[i][1]["action_prefix"]))
        for i in idxs:
            rec, st = pairs[i]
            o_next = pool.true_next_observation(st, rec["baseline_action"])
            corr = metrics.all_metrics(rec["wm_prediction"] or "", o_next, embedder=embedder)
            rec["true_next_observation"] = o_next
            rec.update({f"correctness_{k}": v for k, v in corr.items()})
            records.append(rec)
            done += 1
            if done % 20 == 0 or done == len(pairs):
                print(f"[env_phase] {done}/{len(pairs)}", flush=True)
    records.sort(key=lambda r: r["state_id"])

    out = DATA_DIR / args.out
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[action_level] wrote {len(records)} rows -> {out}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Stage 1: action-level confidence-vs-utility diagnostic.")
    p.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    p.add_argument("--states", default="sampled_states.jsonl")
    p.add_argument("--out", default="action_utility.jsonl")
    p.add_argument("--limit", type=int, default=None)
    add_workers_arg(p, default=8)
    return p


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[2])
    main(build_arg_parser().parse_args())
