"""WM prediction accuracy from episode logs: steps where the executed action
equals a_base, so the logged next observation is the ground truth for the
WM's prediction of a_base. Reports EM / token-F1 (direction_b.metrics)."""
from __future__ import annotations

import glob
import json
import sys

import numpy as np

from preexperiments.direction_b.metrics import exact_match, token_f1


def accuracy(paths, task_ids=None):
    em, f1, hits = [], [], []
    for p in paths:
        for line in open(p):
            r = json.loads(line)
            if task_ids is not None and r["task_id"] not in task_ids:
                continue
            for s in r["step_log"]:
                if s.get("wm_called") and s.get("wm_prediction") and s["action"] == s["baseline_action"]:
                    em.append(exact_match(s["wm_prediction"], s["next_observation"]))
                    f1.append(token_f1(s["wm_prediction"], s["next_observation"]))
                    hits.append(s.get("wm_memory_hits", 0))
    return {"n_steps": len(em), "EM": float(np.mean(em)) if em else None,
            "F1": float(np.mean(f1)) if f1 else None,
            "frac_with_memory": float(np.mean([h > 0 for h in hits])) if hits else None}


if __name__ == "__main__":
    for g in sys.argv[1:]:
        print(g, accuracy(sorted(glob.glob(g))))
