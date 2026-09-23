"""
Shared statistics helpers: bootstrap 95% CI and Spearman correlation with
bootstrap CI, both pinned to spec section 35's protocol
(1000 resamples, seed=2026) so every figure/CSV in experiments A and B that
reports a CI used the exact same procedure.
"""
from __future__ import annotations

from typing import Callable, List, Sequence, Tuple

import numpy as np
from scipy.stats import spearmanr


def bootstrap_ci(
    values: Sequence[float],
    statistic: Callable[[np.ndarray], float] = np.mean,
    n_resamples: int = 1000,
    seed: int = 2026,
    ci: float = 0.95,
) -> Tuple[float, float, float]:
    """Returns (point_estimate, ci_low, ci_high)."""
    arr = np.asarray(values, dtype=float)
    if len(arr) == 0:
        return float("nan"), float("nan"), float("nan")

    rng = np.random.default_rng(seed)
    point = float(statistic(arr))
    boot_stats = np.empty(n_resamples)
    n = len(arr)
    for i in range(n_resamples):
        sample = arr[rng.integers(0, n, size=n)]
        boot_stats[i] = statistic(sample)

    alpha = (1 - ci) / 2
    lo = float(np.quantile(boot_stats, alpha))
    hi = float(np.quantile(boot_stats, 1 - alpha))
    return point, lo, hi


def bootstrap_diff_ci(
    values_a: Sequence[float],
    values_b: Sequence[float],
    n_resamples: int = 1000,
    seed: int = 2026,
    ci: float = 0.95,
) -> Tuple[float, float, float]:
    """Bootstrap CI for mean(a) - mean(b), independent resampling of each
    (used for e.g. SR_TopK - SR_All)."""
    a = np.asarray(values_a, dtype=float)
    b = np.asarray(values_b, dtype=float)
    rng = np.random.default_rng(seed)
    point = float(a.mean() - b.mean())
    boot = np.empty(n_resamples)
    for i in range(n_resamples):
        sa = a[rng.integers(0, len(a), size=len(a))]
        sb = b[rng.integers(0, len(b), size=len(b))]
        boot[i] = sa.mean() - sb.mean()
    alpha = (1 - ci) / 2
    lo = float(np.quantile(boot, alpha))
    hi = float(np.quantile(boot, 1 - alpha))
    return point, lo, hi


def spearman_with_ci(
    x: Sequence[float],
    y: Sequence[float],
    n_resamples: int = 1000,
    seed: int = 2026,
    ci: float = 0.95,
) -> Tuple[float, float, float, float]:
    """Returns (rho, p_value, ci_low, ci_high) via paired bootstrap resampling."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 2:
        return float("nan"), float("nan"), float("nan"), float("nan")

    rho, p = spearmanr(x, y)
    rng = np.random.default_rng(seed)
    n = len(x)
    boot = np.empty(n_resamples)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        r, _ = spearmanr(x[idx], y[idx])
        boot[i] = r if not np.isnan(r) else 0.0
    alpha = (1 - ci) / 2
    lo = float(np.quantile(boot, alpha))
    hi = float(np.quantile(boot, 1 - alpha))
    return float(rho), float(p), lo, hi


def mcnemar_exact(b: int, c: int) -> float:
    """Exact McNemar test p-value for paired binary outcomes, where b/c are
    the two discordant-pair counts. Used as a secondary stat per spec section
    35 (effect size takes priority over p-value in this pre-experiment)."""
    from scipy.stats import binomtest

    n = b + c
    if n == 0:
        return 1.0
    return float(binomtest(min(b, c), n, 0.5).pvalue)
