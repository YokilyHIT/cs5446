"""
Thin OpenAI-compatible client for the vLLM server started on the NPU host
(see scripts/start_vllm_npu.sh). This machine never touches CUDA/NPU/torch
directly -- it only ever speaks HTTP to the server, so this module is the
single integration point between the pre-experiment code and the model.

Every call returns an LLMResponse carrying the text plus token usage, so
callers can log completeness fields required by the spec (prompt_tokens,
completion_tokens).
"""
from __future__ import annotations

import dataclasses
import time
from typing import Optional, Sequence

import openai


@dataclasses.dataclass
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    seed: Optional[int]
    temperature: float
    top_p: float
    raw_finish_reason: Optional[str] = None


class LLMClient:
    """Wraps a vLLM OpenAI-compatible /v1/chat/completions endpoint.

    vLLM supports a per-request `seed` via `extra_body`, which is what makes
    the deterministic-replay requirement in the spec (section 19) achievable:
    same task + same action prefix + same seed + same server/model must
    reproduce the same action sequence at temperature=0.2 as long as the
    server-side sampling seed is pinned per request.
    """

    def __init__(
        self,
        model: str,
        api_base: str,
        api_key: str = "EMPTY",
        temperature: float = 0.2,
        top_p: float = 0.95,
        max_tokens: int = 256,
        request_timeout_s: int = 120,
        max_retries: int = 5,
    ):
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self._client = openai.OpenAI(
            base_url=api_base,
            api_key=api_key,
            timeout=request_timeout_s,
        )

    def health_check(self) -> bool:
        try:
            self._client.models.list()
            return True
        except Exception:
            return False

    def complete(
        self,
        prompt: str,
        seed: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        choices: Optional[Sequence[str]] = None,
        prefill: Optional[str] = None,
        stop: Optional[Sequence[str]] = None,
    ) -> LLMResponse:
        """`choices`, when given, constrains decoding so the completion is
        EXACTLY one of those strings (vLLM's `guided_choice` structured
        output). Used for action selection -- see
        alfworld_runner.choose_action for why this is needed.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        if prefill:
            # Seed the assistant turn and let the model continue it, instead of
            # starting a fresh reply. Needed because Qwen3-4B-Instruct-2507
            # answers a prompt that asks for "<think> </think>" reasoning by
            # emitting EOS as its very first token (empty completion, 1 token,
            # finish_reason="stop") -- prefilling "<think>" makes it write the
            # reasoning it was asked for. Not a vLLM/Ascend quirk: the same
            # prompt returns an empty string at temperature 0.2 and 0.7 alike.
            messages.append({"role": "assistant", "content": prefill})

        temperature = self.temperature if temperature is None else temperature
        top_p = self.top_p if top_p is None else top_p
        max_tokens = self.max_tokens if max_tokens is None else max_tokens

        extra_body = {}
        if seed is not None:
            extra_body["seed"] = seed
        if choices:
            extra_body["guided_choice"] = list(choices)
        if prefill:
            extra_body["continue_final_message"] = True
            extra_body["add_generation_prompt"] = False
        if stop:
            extra_body["stop"] = list(stop)

        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    extra_body=extra_body,
                )
                choice = resp.choices[0]
                usage = resp.usage
                return LLMResponse(
                    text=(choice.message.content or "").strip(),
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    model=self.model,
                    seed=seed,
                    temperature=temperature,
                    top_p=top_p,
                    raw_finish_reason=choice.finish_reason,
                )
            except Exception as e:  # noqa: BLE001 - deliberately broad, we retry any transient error
                last_err = e
                time.sleep(min(2 ** attempt, 30))

        raise RuntimeError(
            f"LLM request failed after {self.max_retries} retries against {self.model}"
        ) from last_err


def load_client_from_config(config: dict) -> LLMClient:
    model_cfg = config["model"]
    sampling_cfg = config["sampling"]
    return LLMClient(
        model=model_cfg["name"],
        api_base=model_cfg["api_base"],
        api_key=model_cfg.get("api_key", "EMPTY"),
        temperature=sampling_cfg["temperature"],
        top_p=sampling_cfg["top_p"],
        max_tokens=sampling_cfg["max_tokens_per_action"],
        request_timeout_s=model_cfg.get("request_timeout_s", 120),
        max_retries=model_cfg.get("max_retries", 5),
    )
