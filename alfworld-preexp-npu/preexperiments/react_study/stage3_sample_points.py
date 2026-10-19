"""Stage 3a: sample on-policy decision points from ReAct `none` trajectories.

Input : stage3 raw/train/none__rep0.jsonl (run_episodes --record_state)
Output: stage3 raw/decision_points.jsonl + tables/sampling_design.json

Candidates are steps t <= max_t (>= max_steps - max_t remaining steps, so the
branch outcome is not decided by budget exhaustion alone). Two strata:

    stuck   repeat_count >= 2  or  >= 2 "Nothing happens." in the last 5 steps
    normal  everything else

`stuck` is oversampled to `stuck_frac` of the sample; every point carries an
inverse-inclusion weight so analyses can report both the stratified
(diagnostic) mean and the visit-distribution mean. At most `per_episode`
points per episode, so no single task dominates.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict

from preexperiments.react_study.common import stage_dir

VERBS = ("go to", "take", "put", "open", "close", "use", "heat", "cool", "clean",
         "examine", "look", "inventory", "toggle", "slice")


def action_type(a: str) -> str:
    for v in VERBS:
        if a.startswith(v):
            return v.replace(" ", "_")
    return "other"


def features(steps, t):
    """Agent-visible features at decision step t (uses only steps < t, plus a_base at t)."""
    prev = steps[:t]
    a_base = steps[t]["baseline_action"]
    prev_actions = [s["action"] for s in prev]
    nothing = [("Nothing happens" in s["next_observation"]) for s in prev]
    run = 0
    for x in reversed(nothing):
        if not x:
            break
        run += 1
    locs = {s["action"] for s in prev if s["action"].startswith("go to")}
    return {
        "step": t,
        "phase": "early" if t < 10 else ("mid" if t < 20 else "late"),
        "action_type": action_type(a_base),
        "repeat_count": prev_actions.count(a_base),
        "nothing_last5": sum(nothing[-5:]),
        "no_progress_run": run,
        "n_distinct_last5": len(set(prev_actions[-5:])),
        "n_locations_visited": len(locs),
        "base_forced": bool(steps[t].get("base_forced", False)),
        "n_admissible": len(steps[t].get("admissible_actions", [])),
    }


def main(a):
    sd = stage_dir(3)
    eps = [json.loads(l) for l in open(sd / "raw" / "train" / "none__rep0.jsonl") if l.strip()]
    cands = []
    for e in eps:
        steps = e["step_log"]
        for t in range(min(len(steps), a.max_t + 1)):
            f = features(steps, t)
            stuck = f["repeat_count"] >= 2 or f["nothing_last5"] >= 2
            cands.append({"task_id": e["task_id"], "gamefile": e["gamefile"],
                          "task_type": e["task_type"], "goal": e["goal"],
                          "episode_success": e["success"], "episode_steps": e["steps"],
                          "stratum": "stuck" if stuck else "normal", "features": f,
                          "t": t, "prefix": [s["action"] for s in steps[:t]],
                          "observation": steps[t]["observation"],
                          "logged_baseline_action": steps[t]["baseline_action"]})
    rng = random.Random(a.seed)
    rng.shuffle(cands)
    n_stuck = round(a.n * a.stuck_frac)
    quota = {"stuck": n_stuck, "normal": a.n - n_stuck}
    per_ep = Counter()
    chosen = []
    for stratum in ("stuck", "normal"):
        pool = [c for c in cands if c["stratum"] == stratum]
        # round-robin over task types for balance
        by_tt = defaultdict(list)
        for c in pool:
            by_tt[c["task_type"]].append(c)
        tts = sorted(by_tt)
        got = 0
        while got < quota[stratum] and any(by_tt.values()):
            for tt in tts:
                while by_tt[tt]:
                    c = by_tt[tt].pop()
                    if per_ep[c["task_id"]] < a.per_episode:
                        per_ep[c["task_id"]] += 1
                        chosen.append(c)
                        got += 1
                        break
                if got >= quota[stratum]:
                    break
    n_cand = Counter(c["stratum"] for c in cands)
    n_chosen = Counter(c["stratum"] for c in chosen)
    for i, c in enumerate(sorted(chosen, key=lambda c: (c["task_id"], c["t"]))):
        c["point_id"] = i
        c["weight"] = n_cand[c["stratum"]] / n_chosen[c["stratum"]]
    chosen.sort(key=lambda c: c["point_id"])
    with open(sd / "raw" / "decision_points.jsonl", "w") as f:
        for c in chosen:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    design = {"n_episodes": len(eps), "episode_sr": sum(e["success"] for e in eps) / len(eps),
              "max_t": a.max_t, "per_episode_cap": a.per_episode, "seed": a.seed,
              "candidates_by_stratum": dict(n_cand), "chosen_by_stratum": dict(n_chosen),
              "candidate_stuck_frac": n_cand["stuck"] / max(len(cands), 1),
              "chosen_by_task_type": dict(Counter(c["task_type"] for c in chosen)),
              "chosen_by_phase": dict(Counter(c["features"]["phase"] for c in chosen)),
              "chosen_by_action_type": dict(Counter(c["features"]["action_type"] for c in chosen)),
              "n_distinct_episodes": len({c["task_id"] for c in chosen}),
              "chosen_from_successful_episodes": sum(c["episode_success"] for c in chosen)}
    (sd / "tables" / "sampling_design.json").write_text(json.dumps(design, indent=2))
    print(json.dumps(design, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--stuck_frac", type=float, default=0.4)
    p.add_argument("--max_t", type=int, default=25)
    p.add_argument("--per_episode", type=int, default=3)
    p.add_argument("--seed", type=int, default=2026)
    main(p.parse_args())
