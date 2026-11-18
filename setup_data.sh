#!/usr/bin/env bash
# One command to (re)build all data: plant database, retrieval index, knowledge graph.
# Needs .env (DATABASE_URL, NEO4J_*, and optionally LLM_API_KEY for LLM graph extraction).
set -euo pipefail
cd "$(dirname "$0")"
python db/seed.py                       # schema, users, plant data, role views and RLS
cd backend
python -m app.ingest                    # parse + OCR + mask + chunk + embed -> pgvector
python -m app.build_graph               # Neo4j
echo "Data ready. Start the API: cd backend && uvicorn app.main:app --port 8000"
