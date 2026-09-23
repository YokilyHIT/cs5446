"""Thread-pool helper for running independent episodes concurrently.

Why this exists: every collection script drives one episode at a time, which
leaves vLLM's batching entirely unused. Measured on this host, single-stream
decoding runs at 37 tok/s while 16 concurrent requests reach 513 tok/s with no
per-request latency penalty -- a ~14x difference. Serially, the full
pre-experiments (~950 episodes, ~24k steps) would take over 30 hours under the
"adamem_think" prompt style; concurrently they fit in a few.

Two properties matter more than raw speed here, and `ordered_map` provides both:

  * **Deterministic output order.** Results come back in INPUT order regardless
    of completion order. Several outputs are order-sensitive -- `failure_id` /
    `point_id` are assigned by position, and score_failure_proxies computes
    novelty against strictly-earlier lessons in file order -- so a race that
    shuffled the file would silently change what the analysis computes.
  * **Failures do not vanish.** An exception in one item is re-raised after the
    pool drains, rather than leaving a short output file that later scripts
    would happily analyse as if it were complete.

TextWorld itself is not thread-safe; alfworld_runner._ENV_LOCK serialises every
env call, which is why the concurrency here is worth having (the LLM wait, not
the env step, is what dominates).
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterable, List, Optional, Sequence, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def ordered_map(
    fn: Callable[[T], R],
    items: Sequence[T],
    workers: int = 1,
    *,
    label: str = "",
    progress_every: int = 10,
    on_result: Optional[Callable[[int, T, R], None]] = None,
) -> List[R]:
    """Apply `fn` to every item, `workers` at a time, returning results in
    INPUT order.

    `on_result(index, item, result)` is invoked under a lock as each item
    finishes -- use it for appending to a JSONL file when streaming output is
    wanted; note that streamed rows arrive in completion order, so anything
    order-sensitive should use the returned list instead.
    """
    n = len(items)
    if n == 0:
        return []

    lock = threading.Lock()
    done = [0]
    t0 = time.time()
    prefix = f"[{label}] " if label else ""

    def run(idx_item):
        idx, item = idx_item
        result = fn(item)
        with lock:
            done[0] += 1
            if on_result is not None:
                on_result(idx, item, result)
            if progress_every and (done[0] % progress_every == 0 or done[0] == n):
                print(
                    f"{prefix}{done[0]}/{n} ({time.time() - t0:.0f}s)",
                    flush=True,
                )
        return result

    if workers <= 1:
        return [run((i, it)) for i, it in enumerate(items)]

    with ThreadPoolExecutor(max_workers=workers) as ex:
        # ThreadPoolExecutor.map preserves input order and re-raises the first
        # exception once the pool has drained.
        return list(ex.map(run, enumerate(items)))


def add_workers_arg(parser, default: int = 1) -> None:
    """Standard --workers flag, so every collection script spells it the same."""
    parser.add_argument(
        "--workers",
        type=int,
        default=default,
        help=(
            "Run this many episodes concurrently. vLLM batches concurrent "
            "requests: 37 tok/s single-stream vs 513 tok/s at 16-way on the "
            "reference host, with no latency penalty. Output order is "
            "unaffected. Default 1 (serial)."
        ),
    )
