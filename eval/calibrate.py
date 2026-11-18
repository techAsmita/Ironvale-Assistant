"""Calibrate the re-ranker not_found threshold on the golden set (docs route).

    cd backend && python ../eval/calibrate.py

For each docs question it records the best re-rank score the user's role can reach. Answerable questions
should score above the threshold and not_found questions (leak tests, missing facts) below it. Prints the
threshold that maximises refusal accuracy; put it in .env (RERANK_THRESHOLD) and in the README.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import pipeline  # noqa: E402
from app.ingest import load_jsonl  # noqa: E402
from app.retrieval import MemoryDenseStore, Retriever  # noqa: E402

ROLE = {"u_sup_l1": "line_supervisor", "u_sup_l3": "line_supervisor", "u_qe": "quality_engineer", "u_head": "plant_head"}


def main():
    if "--fake" in sys.argv:
        sys.path.insert(0, str(ROOT / "backend" / "tests"))
        import fakes
        from app import models
        models.set_models(embed=fakes.embed, embed_query=fakes.embed_query, rerank=fakes.rerank)
    golden = [json.loads(l) for l in (ROOT / "golden.jsonl").read_text().splitlines() if l.strip()]
    cs = load_jsonl()
    r = Retriever(cs, MemoryDenseStore(cs))
    pts = []
    for g in golden:
        if g["expected_route"] != "docs" or g["history"]:
            continue
        role = ROLE[g["user_id"]]
        fused = r.rrf(r.search_bm25(g["question"], role), r.search_dense(g["question"], role))
        top = pipeline._rerank(r, g["question"], role, fused)["top_score"]
        pts.append((top, g["expected_status"] == "answered", g["id"]))
        print(f"{g['id']:<5} {'answer' if pts[-1][1] else 'refuse':<7} top re-rank {top:.3f}  {g['question'][:60]}")
    best = max((sum((s >= t) == ans for s, ans, _ in pts) / len(pts), -abs(t - 0.3), t)
               for t in [i / 100 for i in range(1, 100)])
    print(f"\nbest threshold {best[2]:.2f} -> refusal/answer agreement {best[0]:.2%} on {len(pts)} docs questions")


if __name__ == "__main__":
    main()
