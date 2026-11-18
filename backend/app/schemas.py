"""The /v1/ask response contract, exactly as the Week 3 project rules define it."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

Route = Literal["docs", "data", "graph", "out_of_scope"]
Status = Literal["answered", "not_found", "out_of_scope", "error"]

MSG_NOT_FOUND = "I couldn't find that in the documents and data you have access to."
MSG_OUT_OF_SCOPE = "That's outside what this assistant covers."
MSG_ERROR = "Something went wrong. Try again."


class Citation(BaseModel):
    n: int
    doc_id: str
    title: str
    section: str | None = None
    page: int | None = None
    version: str | None = None
    effective_date: date | None = None
    superseded: bool = False
    chunk_id: str | None = None  # extra: lets the UI open the cited chunk


class SqlResult(BaseModel):
    query: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    chart: dict | None = None


class GraphResult(BaseModel):
    template: str
    params: dict[str, str]
    paths: list[list[str]]


class AskResponse(BaseModel):
    request_id: str
    user_id: str
    role: str
    question: str
    rewritten_query: str
    route: Route
    status: Status
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    sql: SqlResult | None = None
    graph: GraphResult | None = None
    pipeline: dict = Field(default_factory=dict)


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=50)
