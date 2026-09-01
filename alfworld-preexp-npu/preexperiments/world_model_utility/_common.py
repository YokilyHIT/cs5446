"""
Small helpers shared across experiment B's scripts only, mirroring the
pattern used by preexperiments/failure_selection/_common.py (a separate,
experiment-local copy rather than a cross-package import, since these are
specific to how experiment B renders bare action-prefix history and parses
the world-model prediction/confidence response format -- not general enough
for preexperiments/common/).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

# ALFWorld's TextWorld reset() observation conventionally embeds the task
# goal as "...Your task is to: <goal text>." inside the same string as the
# initial room description. See preexperiments/failure_selection/_common.py's
# extract_goal for the matching convention used in experiment A -- verify
# against scripts/inspect_alfworld_api.py if this has drifted.
_GOAL_MARKERS = ["Your task is to:", "Your task is to", "your task is:"]


def extract_goal_and_observation(raw_obs: str) -> Tuple[str, str]:
    """Split a fresh reset() observation into (goal, observation). The base
    ReAct prompt needs `goal` fixed across the whole episode and
    `observation` reflecting only the current room state."""
    for marker in _GOAL_MARKERS:
        idx = raw_obs.lower().find(marker.lower())
        if idx != -1:
            return raw_obs[idx + len(marker):].strip(), raw_obs[:idx].strip()
    return raw_obs.strip(), raw_obs.strip()


def render_action_prefix_history(action_prefix: List[str]) -> str:
    """Best-effort history rendering when only the prior action strings (no
    matching intermediate observations) are available -- see
    generate_foresight.py, which only has each decision point's
    `action_prefix` plus its `observation` at the decision point itself."""
    if not action_prefix:
        return "(no actions taken yet)"
    return "\n".join(f"> {a}" for a in action_prefix)


_PREDICTION_RE = re.compile(
    r"prediction\s*:\s*(.*?)(?:\n\s*confidence\s*:|\Z)", re.IGNORECASE | re.DOTALL
)
_CONFIDENCE_RE = re.compile(r"confidence\s*:\s*([0-9]*\.?[0-9]+)", re.IGNORECASE)


def parse_prediction_confidence(text: str) -> Tuple[str, float]:
    """Parse WORLD_MODEL_PREDICTION_PROMPT's "Prediction: ...\\nConfidence:
    <float>" response format. Tolerates case/whitespace drift; on any parse
    failure falls back to an empty prediction and confidence=0.5 rather than
    crashing the whole collection run."""
    pred_match = _PREDICTION_RE.search(text)
    conf_match = _CONFIDENCE_RE.search(text)
    if not pred_match or not conf_match:
        print(f"[warn] failed to parse world-model response, using fallback: {text!r}")
        return "", 0.5
    prediction = pred_match.group(1).strip()
    try:
        confidence = float(conf_match.group(1))
    except ValueError:
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    return prediction, confidence


def reset_output_file(path: str) -> None:
    """Delete any existing output file so a full re-run of a script doesn't
    accumulate duplicate records via append_jsonl (mirrors
    failure_selection/_common.py::reset_output_file -- plain full re-run is
    the supported workflow, no crash-recovery/checkpointing)."""
    p = Path(path)
    if p.exists():
        p.unlink()
