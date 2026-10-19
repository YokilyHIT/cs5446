"""AgentBoard Progress Rate for ALFWorld, for ANY game file.

AgentBoard labels subgoals only for its 134 test games
(assets/agentboard_alfworld_test.jsonl), but every label is the same
per-task-type regex template filled with the object / receptacle from the
game path (`<type>-<Obj>-<Movable>-<Recep>-<scene>/trial_...`). `subgoals_for`
regenerates exactly those templates (verified against all 134 labels in
`verify()`), translated to the installed ALFWorld's wording where it differs
("You put the X in/on the Y" -> "You move the X to the Y").

Progress (AgentBoard environment/alfworld/alfworld_env.py):
    finished[i] = 1 once any step observation matches subgoal i (never reset);
    PR = 1 if the episode succeeded else sum(finished) / (len(subgoals) + 1).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List

ASSET = Path(__file__).resolve().parent / "assets" / "agentboard_alfworld_test.jsonl"

SEE = r"^(?=.* you see)(?=.*a {o} \d+)"
PICK = r"You pick up the {o} \d+"
THIRD = {
    "look_at_obj_in_light": r"^(?=.* you see)(?=.*a {r})",
    "pick_two_obj_and_place": r"You put the {o} \d+ in/on the {r} \d+",
    "pick_cool_then_place_in_recep": r"You cool the {o} \d+ using the",
    "pick_clean_then_place_in_recep": r"You clean the {o} \d+",
    "pick_heat_then_place_in_recep": r"You heat the {o} \d+ using the",
    "pick_and_place_simple": None,
}


def _parse(gamefile_or_desc: str):
    parts = gamefile_or_desc.replace("\\", "/").split("/")
    for p in parts:
        if p.count("-") >= 4 and p.split("-")[0] in THIRD:
            tt, obj, _mov, recep, _scene = p.split("-")[:5]
            return tt, obj.lower(), recep.lower()
    raise ValueError(gamefile_or_desc)


def subgoals_for(gamefile: str, env_wording: bool = True) -> List[str]:
    tt, o, r = _parse(gamefile)
    sg = [SEE.format(o=o), PICK.format(o=o)]
    if THIRD[tt]:
        sg.append(THIRD[tt].format(o=o, r=r))
    if env_wording:
        sg = [s.replace(r" \d+ in/on the ", r" \d+ to the ").replace("You put the ", "You move the ")
              for s in sg]
    return sg


def progress_rate(gamefile: str, observations: Iterable[str], success: bool) -> float:
    if success:
        return 1.0
    sg = subgoals_for(gamefile)
    done = [0] * len(sg)
    for ob in observations:
        if ob.startswith("You arrive at loc "):  # AgentBoard _process_ob
            ob = ob[ob.find(". ") + 2:]
        for i, pat in enumerate(sg):
            if re.search(pat, ob):
                done[i] = 1
    return sum(done) / (len(sg) + 1)


def verify() -> int:
    n = 0
    for line in ASSET.read_text().splitlines():
        r = json.loads(line)
        assert subgoals_for(r["additional_info"]["description"], env_wording=False) == r["subgoals"], r
        n += 1
    return n


if __name__ == "__main__":
    print("verified", verify(), "AgentBoard labels")
