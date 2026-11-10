"""Round 7: rule-verified WM repair (the WM diagnoses, a small rule set checks the diagnosis, the planner decides).

Same failure gate as the frozen method (planner action not in the admissible list) and the same first WM call
(`WM_REPAIR_PROMPT`). The rules never go to the planner; they only check the WM's answer:

* `inv_wmverify` (hand rules, symbolic check): the per-verb rule cards + the belief state tracked from the
  history (`preconditions.track` / `diagnose`) give the rule-violation category of the proposed action. The WM's
  reason must fall in the same category and its repair must be an action that addresses it (VERB_FIX). Uncovered
  cases ("other", "absent") are accepted as they are. On a conflict the WM is asked once more, with the rule card
  and the tracked facts (not the rule-derived reason or repair), and the planner sees the second answer.
* `inv_wmverify_learned` (WALL-E-style learned rules, LLM check): no tracker, no hand rules; the WM re-checks its
  own answer against the learned rules (`--knowledge r6_baselines/raw/walle_rules.json`) in a second call.
* `inv_wmrules_concat` (control): the frozen repair block followed by the RPMS-style rules + belief state,
  both shown to the planner, no verification.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Sequence, Tuple

from preexperiments.common.alfworld_runner import format_admissible
from preexperiments.react_study.preconditions import (RULE_CARDS, REPAIR_BLOCK, WM_REPAIR_PROMPT, _REASON_RE,
                                                      _REPAIR_RE, diagnose, track)

# copies of deep_analysis.oracle_cat / wm_cat (importing deep_analysis would shadow `set` in preconditions)
def rule_cat(reason):
    r = reason.lower()
    if "already at" in r:
        return "already_at"
    if "already holding" in r:
        return "holding_other"
    if "not holding" in r or "must be holding" in r:
        return "not_holding"
    if "is closed" in r:
        return "closed"
    if "already open" in r or "already closed" in r:
        return "open_state"
    if "not at the" in r or "must be at" in r:
        return "not_at"
    if "there is no" in r:
        return "absent"
    return "other"


def wm_cat(reason):
    r = (reason or "").lower()
    if re.search(r"already (at|in|located at|standing at)", r):
        return "already_at"
    if re.search(r"already (holding|carrying)|carry only one|hands? (are|is) (full|occupied)|holding (the |a )?\w+ already", r):
        return "holding_other"
    if re.search(r"not (holding|carrying)|must be (holding|carrying)|need(s)? to (take|pick|hold)|not in (your |the )?inventory|first take|have to (take|pick)", r):
        return "not_holding"
    if re.search(r"\bclosed\b|needs? to be opened|must (first )?(be )?open", r):
        return "closed"
    if re.search(r"not (at|in|near) (the )?(current )?(location|\w+ \d)|must be at|need(s)? to (go|be at|move to)|not (currently )?(at|accessible|reachable)|go to", r):
        return "not_at"
    if re.search(r"\bno \w+|not present|does not exist|not available|isn't (in|on|there)|is not (in|on|there)|not found", r):
        return "absent"
    return "other"


# repair verbs that can address each rule-violation category (None = any action)
VERB_FIX = {"not_at": {"go"}, "closed": {"open"}, "holding_other": {"move", "put"},
            "not_holding": {"go", "take", "open"}, "already_at": None, "open_state": None}
UNCOVERED = ("other", "absent")


def parse_repair(text: str, state) -> Dict[str, Optional[str]]:
    """Same parsing as preconditions.wm_repair_block."""
    t = text or ""
    m1, m2 = _REASON_RE.search(t), _REPAIR_RE.search(t)
    reason = (m1.group(1).strip().rstrip(".") if m1 else "it is not valid in the current state")
    rep = (m2.group(1).strip().strip('"').strip("'").rstrip(".") if m2 else "")
    rep = {a.lower(): a for a in state["admissible_actions"]}.get(rep.lower())
    if reason and reason[0].isupper() and not reason[:2].isupper():
        reason = reason[0].lower() + reason[1:]
    return {"reason": reason, "repair": rep, "raw": t}


def block_of(action, d):
    line = f' To make progress toward it, first do: "{d["repair"]}".' if d["repair"] else ""
    return REPAIR_BLOCK.format(base_action=action, reason=d["reason"], repair_line=line)


def _ask(pipe, state, action, extra=""):
    prompt = WM_REPAIR_PROMPT.format(goal=state["goal"], history=state["history"] or "(no actions taken yet)",
                                     observation=state["current_observation"],
                                     admissible=format_admissible(state["admissible_actions"]), action=action)
    if extra:
        prompt = prompt.replace("\n\nReturn exactly:", "\n\n" + extra + "\n\nReturn exactly:")
    resp = pipe.llm.complete(prompt, seed=pipe.seed, temperature=pipe.temperature, top_p=pipe.top_p,
                             max_tokens=pipe.max_tokens_prediction)
    return parse_repair(resp.text, state)


def facts(history):
    s = track(history)
    fmt = lambda xs: ", ".join(sorted(xs)) if xs else "none"
    return (f"you are at {s['loc'] or 'the middle of the room (no receptacle yet)'}; you are holding "
            f"{s['holding'] or 'nothing'}; receptacles you opened: {fmt(s['opened'])}; receptacles known to be "
            f"closed: {fmt(s['closed'])}")


def check(action, d, history: Sequence[Tuple[str, str]], admissible) -> Dict[str, object]:
    """Symbolic check of a WM diagnosis against the rule cards + tracked belief state."""
    c_rule = rule_cat(diagnose(action, history, admissible)["reason"])
    c_wm = wm_cat(d["reason"])
    if c_rule in UNCOVERED:
        return {"ok": True, "covered": False, "c_rule": c_rule, "c_wm": c_wm, "reason_ok": None, "repair_ok": None}
    fix = VERB_FIX[c_rule]
    rep_verb = d["repair"].split(" ")[0] if d["repair"] else None
    reason_ok = c_wm == c_rule
    repair_ok = fix is None or (rep_verb in fix)
    return {"ok": reason_ok and repair_ok, "covered": True, "c_rule": c_rule, "c_wm": c_wm,
            "reason_ok": reason_ok, "repair_ok": repair_ok}


RECHECK_HAND = """Your previous answer was:
Reason: {reason}
Repair: {repair}
It is inconsistent with the environment rules and the facts tracked from the history:
Rule: {rule}
Tracked facts: {facts}.
Re-check which precondition is missing and answer again."""


def wm_verify_hand(pipe, state, action, history):
    d1 = _ask(pipe, state, action)
    v = check(action, d1, history, state["admissible_actions"])
    if v["ok"]:
        return block_of(action, d1), d1, d1, v
    verb = action.split(" ")[0] if action else ""
    rule = RULE_CARDS.get(verb) or " ".join(RULE_CARDS.values())
    d2 = _ask(pipe, state, action, RECHECK_HAND.format(reason=d1["reason"], repair=d1["repair"] or "none", rule=rule,
                                                       facts=facts(history)))
    return block_of(action, d2), d2, d1, v


RECHECK_LEARNED = """Your previous answer was:
Reason: {reason}
Repair: {repair}
Rules learned about this environment:
{rules}
Check your answer against these rules and the history. If it is consistent, repeat it; otherwise correct it."""


def wm_verify_learned(pipe, state, action, rules):
    d1 = _ask(pipe, state, action)
    d2 = _ask(pipe, state, action, RECHECK_LEARNED.format(reason=d1["reason"], repair=d1["repair"] or "none",
                                                          rules="\n".join(f"- {r}" for r in rules)))
    return block_of(action, d2), d2, d1


CONCAT_TAIL = """Relevant environment rules:
{rules}
Current belief state (tracked from your observations): {facts}.
"""


def concat_block(pipe, state, action, history):
    d = _ask(pipe, state, action)
    verb = action.split(" ")[0] if action else ""
    rules = [RULE_CARDS[verb]] if verb in RULE_CARDS else list(RULE_CARDS.values())
    b = block_of(action, d)
    tail = CONCAT_TAIL.format(rules="\n".join("- " + r for r in rules), facts=facts(history))
    b = b.replace("\nYou are still at the current state", tail + "\nYou are still at the current state")
    return b, d
