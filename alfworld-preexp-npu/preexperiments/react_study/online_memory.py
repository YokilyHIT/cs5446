"""Online Episodic Memory (WorldEvolver §3.2), shared across tasks and attempts.

    M_E <- M_E U {(o_t, a_t, o_{t+1})}   after every executed env step
    retrieval: top-k_ME (default 5) entries by Jaccard over action tokens,
               rendered with direction_b.episodic_memory's block format.

The bank starts empty (WorldEvolver Table 1) unless `load()` seeds it from a
previous run's dump, which is how memory persists across attempts. Episodes
run concurrently, so "online" here means: an entry is retrievable as soon as
the step that produced it has been executed by ANY episode -- still strictly
causal (nothing is visible before it happened). Ties in Jaccard are broken by
recency (latest first); the paper does not specify a tie-break.
`check valid actions` pseudo-steps are not stored (no env transition).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List

from preexperiments.direction_b.episodic_memory import TRANSITION_BLOCK_HEADER, _tokens


class OnlineEpisodicMemory:
    def __init__(self, k: int = 5):
        self.k = k
        self.entries: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def add(self, observation: str, action: str, next_observation: str, task_id: str = "", step: int = -1):
        with self._lock:
            self.entries.append({"observation": observation, "action": action,
                                 "next_observation": next_observation, "task_id": task_id,
                                 "step": step, "seq": len(self.entries), "_tok": _tokens(action)})

    def retrieve(self, action: str) -> List[Dict[str, Any]]:
        with self._lock:
            pool = list(self.entries)
        q = _tokens(action)
        if not q:
            return []
        scored = [(len(q & e["_tok"]) / len(q | e["_tok"]) if e["_tok"] else 0.0, e["seq"], e) for e in pool]
        scored = [s for s in scored if s[0] > 0.0]
        scored.sort(key=lambda t: (-t[0], -t[1]))
        return [e for _, _, e in scored[: self.k]]

    def render(self, action: str) -> str:
        hits = self.retrieve(action)
        if not hits:
            return ""
        lines = [TRANSITION_BLOCK_HEADER, "Use these as analogies for what can change after this action.", ""]
        for i, e in enumerate(hits, 1):
            lines += [f"Transition {i}:", f"  State: {e['observation']}", f"  Action: {e['action']}",
                      f"  Observation: {e['next_observation']}", ""]
        return "\n".join(lines)

    def dump(self, path: Path) -> None:
        with self._lock, open(path, "w", encoding="utf-8") as f:
            for e in self.entries:
                f.write(json.dumps({k: v for k, v in e.items() if k != "_tok"}, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path: Path, k: int = 5) -> "OnlineEpisodicMemory":
        m = cls(k=k)
        for line in open(path, encoding="utf-8"):
            if line.strip():
                e = json.loads(line)
                m.add(e["observation"], e["action"], e["next_observation"], e.get("task_id", ""), e.get("step", -1))
        return m
