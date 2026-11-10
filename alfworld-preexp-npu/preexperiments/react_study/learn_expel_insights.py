"""Round 6: ExpeL-style insight extraction, aligned with our setting.

Experience = the planner's own label-pool `none` trajectories (2 runs x 448 training-split tasks, disjoint from
fresh600 / unseen134), separately for the 4B and the 14B planner. Extraction model = the same frozen Qwen3-14B
(role wm_alt). Following ExpeL: (1) compare a failed and a successful trajectory of the same task, (2) compare
batches of successful trajectories, and each time update the insight list with ADD / EDIT / AGREE / REMOVE
operations; importance starts at 2, AGREE and EDIT add 1, REMOVE subtracts 1 and an insight at 0 is dropped.
The final list is the TOP_K insights by importance.

    $PY -m preexperiments.react_study.learn_expel_insights --planner p4b
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict

from preexperiments.common.logging_utils import load_yaml_config
from preexperiments.react_study.common import MeteredLLM, OUT_ROOT, set_role, stage_dir
from preexperiments.react_study.protocol_v2 import PipelineV2

TOP_K = 15
HEAD = """You are an expert at learning from an agent's experience in a text-based household environment (ALFWorld).
The agent can use actions such as: go to X, take X from Y, move X to Y, open X, close X, use X, examine X,
heat X with Y, cool X with Y, clean X with Y, look, inventory, check valid actions.
"""
OPS = """Existing insights:
{insights}

Update the insight list so that it helps the agent succeed in new tasks. Insights must be general (no specific
object numbers). Reply with at most 4 operations, one per line, using exactly these forms:
AGREE <n>
REMOVE <n>
EDIT <n>: <new insight>
ADD: <new insight>"""
PAIR_PROMPT = HEAD + """Below are a FAILED and a SUCCESSFUL attempt at the same task. Identify what made the difference.

FAILED attempt:
{fail}

SUCCESSFUL attempt:
{succ}

""" + OPS
BATCH_PROMPT = HEAD + """Below are several SUCCESSFUL attempts at tasks of the same type. Identify common patterns that led to success.

{succ}

""" + OPS


def render(r, max_steps=25, obs_chars=160):
    lines = [f"Task: {r['goal']}"]
    for s in r["step_log"][:max_steps]:
        lines.append(f"> {s['action']}\n{s['next_observation'][:obs_chars]}")
    lines.append(f"Outcome: {'SUCCESS' if r['success'] else 'FAILURE'} after {r['steps']} steps")
    return "\n".join(lines)


def apply_ops(text, ins):
    for line in (text or "").splitlines():
        line = line.strip()
        m = re.match(r"ADD\s*:\s*(.+)", line, re.I)
        if m and len(m.group(1)) > 10:
            ins.append({"text": m.group(1).strip(), "importance": 2})
            continue
        m = re.match(r"(AGREE|REMOVE|EDIT)\s*(\d+)\s*:?\s*(.*)", line, re.I)
        if not m:
            continue
        op, n, rest = m.group(1).upper(), int(m.group(2)) - 1, m.group(3).strip()
        if not 0 <= n < len(ins):
            continue
        if op == "AGREE":
            ins[n]["importance"] += 1
        elif op == "REMOVE":
            ins[n]["importance"] -= 1
        elif op == "EDIT" and len(rest) > 10:
            ins[n]["text"], ins[n]["importance"] = rest, ins[n]["importance"] + 1
    return [x for x in ins if x["importance"] > 0]


def shown(ins):
    top = sorted(range(len(ins)), key=lambda i: -ins[i]["importance"])[:TOP_K * 2]
    return "\n".join(f"{i + 1}. {ins[i]['text']}" for i in sorted(top)) or "(none yet)"


def main(a):
    config = load_yaml_config(a.config)
    pipe = PipelineV2(MeteredLLM(config), config.get("direction_b", {}), variant="list")
    by = defaultdict(dict)
    for rep in (0, 1):
        for l in open(OUT_ROOT / f"r4_common/raw/train/{a.planner}_label_none__rep{rep}.jsonl"):
            r = json.loads(l)
            by[r["task_id"]][rep] = r
    pairs = [(v[0], v[1]) if not v[0]["success"] else (v[1], v[0]) for v in by.values()
             if len(v) == 2 and v[0]["success"] != v[1]["success"]]
    succ_by_type = defaultdict(list)
    for v in by.values():
        for r in v.values():
            if r["success"]:
                succ_by_type[r["task_type"]].append(r)
    rng = random.Random(2031)
    batches = []
    for tt, rs in succ_by_type.items():
        rng.shuffle(rs)
        batches += [rs[i:i + 3] for i in range(0, min(len(rs), a.max_succ_per_type), 3)]
    jobs = [("pair", p) for p in pairs] + [("batch", b) for b in batches]
    rng.shuffle(jobs)
    ins = []
    set_role("wm_alt")
    for i, (kind, x) in enumerate(jobs):
        if kind == "pair":
            prompt = PAIR_PROMPT.format(fail=render(x[0]), succ=render(x[1]), insights=shown(ins))
        else:
            prompt = BATCH_PROMPT.format(succ="\n\n".join(render(r) for r in x), insights=shown(ins))
        resp = pipe.llm.complete(prompt, seed=pipe.seed, temperature=0.0, top_p=1.0, max_tokens=500)
        ins = apply_ops(resp.text, ins)
        if (i + 1) % 10 == 0:
            print(f"[expel] {a.planner} {i+1}/{len(jobs)} insights={len(ins)}", flush=True)
    final = sorted(ins, key=lambda x: -x["importance"])[:TOP_K]
    sd = stage_dir(40)
    out = {"planner": a.planner, "n_pairs": len(pairs), "n_success_batches": len(batches), "insights": final}
    json.dump(out, open(sd / "raw" / f"expel_insights_{a.planner}.json", "w"), indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    ap.add_argument("--planner", required=True, choices=["p4b", "p14b"])
    ap.add_argument("--max_succ_per_type", type=int, default=12)
    main(ap.parse_args())
