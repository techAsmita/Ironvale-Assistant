"""Deterministic stand-ins for the CPU models and the LLM, so tests run offline and fast.
They are deliberately simple: the real bge models are used in the evaluation run."""
from __future__ import annotations

import hashlib
import math
import re

import numpy as np

from app.retrieval import tokenize

DIM = 384


def _vec(text: str) -> list[float]:
    v = np.zeros(DIM, dtype=np.float32)
    for tok in tokenize(text):
        # "dense-like" fuzziness: also hash sub-pieces, so E-417 and E-471 share mass (the failure BM25 avoids)
        for piece in [tok] + re.split(r"[-.]", tok):
            h = int(hashlib.md5(piece.encode()).hexdigest(), 16)
            v[h % DIM] += 1.0
    n = np.linalg.norm(v)
    return (v / n if n else v).tolist()


def embed(texts):
    return [_vec(t) for t in texts]


def embed_query(text):
    return _vec(text)


def rerank(query, docs):
    q = set(tokenize(query))
    out = []
    for d in docs:
        dt = set(tokenize(d))
        matched = len(q & dt)  # 1 term -> 0.12, 2 -> 0.5, 3 -> 0.88 (a cross-encoder rewards specific matches)
        out.append(1 / (1 + math.exp(-(2 * matched - 4))))
    return out


# ------------------------------------------------------------------------------------------------ fake LLM
import json as _json

from app.llm import LLMReply


class FakeLLM:
    """Routes on the system prompt. Behaves like a careful, extractive model so the pipeline's plumbing
    (routing, filtering, citations, refusals, SQL guards) can be tested without network access."""

    def __init__(self, sql_map: dict[str, str] | None = None, fail: str | None = None):
        self.sql_map = sql_map or {}
        self.fail = fail
        self.calls: list[dict] = []

    def chat(self, messages, *, model, json_mode=False, max_tokens=700, temperature=0.0):
        system, user = messages[0]["content"], messages[-1]["content"]
        self.calls.append({"system": system[:40], "user": user})
        if self.fail:
            from app.llm import LLMError
            raise LLMError(self.fail, "fake failure")
        if system.startswith("You route questions"):
            out = self._understand(user)
        elif system.startswith("You are Ironvale Components' shop-floor assistant"):
            out = self._answer(user)
        elif system.startswith("You write one PostgreSQL SELECT"):
            q = user.split("Question:", 1)[1].split("\n")[0].strip()
            out = {"sql": self._sql(q), "metric_note": None}
        elif system.startswith("Pick one graph query template"):
            from datetime import date
            from app.graph import fill_rules
            q = user.split("Question:", 1)[1].strip()
            out = fill_rules(q, date(2026, 11, 18))
        else:
            out = {}
        return LLMReply(text=_json.dumps(out), model=model, ms=1, usage={"prompt_tokens": 10, "completion_tokens": 5})

    def _understand(self, user):
        from app.understand import fallback
        q = user.split("Latest question:", 1)[1].strip()
        convo = user.split("Conversation so far:\n", 1)[1].split("\n\nLatest question:")[0]
        turns = [] if convo == "(none)" else [
            {"role": ln.split(":", 1)[0], "content": ln.split(":", 1)[1].strip()} for ln in convo.splitlines() if ":" in ln]
        fb = fallback(q, turns)
        if re.search(r"(?i)bypass", q) and "E-417" not in fb["rewritten_query"]:
            fb["rewritten_query"] += " (E-417)"
        if re.search(r"(?i)^and in (\w+)", q) and turns:
            prev = next(t["content"] for t in reversed(turns) if t["role"] == "user")
            month = re.search(r"(?i)^and in (\w+)", q).group(1).capitalize()
            fb = {"rewritten_query": re.sub(r"(?i)\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", month, prev), "route": "data"}
        return fb

    def _answer(self, user):
        """Pick the excerpt (header + body) that overlaps the question most; answer with its best sentences."""
        excerpts = user.split("Excerpts:\n\n", 1)[1].rsplit("\n\nQuestion:", 1)[0]
        question = user.rsplit("Question:", 1)[1].split("(Note for the answer")[0]
        qtok = set(tokenize(question))
        best = None
        for block in ("\n\n" + excerpts).split("\n\n[")[1:]:
            n = int(block.split("]", 1)[0])
            header, body = (block.split("\n", 1) + [""])[:2]
            common = qtok & set(tokenize(header + " " + body))
            score = len(common) + sum(2 for t in common if "-" in t and any(ch.isdigit() for ch in t))
            if best is None or score > best[0]:
                best = (score, n, body)
        if not best or best[0] < 2:
            return {"status": "not_found", "answer": ""}
        sents = [x.strip() for x in re.split(r"(?<=[.])\s+|\n", best[2])
                 if x.strip() and "instruction-like text removed" not in x]
        sents.sort(key=lambda x: -len(qtok & set(tokenize(x))))
        return {"status": "answered", "answer": " ".join(f"{x} [{best[1]}]" for x in sents[:2])}

    def _sql(self, q):
        for pattern, sql in self.sql_map.items():
            if re.search(pattern, q, re.I):
                return sql
        return None
