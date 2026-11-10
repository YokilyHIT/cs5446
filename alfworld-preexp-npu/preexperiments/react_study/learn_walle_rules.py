"""Round 6: WALL-E-style rule learning (induce -> consolidate -> prune), aligned with our setting.

Data: real transitions from the label-pool `none` runs (4B and 14B planners, record_state; 448 training-split
tasks disjoint from fresh600/unseen134). Tasks are split into train / validation by task id. The world model is
the same frozen Qwen3-14B (role wm_alt) used by every other arm; the rule learner is the same model.

Per iteration (WALL-E: compare world-model predictions with real outcomes, induce rules from mismatches,
then prune): (1) the WM with the current rules judges success/failure on a fresh sample of training
transitions; (2) mispredicted transitions are shown in batches and the model induces general rules; (3) all
rules are consolidated into at most MAX_RULES; (4) greedy pruning on validation transitions removes every rule
whose removal does not lower judgement accuracy.

    $PY -m preexperiments.react_study.learn_walle_rules --iters 2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re

from preexperiments.common.alfworld_runner import format_history
from preexperiments.common.logging_utils import load_yaml_config
from preexperiments.common.parallel import ordered_map
from preexperiments.react_study.baselines_r6 import walle_judge
from preexperiments.react_study.common import MeteredLLM, OUT_ROOT, set_role, stage_dir
from preexperiments.react_study.protocol_v2 import CHECK_VALID, PipelineV2

MAX_RULES = 12

INDUCE_PROMPT = """You are learning the rules of a text-based household environment (ALFWorld) so that a world model
can correctly predict whether an action will succeed or fail ("Nothing happens.").
Below are cases where the world model's prediction was WRONG.

{cases}

Write at most 5 general rules that would have led to the correct predictions. Each rule must be general (no
specific object numbers), state an action type and the conditions under which it succeeds or fails, and be
consistent with all cases. One rule per line, each starting with "Rule:"."""

CONSOLIDATE_PROMPT = """Below are candidate rules for predicting whether actions succeed or fail in a text-based household
environment (ALFWorld).

{rules}

