"""Hosted LLM through any OpenAI-compatible API (Groq by default, OpenAI by changing three env vars).

Neither provider trains on API traffic by default (see README, "Providers and data terms").
Tests swap the client for a fake with set_client().
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

import httpx

from .config import get_settings


class LLMError(RuntimeError):
    def __init__(self, error_class: str, msg: str):
        super().__init__(msg)
        self.error_class = error_class


@dataclass
class LLMReply:
    text: str
    model: str
    ms: int
    usage: dict = field(default_factory=dict)

    def json(self) -> dict:
        return parse_json(self.text)


def parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


class OpenAICompatible:
    def __init__(self):
        s = get_settings()
        self.base, self.key, self.timeout = s.llm_base_url, s.llm_api_key, s.llm_timeout
        self.http = httpx.Client(timeout=self.timeout)

    def chat(self, messages: list[dict], *, model: str, json_mode: bool = False, max_tokens: int = 700,
             temperature: float = 0.0) -> LLMReply:
        if not self.key:
            raise LLMError("llm_not_configured", "LLM_API_KEY is not set")
        body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        t0 = time.perf_counter()
        for attempt in range(3):
            try:
                r = self.http.post(f"{self.base}/chat/completions", json=body,
                                   headers={"Authorization": f"Bearer {self.key}"})
            except httpx.TimeoutException as e:
                raise LLMError("llm_timeout", str(e)) from e
            except httpx.HTTPError as e:
                raise LLMError("llm_unreachable", type(e).__name__) from e
            if r.status_code == 429 and attempt < 2:  # free-tier rate limit: back off and retry
                time.sleep(float(r.headers.get("retry-after", 2 + 3 * attempt)))
                continue
            if r.status_code >= 400:
                raise LLMError("llm_http_error", f"{r.status_code}: {r.text[:200]}")
            data = r.json()
            text = data["choices"][0]["message"].get("content") or ""
            return LLMReply(text=text, model=data.get("model", model), ms=int((time.perf_counter() - t0) * 1000),
                            usage=data.get("usage", {}))
        raise LLMError("llm_rate_limited", "rate limited after retries")


_client = None


def client():
    global _client
    if _client is None:
        _client = OpenAICompatible()
    return _client


def set_client(c) -> None:
    global _client
    _client = c
