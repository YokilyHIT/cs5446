"""Planner + World Model for the direction-two pre-experiment (方案 §5, §9, §39).

The single most important property of this file is the one §39 asks for:

    planner_baseline(state)  and  planner_with_foresight(state, foresight)

must differ in EXACTLY ONE THING -- whether the imagined next observation is
present. `_action_prompt()` therefore builds both from one template and one
optional block, so the two prompts cannot drift apart as the code is edited.
That invariant now holds independently for BOTH reasoning modes below (see
`reasoning_mode`) -- switching mode never lets baseline and foresight diverge
in how they reason or how their output is parsed into an action.

Decoding is aligned with WorldEvolver: temperature 0, top_p 0.5, seed 42
(方案 §40 independently requires temperature 0 and a fixed seed).

Two reasoning modes, both first-class and selectable via
`direction_b.reasoning_mode` in preexperiment.yaml (default "direct", so every
existing config/result is reproduced unchanged unless a script opts in):

  "direct" (unchanged from the original round; the deliberate, documented
      deviation from WorldEvolver described below):
      WorldEvolver's own ReAct agent decodes actions freely in a
      "Thought:/Action:" format. Measured on this host, free decoding with
      Qwen3-4B-Instruct-2507 produced an action outside the admissible set on
      51% of steps, and alfworld_runner.ground_action's difflib fallback then
      substituted a different object's action -- so a_base vs a_fore
      differences would have been dominated by formatting noise rather than
      by the foresight. Both calls are therefore constrained to the
      admissible set with vLLM `guided_choice`. The constraint is identical
      on both sides, so it cannot bias the comparison it is used to measure.

  "react" (new: the literal WorldEvolver format, for anyone who wants the
      unconstrained reproduction rather than the guided_choice workaround):
      free "Thought: ...\\nAction: ..." decoding, no guided_choice. Grounding
      is STRICT -- `parse_react_action` below never falls back to a
      difflib-nearest admissible action or a fixed default the way
      alfworld_runner.ground_action does. An output that does not name an
      admissible action is passed through VERBATIM (`forced=True` flags it),
      because a silent fuzzy substitution can manufacture or erase an
      a_base-vs-a_fore difference for reasons that have nothing to do with
      foresight -- exactly the confound direction two exists to avoid. This
      is expected to reproduce the high off-admissible rate measured before;
      that rate itself is diagnostic data now, not something to paper over.

Both modes expose the same public surface (`baseline_action`,
`foresight_action`, and the *_ex variants that also return the full prompt +
raw response for auditing), so callers do not need mode-specific branching.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

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

# "react" mode's counterpart to ACTION_PROMPT: byte-identical up through
# {foresight_block} (goal/history/observation/admissible_actions), so the only
# thing this mode changes relative to "direct" is the final instruction --
# free-form WorldEvolver-style "Thought:/Action:" output instead of a
# guided_choice-constrained bare action. Baseline vs foresight within this
# template still differ in exactly the foresight_block, same as "direct".
ACTION_PROMPT_REACT = """You are an expert agent operating in the ALFRED Embodied Environment.

Your task is to: {goal}

Recent interaction history:
{history}

Your current observation is:
{observation}

