"""Planner + World Model for the direction-two pre-experiment (方案 §5, §9, §39).

The single most important property of this file is the one §39 asks for:

    planner_baseline(state)  and  planner_with_foresight(state, foresight)

must differ in EXACTLY ONE THING -- whether the imagined next observation is
present. `_action_prompt()` therefore builds both from one template and one
optional block, so the two prompts cannot drift apart as the code is edited.

Decoding is aligned with WorldEvolver: temperature 0, top_p 0.5, seed 42
(方案 §40 independently requires temperature 0 and a fixed seed).

Deviation from WorldEvolver, deliberate and documented: WorldEvolver's ReAct
agent decodes actions freely in a "Thought:/Action:" format. Measured on this
host, free decoding with Qwen3-4B-Instruct-2507 produced an action outside the
admissible set on 51% of steps, and the difflib fallback then substituted a
different object's action -- so a_base vs a_fore differences would have been
dominated by formatting noise rather than by the foresight. Both calls here
are therefore constrained to the admissible set with vLLM `guided_choice`.
The constraint is identical on both sides, so it cannot bias the comparison it
is used to measure.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Sequence

from preexperiments.common.alfworld_runner import format_admissible, ground_action
from preexperiments.common.llm_client import LLMClient

# --- 方案 §5: one action template, one optional foresight block ---------------
ACTION_PROMPT = """You are an expert agent operating in the ALFRED Embodied Environment.

Your task is to: {goal}

Recent interaction history:
{history}

Your current observation is:
{observation}

Your admissible actions are:
{admissible_actions}
{foresight_block}
Choose exactly one action from the admissible actions above."""

# The trailing sentence is not decoration. Reading the U = -1 cases from the
# first Stage 1 run showed the planner treating the predicted observation as
# something that had already happened, and then choosing the action that would
# follow it -- e.g. shown a correct prediction of "You open the drawer 1. In it,
# you see a bowl.", it switched from `open drawer 1` (the expert action) to
# `examine drawer 1`. A three-arm ablation over 353 states, holding a_base and
# the prediction fixed and varying only this wording, gave:
#
#   framing                       ACR     AIR     AHR    net
#   A  (no such sentence)       12.7%    0.6%    3.4%   -2.8%
#   B  (this wording)           11.9%    1.7%    2.5%   -0.8%   <- best
#   C  (fully hypothetical)     27.8%    3.7%    6.2%   -2.5%
#
# B is used because it more than halves the net harm. C is instructive and NOT
# used: the strongest framing makes the planner far more willing to change its
# action (ACR 27.8%) without making those changes any more likely to be right --
# helpful and harmful both scale up together.
FORESIGHT_BLOCK = """
A world model predicts that executing "{base_action}" would lead to this next
observation:
{prediction}

This has NOT happened yet. You are still at the current state described above.
"""

# --- 方案 §9.1 + WorldEvolver: single-step next-observation prediction --------
#
# `{memory_block}` is the Episodic Memory slot (方案 §35.3, Strong-WM arm). It is
# empty for the Weak arm, and the template then renders byte-identically to the
# zero-shot prompt used for every result reported so far -- the same discipline
# §39 imposes on the planner, applied to the world model, so Weak vs Strong
# differs in exactly one thing.
WORLD_MODEL_PROMPT = """You are a world model for an interactive household environment.
{memory_block}
Current task:
{goal}

Current observation:
{observation}

Recent action-observation history:
{history}

Candidate action:
{base_action}

Predict the immediate NEXT observation after executing this action.

Also report your confidence that the important state changes and
preconditions in your prediction are correct.

