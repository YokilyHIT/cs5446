"""Round 4 probe: why is a proposed ALFWorld action not executable, and what would fix it?

Environment-derived ("oracle") diagnosis for the precondition-repair probe. Agent state is
tracked from the episode history with the installed ALFWorld wording:
    location   last "go to R" answered by "You arrive at ..."
    holding    "You pick up the O from ..." / "You move the O to ..."
    open/closed  "You open the R" / "You close the R" / "The R is closed." / "The R is open."
Rules (ALFWorld PDDL, text wording): take O from R needs empty hands, being at R, R open;
move O to R needs holding O, being at R, R open; heat/cool/clean O with A needs holding O and
being at A; open/close/use/examine R need being at R. A repair action is only suggested when it
is admissible right now. Anything not covered falls back to "not valid here".
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple


def track(history: Sequence[Tuple[str, str]]) -> Dict[str, object]:
    loc, holding, opened, closed = None, None, set(), set()
    for a, o in history:
        if a.startswith("go to ") and o.startswith("You arrive at"):
            loc = a[6:]
            m = re.search(r"The (.+?) is (open|closed)\.", o)
            if m and m.group(1) == loc:
                (opened if m.group(2) == "open" else closed).add(loc)
        m = re.match(r"You pick up the (.+?) from the (.+?)\.", o)
        if m:
            holding = m.group(1)
        m = re.match(r"You move the (.+?) to the (.+?)\.", o)
        if m and holding == m.group(1):
            holding = None
        m = re.match(r"You open the (.+?)\.", o)
        if m:
            opened.add(m.group(1)); closed.discard(m.group(1))
        m = re.match(r"You close the (.+?)\.", o)
        if m:
            closed.add(m.group(1)); opened.discard(m.group(1))
    return {"loc": loc, "holding": holding, "opened": opened, "closed": closed}


def diagnose(action: str, history: Sequence[Tuple[str, str]], admissible: Sequence[str]) -> Dict[str, Optional[str]]:
    """Returns {"reason": str, "repair": admissible action or None}."""
    s = track(history)
    loc, holding, closed = s["loc"], s["holding"], s["closed"]
    adm = set(admissible)

    def rep(x):
        return x if x in adm else None

    def at_closed(r):
        return r in closed and loc == r

    m = re.match(r"take (.+?) from (.+)$", action)
    if m:
        o, r = m.groups()
        if holding:
            return {"reason": f"you are already holding the {holding}; you can carry only one object",
                    "repair": rep(f"move {holding} to {loc}") if loc else None}
        if loc != r:
            return {"reason": f"you are not at the {r}", "repair": rep(f"go to {r}")}
        if at_closed(r):
            return {"reason": f"the {r} is closed", "repair": rep(f"open {r}")}
        return {"reason": f"there is no {o} at the {r}", "repair": None}
    m = re.match(r"move (.+?) to (.+)$", action)
    if m:
        o, r = m.groups()
        if holding != o:
            return {"reason": f"you are not holding the {o}" + (f" (you are holding the {holding})" if holding else ""),
                    "repair": None}
        if loc != r:
            return {"reason": f"you are not at the {r}", "repair": rep(f"go to {r}")}
        if at_closed(r):
            return {"reason": f"the {r} is closed", "repair": rep(f"open {r}")}
        return {"reason": "this placement is not possible here", "repair": None}
    m = re.match(r"(heat|cool|clean) (.+?) with (.+)$", action)
    if m:
        v, o, app = m.groups()
        if holding != o:
            return {"reason": f"you must be holding the {o} to {v} it" + (f" (you are holding the {holding})" if holding else ""),
                    "repair": None}
        if loc != app:
            return {"reason": f"you must be at the {app} to {v} the {o}", "repair": rep(f"go to {app}")}
        return {"reason": f"the {o} cannot be {v}ed with the {app} right now", "repair": None}
    m = re.match(r"(open|close|use|examine) (.+)$", action)
    if m:
        v, r = m.groups()
        if loc != r and not (v == "examine" and holding == r):
            return {"reason": f"you are not at the {r}", "repair": rep(f"go to {r}")}
        if v == "open" and r not in closed:
            return {"reason": f"the {r} is already open or cannot be opened", "repair": None}
        if v == "close" and r in closed:
            return {"reason": f"the {r} is already closed", "repair": None}
        return {"reason": f"you cannot {v} the {r} right now", "repair": None}
    m = re.match(r"go to (.+)$", action)
    if m:
        if loc == m.group(1):
            return {"reason": f"you are already at the {loc}", "repair": None}
        return {"reason": f"there is no {m.group(1)} in this room", "repair": None}
    return {"reason": "this is not a valid action in the current state", "repair": None}


FAIL_BLOCK = """
Note: executing "{base_action}" now would have no effect ("Nothing happens."): it is not a valid action in the current state.

You are still at the current state described above.
"""

REPAIR_BLOCK = """
Note: executing "{base_action}" now would have no effect ("Nothing happens.") because {reason}.{repair_line}

