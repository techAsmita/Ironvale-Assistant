"""Local CPU models: BAAI/bge-small-en-v1.5 embeddings and BAAI/bge-reranker-base cross-encoder, both via
fastembed (ONNX, no PyTorch), so the API fits a free CPU host. Models download from Hugging Face on first
use and are cached. Tests swap them for fakes with set_models()."""
from __future__ import annotations

import math
from functools import lru_cache

from .config import get_settings

_override: dict = {}


def set_models(embed=None, embed_query=None, rerank=None) -> None:
    _override.update({k: v for k, v in dict(embed=embed, embed_query=embed_query, rerank=rerank).items() if v})


@lru_cache(maxsize=1)
def _embedder():
    from fastembed import TextEmbedding

    return TextEmbedding(get_settings().embed_model)


@lru_cache(maxsize=1)
def _reranker():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(get_settings().rerank_model)


def embed_passages(texts: list[str]) -> list[list[float]]:
    if "embed" in _override:
        return _override["embed"](texts)
    return [v.tolist() for v in _embedder().passage_embed(texts)]


def embed_query(text: str) -> list[float]:
    if "embed_query" in _override:
        return _override["embed_query"](text)
    return next(iter(_embedder().query_embed([text]))).tolist()


def rerank(query: str, docs: list[str]) -> list[float]:
    """Relevance in 0..1 (sigmoid of the cross-encoder logit), one score per doc."""
    if not docs:
        return []
    if "rerank" in _override:
        return _override["rerank"](query, docs)
    return [1 / (1 + math.exp(-s)) for s in _reranker().rerank(query, docs)]


def warm_up() -> None:
    embed_query("warm up")
    rerank("warm up", ["warm up"])
