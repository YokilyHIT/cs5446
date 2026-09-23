"""
Small helpers shared across experiment A's scripts only (goal/task-type text
extraction and a candidate-goal cache). These are ALFWorld-goal-text-specific
heuristics tied to this experiment's needs, not general enough for
preexperiments/common/, so they live here instead of being added to the
shared modules.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from preexperiments.common.alfworld_runner import build_single_game_adapter, extract_task_id
from preexperiments.common.logging_utils import append_jsonl, read_jsonl

# ALFWorld's TextWorld observation templates conventionally state the task
# goal as "Your task is to: <goal text>." in the very first reset()
# observation. This must be verified against the real installed ALFWorld
# version (see scripts/inspect_alfworld_api.py, spec section 38 step 1) --
# if the marker text has drifted, add the new spelling to _GOAL_MARKERS.
_GOAL_MARKERS = ["Your task is to:", "Your task is to", "your task is:"]
_GOAL_INFO_KEYS = ["goal", "extra.goal"]


def extract_goal(observation: str, info: Optional[Dict[str, Any]] = None) -> str:
    """Best-effort extraction of the task goal text for prompting.

    Prefers an explicit info dict key if the installed ALFWorld version
    exposes one; otherwise falls back to the "Your task is to:" marker
    conventionally embedded in the first reset() observation; otherwise
    falls back to using the raw observation itself as the goal text.
    """
    info = info or {}
    for key in _GOAL_INFO_KEYS:
        if key in info:
            val = info[key]
            if isinstance(val, (list, tuple)):
                val = val[0] if val else None
            if val:
                return str(val).strip()

    for marker in _GOAL_MARKERS:
        idx = observation.lower().find(marker.lower())
        if idx != -1:
            return observation[idx + len(marker):].strip()

    return observation.strip()


def extract_task_type(gamefile: str) -> str:
    """ALFWorld gamefiles conventionally live at
    .../<task_type>-<object>-<obj2_or_None>-<receptacle>-<scene>/trial_.../...
    so the directory that is the parent of the trial_ directory encodes the
    task type before its first '-'. Falls back to "unknown" if the pattern
    isn't found (e.g. a differently-laid-out dataset version)."""
    parts = gamefile.replace("\\", "/").split("/")
    for i, part in enumerate(parts):
        if part.startswith("trial_") and i > 0:
            candidate = parts[i - 1]
            if "-" in candidate:
                return candidate.split("-")[0]
    for part in parts:
        if "-" in part and not part.startswith("trial_"):
            return part.split("-")[0]
    return "unknown"


def reset_output_file(path: str) -> None:
    """Delete any existing output file so a full re-run of a script doesn't
    accumulate duplicate records via append_jsonl (these scripts do not
    implement crash-recovery/checkpointing -- a plain full re-run is the
    supported workflow, see evaluate_single_lessons.py)."""
    p = Path(path)
    if p.exists():
        p.unlink()


CANDIDATE_POOL_CACHE_FILENAME = "_A_eval_candidate_pool_cache.jsonl"


def load_candidate_pool_cache(results_dir: str) -> Dict[str, Dict[str, Any]]:
    """Loads the (gamefile -> {task_id, gamefile, task_type, goal}) cache
    written by select_related_tasks.py / evaluate_topk_vs_all.py so repeated
    goal-extraction resets across scripts/re-runs can be skipped. This cache
    file is an internal implementation detail, not part of the mandatory
    output list."""
    path = os.path.join(results_dir, CANDIDATE_POOL_CACHE_FILENAME)
    cache: Dict[str, Dict[str, Any]] = {}
    for rec in read_jsonl(path):
        cache[rec["gamefile"]] = rec
    return cache


def get_or_build_candidate_record(
    config: Dict[str, Any],
    split: str,
    gamefile: str,
    cache: Dict[str, Dict[str, Any]],
    results_dir: str,
) -> Dict[str, Any]:
    """Returns {task_id, gamefile, task_type, goal} for `gamefile`, from the
    cache if present, else by resetting a single-game adapter once (cheap:
    no further steps, no LLM calls) and appending the new record to the
    on-disk cache."""
    if gamefile in cache:
        return cache[gamefile]

    adapter = build_single_game_adapter(config, split, gamefile)
    obs, info = adapter.reset()
    record = {
        "task_id": extract_task_id(gamefile),
        "gamefile": gamefile,
        "task_type": extract_task_type(gamefile),
        "goal": extract_goal(obs, info),
    }
    cache[gamefile] = record
    cache_path = os.path.join(results_dir, CANDIDATE_POOL_CACHE_FILENAME)
    append_jsonl(cache_path, record)
    return record
