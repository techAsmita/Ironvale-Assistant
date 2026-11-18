"""Settings from environment variables (.env locally, the host's secrets in production)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_fast_model: str
    llm_timeout: float
    database_url: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    langfuse_host: str
    langfuse_public_key: str
    langfuse_secret_key: str
    embed_model: str
    rerank_model: str
    rerank_threshold: float
    cors_origins: list[str]
    prompt_version: str = "answer-v1"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    e = os.environ.get
    return Settings(
        llm_base_url=e("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
        llm_api_key=e("LLM_API_KEY", ""),
        llm_model=e("LLM_MODEL", "openai/gpt-oss-120b"),
        llm_fast_model=e("LLM_FAST_MODEL", "") or e("LLM_MODEL", "openai/gpt-oss-120b"),
        llm_timeout=float(e("LLM_TIMEOUT", "40")),
        database_url=e("DATABASE_URL", "postgresql://ironvale:ironvale@localhost:5432/ironvale"),
        neo4j_uri=e("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=e("NEO4J_USER", "neo4j"),
        neo4j_password=e("NEO4J_PASSWORD", ""),
        langfuse_host=e("LANGFUSE_HOST", ""),
        langfuse_public_key=e("LANGFUSE_PUBLIC_KEY", ""),
        langfuse_secret_key=e("LANGFUSE_SECRET_KEY", ""),
        embed_model=e("EMBED_MODEL", "BAAI/bge-small-en-v1.5"),
        rerank_model=e("RERANK_MODEL", "BAAI/bge-reranker-base"),
        rerank_threshold=float(e("RERANK_THRESHOLD", "0.30")),
        cors_origins=[o.strip() for o in e("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()],
    )
