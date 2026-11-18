"""Offline demo server for UI work: in-memory retrieval and graph, fake LLM, local Postgres for SQL.
Not used in production. Run from backend/:  TEST_DATABASE_URL=... python tests/dev_server.py"""
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", os.environ.get("DATABASE_URL", ""))

import conftest  # noqa: E402  (sets fake models)
import fakes  # noqa: E402
import uvicorn  # noqa: E402
from app import llm, main  # noqa: E402
from app.graph import MemoryGraph, build_graph  # noqa: E402
from app.ingest import load_jsonl  # noqa: E402
from app.pipeline import Services, User  # noqa: E402
from app.retrieval import MemoryDenseStore, Retriever  # noqa: E402
from app.sql_agent import Executor  # noqa: E402

llm.set_client(fakes.FakeLLM(sql_map=conftest.sql_map()))
chunks = load_jsonl()
sys.path.insert(0, str(Path(__file__).parents[2] / "db"))
import seed  # noqa: E402
wos, _, _ = seed.build()
g = build_graph(chunks, [(m[0], m[1], m[2], m[3]) for m in seed.MACHINES], sorted({(w[1], w[2]) for w in wos}), use_llm=False)
users = {u[0]: User(*u) for u in seed.USERS}

main.load_services = lambda: main.STATE["svc"]  # skip the production wiring (pgvector, Neo4j)
main.STATE["svc"] = Services(Retriever(chunks, MemoryDenseStore(chunks)), users, Executor(), MemoryGraph(g), today=date(2026, 11, 18))
uvicorn.run(main.app, host="127.0.0.1", port=8000, log_level="warning")
