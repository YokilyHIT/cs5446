"""Paired statistics used across stages: exact McNemar, task-clustered bootstrap."""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

import numpy as np


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value on discordant counts b, c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def bootstrap_mean_ci(x: Sequence[float], n_boot: int = 10000, seed: int = 2026,
                      alpha: float = 0.05) -> Tuple[float, float, float]:
    """Mean and percentile CI, resampling the units (tasks) in x."""
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    means = x[idx].mean(axis=1)
    return float(x.mean()), float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def paired_task_diff(a: Dict[str, List[float]], b: Dict[str, List[float]]) -> Dict[str, float]:
    """a, b: task_id -> per-repeat success list. Task-level difference of
    per-task mean success (repeats averaged within task, tasks resampled)."""
    tasks = sorted(set(a) & set(b))
    d = [np.mean(b[t]) - np.mean(a[t]) for t in tasks]
    m, lo, hi = bootstrap_mean_ci(d)
    return {"n_tasks": len(tasks), "delta": m, "ci_low": lo, "ci_high": hi}


def discordant(a: Dict[str, bool], b: Dict[str, bool]) -> Tuple[int, int]:
    """(#tasks only a succeeds, #tasks only b succeeds) for one repeat each."""
    tasks = set(a) & set(b)
    return (sum(1 for t in tasks if a[t] and not b[t]),
            sum(1 for t in tasks if b[t] and not a[t]))