Your admissible actions are:
{admissible_actions}
{foresight_block}
Think step-by-step about which admissible action is best, then respond with
EXACTLY two lines and nothing else:
Thought: <one or two sentences of reasoning>
Action: <the action you choose, copied EXACTLY as it appears in the admissible actions above>"""

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
#
# This block is shared verbatim by BOTH reasoning modes (direct and react):
# the run_ground_truth_foresight_probe.py diagnostic exists precisely to check
# whether react mode still skips ahead under this same wording when the
# "prediction" is not a world-model guess but the environment's real next
# observation.
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

# Grabs the LAST "Action: ..." line in a react-mode completion (last, in case
# the model echoes the word "Action:" inside its own Thought first).
_REACT_ACTION_LINE_RE = re.compile(r"^[ \t]*action[ \t]*:[ \t]*(.+?)[ \t]*$", re.IGNORECASE | re.MULTILINE)


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


def parse_react_action(text: str, admissible_actions: Sequence[str]) -> Tuple[str, bool]:
    """Strict (non-fuzzy) grounding for free-form "Thought:/Action:" output.

    Returns (action, forced), mirroring alfworld_runner.ground_action's shape
    but WITHOUT its difflib-nearest-match / first-admissible-action fallback.
    `forced=True` here means "the model's own text is returned verbatim,
    unresolved against the admissible list" -- never "a different,
    plausible-looking action was silently substituted for it". That
    distinction is load-bearing for direction two: a fuzzy substitution can
    manufacture or erase an a_base-vs-a_fore difference for reasons that have
    nothing to do with foresight, which would corrupt the exact quantity this
    experiment measures.

    Passing an unresolved string straight through to ALFWorld's TextWorld env
    is safe -- it is a text-adventure command parser, and an unparseable
    command elicits "Nothing happens." rather than a crash -- so callers may
    hand this function's `action` output directly to `adapter.step()` even
    when `forced` is True.
    """
    matches = list(_REACT_ACTION_LINE_RE.finditer(text or ""))
    raw = matches[-1].group(1).strip() if matches else (text or "").strip()
    raw = raw.strip('"').strip("'")

    if raw in admissible_actions:
        return raw, False
    norm_map = {a.strip().lower(): a for a in admissible_actions}
    if raw.lower() in norm_map:
        return norm_map[raw.lower()], False
    return raw, True


def _mean_logprob_in_span(
    token_logprobs: List[Tuple[str, float]], start: Optional[int], end: Optional[int]
) -> float:
    """Mean logprob of only the tokens whose reconstructed text falls inside
    the half-open character span [start, end) of the full completion string.

    This is what keeps the WorldEvolver-style confidence
    q_t = exp(mean logprob) restricted to the PREDICTED OBSERVATION tokens.
    The original implementation averaged `resp.mean_logprob` over the ENTIRE
    completion, which also contains the model's own self-reported
    "Confidence: 0.87" line -- a short, highly predictable numeral whose
    logprob has nothing to do with whether the predicted observation is
    correct. Averaging it in silently mixed the two confidence signals the
    pipeline is supposed to keep separate (`wm_confidence_self_report` vs
    `wm_confidence_logprob`).

    Token boundaries are reconstructed by concatenating token text in order
    (vLLM/OpenAI logprob tokens are returned as plain decoded substrings, so
    concatenation reproduces the original completion text); a token counts as
    "in span" if it overlaps [start, end) at all, so a token straddling the
    boundary (e.g. spanning "...bowl.\\nConfidence") is still counted on the
    prediction side only up to where it overlaps.
    """
    if not token_logprobs or start is None or end is None or end <= start:
        return float("nan")
    pos = 0
    picked: List[float] = []
    for tok, lp in token_logprobs:
        tok_start, tok_end = pos, pos + len(tok)
        if tok_end > start and tok_start < end:
            picked.append(lp)
        pos = tok_end
    if not picked:
        return float("nan")
    return sum(picked) / len(picked)


class DirectionBPipeline:
    """Frozen planner + frozen world model, both on one LLM endpoint."""

    _VALID_REASONING_MODES = ("direct", "react")

    def __init__(self, llm: LLMClient, cfg: Dict[str, Any]):
        self.llm = llm
        self.temperature = cfg.get("temperature", 0.0)
        self.top_p = cfg.get("top_p", 0.5)
        self.seed = cfg.get("seed", 42)
        self.max_tokens_action = cfg.get("max_tokens_action", 64)
        self.max_tokens_prediction = cfg.get("max_tokens_prediction", 256)
        # "direct" (default, byte-identical to every prior round) or "react"
        # (new, see module docstring). Any other value fails loudly rather
        # than silently falling back to a default reasoning mode.
        self.reasoning_mode = cfg.get("reasoning_mode", "direct")
        if self.reasoning_mode not in self._VALID_REASONING_MODES:
            raise ValueError(
                f"direction_b.reasoning_mode={self.reasoning_mode!r} is not one of "
                f"{self._VALID_REASONING_MODES}."
            )
        # react-only: the reasoning + action share one free-form completion, so
        # it needs materially more budget than the bare-action "direct" call.
        self.max_tokens_action_react = cfg.get("max_tokens_action_react", 256)

    def _action_prompt(self, state: Dict[str, Any], foresight_block: str) -> str:
        return ACTION_PROMPT.format(
            goal=state["goal"],
            history=state["history"] or "(no actions taken yet)",
            observation=state["current_observation"],
            admissible_actions=format_admissible(state["admissible_actions"]),
            foresight_block=foresight_block,
        )

    def _react_prompt(self, state: Dict[str, Any], foresight_block: str) -> str:
        return ACTION_PROMPT_REACT.format(
            goal=state["goal"],
            history=state["history"] or "(no actions taken yet)",
            observation=state["current_observation"],
            admissible_actions=format_admissible(state["admissible_actions"]),
            foresight_block=foresight_block,
        )

    def _choose(self, prompt: str, admissible: Sequence[str]):
        """Direct mode: vLLM guided_choice constrains the completion to
        exactly one admissible action. Unchanged from the original pipeline --
        run_framing_ablation.py calls this directly and must keep seeing this
        exact 3-tuple."""
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

    def _choose_react(self, prompt: str, admissible: Sequence[str]):
        """React mode: free-form Thought:/Action: decoding, no guided_choice,
        strict (non-fuzzy) grounding via `parse_react_action`."""
        resp = self.llm.complete(
            prompt,
            seed=self.seed,
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens_action_react,
            choices=None,
        )
        action, forced = parse_react_action(resp.text, admissible)
        return action, forced, resp.completion_tokens, resp.text

    def _dispatch_choose(
        self, state: Dict[str, Any], foresight_block: str
    ) -> Tuple[str, bool, int, Dict[str, Any]]:
        """Route to the configured reasoning mode. Both branches build their
        prompt from the SAME state + foresight_block, so baseline_action and
        foresight_action differ in exactly the foresight_block regardless of
        mode. Returns (action, forced, completion_tokens, diagnostics) where
        diagnostics carries the full prompt/raw response/mode for callers
        (e.g. the ground-truth foresight probe) that need to audit them --
        the public baseline_action/foresight_action methods below drop it to
        keep their historical 3-tuple return shape.
        """
        if self.reasoning_mode == "react":
            prompt = self._react_prompt(state, foresight_block)
            action, forced, tokens, raw = self._choose_react(prompt, state["admissible_actions"])
        else:
            prompt = self._action_prompt(state, foresight_block)
            action, forced, tokens = self._choose(prompt, state["admissible_actions"])
            raw = action  # guided_choice's completion IS the chosen action string
        diag = {
            "mode": self.reasoning_mode,
            "prompt": prompt,
            "raw_response": raw,
            "matched": not forced,
        }
        return action, forced, tokens, diag

    def baseline_action(self, state: Dict[str, Any]):
        """a_base = pi(h_t, g)  -- no foresight block at all."""
        action, forced, tokens, _diag = self._dispatch_choose(state, "")
        return action, forced, tokens

    def foresight_action(self, state: Dict[str, Any], base_action: str, prediction: str):
        """a_fore = pi(h_t, g, ô_{t+1}) -- identical prompt plus the block."""
        block = FORESIGHT_BLOCK.format(base_action=base_action, prediction=prediction)
        action, forced, tokens, _diag = self._dispatch_choose(state, block)
        return action, forced, tokens

    def baseline_action_ex(self, state: Dict[str, Any]):
        """Same as baseline_action, but also returns the diagnostics dict
        (prompt, raw_response, mode, matched) -- for scripts that need to
        audit exactly what the model was shown and said, not just the
        grounded action."""
        return self._dispatch_choose(state, "")

    def foresight_action_ex(self, state: Dict[str, Any], base_action: str, prediction: str):
        """Same as foresight_action, but also returns the diagnostics dict."""
        block = FORESIGHT_BLOCK.format(base_action=base_action, prediction=prediction)
        return self._dispatch_choose(state, block)

    def predict(self, state: Dict[str, Any], base_action: str, memory_block: str = ""):
        """ô_{t+1} plus both confidence signals (方案 §9.1 and §9.2).

        The logprob confidence uses WorldEvolver's own definition:
            l_t = (1/n) sum_i log p(y_i | ...)      q_t = exp(l_t) in (0, 1]
        i.e. the geometric mean token probability of the prediction -- and
        ONLY the prediction: `_mean_logprob_in_span` restricts the average to
        the character span `_PREDICTION_RE` captured, excluding the
        self-reported "Confidence: <number>" line that follows it in the same
        completion. (The previous round averaged over the whole completion,
        which silently pulled the self-report's easy-to-predict numeral into
        what was supposed to be a signal about the prediction alone --
        `wm_confidence_logprob_full_response_uncorrected` below is that old
        computation, kept only so a re-run can be diffed against it.)

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

        pred_match = _PREDICTION_RE.search(resp.text or "")
        pred_span = (pred_match.start(1), pred_match.end(1)) if pred_match else (None, None)
        pred_mean_lp = _mean_logprob_in_span(resp.token_logprobs, *pred_span)
        full_mean_lp = resp.mean_logprob

        return {
            "wm_prediction": prediction,
            "wm_raw_response": resp.text,
            "wm_confidence_self_report": self_conf,
            "wm_mean_logprob": pred_mean_lp,
            "wm_confidence_logprob": (math.exp(pred_mean_lp) if pred_mean_lp == pred_mean_lp else float("nan")),
            # Legacy/audit only -- see docstring above. Not used by any gate.
            "wm_mean_logprob_full_response_uncorrected": full_mean_lp,
            "wm_confidence_logprob_full_response_uncorrected": (
                math.exp(full_mean_lp) if full_mean_lp == full_mean_lp else float("nan")
            ),
            "wm_completion_tokens": resp.completion_tokens,
        }
