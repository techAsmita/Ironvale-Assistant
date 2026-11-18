"""The /v1/ask pipeline, independent of FastAPI so the eval script runs exactly the same code.

understand -> route -> (docs: retrieve, fuse, rerank, threshold, generate | data: Text-to-SQL | graph: template)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date

from . import answer as answer_mod
from . import graph as graph_mod
from . import sql_agent, understand
from .config import ROOT, get_settings
from .llm import LLMError
from .retrieval import Retriever
from .schemas import (MSG_ERROR, MSG_NOT_FOUND, MSG_OUT_OF_SCOPE, AskRequest, AskResponse, Citation, GraphResult,
                      SqlResult)
from .telemetry import Trace, new_request_id

_HISTORY_Q = re.compile(r"(?i)\b(before|previous(?:ly)?|earlier|old(?:er)?|history|histor(?:ic|ical)|used to|"
                        r"superseded|changed|change from|v[12]\b|version [12]\b)")


@dataclass
class User:
    user_id: str
    name: str
    role: str
    line: int | None

    @property
    def scope(self) -> str:
        return f"Line {self.line}" if self.line else ("All lines" if self.role == "quality_engineer" else "Whole plant")


class Services:
    """Wires the stores. Production: Postgres (pgvector + SQL), Neo4j. Tests/offline eval: in-memory stores."""

    def __init__(self, retriever: Retriever, users: dict[str, User], sql_executor, graph_store, today=None):
        self.retriever, self.users, self.sql_executor, self.graph_store = retriever, users, sql_executor, graph_store
        self.today = today
        self.current_versions = {m["doc_id"]: m for m in _manifest() if not m["superseded"]}

    def find_user(self, user_id: str) -> User | None:
        return self.users.get(user_id)


def _manifest() -> list[dict]:
    return json.loads((ROOT / "corpus" / "manifest.json").read_text())


def ask(req: AskRequest, svc: Services) -> AskResponse:
    s = get_settings()
    rid = new_request_id()
    user = svc.find_user(req.user_id)
    if user is None:  # unknown ids get the same answer as missing data, nothing about who exists
        return AskResponse(request_id=rid, user_id=req.user_id, role="unknown", question=req.question,
                           rewritten_query=req.question, route="out_of_scope", status="not_found",
                           answer=MSG_NOT_FOUND, pipeline={"error_class": "unknown_user"})
    tr = Trace(rid, user.user_id, user.role, len(req.question))
    pipe = {"timings_ms": tr.timings, "model": s.llm_model, "trace_id": tr.trace_id, "error_class": None}
    resp = dict(request_id=rid, user_id=user.user_id, role=user.role, question=req.question,
                rewritten_query=req.question, route="docs", status="error", answer=MSG_ERROR, citations=[],
                sql=None, graph=None)
    try:
        with tr.span("understand", history_turns=len(req.history)) as out:
            u = understand.understand(req.question, [t.model_dump() for t in req.history])
            out.update(rewritten_query=u["rewritten_query"], route=u["route"], fallback=u["fallback"])
        tr.generation("understand", u["model"], u.get("usage"), understand.PROMPT_VERSION)
        resp.update(rewritten_query=u["rewritten_query"], route=u["route"])
        pipe["understand"] = {"model": u["model"], "fallback": u["fallback"]}

        if u["route"] == "out_of_scope":
            resp.update(status="out_of_scope", answer=MSG_OUT_OF_SCOPE)
        elif u["route"] == "docs":
            _docs(u["rewritten_query"], user, svc, tr, resp, pipe)
        elif u["route"] == "data":
            _data(u["rewritten_query"], user, svc, tr, resp, pipe)
        else:
            _graph(u["rewritten_query"], user, svc, tr, resp, pipe)
    except LLMError as e:
        resp.update(status="error", answer=MSG_ERROR, citations=[], sql=None, graph=None)
        pipe["error_class"] = e.error_class
    except Exception as e:  # noqa: BLE001 - never a stack trace to the client
        resp.update(status="error", answer=MSG_ERROR, citations=[], sql=None, graph=None)
        pipe["error_class"] = type(e).__name__
    if resp["status"] in ("not_found", "out_of_scope"):
        resp.update(citations=[], sql=None, graph=None)
    tr.end(role=user.role, route=resp["route"], status=resp["status"], error_class=pipe["error_class"],
           rewritten_query=resp["rewritten_query"], cited_doc_ids=[c.doc_id for c in resp["citations"]],
           prompt_version=pipe.get("prompt_version"))
    pipe["spans"] = [sp["name"] for sp in tr.spans]
    return AskResponse(**resp, pipeline=pipe)


def _docs(query: str, user: User, svc: Services, tr: Trace, resp: dict, pipe: dict) -> None:
    s = get_settings()
    pipe["prompt_version"] = answer_mod.PROMPT_VERSION
    r = svc.retriever
    with tr.span("retrieve.bm25", role=user.role) as out:
        bm = r.search_bm25(query, user.role)
        out.update(count=len(bm), chunk_ids=[c for c, _ in bm[:10]])
    with tr.span("retrieve.dense", role=user.role) as out:
        de = r.search_dense(query, user.role)
        out.update(count=len(de), chunk_ids=[c for c, _ in de[:10]])
    with tr.span("fuse", k=60) as out:
        fused = r.rrf(bm, de)
        out.update(count=len(fused))
    with tr.span("rerank", model=s.rerank_model) as out:
        res = _rerank(r, query, user.role, fused)
        out.update(reranked=[(h.chunk.chunk_id, round(h.score, 3)) for h in res["hits"]], top=round(res["top_score"], 3),
                   code_gate=res["codes"])
    pipe["retrieved"] = {"bm25": len(bm), "dense": len(de), "fused": len(fused), "reranked": len(res["hits"])}
    pipe["top_rerank_score"] = round(res["top_score"], 3)
    pipe["rerank_threshold"] = s.rerank_threshold
    hits = res["hits"]
    if not hits or res["top_score"] < s.rerank_threshold:
        resp.update(status="not_found", answer=MSG_NOT_FOUND)
        return
    hits = prefer_current(hits, query)
    note = superseded_note(hits, svc)
    with tr.span("generate", chunks=[h.chunk.chunk_id for h in hits], prompt_version=answer_mod.PROMPT_VERSION) as out:
        q = query + (f"\n\n(Note for the answer: {note})" if note else "")
        a = answer_mod.answer_docs(q, hits)
        out.update(status=a["status"], cited=[c.doc_id for c in a["citations"]])
    tr.generation("generate", a.get("model", s.llm_model), a.get("usage"), answer_mod.PROMPT_VERSION)
    resp.update(status=a["status"], answer=a["answer"], citations=a["citations"])


def _rerank(r: Retriever, query: str, role: str, fused) -> dict:
    """Re-rank + exact-code gate (shared with Retriever.retrieve, split out so each step gets its own span)."""
    from . import models
    from .retrieval import KEEP, Hit, codes_in, normalise_codes

    cands = [r.by_id[cid] for cid, _ in fused[:30]]
    assert all(role in c.allowed_roles for c in cands)
    scores = models.rerank(normalise_codes(query), [c.search_text() for c in cands])
    ranked = sorted(zip(cands, scores), key=lambda x: -x[1])
    asked = codes_in(query)
    if asked:
        ranked = [(c, sc) for c, sc in ranked if asked & codes_in(c.search_text())]
    top = ranked[:KEEP]
    return {"hits": [Hit(c, sc) for c, sc in top], "top_score": top[0][1] if top else 0.0, "codes": sorted(asked)}


def prefer_current(hits, query: str):
    """Superseded chunks stay in the index, but when the current version of the same document was also
    retrieved and the question is not about history, the model only sees the current one."""
    if _HISTORY_Q.search(query):
        return hits
    current_docs = {h.chunk.doc_id for h in hits if not h.chunk.superseded}
    return [h for h in hits if not (h.chunk.superseded and h.chunk.doc_id in current_docs)]


def superseded_note(hits, svc: Services) -> str | None:
    """If only superseded versions of a document matched, tell the model the current version's date."""
    notes = []
    for doc in {h.chunk.doc_id for h in hits if h.chunk.superseded}:
        if all(h.chunk.superseded for h in hits if h.chunk.doc_id == doc) and doc in svc.current_versions:
            cur = svc.current_versions[doc]
            notes.append(f"{doc} {cur['version']} is the current version, effective {cur['effective_date']}; "
                         f"the excerpt shown is superseded.")
    return " ".join(notes) or None


