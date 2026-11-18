"""Steps 2 and 4: two indexes over the same chunk ids, hybrid retrieval, fusion and re-ranking.

Access control happens inside both queries, before any scoring:
  * BM25: one index per role, built only from chunks that role may open.
  * Dense: pgvector query with `WHERE allowed_roles @> ARRAY[role]`.
So the fuser, the re-ranker and the LLM never see a chunk the user cannot open.

Exact codes (E-417 vs E-471, HX-220-B, SOP ids) carry the meaning. The BM25 tokenizer keeps them whole,
and an exact-code gate drops re-ranked chunks that do not contain a code the question names.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import numpy as np
from rank_bm25 import BM25Okapi

from . import models
from .config import get_settings
from .ingest import Chunk

ROLES = ("line_supervisor", "quality_engineer", "plant_head")
TOP_K, KEEP, RRF_K = 20, 5, 60

_TOKEN = re.compile(r"[a-z0-9]+(?:[-./][a-z0-9]+)*")
_STOP = set("a an the of on in at to for is are was what which how does do did i my me it its this that "
            "with by from and or be can should when where who whom whose why there their".split())
# Codes that carry meaning: alarms (E-417, F-30, L-05), parts (HX-220-B, BR-310-A), docs (SOP-L2-011, QDR-2026-014),
# machines (CNC-L1-04).
CODE = re.compile(r"\b(?:[A-Z]{1,4}-[A-Z0-9]{1,4}(?:-[A-Z0-9]{1,4})*)\b")


def normalise_codes(text: str) -> str:
    """'e417', 'E 417', 'e-417' -> 'E-417'. 'hx220b' -> 'HX-220-B'."""
    text = re.sub(r"\b([EeFfLlPp])\s?-?\s?(\d{2,3})\b", lambda m: f"{m.group(1).upper()}-{m.group(2)}", text)
    text = re.sub(r"\b([Hh][Xx]|[Bb][Rr])\s?-?(\d{3})\s?-?([A-Za-z])\b",
                  lambda m: f"{m.group(1).upper()}-{m.group(2)}-{m.group(3).upper()}", text)
    return text


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(normalise_codes(text).lower()) if t not in _STOP]


def codes_in(text: str) -> set[str]:
    return {c for c in CODE.findall(normalise_codes(text)) if any(ch.isdigit() for ch in c)}


@dataclass
class Hit:
    chunk: Chunk
    score: float = 0.0
    ranks: dict = field(default_factory=dict)


class DenseStore:
    """pgvector in production."""

    def search(self, qvec: list[float], role: str, k: int) -> list[tuple[str, float]]:
        import psycopg

        vec = "[" + ",".join(f"{x:.6f}" for x in qvec) + "]"
        with psycopg.connect(get_settings().database_url) as conn:
            rows = conn.execute(
                "SELECT chunk_id, 1 - (embedding <=> %s::vector) AS sim FROM chunks "
                "WHERE allowed_roles @> ARRAY[%s]::text[] ORDER BY embedding <=> %s::vector LIMIT %s",
                (vec, role, vec, k)).fetchall()
        return [(r[0], float(r[1])) for r in rows]


class MemoryDenseStore:
    """Same contract, in memory (tests and offline evaluation). The role filter runs before scoring."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.mat = np.array(models.embed_passages([c.search_text() for c in chunks]), dtype=np.float32)
        self.mat /= np.linalg.norm(self.mat, axis=1, keepdims=True) + 1e-9

    def search(self, qvec, role, k):
        idx = [i for i, c in enumerate(self.chunks) if role in c.allowed_roles]
        q = np.asarray(qvec, dtype=np.float32)
        q /= np.linalg.norm(q) + 1e-9
        sims = self.mat[idx] @ q
        order = np.argsort(-sims)[:k]
        return [(self.chunks[idx[i]].chunk_id, float(sims[i])) for i in order]


class Retriever:
    def __init__(self, chunks: list[Chunk], dense=None):
        self.by_id = {c.chunk_id: c for c in chunks}
        self.dense = dense or DenseStore()
        self.bm25: dict[str, tuple[BM25Okapi, list[Chunk]]] = {}
        for role in ROLES:
            allowed = [c for c in chunks if role in c.allowed_roles]
            self.bm25[role] = (BM25Okapi([tokenize(c.search_text()) for c in allowed]), allowed)

    # -- the three retrievers compared in the README
    def search_bm25(self, query: str, role: str, k: int = TOP_K) -> list[tuple[str, float]]:
        index, allowed = self.bm25[role]
        scores = index.get_scores(tokenize(query))
        order = np.argsort(-scores)[:k]
        return [(allowed[i].chunk_id, float(scores[i])) for i in order if scores[i] > 0]

    def search_dense(self, query: str, role: str, k: int = TOP_K) -> list[tuple[str, float]]:
        return self.dense.search(models.embed_query(normalise_codes(query)), role, k)

    @staticmethod
    def rrf(*lists: list[tuple[str, float]], k: int = RRF_K) -> list[tuple[str, float]]:
        fused: dict[str, float] = {}
        for lst in lists:
            for rank, (cid, _) in enumerate(lst, 1):
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (k + rank)
        return sorted(fused.items(), key=lambda x: -x[1])

    def retrieve(self, query: str, role: str, span=None) -> dict:
        """Full docs-route retrieval. Returns hits (top 5 after re-ranking and the code gate) plus stats."""
        t = {}
        t0 = time.perf_counter()
        bm = self.search_bm25(query, role)
        t["retrieve_bm25"] = int((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter()
        de = self.search_dense(query, role)
        t["retrieve_dense"] = int((time.perf_counter() - t0) * 1000)
        fused = self.rrf(bm, de)
        t0 = time.perf_counter()
        cands = [self.by_id[cid] for cid, _ in fused[:30]]
        assert all(role in c.allowed_roles for c in cands)  # defence in depth: the filter already ran
        scores = models.rerank(normalise_codes(query), [c.search_text() for c in cands])
        ranked = sorted(zip(cands, scores), key=lambda x: -x[1])
        t["rerank"] = int((time.perf_counter() - t0) * 1000)

        asked = codes_in(query)
        gated = ranked
        if asked:  # exact-code gate: keep only chunks that contain a code the question names
            gated = [(c, s) for c, s in ranked if asked & codes_in(c.search_text())]
        top = gated[:KEEP]
        return {
            "hits": [Hit(c, s) for c, s in top],
            "top_score": top[0][1] if top else 0.0,
            "codes": sorted(asked),
            "counts": {"bm25": len(bm), "dense": len(de), "fused": len(fused), "reranked": len(top)},
            "timings": t,
            "ids": {"bm25": [c for c, _ in bm[:10]], "dense": [c for c, _ in de[:10]],
                    "reranked": [(h.chunk_id, round(s, 3)) for h, s in top]},
        }
