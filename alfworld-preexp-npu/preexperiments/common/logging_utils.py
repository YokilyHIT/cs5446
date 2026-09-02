"""
Shared logging helpers: JSONL append/read, deterministic run-id generation,
and the per-step log schema required by spec section 5.2.

Every episode/decision-point record produced anywhere in preexperiments/
should be built with `build_step_log` (or a superset of its keys) so that
downstream analysis scripts can rely on a single schema across experiments
A and B, and so that "no duplicate run_id" (spec section 37, test 6) is
checkable mechanically.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


def new_run_id(prefix: str = "run") -> str:
    """Collision-resistant run id: prefix + wall time + random suffix."""
    return f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def deterministic_task_hash(task_id: str, seed: int, condition: str) -> str:
    """Stable id for a (task, seed, condition) triple, used to detect
    accidental duplicate episodes across re-runs / crash-resumes."""
    key = f"{task_id}|{seed}|{condition}".encode("utf-8")
    return hashlib.sha1(key).hexdigest()[:16]


def append_jsonl(path: str | Path, record: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path) -> Iterator[Dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def read_jsonl_all(path: str | Path) -> List[Dict[str, Any]]:
    return list(read_jsonl(path))


def assert_no_duplicate_run_ids(records: Iterable[Dict[str, Any]], key: str = "run_id") -> None:
    seen = set()
    for r in records:
        rid = r.get(key)
        if rid is None:
            continue
        if rid in seen:
            raise ValueError(f"Duplicate {key} detected: {rid}")
        seen.add(rid)


def build_step_log(
    *,
    run_id: str,
    task_id: str,
    game_id_or_path: str,
    split: str,
    seed: int,
    step: int,
    goal: str,
    observation: str,
    admissible_actions: List[str],
    action: str,
    next_observation: str,
    done: bool,
    success: bool,
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    temperature: float,
    top_p: float,
    max_episode_steps: int,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Per-step record matching spec section 5.2 plus the model/seed config
    block required by spec section 2."""
    record = {
        "run_id": run_id,
        "task_id": task_id,
        "game_id_or_path": game_id_or_path,
        "split": split,
        "seed": seed,
        "step": step,
        "goal": goal,
        "observation": observation,
        "admissible_actions": admissible_actions,
        "action": action,
        "next_observation": next_observation,
        "done": done,
        "success": success,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "model": model,
        "temperature": temperature,
        "top_p": top_p,
        "max_episode_steps": max_episode_steps,
    }
    if extra:
        record.update(extra)
    return record


def env_config_block(config: Dict[str, Any], seed: int) -> Dict[str, Any]:
    """The fixed per-result-file config block required by spec section 2."""
    model_cfg = config["model"]
    sampling_cfg = config["sampling"]
    return {
        "model": model_cfg["name"],
        "temperature": sampling_cfg["temperature"],
        "top_p": sampling_cfg["top_p"],
        "seed": seed,
        "max_episode_steps": sampling_cfg["max_episode_steps"],
    }


# Host-specific overrides for values in preexperiment.yaml that are paths or
# endpoints rather than experiment parameters. Added so a machine that keeps
# its model weights somewhere other than the config's default (e.g. an
# air-gapped/offline host with a local snapshot of the embedding model) does
# not have to edit -- and accidentally commit -- a machine-specific path into
# the shared config. Nothing here can change an EXPERIMENT parameter: seeds,
# temperature, episode caps and thresholds are deliberately not overridable,
# so a run's protocol always matches the checked-in config.
_ENV_OVERRIDES: Dict[str, tuple] = {
    "PREEXP_MODEL_NAME": ("model", "name"),
    "PREEXP_API_BASE": ("model", "api_base"),
    "PREEXP_EMBEDDING_MODEL": ("embedding", "model_name"),
    "PREEXP_EMBEDDING_DEVICE": ("embedding", "device"),
}


def load_yaml_config(path: str | Path) -> Dict[str, Any]:
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for env_var, (section, key) in _ENV_OVERRIDES.items():
        value = os.environ.get(env_var)
        if value:
            config.setdefault(section, {})[key] = value
            print(f"[config] {section}.{key} overridden by ${env_var} -> {value}")

    return config


def ensure_dirs(*paths: str | Path) -> None:
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)
