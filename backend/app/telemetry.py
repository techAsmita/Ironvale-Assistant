"""One Langfuse trace per request, with the span names the rules require:
understand, retrieve.bm25, retrieve.dense, fuse, rerank, generate, sql.generate, sql.validate, sql.execute,
graph.fill, graph.query.

What goes in: role, route, status, prompt version, model, tokens, rewritten query, chunk ids, re-rank scores,
cited doc ids, SQL text, row count, error class, graph template, parameters and path count.
What never goes in: user display names, text of restricted documents, SQL result rows, the week-2
placeholder map, API keys and connection strings. Every value passes through scrub() first.

Works with Langfuse (self-hosted v2 in docker compose, or Langfuse Cloud). Without keys it records the
same spans locally and returns a local trace id, so the API never depends on Langfuse being up.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from contextlib import contextmanager

from .config import get_settings

log = logging.getLogger("ironvale")
_SECRET = re.compile(r"(?i)(sk-[a-z0-9-]{8,}|gsk_[a-z0-9]{8,}|postgres(?:ql)?://\S+|neo4j\+?s?://\S+|bolt://\S+)")
_lf = None
_lf_checked = False


def _langfuse():
    global _lf, _lf_checked
    if _lf_checked:
        return _lf
    _lf_checked = True
    s = get_settings()
    if not (s.langfuse_public_key and s.langfuse_secret_key and s.langfuse_host):
        return None
    try:
        from langfuse import Langfuse

        _lf = Langfuse(public_key=s.langfuse_public_key, secret_key=s.langfuse_secret_key, host=s.langfuse_host,
                       mask=_mask)
    except Exception as e:  # noqa: BLE001
        log.warning("Langfuse unavailable (%s); tracing locally only", type(e).__name__)
        _lf = None
    return _lf


_PRICE = re.compile(r"(?i)\b(?:rs\.?|inr|₹)\s?\d[\d,]*(?:\.\d+)?|unit[_ ]price\S*\s*[:=]?\s*\d+")


def _mask(*, data, **_):
    """Langfuse mask function (runs on this machine before anything is sent): secrets, connection strings and
    anything that looks like a supplier price. The pipeline never sends restricted text; this is the backstop."""
    if isinstance(data, str):
        return _PRICE.sub("[masked]", scrub(data))
    if isinstance(data, dict):
        return {k: _mask(data=v) for k, v in data.items()}
    if isinstance(data, list):
        return [_mask(data=v) for v in data]
    return data


def scrub(v):
    """Remove secrets and connection strings from anything sent to the trace."""
    if isinstance(v, str):
        return _SECRET.sub("[redacted]", v)
    if isinstance(v, dict):
        return {k: scrub(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [scrub(x) for x in v]
    return v


class Trace:
    def __init__(self, request_id: str, user_id: str, role: str, question_len: int):
        self.request_id = request_id
        self.spans: list[dict] = []
        self.timings: dict[str, int] = {}
        self.tokens = {"input": 0, "output": 0}
        self._lf_trace = None
        lf = _langfuse()
        if lf:
            try:
                self._lf_trace = lf.trace(id=request_id, name="ask", user_id=user_id,
                                          metadata={"role": role, "question_chars": question_len},
                                          tags=[role])
            except Exception:  # noqa: BLE001
                self._lf_trace = None
        self.trace_id = f"lf-{request_id}" if self._lf_trace else f"local-{request_id}"

    @contextmanager
    def span(self, name: str, **inp):
        rec = {"name": name, "input": scrub(inp), "output": {}}
        t0 = time.perf_counter()
        try:
            yield rec["output"]
        finally:
            ms = int((time.perf_counter() - t0) * 1000)
            rec["ms"] = ms
            self.timings[name] = self.timings.get(name, 0) + ms
            self.spans.append(rec)
            if self._lf_trace:
                try:
                    sp = self._lf_trace.span(name=name, input=rec["input"])
                    sp.end(output=scrub(rec["output"]))
                except Exception:  # noqa: BLE001
                    pass

    def generation(self, name: str, model: str, usage: dict | None, prompt_version: str, **meta):
        if usage:
            self.tokens["input"] += int(usage.get("prompt_tokens", 0) or 0)
            self.tokens["output"] += int(usage.get("completion_tokens", 0) or 0)
        if self._lf_trace and usage:
            try:
                self._lf_trace.generation(name=name, model=model, metadata={"prompt_version": prompt_version, **scrub(meta)},
                                          usage={"input": usage.get("prompt_tokens", 0),
                                                 "output": usage.get("completion_tokens", 0)})
            except Exception:  # noqa: BLE001
                pass

    def end(self, **out):
        if self._lf_trace:
            try:
                self._lf_trace.update(output=scrub(out), metadata=scrub(out))
                _langfuse().flush()
            except Exception:  # noqa: BLE001
                pass


def score(trace_id: str, value: float, name: str = "user_feedback") -> bool:
    lf = _langfuse()
    if not lf or not trace_id.startswith("lf-"):
        return False
    try:
        lf.score(trace_id=trace_id[3:], name=name, value=value)
        lf.flush()
        return True
    except Exception:  # noqa: BLE001
        return False


def new_request_id() -> str:
    return str(uuid.uuid4())