Merge duplicates, drop rules that are too specific, contradictory or vague, and output at most {k} general rules,
one per line, each starting with "Rule:"."""


def transitions(pl):
    out = []
    for rep in (0, 1):
        for l in open(OUT_ROOT / f"r4_common/raw/train/{pl}_label_none__rep{rep}.jsonl"):
            r = json.loads(l)
            hist = []
            for s in r["step_log"]:
                if s["action"] != CHECK_VALID:
                    out.append({"task_id": r["task_id"], "goal": r["goal"], "hist": list(hist), "obs": s["observation"],
                                "action": s["action"], "next": s["next_observation"],
                                "fail": "Nothing happens" in s["next_observation"]})
                hist.append((s["action"], s["next_observation"]))
    return out


def is_val(task_id):
    return int(hashlib.sha256(task_id.encode()).hexdigest()[:6], 16) % 4 == 0


def balanced(xs, n, rng):
    f = [x for x in xs if x["fail"]]
    ok = [x for x in xs if not x["fail"]]
    rng.shuffle(f), rng.shuffle(ok)
    return f[:n // 2] + ok[:n - n // 2]


def judge_all(pipe, items, rules, workers):
    def one(x):
        set_role("wm_alt")
        st = {"goal": x["goal"], "history": format_history(x["hist"], max_turns=50), "current_observation": x["obs"]}
        return walle_judge(pipe, st, x["action"], rules)["fail"]
    return ordered_map(one, items, workers=workers, label="judge", progress_every=200)


def acc(pred, items):
    return sum(p == x["fail"] for p, x in zip(pred, items)) / len(items)


def parse_rules(text):
    return [m.group(1).strip() for m in re.finditer(r"rule\s*:\s*(.+)", text or "", re.I) if len(m.group(1).strip()) > 10]


def main(a):
    config = load_yaml_config(a.config)
    pipe = PipelineV2(MeteredLLM(config), config.get("direction_b", {}), variant="list")
    rng = random.Random(2030)
    allx = transitions("p4b") + transitions("p14b")
    tr = [x for x in allx if not is_val(x["task_id"])]
    va = balanced([x for x in allx if is_val(x["task_id"])], a.n_val, rng)
    log = {"n_train_pool": len(tr), "n_val": len(va), "iterations": []}
    rules = []
    base_acc = acc(judge_all(pipe, va, [], a.workers), va)
    log["val_acc_no_rules"] = base_acc
    print(f"[walle] val acc without rules {base_acc:.3f}", flush=True)
    for it in range(a.iters):
        sample = balanced(tr, a.n_train, rng)
        pred = judge_all(pipe, sample, rules, a.workers)
        wrong = [x for p, x in zip(pred, sample) if p != x["fail"]]
        rng.shuffle(wrong)
        cand = list(rules)
        batches = [wrong[i:i + 15] for i in range(0, min(len(wrong), a.max_wrong), 15)]

        def induce(b):
            cases = "\n\n".join(
                f"Task: {x['goal']}\nRecent history:\n{format_history(x['hist'][-5:], max_turns=5)}\n"
                f"Current observation: {x['obs'][:300]}\nAction: {x['action']}\n"
                f"World model predicted: {'failure' if not x['fail'] else 'success'}; actual outcome: {x['next'][:200]}"
                for x in b)
            set_role("wm_alt")
            r = pipe.llm.complete(INDUCE_PROMPT.format(cases=cases), seed=pipe.seed, temperature=0.0, top_p=1.0, max_tokens=600)
            return parse_rules(r.text)
        for rs in ordered_map(induce, batches, workers=min(8, len(batches) or 1), label="induce"):
            cand += rs
        set_role("wm_alt")
        r = pipe.llm.complete(CONSOLIDATE_PROMPT.format(rules="\n".join(f"Rule: {x}" for x in cand), k=MAX_RULES),
                              seed=pipe.seed, temperature=0.0, top_p=1.0, max_tokens=1200)
        rules = parse_rules(r.text)[:MAX_RULES]
        full = acc(judge_all(pipe, va, rules, a.workers), va)
        pruned = list(rules)
        for rule in list(rules):           # greedy: drop a rule if accuracy does not fall without it
            trial = [x for x in pruned if x != rule]
            a_trial = acc(judge_all(pipe, va, trial, a.workers), va)
            if a_trial >= full:
                pruned, full = trial, a_trial
        rules = pruned
        it_log = {"iter": it + 1, "train_acc_before": acc(pred, sample), "n_wrong": len(wrong), "n_candidates": len(cand),
                  "n_rules_after_prune": len(rules), "val_acc": full, "rules": rules}
        log["iterations"].append(it_log)
        print(f"[walle] iter {it+1}: train acc {it_log['train_acc_before']:.3f}, wrong {len(wrong)}, "
              f"rules {len(rules)}, val acc {full:.3f}", flush=True)
    sd = stage_dir(40)
    json.dump({"rules": rules, "val_acc": log["iterations"][-1]["val_acc"] if log["iterations"] else base_acc,
               "val_acc_no_rules": base_acc}, open(sd / "raw" / "walle_rules.json", "w"), indent=2)
    json.dump(log, open(sd / "tables" / "walle_rule_learning.json", "w"), indent=2)
    print(json.dumps(rules, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="preexperiments/configs/preexperiment.yaml")
    ap.add_argument("--iters", type=int, default=2)
    ap.add_argument("--n_train", type=int, default=600)
    ap.add_argument("--n_val", type=int, default=300)
    ap.add_argument("--max_wrong", type=int, default=150)
    ap.add_argument("--workers", type=int, default=48)
    main(ap.parse_args())
