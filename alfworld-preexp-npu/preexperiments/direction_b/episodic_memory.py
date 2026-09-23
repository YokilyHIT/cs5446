"""WorldEvolver's Episodic Memory (retrieval-based simulation) for the Strong-WM arm.

Why this exists. Our zero-shot world model scores Token F1 53.3% on ALFWorld,
which is already better than every zero-shot row WorldEvolver reports
(35.5% / 34.1% / 38.4% for Gemma-4-26B, Qwen3.5-9B, Gemma-4-31B). But their
FULL system reaches 76.8% Token F1, and essentially all of that gain comes from
memory, not from the gate. Reproducing only Selective Foresight on a zero-shot
world model therefore reproduces their ablation row, not their system -- and
"foresight is net harmful" measured on a half-wrong prediction says little about
foresight on a prediction worth acting on. This module supplies the missing arm.

Mechanism, following the paper:
  * each entry stores the full triple (observation, action, next_observation);
  * the retrieval KEY is the candidate action, and similarity is **Jaccard
    overlap over action tokens** -- lexical, not embedding-based;
  * k_ME = 5 by default (they report Exact Match improving by 16.8/23.5 points
    going from k=1 to k=5);
  * retrieved entries are rendered as a "## Retrieved similar past transitions"
    block ahead of the prediction request.

Leakage control. WorldEvolver accumulates memory online and argues retrieval is
safe because entries are appended only after execution. Our diagnostic scores a
fixed set of pre-sampled states rather than running an agent, so the bank is
materialised up front and that argument has to be enforced explicitly: a bank
built from the same expert trajectories contains the very transition being
predicted. `retrieve()` reimposes exactly their rule -- for a query at
(episode e, step t), entries from episode e with step >= t are dropped, while
earlier steps of the same episode remain visible, because those are experience
the agent really would have had in hand. Everything from other episodes is
usable; they are different game instances with different layouts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


def _tokens(action: str) -> set:
    return set((action or "").lower().replace("/", " ").split())


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


TRANSITION_BLOCK_HEADER = "## Retrieved similar past transitions"


class EpisodicMemory:
    """A bank of (observation, action, next_observation) triples with
    action-Jaccard retrieval."""

    def __init__(self, entries: List[Dict[str, Any]], k: int = 5):
        self.entries = entries
        self.k = k
        # Bucket by episode so the exclusion below is a dict lookup rather than
        # a scan over the whole bank for every query.
        self._by_episode: Dict[str, List[Dict[str, Any]]] = {}
        for e in entries:
            self._by_episode.setdefault(e.get("episode_id", ""), []).append(e)

    @classmethod
    def load(cls, path: Path, k: int = 5) -> "EpisodicMemory":
        return cls([json.loads(l) for l in open(path)], k=k)

    def retrieve(self, action: str, episode_id: Optional[str] = None,
                 step_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Top-k by action-Jaccard, with the causal filter of the docstring.

        Ties are broken by (episode_id, step_id) so retrieval is deterministic:
        ALFWorld actions are templated, so exact-Jaccard ties are common and an
        unstable sort would make the whole Strong-WM arm irreproducible.
        """
        pool: Iterable[Dict[str, Any]] = self.entries
        if episode_id is not None:
            own = self._by_episode.get(episode_id, [])
            if own:
                cut = step_id if step_id is not None else -1
                blocked = {id(e) for e in own if e.get("step_id", 0) >= cut}
                pool = (e for e in self.entries if id(e) not in blocked)
        scored = [(jaccard(action, e["action"]), e) for e in pool]
        scored = [s for s in scored if s[0] > 0.0]
        scored.sort(key=lambda t: (-t[0], t[1].get("episode_id", ""), t[1].get("step_id", 0)))
        return [e for _, e in scored[: self.k]]

    def render(self, action: str, episode_id: Optional[str] = None,
               step_id: Optional[int] = None) -> str:
        """The prompt block, or "" when nothing similar was found (in which case
        the world model falls back to exactly the zero-shot prompt)."""
        hits = self.retrieve(action, episode_id=episode_id, step_id=step_id)
        if not hits:
            return ""
        lines = [TRANSITION_BLOCK_HEADER,
                 "Use these as analogies for what can change after this action.", ""]
        for i, e in enumerate(hits, 1):
            lines.append(f"Transition {i}:")
            lines.append(f"  State: {e['observation']}")
            lines.append(f"  Action: {e['action']}")
            lines.append(f"  Observation: {e['next_observation']}")
            lines.append("")
        return "\n".join(lines)
