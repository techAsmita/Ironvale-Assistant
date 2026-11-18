"""Ironvale shop-floor assistant API.

    uvicorn app.main:app --port 8000          (from backend/)

POST /v1/ask            the one endpoint: {"user_id", "question", "history"} -> AskResponse
GET  /v1/users          demo-user picker
GET  /v1/chunks/{id}    open a cited chunk (only if the user's role may open that document)
GET  /v1/eval           latest eval run, trend across runs, failed questions
POST /v1/feedback       thumbs up/down -> Langfuse score
GET  /health
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import pipeline, telemetry
from .config import get_settings
from .ingest import Chunk
from .pipeline import Services, User
from .retrieval import DenseStore, Retriever
from .schemas import AskRequest, AskResponse

log = logging.getLogger("ironvale")
STATE: dict = {}


def load_services() -> Services:
    s = get_settings()
    with psycopg.connect(s.database_url) as conn:
        users = {r[0]: User(*r) for r in conn.execute("SELECT user_id, name, role, line FROM users")}
        rows = conn.execute("SELECT chunk_id, doc_id, title, section, page, version, effective_date::text, superseded,"
                            " allowed_roles, scope, source, text FROM chunks").fetchall()
    chunks = [Chunk(*r) for r in rows]
    from .graph import Neo4jGraph
    from .sql_agent import Executor

    return Services(Retriever(chunks, DenseStore()), users, Executor(), Neo4jGraph())


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        STATE["svc"] = await run_in_threadpool(load_services)
        from . import models

        await run_in_threadpool(models.warm_up)
        log.info("ready: %d chunks", len(STATE["svc"].retriever.by_id))
    except Exception as e:  # noqa: BLE001 - start anyway; /health reports what is missing
        STATE["startup_error"] = f"{type(e).__name__}: {str(e)[:200]}"
        log.exception("startup failed")
    yield


app = FastAPI(title="Ironvale shop-floor assistant", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_methods=["GET", "POST"],
                   allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Invalid request body",
                                                  "errors": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]})


@app.exception_handler(Exception)
async def any_error(request: Request, exc: Exception):  # never a stack trace to the client
    log.exception("unhandled")
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Try again."})


def svc() -> Services:
    if "svc" not in STATE:
        raise HTTPException(503, "The assistant is starting or misconfigured. Check /health.")
    return STATE["svc"]


@app.get("/health")
def health():
    s = get_settings()
    return {"status": "ok" if "svc" in STATE else "degraded", "startup_error": STATE.get("startup_error"),
            "chunks": len(STATE["svc"].retriever.by_id) if "svc" in STATE else 0, "llm_model": s.llm_model,
            "llm_configured": bool(s.llm_api_key), "langfuse": bool(s.langfuse_public_key),
            "rerank_threshold": s.rerank_threshold}


@app.post("/v1/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    return await run_in_threadpool(pipeline.ask, req, svc())


@app.get("/v1/users")
def users():
    return [{"user_id": u.user_id, "name": u.name, "role": u.role, "scope": u.scope} for u in svc().users.values()]


@app.get("/v1/chunks/{chunk_id}")
def chunk(chunk_id: str, user_id: str):
    s = svc()
    user = s.find_user(user_id)
    c = s.retriever.by_id.get(chunk_id)
    if not user or not c or user.role not in c.allowed_roles:  # denied looks like missing
        raise HTTPException(404, "Not found")
    return {"chunk_id": c.chunk_id, "doc_id": c.doc_id, "title": c.title, "section": c.section, "page": c.page,
            "version": c.version, "effective_date": c.effective_date, "superseded": c.superseded,
            "source": c.source, "text": c.text}


@app.get("/v1/eval")
def eval_runs(limit: int = 20):
    with psycopg.connect(get_settings().database_url) as conn:
        runs = conn.execute("SELECT run_id, created_at, git_commit, prompt_version, model, metrics FROM eval_runs "
                            "ORDER BY created_at DESC LIMIT %s", (limit,)).fetchall()
        failed = []
        if runs:
            failed = conn.execute("SELECT q_id, detail FROM eval_results WHERE run_id = %s AND NOT passed ORDER BY q_id",
                                  (runs[0][0],)).fetchall()
    return {"runs": [{"run_id": r[0], "created_at": r[1].isoformat(), "git_commit": r[2], "prompt_version": r[3],
                      "model": r[4], "metrics": r[5]} for r in runs],
            "failed": [{"id": q, **d} for q, d in failed],
            "langfuse_host": get_settings().langfuse_host}


class Feedback(BaseModel):
    trace_id: str = Field(min_length=3, max_length=80)
    value: int = Field(ge=0, le=1)


@app.post("/v1/feedback")
def feedback(fb: Feedback):
    return {"recorded": telemetry.score(fb.trace_id, float(fb.value))}
