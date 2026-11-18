"""Exact-code check required by the brief: BM25 alone, dense alone and hybrid (RRF + re-ranker + code gate)
on every alarm question in the golden set, with and without table-aware ingestion (stretch goal).

    cd backend && python ../eval/alarm_compare.py            # real bge models (run on your machine)

A question passes at top-1 when the first chunk contains the asked code; it is "confused" when any of the
top 5 is about a different alarm code but not the asked one (E-471 returned for E-417).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import pipeline  # noqa: E402
from app.ingest import load_jsonl  # noqa: E402
from app.retrieval import MemoryDenseStore, Retriever, codes_in  # noqa: E402

ALARM = __import__("re").compile(r"\b[EFL]-\d{2,3}\b")


def evaluate(retriever: Retriever, questions: list[dict]) -> dict:
    out = {}
    for mode in ("bm25", "dense", "hybrid"):
        top1 = confused = 0
        rows = []
        for g in questions:
            q, code, role = g["question"], g["alarm_lookup"], "line_supervisor"
            if mode == "bm25":
                ids = [c for c, _ in retriever.search_bm25(q, role, 5)]
            elif mode == "dense":
                ids = [c for c, _ in retriever.search_dense(q, role, 5)]
            else:
                fused = retriever.rrf(retriever.search_bm25(q, role), retriever.search_dense(q, role))
                ids = [h.chunk.chunk_id for h in pipeline._rerank(retriever, q, role, fused)["hits"]]
            chunks = [retriever.by_id[i] for i in ids]
            ok = bool(chunks) and code in chunks[0].text
            bad = any(ALARM.findall(c.text) and code not in c.text for c in chunks)
            top1 += ok
            confused += bad
            rows.append({"id": g["id"], "code": code, "top1": ids[0] if ids else None, "ok": ok, "confused": bad})
        out[mode] = {"top1_accuracy": round(top1 / len(questions), 3), "confused": confused, "rows": rows}
    return out


def main():
    golden = [json.loads(l) for l in (ROOT / "golden.jsonl").read_text().splitlines() if l.strip()]
    qs = [g for g in golden if g.get("alarm_lookup") and g["id"] != "G-02"]
    if "--fake" in sys.argv:  # offline smoke test with the test doubles
        sys.path.insert(0, str(ROOT / "backend" / "tests"))
        import fakes
        from app import models
        models.set_models(embed=fakes.embed, embed_query=fakes.embed_query, rerank=fakes.rerank)
    chunks = load_jsonl()
    report = {}
    for label, cs in (("table-aware (rows as chunks)", chunks),
                      ("plain (no row chunks)", [c for c in chunks if "· row" not in (c.section or "")])):
        r = evaluate(Retriever(cs, MemoryDenseStore(cs)), qs)
        report[label] = r
        print(f"\n{label}: {len(qs)} alarm questions")
        print(f"{'retriever':<8} {'top-1 acc':>9} {'confused':>9}")
        for mode in ("bm25", "dense", "hybrid"):
            print(f"{mode:<8} {r[mode]['top1_accuracy']:>9} {r[mode]['confused']:>9}")
    (ROOT / "eval" / "runs" / "alarm_compare.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
