"""Spec section 37, test 1: vLLM client can return text.

This is an integration test against a LIVE vLLM OpenAI-compatible server
(see scripts/start_vllm_npu.sh). It is skipped automatically wherever no
server is reachable -- e.g. on the Windows authoring machine, or in CI
without an NPU -- but it MUST pass on the actual NPU host before any
experiment script runs (spec section 38, step 4/5).
"""
import pytest

from preexperiments.common.llm_client import load_client_from_config
from .conftest import vllm_server_available


def test_llm_client_returns_text(config):
    if not vllm_server_available(config):
        pytest.skip(
            "vLLM server not reachable at "
            f"{config['model']['api_base']} -- start it with "
            "scripts/start_vllm_npu.sh before running this test."
        )
    client = load_client_from_config(config)
    resp = client.complete("Say the single word: hello", seed=13, max_tokens=8)
    assert isinstance(resp.text, str)
    assert len(resp.text.strip()) > 0
    assert resp.prompt_tokens > 0
    assert resp.completion_tokens >= 0


def test_llm_client_seeded_determinism(config):
    """Same prompt + same seed + temperature=0 should reproduce the same
    text -- the property spec section 2/19 rely on for reproducibility."""
    if not vllm_server_available(config):
        pytest.skip("vLLM server not reachable.")
    client = load_client_from_config(config)
    r1 = client.complete("Return only the digit 7.", seed=13, temperature=0.0, max_tokens=4)
    r2 = client.complete("Return only the digit 7.", seed=13, temperature=0.0, max_tokens=4)
    assert r1.text == r2.text
