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
        overlap = len(q & dt) / (len(q) or 1)
        out.append(1 / (1 + math.exp(-(8 * overlap - 4))))
    return out
