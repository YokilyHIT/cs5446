"""Shared plumbing for the ReAct study: output layout, metered LLM, gate RNG.

Cost accounting
---------------
`MeteredLLM` wraps one `LLMClient` per vLLM endpoint and records every call's
prompt/completion tokens, wall-clock latency and retry-inclusive outcome into
the calling thread's current `Meter` under the calling thread's current role
("planner_base", "planner_second", "wm"). Callers never have to thread token
counts through the pipeline's return values, so `direction_b.pipeline` stays
unchanged and every LLM call is counted -- including calls whose result is
later discarded (e.g. a WM prediction that a post-hoc gate rejects).

Endpoints: PREEXP_API_BASES="http://127.0.0.1:8001/v1,http://...:8002/v1"
(falls back to config model.api_base). Each worker thread is pinned to one
endpoint, so one episode's calls all hit the same server.
"""
from __future__ import annotations

import hashlib
import itertools
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from preexperiments.common.llm_client import LLMClient, LLMResponse

ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "outputs" / "react_study"
STAGES = {
    1: "stage1_protocol_logging",
    2: "stage2_baselines",
    3: "stage3_paired_branching",
    # round 2 (plan steps 0-4, started 2026-10-13)
    10: "step0_protocol_v2_measurement",
    11: "step1_upper_bound_controls",
    12: "step2_episodic_memory",
    13: "step3_gating",
    14: "step4_unseen_test",
}
SUBDIRS = ("raw", "tables", "figures", "logs")

ROLES = ("planner_base", "planner_second", "wm")


def stage_dir(stage: int) -> Path:
    d = OUT_ROOT / STAGES[stage]
    for s in SUBDIRS:
        (d / s).mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- metering
_TLS = threading.local()


class Meter:
    """Accumulates LLM usage for one episode (or one branch), step by step."""

    def __init__(self) -> None:
        self._step: Dict[str, Dict[str, float]] = {}
        self.total: Dict[str, Dict[str, float]] = {}

    @staticmethod
    def _empty() -> Dict[str, float]:
        return {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
                "latency_s": 0.0, "failed_calls": 0}

    def add(self, role: str, resp: Optional[LLMResponse], latency: float) -> None:
        for bucket in (self._step, self.total):
            e = bucket.setdefault(role, self._empty())
            e["calls"] += 1
            e["latency_s"] += latency
            if resp is None:
                e["failed_calls"] += 1
            else:
                e["prompt_tokens"] += resp.prompt_tokens
                e["completion_tokens"] += resp.completion_tokens

    def pop_step(self) -> Dict[str, Dict[str, float]]:
        s, self._step = self._step, {}
        return s


def set_meter(m: Optional[Meter]) -> None:
    _TLS.meter = m


def set_role(role: str) -> None:
    _TLS.role = role


def default_endpoints(config: Dict[str, Any]) -> List[str]:
    env = os.environ.get("PREEXP_API_BASES", "").strip()
    if env:
        return [e.strip() for e in env.split(",") if e.strip()]
    return [config["model"]["api_base"]]


class MeteredLLM:
    """Drop-in for LLMClient.complete() that load-balances and meters."""

    def __init__(self, config: Dict[str, Any], endpoints: Optional[List[str]] = None):
        m, s = config["model"], config["sampling"]
        self.endpoints = endpoints or default_endpoints(config)
        self.clients = [
            LLMClient(model=m["name"], api_base=ep, api_key=m.get("api_key", "EMPTY"),
                      temperature=s["temperature"], top_p=s["top_p"],
                      max_tokens=s["max_tokens_per_action"],
                      request_timeout_s=m.get("request_timeout_s", 120),
                      max_retries=m.get("max_retries", 5))
            for ep in self.endpoints
        ]
        self.model = m["name"]
        self._rr = itertools.count()
        self._lock = threading.Lock()

    def _client(self) -> LLMClient:
        c = getattr(_TLS, "client", None)
        if c is None:
            with self._lock:
                c = self.clients[next(self._rr) % len(self.clients)]
            _TLS.client = c
        return c

    def complete(self, prompt: str, **kw) -> LLMResponse:
        meter: Optional[Meter] = getattr(_TLS, "meter", None)
        role = getattr(_TLS, "role", "unknown")
        t0 = time.time()
        try:
            resp = self._client().complete(prompt, **kw)
        except Exception:
            if meter is not None:
                meter.add(role, None, time.time() - t0)
            raise
        if meter is not None:
            meter.add(role, resp, time.time() - t0)
        return resp


# ---------------------------------------------------------------- gate RNG
def gate_uniform(gate_seed: int, task_id: str, step: int) -> float:
    """Deterministic U(0,1) per (seed, task, step): reproducible random gates
    that do not depend on thread scheduling."""
    h = hashlib.sha256(f"{gate_seed}|{task_id}|{step}".encode()).hexdigest()
    return int(h[:13], 16) / float(16 ** 13)


def sum_costs(costs: List[Dict[str, Dict[str, float]]]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for c in costs:
        for role, e in c.items():
            o = out.setdefault(role, Meter._empty())
            for k, v in e.items():
                o[k] += v
    return out
