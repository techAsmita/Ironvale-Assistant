import json
import os
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "")
os.environ.setdefault("RERANK_THRESHOLD", "0.30")

import fakes  # noqa: E402
from app import llm, models  # noqa: E402

models.set_models(embed=fakes.embed, embed_query=fakes.embed_query, rerank=fakes.rerank)

TEST_DB = os.environ.get("TEST_DATABASE_URL", "")


def golden():
    return [json.loads(l) for l in (ROOT / "golden.jsonl").read_text().splitlines() if l.strip()]


def sql_map():
    g = {r["id"]: r for r in golden()}
    return {
        r"breakdown downtime by machine on line 1 in october": g["G-05"]["gold_sql"],
        r"breakdown downtime by machine on line 1 in september": g["G-26"]["gold_sql"],
        r"top 3 machines by breakdown downtime on line 1 in september": g["G-22"]["gold_sql"],
        r"yield by machine on line 3": g["G-23"]["gold_sql"],
        r"defect quantity by defect type": g["G-24"]["gold_sql"],
        r"monthly breakdown downtime": g["G-25"]["gold_sql"],
        r"e-417 stop cnc-l1-04": g["G-30"]["gold_sql"],
        r"downtime on line 3 in october": "SELECT d.machine_id, ROUND(SUM(EXTRACT(EPOCH FROM d.end_at - d.start_at) / 60)) AS downtime_minutes FROM downtime_events d JOIN machines m ON m.machine_id = d.machine_id WHERE m.line = 3 AND d.start_at >= '2026-10-01' AND d.start_at < '2026-11-01' GROUP BY d.machine_id ORDER BY d.machine_id",
    }


@pytest.fixture(scope="session")
def chunks():
    from app.ingest import load_jsonl
    return load_jsonl()


@pytest.fixture(scope="session")
def retriever(chunks):
    from app.retrieval import MemoryDenseStore, Retriever
    return Retriever(chunks, MemoryDenseStore(chunks))


@pytest.fixture(scope="session")
def db_rows():
    """Machines and machine->part runs, straight from the seed generator (no database needed)."""
    sys.path.insert(0, str(ROOT / "db"))
    import seed
    wos, _, _ = seed.build()
    machines = [(m[0], m[1], m[2], m[3]) for m in seed.MACHINES]
    runs = sorted({(w[1], w[2]) for w in wos})
    return machines, runs


@pytest.fixture(scope="session")
def graph_store(chunks, db_rows):
    from app.graph import MemoryGraph, build_graph
    return MemoryGraph(build_graph(chunks, *db_rows, use_llm=False))


class NoDbExecutor:
    def run(self, sql, role, user_id):
        raise RuntimeError("no test database")


@pytest.fixture
def services(retriever, graph_store):
    from app.pipeline import Services, User
    users = {"u_sup_l1": User("u_sup_l1", "Priya Natarajan", "line_supervisor", 1),
             "u_sup_l3": User("u_sup_l3", "Karthik Selvam", "line_supervisor", 3),
             "u_qe": User("u_qe", "Farah Qureshi", "quality_engineer", None),
             "u_head": User("u_head", "Vikram Rao", "plant_head", None)}
    if TEST_DB:
        os.environ["DATABASE_URL"] = TEST_DB
        from app.config import get_settings
        get_settings.cache_clear()
        from app.sql_agent import Executor
        ex = Executor()
    else:
        ex = NoDbExecutor()
    return Services(retriever, users, ex, graph_store, today=date(2026, 11, 18))


@pytest.fixture
def fake_llm():
    f = fakes.FakeLLM(sql_map=sql_map())
    llm.set_client(f)
    yield f
    llm.set_client(None)
