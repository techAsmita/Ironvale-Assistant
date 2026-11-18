"""Build the knowledge graph and load it into Neo4j.

    python -m app.build_graph          # from backend/, after db/seed.py and app.ingest

Machine rows and machine->part runs come straight from Postgres; the rest is extracted chunk by chunk
(LLM restricted to the schema when LLM_API_KEY is set, otherwise the deterministic extractor).
"""
from __future__ import annotations

import psycopg

from .config import get_settings
from .graph import Neo4jGraph, build_graph
from .ingest import load_jsonl


def main() -> None:
    with psycopg.connect(get_settings().database_url) as conn:
        machines = conn.execute("SELECT machine_id, line, type, model FROM machines ORDER BY 1").fetchall()
        runs = conn.execute("SELECT DISTINCT machine_id, part_no FROM work_orders ORDER BY 1, 2").fetchall()
    g = build_graph(load_jsonl(), machines, runs)
    Neo4jGraph().load(g)
    print("graph loaded:", g.stats())


if __name__ == "__main__":
    main()
