"""Ironvale shop-floor assistant API.

    uvicorn app.main:app --port 8000          (from backend/)

POST /v1/ask            the one endpoint: {"user_id", "question", "history"} -> AskResponse
GET  /v1/users          demo-user picker
GET  /v1/chunks/{id}    open a cited chunk (only if the user's role may open that document)
GET  /v1/documents      documents the user's role may open (one row per document version)
GET  /v1/overview       real plant figures in the user's scope (coverage, machines, downtime, alarms)
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


DOC_KIND = {"SOP": "Standard operating procedure", "WI": "Work instruction", "MAN": "Machine manual",
            "QDR": "Quality deviation report", "ASL": "Approved supplier list", "SQA": "Supplier quality agreement",
            "PRC": "Price list"}


@app.get("/v1/documents")
def documents(user_id: str):
    """Only what the role can open; restricted documents are not listed or counted."""
    s = svc()
    user = s.find_user(user_id)
    if not user:
        raise HTTPException(404, "Not found")
    docs: dict[tuple, dict] = {}
    for c in s.retriever.by_id.values():
        if user.role not in c.allowed_roles:
            continue
        d = docs.setdefault((c.doc_id, c.version), {
            "doc_id": c.doc_id, "title": c.title, "version": c.version, "effective_date": c.effective_date,
            "superseded": c.superseded, "scope": c.scope, "source": c.source,
            "kind": DOC_KIND.get(c.doc_id.split("-")[0], "Document"), "pages": set(), "sections": 0,
            "first_chunk_id": c.chunk_id})
        d["sections"] += 1
        if c.page is not None:
            d["pages"].add(c.page)
        d.setdefault("_rank", [])
        d["_rank"].append(("-row-" in c.chunk_id, c.page or 0, c.chunk_id))
    out = []
    for d in sorted(docs.values(), key=lambda d: (d["doc_id"], d["superseded"])):
        d["first_chunk_id"] = min(d.pop("_rank"))[2]
        pages = sorted(d.pop("pages"))
        d["page_range"] = [pages[0], pages[-1]] if pages else None
        out.append(d)
    return out


OVERVIEW_SQL = {
    "machines": "SELECT machine_id, line, type, model FROM machines ORDER BY machine_id",
    "coverage": "SELECT min(start_at)::date, max(start_at)::date, count(*) FROM downtime_events",
    "orders": "SELECT count(*), sum(qty_good), sum(qty_planned) FROM work_orders",
    "breakdown_by_month": "SELECT to_char(date_trunc('month', start_at), 'YYYY-MM') AS month, "
                          "round(sum(extract(epoch FROM end_at - start_at)) / 3600.0, 1) AS hours, count(*) AS events "
                          "FROM downtime_events WHERE category = 'breakdown' GROUP BY 1 ORDER BY 1",
    "downtime_by_category": "SELECT category, round(sum(extract(epoch FROM end_at - start_at)) / 3600.0, 1) AS hours "
                            "FROM downtime_events GROUP BY 1 ORDER BY 2 DESC",
    "breakdown_by_machine": "SELECT machine_id, round(sum(extract(epoch FROM end_at - start_at)) / 3600.0, 1) AS hours, "
                            "count(*) AS events FROM downtime_events WHERE category = 'breakdown' "
                            "AND start_at >= date_trunc('month', (SELECT max(start_at) FROM downtime_events)) "
                            "GROUP BY 1 ORDER BY 2 DESC",
    "alarms": "SELECT alarm_code, count(*) AS events, round(sum(extract(epoch FROM end_at - start_at)) / 3600.0, 1) AS hours, "
              "count(DISTINCT machine_id) AS machines FROM downtime_events WHERE alarm_code IS NOT NULL "
              "GROUP BY 1 ORDER BY 2 DESC LIMIT 8",
    "recent": "SELECT machine_id, start_at, round(extract(epoch FROM end_at - start_at) / 60.0) AS minutes, reason_code, "
              "alarm_code FROM downtime_events WHERE category = 'breakdown' ORDER BY start_at DESC LIMIT 8",
    "defects": "SELECT count(*), sum(qty) FROM defects",
    "yield_by_month": "SELECT to_char(date_trunc('month', started_at), 'YYYY-MM') AS month, "
                      "round(100.0 * sum(qty_good) / nullif(sum(qty_planned), 0), 1) AS yield_pct "
                      "FROM work_orders GROUP BY 1 ORDER BY 1",
}


@app.get("/v1/overview")
def overview(user_id: str):
    """Fixed queries run as the user's restricted database role, so row scope (RLS) applies as for any question."""
    s = svc()
    user = s.find_user(user_id)
    if not user:
        raise HTTPException(404, "Not found")
    ex = s.sql_executor
    q = {}
    for key, sql in OVERVIEW_SQL.items():
        if key == "defects" and user.role == "line_supervisor":
            continue
        try:
            q[key] = ex.run(sql, user.role, user.user_id)
        except Exception:  # noqa: BLE001 - one missing figure must not blank the page
            log.exception("overview %s", key)
    rows = lambda k: q[k][1] if k in q else []  # noqa: E731
    cov = rows("coverage")[0] if rows("coverage") else [None, None, 0]
    orders = rows("orders")[0] if rows("orders") else [0, None, None]
    defects = rows("defects")[0] if rows("defects") else None
    return {
        "user": {"user_id": user.user_id, "name": user.name, "role": user.role, "line": user.line},
        "coverage": {"from": cov[0], "to": cov[1], "downtime_events": cov[2]},
        "machines": [dict(zip(["machine_id", "line", "type", "model"], r)) for r in rows("machines")],
        "work_orders": {"count": orders[0], "yield_pct": round(100 * orders[1] / orders[2], 1) if orders[2] else None},
        "defects": None if defects is None else {"records": defects[0], "qty": defects[1] or 0},
        "breakdown_by_month": [dict(zip(["month", "hours", "events"], r)) for r in rows("breakdown_by_month")],
        "downtime_by_category": [dict(zip(["category", "hours"], r)) for r in rows("downtime_by_category")],
        "breakdown_by_machine": [dict(zip(["machine_id", "hours", "events"], r)) for r in rows("breakdown_by_machine")],
        "alarms": [dict(zip(["alarm_code", "events", "hours", "machines"], r)) for r in rows("alarms")],
        "recent_breakdowns": [dict(zip(["machine_id", "start_at", "minutes", "reason_code", "alarm_code"], r))
                              for r in rows("recent")],
        "yield_by_month": [dict(zip(["month", "yield_pct"], r)) for r in rows("yield_by_month")],
        "documents": len({(d["doc_id"]) for d in documents(user_id) if not d["superseded"]}),
    }


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
