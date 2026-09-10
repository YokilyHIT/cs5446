"""Action canonicalization for Action-Level Utility (方案 §12).

U^action compares three action strings -- a_base, a_fore, a* -- and §12 warns
against raw string equality because several surface forms can denote the same
ALFWorld action:

    take mug 1 from sink 1
    pick up mug 1 from sink 1
    grab mug 1 from sink 1        ->  pickup(mug 1, sink 1)

In this pipeline all three strings are drawn from the SAME `admissible_commands`
list (the planner is constrained to it, and the expert plan is an admissible
command), so exact match already agrees with canonical match almost always.
Canonicalization is kept anyway for two reasons: it is what §12 asks for, and
it makes the comparison robust if a later variant ever lets the planner decode
freely -- at which point synonym drift becomes real. `canonicalize` therefore
never *invents* an interpretation; it only normalizes verbs and strips
articles, and `same_action` falls back to normalized-string equality.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# ALFWorld's own verb set, plus the synonyms a free-decoding model tends to emit.
_VERB_SYNONYMS = {
    "take": "take", "pick": "take", "pickup": "take", "grab": "take", "get": "take",
    "put": "put", "place": "put", "move": "put", "drop": "put",
    "go": "goto", "goto": "goto", "walk": "goto", "navigate": "goto",
    "open": "open", "close": "close",
    "toggle": "toggle", "use": "toggle", "turn": "toggle",
    "heat": "heat", "cool": "cool", "clean": "clean", "slice": "slice",
    "examine": "examine", "inspect": "examine",
    "look": "look", "inventory": "inventory",
}
# "<noun> <index>", e.g. "drawer 7"
_ENTITY = re.compile(r"\b([a-z]+ \d+)\b")
_PREPOSITIONS = (" from ", " in/on ", " in ", " on ", " with ", " to ", " at ")


def _normalize(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\b(a|an|the)\b", " ", t)
    return " ".join(t.split())


def canonicalize(action: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Map an action string to `(verb, object, receptacle)`.

    Missing slots come back as None. Unrecognised verbs are kept verbatim
    rather than being forced into the known set -- silently rewriting an
    action we do not understand would be worse than reporting it as-is.
    """
    t = _normalize(action)
    if not t:
        return ("", None, None)

    head = t.split()[0]
    # "pick up X", "turn on X" -- the verb is two tokens
    rest = t
    if head in ("pick", "turn") and len(t.split()) > 1:
        rest = " ".join(t.split()[2:])
    else:
        rest = " ".join(t.split()[1:])
    verb = _VERB_SYNONYMS.get(head, head)

    ents = _ENTITY.findall(rest)
    obj = ents[0] if ents else (rest.strip() or None)
    recep = None
    for prep in _PREPOSITIONS:
        if prep in f" {rest} ":
            tail = f" {rest} ".split(prep, 1)[1]
            tail_ents = _ENTITY.findall(tail)
            if tail_ents:
                recep = tail_ents[0]
            break
    if recep is None and len(ents) > 1:
        recep = ents[1]
    return (verb, obj, recep)


def same_action(a: str, b: str) -> bool:
    """True when two action strings denote the same ALFWorld action.

    Normalized-string equality is checked first so that identical commands
    always agree regardless of how well `canonicalize` parsed them.
    """
    if _normalize(a) == _normalize(b):
        return True
    ca, cb = canonicalize(a), canonicalize(b)
    if not ca[0] or not cb[0]:
        return False
    return ca == cb


def action_utility(base_action: str, foresight_action: str, expert_action: str) -> int:
    """方案 §11:  U = 1[a_fore == a*] - 1[a_base == a*]  in {-1, 0, +1}."""
    return int(same_action(foresight_action, expert_action)) - int(
        same_action(base_action, expert_action)
    )
