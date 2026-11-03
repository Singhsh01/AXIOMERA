"""Model provider abstraction with structured (Pydantic) outputs.

* AnthropicProvider – Messages API; structured output via a forced tool call whose
  input_schema is the Pydantic model's JSON schema.
* OpenAICompatibleProvider – any /chat/completions endpoint supporting json_schema output
  (OpenAI, Azure OpenAI, vLLM, Ollama, LM Studio, OpenRouter …).
* FixtureProvider – deterministic, offline. Returns the agent's rule-based result. Every run
  made with it is recorded with provider="fixture" so results are never mistaken for model output.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings

# USD per million tokens (input, output). Estimates for cost tracking only.
PRICING = {
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-opus-4-1": (15.0, 75.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.5, 10.0),
    "fixture": (0.0, 0.0),
}


@dataclass
class LLMResult:
    parsed: BaseModel | None
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int

    @property
    def cost_usd(self) -> float:
        pin, pout = PRICING.get(self.model, (3.0, 15.0))
        return round(self.input_tokens / 1e6 * pin + self.output_tokens / 1e6 * pout, 6)


class ProviderError(Exception):
    pass


def _estimate_tokens(s: str) -> int:
    return max(1, len(s) // 4)


class FixtureProvider:
    name, model = "fixture", "fixture"

    def complete(self, system: str, prompt: str, schema: type[BaseModel], fixture: Callable[[], BaseModel] | None = None,
                 max_tokens: int = 1024) -> LLMResult:
        t0 = time.perf_counter()
        if fixture is None:
            raise ProviderError("Fixture provider requires a deterministic fixture function for this task")
        parsed = fixture()
        text = parsed.model_dump_json()
        return LLMResult(parsed, text, self.name, self.model, _estimate_tokens(system + prompt), _estimate_tokens(text),
                         int((time.perf_counter() - t0) * 1000))


class DeterministicProvider(FixtureProvider):
    """For agents that are rule-based by design (executor, verifier). No model is involved."""

    name, model = "deterministic", "rules-v1"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    def complete(self, system, prompt, schema, fixture=None, max_tokens=1024):
        t0 = time.perf_counter()
        tool = {"name": "submit_result", "description": "Return the structured result.", "input_schema": schema.model_json_schema()}
        body = {"model": self.model, "max_tokens": max_tokens, "system": system, "tools": [tool],
                "tool_choice": {"type": "tool", "name": "submit_result"}, "messages": [{"role": "user", "content": prompt}]}
        try:
            r = httpx.post("https://api.anthropic.com/v1/messages", json=body, timeout=60,
                           headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
        except httpx.HTTPError as e:
            raise ProviderError(str(e)) from e
        if r.status_code >= 400:
            raise ProviderError(f"Anthropic {r.status_code}: {r.text[:300]}")
        data = r.json()
        block = next((b for b in data["content"] if b["type"] == "tool_use"), None)
        if block is None:
            raise ProviderError("No structured output returned")
        try:
            parsed = schema.model_validate(block["input"])
        except ValidationError as e:
            raise ProviderError(f"Output failed validation: {e}") from e
        u = data.get("usage", {})
        return LLMResult(parsed, json.dumps(block["input"]), self.name, self.model, u.get("input_tokens", 0),
                         u.get("output_tokens", 0), int((time.perf_counter() - t0) * 1000))


class OpenAICompatibleProvider:
    name = "openai"

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key, self.base_url, self.model = api_key, base_url.rstrip("/"), model

    def complete(self, system, prompt, schema, fixture=None, max_tokens=1024):
        t0 = time.perf_counter()
        body = {"model": self.model, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "response_format": {"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}}}
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", json=body, timeout=60, headers={"Authorization": f"Bearer {self.api_key}"})
        except httpx.HTTPError as e:
            raise ProviderError(str(e)) from e
        if r.status_code >= 400:
            raise ProviderError(f"OpenAI-compatible {r.status_code}: {r.text[:300]}")
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        try:
            parsed = schema.model_validate_json(content)
        except ValidationError as e:
            raise ProviderError(f"Output failed validation: {e}") from e
        u = data.get("usage", {})
        return LLMResult(parsed, content, self.name, self.model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0),
                         int((time.perf_counter() - t0) * 1000))


def get_provider():
    s = get_settings()
    if s.llm_provider == "anthropic" and s.anthropic_api_key:
        return AnthropicProvider(s.anthropic_api_key, s.anthropic_model)
    if s.llm_provider == "openai" and s.openai_api_key:
        return OpenAICompatibleProvider(s.openai_api_key, s.openai_base_url, s.openai_model)
    return FixtureProvider()
