"""Protocol v2: AgentBoard-style ReAct planner (closer to WorldEvolver).

Differences from protocol v1 (direction_b.pipeline.ACTION_PROMPT_REACT):
  * AgentBoard VanillaAgent ALFWorld instruction + action templates, and ONE
    in-context example matched to the task type (AgentBoard `prefixes`), from
    assets/agentboard_alfworld_base.json (hkust-nlp/AgentBoard, main branch).
  * Examples/templates translated to the installed ALFWorld syntax:
        put X in/on Y      -> move X to Y      (obs "You move the X to the Y.")
        <verb> X using Y   -> <verb> X with Y  (clean/cool/heat; obs unchanged)
        toggle X           -> use X
  * Full history in AgentBoard format ("Observation: ...\\nAction: ..."),
    starting from the initial room description (32k context, 30 steps fit).
  * `check valid actions` is a legal pseudo-action (AgentBoard): it costs a
    step and returns the admissible list without stepping the env.
  * variant "list": additionally shows the current admissible actions every
    step (v1 behaviour); variant "query": does not (AgentBoard behaviour).
  * Output is still "Thought: ...\\nAction: ..." (WorldEvolver ReAct), parsed
    strictly after `normalize_action` maps old-syntax actions to the new one.
  * WM prompt and FORESIGHT_BLOCK are unchanged from v1, so only the planner
    side changes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from preexperiments.common.alfworld_runner import format_admissible
from preexperiments.direction_b.pipeline import DirectionBPipeline

ASSET = Path(__file__).resolve().parent / "assets" / "agentboard_alfworld_base.json"
CHECK_VALID = "check valid actions"

PREFIXES = {  # AgentBoard tasks/alfworld.py
    "pick_and_place": "put", "pick_clean_then_place": "clean", "pick_heat_then_place": "heat",
    "pick_cool_then_place": "cool", "look_at_obj": "examine", "pick_two_obj": "puttwo",
}


def _translate_line(s: str) -> str:
    if s.startswith("Action:"):
        s = re.sub(r"^Action: put (.+?) in/on (.+)$", r"Action: move \1 to \2", s.rstrip("\n")) + "\n"
        s = re.sub(r"^Action: (clean|cool|heat) (.+?) using (.+)$", r"Action: \1 \2 with \3", s.rstrip("\n")) + "\n"
        s = re.sub(r"^Action: toggle (.+)$", r"Action: use \1", s.rstrip("\n")) + "\n"
    elif s.startswith("Observation: You put the "):
        s = re.sub(r"You put the (.+?) in/on the (.+?)\.", r"You move the \1 to the \2.", s)
    return s


def _load():
    d = json.loads(ASSET.read_text())
    instr = d["instruction"]
    instr = instr.replace("'put {obj} in/on {recep}'", "'move {obj} to {recep}'")
    instr = instr.replace("'toggle {obj}/{recep}'", "'use {obj}'")
    for v in ("clean", "cool", "heat"):
        instr = instr.replace(f"'{v} {{obj}} using {{recep}}'", f"'{v} {{obj}} with {{recep}}'")
    ex = {k: "".join(_translate_line(x) for x in v) for k, v in d["examples"].items()}
    return instr.strip(), ex


INSTRUCTION, EXAMPLES = _load()


def example_for(task_type: str) -> str:
    for k, v in PREFIXES.items():
        if task_type.startswith(k):
            return EXAMPLES[v]
    return EXAMPLES["put"]


def normalize_action(raw: str) -> str:
    a = raw.strip().strip("'\"`").strip()
    if a.endswith("."):
        a = a[:-1].strip()
    m = re.match(r"^put (.+?) (?:in/on|in|on|into|to) (.+)$", a)
    if m:
        a = f"move {m.group(1)} to {m.group(2)}"
    a = re.sub(r"^(clean|cool|heat) (.+?) using (.+)$", r"\1 \2 with \3", a)
    a = re.sub(r"^toggle (.+)$", r"use \1", a)
    return a


_ACTION_RE = re.compile(r"^[ \t]*action[ \t]*:[ \t]*(.+?)[ \t]*$", re.IGNORECASE | re.MULTILINE)


def parse_action_v2(text: str, admissible: Sequence[str]) -> Tuple[str, bool]:
    """Strict grounding after syntax normalisation. Returns (action, forced)."""
    ms = list(_ACTION_RE.finditer(text or ""))
    raw = ms[-1].group(1) if ms else (text or "").strip().split("\n")[-1]
    a = normalize_action(raw)
    if a.lower() == CHECK_VALID:
        return CHECK_VALID, False
    low = {x.lower(): x for x in admissible}
    if a.lower() in low:
        return low[a.lower()], False
    return a, True


def init_room_obs(initial_observation: str) -> str:
    for part in initial_observation.split("\n\n"):
        if part.strip().startswith("You are in the middle"):
            return part.strip()
    return initial_observation.strip()


def history_v2(init_obs: str, history: List[Tuple[str, str]]) -> str:
    lines = [f"Observation: {init_obs}"]
    for a, o in history:
        lines.append(f"Action: {a}")
        lines.append(f"Observation: {o}")
    return "\n".join(lines)


PROMPT_V2 = """{instruction}
You can also use 'look', and 'check valid actions' (lists every action that is valid right now).

Here is an example:
{example}
Now it's your turn.
Your task is to: {goal}

{history}
{admissible_block}{foresight_block}
Think briefly about what to do next, then respond with EXACTLY two lines:
Thought: <one or two sentences of reasoning>
Action: <one action>"""


class PipelineV2(DirectionBPipeline):
    """Same LLM/WM/decoding as v1; only the planner prompt + parser differ."""

    def __init__(self, llm, cfg: Dict[str, Any], variant: str = "query"):
        super().__init__(llm, {**cfg, "reasoning_mode": "react"})
        assert variant in ("query", "list")
        self.variant = variant

    def _react_prompt(self, state: Dict[str, Any], foresight_block: str) -> str:
        adm = ""
        if self.variant == "list":
            adm = "\nValid actions now:\n" + format_admissible(state["admissible_actions"]) + "\n"
        return PROMPT_V2.format(instruction=INSTRUCTION, example=example_for(state["task_type"]),
                                goal=state["goal"], history=state["history_v2"],
                                admissible_block=adm, foresight_block=foresight_block)

    def _dispatch_choose(self, state: Dict[str, Any], foresight_block: str):
        prompt = self._react_prompt(state, foresight_block)
        resp = self.llm.complete(prompt, seed=self.seed, temperature=self.temperature,
                                 top_p=self.top_p, max_tokens=self.max_tokens_action_react)
        action, forced = parse_action_v2(resp.text, state["admissible_actions"])
        return action, forced, resp.completion_tokens, {"mode": "react_v2", "prompt": prompt,
                                                         "raw_response": resp.text, "matched": not forced}