You are still at the current state described above.
"""


def repair_block(action, history, admissible):
    d = diagnose(action, history, admissible)
    line = f' To make progress toward it, first do: "{d["repair"]}".' if d["repair"] else ""
    return REPAIR_BLOCK.format(base_action=action, reason=d["reason"], repair_line=line), d


# ---------------------------------------------------------------- real-WM version (no rules)
WM_REPAIR_PROMPT = """You are a world model for an interactive household environment.

Current task:
{goal}

Recent action-observation history:
{history}

Current observation:
{observation}

Valid actions now:
{admissible}

Candidate action:
{action}

The candidate action is NOT executable in the current state (executing it would give "Nothing happens.").
In one short sentence, state which precondition is missing. Then give the single valid action, copied exactly
from the list above, that is the best first step toward making the intended action possible (or "none").

Return exactly:
Reason: <one sentence>
Repair: <one valid action or none>"""

_REASON_RE = re.compile(r"reason\s*:\s*(.+)", re.IGNORECASE)
_REPAIR_RE = re.compile(r"repair\s*:\s*(.+)", re.IGNORECASE)


def wm_repair_block(pipe, state, action):
    """Ask the (frozen) world model -- the LLM behind the current role -- for reason + repair."""
    from preexperiments.common.alfworld_runner import format_admissible
    prompt = WM_REPAIR_PROMPT.format(goal=state["goal"], history=state["history"] or "(no actions taken yet)",
                                     observation=state["current_observation"],
                                     admissible=format_admissible(state["admissible_actions"]), action=action)
    resp = pipe.llm.complete(prompt, seed=pipe.seed, temperature=pipe.temperature, top_p=pipe.top_p,
                             max_tokens=pipe.max_tokens_prediction)
    t = resp.text or ""
    m1, m2 = _REASON_RE.search(t), _REPAIR_RE.search(t)
    reason = (m1.group(1).strip().rstrip(".") if m1 else "it is not valid in the current state")
    rep = (m2.group(1).strip().strip('"').strip("'").rstrip(".") if m2 else "")
    low = {a.lower(): a for a in state["admissible_actions"]}
    rep = low.get(rep.lower())
    line = f' To make progress toward it, first do: "{rep}".' if rep else ""
    if reason and reason[0].isupper() and not reason[:2].isupper():
        reason = reason[0].lower() + reason[1:]
    return REPAIR_BLOCK.format(base_action=action, reason=reason, repair_line=line), {"reason": reason, "repair": rep, "raw": t}


# ---------------------------------------------------------------- round 5 baselines
_NOTICE = 'Note: you proposed "{base_action}", but it cannot be executed in the current state (it would give "Nothing happens.").'

REFLECT_BLOCK = "\n" + _NOTICE + """
Think carefully about why it failed, then choose a better next action.

You are still at the current state described above.
"""

SREFLECT_BLOCK = "\n" + _NOTICE + """
Before choosing, identify which precondition of "{base_action}" is not satisfied and the first valid action that
would satisfy it. Write both in your Thought ("Missing precondition: ...; First step: ..."), then give the Action.

You are still at the current state described above.
"""

# RPMS-style rule cards: written once per verb from the ALFWorld action semantics, independent of any state.
RULE_CARDS = {
    "take": "'take X from Y' requires: you are at Y; Y is open if it can be opened; X is in/on Y; your hands are empty (you can carry only one object).",
    "move": "'move X to Y' requires: you are holding X; you are at Y; Y is open if it can be opened.",
    "heat": "'heat X with Y' requires: you are holding X; you are at Y (a microwave).",
    "cool": "'cool X with Y' requires: you are holding X; you are at Y (a fridge).",
    "clean": "'clean X with Y' requires: you are holding X; you are at Y (a sinkbasin).",
    "open": "'open Y' requires: you are at Y; Y is closed.",
    "close": "'close Y' requires: you are at Y; Y is open.",
    "use": "'use Y' requires: you are at the place where Y is (e.g. the desklamp is on that receptacle).",
    "examine": "'examine Y' requires: you are at Y, or you are holding Y.",
    "go": "'go to Y' requires: Y is a receptacle in this room; you are not already at Y.",
}
RULES_BLOCK = "\n" + _NOTICE + """
Relevant environment rules:
{rules}
Use these rules and the history above to decide what to do next.

You are still at the current state described above.
"""


def rules_block(action):
    verb = action.split(" ")[0] if action else ""
    rules = [RULE_CARDS[verb]] if verb in RULE_CARDS else list(RULE_CARDS.values())
    return RULES_BLOCK.format(base_action=action, rules="\n".join("- " + r for r in rules))


STATE_BLOCK = "\n" + _NOTICE + """
Current state facts: you are at {loc}; you are holding {holding}; receptacles you opened: {opened}; receptacles known to be closed: {closed}.

You are still at the current state described above.
"""


def state_block(action, history):
    s = track(history)
    fmt = lambda xs: ", ".join(sorted(xs)) if xs else "none"
    return STATE_BLOCK.format(base_action=action, loc=s["loc"] or "the middle of the room (no receptacle yet)",
                              holding=s["holding"] or "nothing", opened=fmt(s["opened"]), closed=fmt(s["closed"]))
