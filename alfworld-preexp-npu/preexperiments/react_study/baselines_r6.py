"""Round 6: recent-work baselines aligned with the frozen method (same planners, same 14B model for every
world-model / knowledge role, same protocol, same tasks).

  WALL-E-style (arXiv 2410.07484 / 2504.15785), arms `walle` (no rules) and `walle` + --knowledge rules:
      every step the world model judges the planner's proposed action WITHOUT the valid-action list
      (Result: success|failure); on predicted failure it returns Feedback + Suggestion and the planner
      revises (one-step MPC, at most MAX_WALLE_REVISIONS revisions). Rules are learned by
      `learn_walle_rules.py` (induce from mispredictions -> consolidate -> prune on validation).
  RPMS-style (arXiv 2603.17831), arm `inv_rpms`: same failure gate as the frozen method; the planner gets
      verb-relevant rule cards + a belief state tracked from the observation history, rules first.
      RPMS's episodic memory is not used.
  ExpeL-style (AAAI 2024), arms `expel` (insights in every planner call) and `inv_expel` (insights at the
      failure gate): insights distilled by `learn_expel_insights.py` from the planner's own label-pool
      trajectories (success/failure pairs, success batches) with ADD / EDIT / AGREE / REMOVE operations.
      ExpeL's retrieval of successful trajectories as extra in-context examples is not used (the protocol
      keeps its one fixed example).
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Sequence, Tuple

from preexperiments.react_study.preconditions import RULE_CARDS, track

MAX_WALLE_REVISIONS = 2
KNOWLEDGE: List[str] = []          # rules (WALL-E) or insights (ExpeL), set by run_episodes --knowledge


def load_knowledge(path: str) -> List[str]:
    d = json.load(open(path))
    items = d["rules"] if "rules" in d else d["insights"]
    return [x["text"] if isinstance(x, dict) else x for x in items]


# ---------------------------------------------------------------- WALL-E-style judge
WALLE_JUDGE_PROMPT = """You are a world model for an interactive household environment (ALFWorld).
{rules_block}
Current task:
{goal}

Recent action-observation history:
{history}

Current observation:
{observation}

Proposed action:
{action}

Judge whether executing the proposed action now will succeed (change the state or return useful information)
or fail (the environment would answer "Nothing happens."). If it will fail, explain why and suggest what to do
instead.

Return exactly:
Result: <success or failure>
Feedback: <if failure, one sentence explaining why; otherwise none>
Suggestion: <if failure, one sentence suggesting a corrective action; otherwise none>"""

_RES = re.compile(r"result\s*:\s*(\w+)", re.I)
_FB = re.compile(r"feedback\s*:\s*(.+)", re.I)
_SG = re.compile(r"suggestion\s*:\s*(.+)", re.I)


def walle_judge(pipe, state, action, rules: Sequence[str]) -> Dict[str, Optional[str]]:
    rb = ""
    if rules:
        rb = "\nRules of this environment (learned from experience):\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1)) + "\n"
    prompt = WALLE_JUDGE_PROMPT.format(rules_block=rb, goal=state["goal"], history=state["history"] or "(no actions taken yet)",
                                       observation=state["current_observation"], action=action)
    resp = pipe.llm.complete(prompt, seed=pipe.seed, temperature=pipe.temperature, top_p=pipe.top_p,
                             max_tokens=pipe.max_tokens_prediction)
    t = resp.text or ""
    m = _RES.search(t)
    fail = bool(m and m.group(1).lower().startswith("fail"))
    fb, sg = _FB.search(t), _SG.search(t)
    clean = lambda x: (x.group(1).strip() if x else "")
    return {"fail": fail, "feedback": clean(fb), "suggestion": clean(sg), "raw": t}


WALLE_BLOCK = """
A world model predicts that executing "{action}" now would fail.
Feedback: {feedback}
Suggestion: {suggestion}

This has NOT happened yet. You are still at the current state described above.
"""


# ---------------------------------------------------------------- RPMS-style
RPMS_BLOCK = """
Note: you proposed "{action}", but it cannot be executed in the current state (it would give "Nothing happens.").
Relevant environment rules (follow these first):
{rules}
Current belief state (tracked from your observations): you are at {loc}; you are holding {holding}; receptacles you opened: {opened}; receptacles known to be closed: {closed}.
Check the proposed action against the rules and the belief state, then choose an action.

You are still at the current state described above.
"""


def rpms_block(action, history):
    verb = action.split(" ")[0] if action else ""
    rules = [RULE_CARDS[verb]] if verb in RULE_CARDS else list(RULE_CARDS.values())
    s = track(history)
    fmt = lambda xs: ", ".join(sorted(xs)) if xs else "none"
    return RPMS_BLOCK.format(action=action, rules="\n".join("- " + r for r in rules),
                             loc=s["loc"] or "the middle of the room (no receptacle yet)", holding=s["holding"] or "nothing",
                             opened=fmt(s["opened"]), closed=fmt(s["closed"]))


# ---------------------------------------------------------------- ExpeL-style
def expel_block(insights: Sequence[str]) -> str:
    if not insights:
        return ""
    return ("\nInsights learned from earlier attempts at similar tasks:\n"
            + "\n".join(f"{i}. {x}" for i, x in enumerate(insights, 1)) + "\n")


EXPEL_GATE_BLOCK = """
Note: you proposed "{action}", but it cannot be executed in the current state (it would give "Nothing happens.").
{insights}
Use these insights and the history above to decide what to do next.

You are still at the current state described above.
"""