Return exactly:
Prediction: <one concise predicted observation>
Confidence: <number from 0.0 to 1.0>"""

_PREDICTION_RE = re.compile(r"prediction\s*:\s*(.*?)(?:\n\s*confidence\s*:|\Z)", re.IGNORECASE | re.DOTALL)
_CONFIDENCE_RE = re.compile(r"confidence\s*:\s*([0-9]*\.?[0-9]+)", re.IGNORECASE)


def parse_prediction(text: str):
    """Split the world model's reply into (prediction, self-reported confidence).

    Returns (None, nan) on a parse failure rather than substituting a default:
    the previous round silently fell back to ("", 0.5), which put an empty
    prediction and a fabricated confidence into the statistics.
    """
    p, c = _PREDICTION_RE.search(text or ""), _CONFIDENCE_RE.search(text or "")
    if not p:
        return None, float("nan")
    pred = p.group(1).strip()
    conf = float("nan")
    if c:
        try:
            conf = max(0.0, min(1.0, float(c.group(1))))
        except ValueError:
            pass
    return (pred or None), conf


class DirectionBPipeline:
    """Frozen planner + frozen world model, both on one LLM endpoint."""

    def __init__(self, llm: LLMClient, cfg: Dict[str, Any]):
        self.llm = llm
        self.temperature = cfg.get("temperature", 0.0)
        self.top_p = cfg.get("top_p", 0.5)
        self.seed = cfg.get("seed", 42)
        self.max_tokens_action = cfg.get("max_tokens_action", 64)
        self.max_tokens_prediction = cfg.get("max_tokens_prediction", 256)

    def _action_prompt(self, state: Dict[str, Any], foresight_block: str) -> str:
        return ACTION_PROMPT.format(
            goal=state["goal"],
            history=state["history"] or "(no actions taken yet)",
            observation=state["current_observation"],
            admissible_actions=format_admissible(state["admissible_actions"]),
            foresight_block=foresight_block,
        )

    def _choose(self, prompt: str, admissible: Sequence[str]):
        resp = self.llm.complete(
            prompt,
            seed=self.seed,
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens_action,
            choices=list(admissible),
        )
        action, forced = ground_action(resp.text, admissible)
        return action, forced, resp.completion_tokens

    def baseline_action(self, state: Dict[str, Any]):
        """a_base = pi(h_t, g)  -- no foresight block at all."""
        return self._choose(self._action_prompt(state, ""), state["admissible_actions"])

    def foresight_action(self, state: Dict[str, Any], base_action: str, prediction: str):
        """a_fore = pi(h_t, g, ô_{t+1}) -- identical prompt plus the block."""
        block = FORESIGHT_BLOCK.format(base_action=base_action, prediction=prediction)
        return self._choose(self._action_prompt(state, block), state["admissible_actions"])

    def predict(self, state: Dict[str, Any], base_action: str, memory_block: str = ""):
        """ô_{t+1} plus both confidence signals (方案 §9.1 and §9.2).

        The logprob confidence uses WorldEvolver's own definition:
            l_t = (1/n) sum_i log p(y_i | ...)      q_t = exp(l_t) in (0, 1]
        i.e. the geometric mean token probability of the prediction.

        `memory_block` is Episodic Memory's retrieved-transitions block; ""
        gives the zero-shot Weak arm. Note the confidence is still computed over
        the prediction tokens only, so the two arms' confidences remain
        comparable even though their prompts differ in length.
        """
        prompt = WORLD_MODEL_PROMPT.format(
            goal=state["goal"],
            observation=state["current_observation"],
            history=state["history"] or "(no actions taken yet)",
            base_action=base_action,
            memory_block=("\n" + memory_block if memory_block else ""),
        )
        resp = self.llm.complete(
            prompt,
            seed=self.seed,
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens_prediction,
            logprobs=True,
        )
        prediction, self_conf = parse_prediction(resp.text)
        mean_lp = resp.mean_logprob
        return {
            "wm_prediction": prediction,
            "wm_raw_response": resp.text,
            "wm_confidence_self_report": self_conf,
            "wm_mean_logprob": mean_lp,
            "wm_confidence_logprob": (math.exp(mean_lp) if mean_lp == mean_lp else float("nan")),
            "wm_completion_tokens": resp.completion_tokens,
        }
