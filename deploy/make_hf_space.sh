#!/usr/bin/env bash
# Assemble the folder that becomes the Hugging Face Space (API only). Then push it to the Space's git repo.
#   ./deploy/make_hf_space.sh ../ironvale-api-space
set -euo pipefail
OUT=${1:?usage: make_hf_space.sh <output-folder>}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$OUT"
rsync -a --delete --exclude '__pycache__' --exclude '.pytest_cache' "$ROOT/backend" "$ROOT/corpus" "$ROOT/db" "$OUT/"
cp "$ROOT/golden.jsonl" "$OUT/"
cp "$ROOT/backend/Dockerfile" "$OUT/Dockerfile"
cat > "$OUT/README.md" <<'MD'
---
title: Ironvale shop-floor assistant API
emoji: 🏭
colorFrom: gray
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
---
FastAPI backend for the Ironvale shop-floor assistant (Team Gamma, AI FDE Fellowship week 3).
Endpoints: POST /v1/ask, GET /v1/users, GET /v1/chunks/{id}, GET /v1/eval, POST /v1/feedback, GET /health.
MD
echo "Space folder ready in $OUT"