def _data(query: str, user: User, svc: Services, tr: Trace, resp: dict, pipe: dict) -> None:
    pipe["prompt_version"] = sql_agent.PROMPT_VERSION
    timings: dict = {}
    res = sql_agent.answer_data(query, user.role, user.user_id, executor=svc.sql_executor, timings=timings)
    for name, info in res["spans"]:
        with tr.span(name) as out:
            out.update(info)
    if res.get("sql"):
        with tr.span("sql.result") as out:  # SQL text and row count only, never the rows
            out.update(sql=res["sql"]["query"], row_count=res["sql"]["row_count"])
    tr.generation("sql.generate", get_settings().llm_model, res.get("usage"), sql_agent.PROMPT_VERSION)
    pipe["error_class"] = res.get("error_class")
    pipe["timings_ms"].update(timings)
    if res["status"] == "answered":
        resp.update(status="answered", answer=res["answer"], sql=SqlResult(**res["sql"]))
    elif res["status"] == "not_found":
        resp.update(status="not_found", answer=MSG_NOT_FOUND)
    else:
        resp.update(status="error", answer=MSG_ERROR,
                    sql=SqlResult(**res["sql"]) if res.get("sql") else None)


def _graph(query: str, user: User, svc: Services, tr: Trace, resp: dict, pipe: dict) -> None:
    pipe["prompt_version"] = graph_mod.PROMPT_VERSION
    today = svc.today or date.today()
    with tr.span("graph.fill") as out:
        fill = graph_mod.fill_template(query, today)
        out.update(template=fill["template"], params=fill["params"])
    if not fill["template"]:
        resp.update(status="not_found", answer=MSG_NOT_FOUND)
        return
    allowed = graph_mod.openable_sources(user.role, user.line)
    with tr.span("graph.query", template=fill["template"], params=fill["params"]) as out:
        p = fill["params"]
        if fill["template"] == "supplier_exposure":
            rows = svc.graph_store.supplier_exposure(p["supplier"], allowed)
        else:
            rows = svc.graph_store.deviation_trail(int(p["line"]), p["date_from"], p["date_to"], allowed)
        out.update(path_count=len(rows))
    if not rows:
        resp.update(status="not_found", answer=MSG_NOT_FOUND)
        return
    rendered = graph_mod.render(fill["template"], p, rows)
    meta = {m["doc_id"]: m for m in _manifest() if not m["superseded"]}
    cites = [Citation(n=i, doc_id=d, title=meta[d]["title"], version=meta[d]["version"],
                      effective_date=meta[d]["effective_date"])
             for i, d in enumerate(rendered["sources"], 1) if d in meta]
    resp.update(status="answered", answer=rendered["answer"], citations=cites,
                graph=GraphResult(template=fill["template"], params=p, paths=rendered["paths"]))
