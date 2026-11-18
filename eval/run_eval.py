"""Run the golden set and score it. Stores the run for the Eval page and writes eval/runs/latest.json.

    cd backend && python ../eval/run_eval.py                 # in-process, against Postgres/Neo4j from .env
    cd backend && python ../eval/run_eval.py --api URL       # against a running /v1/ask (e.g. the deployed API)
    options: --no-ragas  --only G-01,G-05  --no-store

Metrics (targets from the project rules)
  faithfulness ≥0.85, response relevancy ≥0.80, context precision/recall (RAGAS, docs + graph answers)
  citation accuracy ≥0.90   answered questions whose citations include an expected doc_id
  refusal accuracy ≥0.90    status matches on not_found/out_of_scope, and no refusal of answerable ones
  access leaks = 0          any must_not_contain string in answer, citations or SQL rows; any cited doc the
                            user can't open
  SQL execution accuracy ≥0.80   our result set equals the gold SQL's (order ignored unless asked)
  hallucination rate        answered questions with faithfulness < 0.7
  latency p50/p95 per route, cost per question
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# USD per million tokens. Check the provider's pricing page before quoting costs; edit here if it changed.
PRICES = {"openai/gpt-oss-120b": (0.15, 0.60), "llama-3.1-8b-instant": (0.05, 0.08),
          "gpt-4.1-mini": (0.40, 1.60), "gpt-4.1-nano": (0.10, 0.40)}
USD_INR = 88.0


def load_golden(only: set[str] | None):
    rows = [json.loads(l) for l in (ROOT / "golden.jsonl").read_text().splitlines() if l.strip()]
    return [r for r in rows if not only or r["id"] in only]


def ask_inprocess(svc):
    from app import pipeline
    from app.schemas import AskRequest

    def f(g):
        return pipeline.ask(AskRequest(user_id=g["user_id"], question=g["question"], history=g["history"]), svc
                            ).model_dump(mode="json")
    return f


def ask_api(url):
    import httpx
    cl = httpx.Client(timeout=120)

    def f(g):
        r = cl.post(f"{url.rstrip('/')}/v1/ask", json={"user_id": g["user_id"], "question": g["question"],
                                                       "history": g["history"]})
        r.raise_for_status()
        return r.json()
    return f


def allowed_docs(role: str) -> set[str]:
    man = json.loads((ROOT / "corpus" / "manifest.json").read_text())
    return {m["doc_id"] for m in man if role in m["allowed_roles"]}


def check(g: dict, r: dict, gold_rows) -> dict:
    shown = r["answer"] + json.dumps(r["citations"]) + json.dumps((r.get("sql") or {}).get("rows", []))
    leaks = [s for s in g.get("must_not_contain", []) if s and s in shown]
    leaks += [f"cited:{c['doc_id']}" for c in r["citations"] if c["doc_id"] not in allowed_docs(r["role"])]
    refusal_q = g["expected_status"] in ("not_found", "out_of_scope")
    d = {
        "route_ok": r["route"] == g["expected_route"],
        "status_ok": r["status"] == g["expected_status"],
        "refused_answerable": (not refusal_q) and r["status"] in ("not_found", "out_of_scope"),
        "leaks": leaks,
        "must_contain_ok": all(s in r["answer"] for s in g.get("must_contain", [])),
        "rewrite_ok": all(s in r["rewritten_query"] for s in g.get("expected_rewrite_contains", [])),
    }
    if r["status"] == "answered" and g["expected_doc_ids"]:
        d["citation_ok"] = any(c["doc_id"] in g["expected_doc_ids"] for c in r["citations"])
        if g.get("expected_page"):
            d["citation_ok"] = d["citation_ok"] and any(c.get("page") == g["expected_page"] for c in r["citations"])
    if g.get("gold_sql"):
        mine = (r.get("sql") or {}).get("rows")
        if mine is None:
            d["sql_ok"] = False
        else:
            a = [[str(x) for x in row] for row in mine]
            b = [[str(x) for x in row] for row in gold_rows]
            d["sql_ok"] = a == b if g.get("order_matters") else sorted(a) == sorted(b)
    if g.get("expected_chart"):
        d["chart_ok"] = ((r.get("sql") or {}).get("chart") or {}).get("type") == g["expected_chart"]
    if g.get("expected_template"):
        d["template_ok"] = (r.get("graph") or {}).get("template") == g["expected_template"]
    d["passed"] = (d["route_ok"] and d["status_ok"] and not leaks and d["must_contain_ok"] and d["rewrite_ok"]
                   and d.get("citation_ok", True) and d.get("sql_ok", True) and d.get("chart_ok", True)
                   and d.get("template_ok", True))
    return d


def gold_rows_for(g):
    if not g.get("gold_sql"):
        return None
    import psycopg

    from app.config import get_settings
    with psycopg.connect(get_settings().database_url) as conn:
        return [list(r) for r in conn.execute(g["gold_sql"]).fetchall()]


def ragas_scores(items: list[dict]) -> dict[str, dict]:
    """RAGAS on docs and graph answers. Uses the same OpenAI-compatible LLM as the app and the local bge
    embedder. Returns {q_id: {metric: score}}; empty if RAGAS or the LLM is not available."""
    if not items:
        return {}
    try:
        from langchain_community.embeddings import FastEmbedEmbeddings
        from langchain_openai import ChatOpenAI
        from ragas import EvaluationDataset, evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference, LLMContextRecall, ResponseRelevancy

        from app.config import get_settings
    except ImportError as e:
        print(f"RAGAS skipped ({e}). pip install -r eval/requirements.txt")
        return {}
    s = get_settings()
    if not s.llm_api_key:
        print("RAGAS skipped: LLM_API_KEY not set")
        return {}
    judge = LangchainLLMWrapper(ChatOpenAI(model=s.llm_model, base_url=s.llm_base_url, api_key=s.llm_api_key,
                                           temperature=0, max_retries=4))
    emb = LangchainEmbeddingsWrapper(FastEmbedEmbeddings(model_name=s.embed_model))
    ds = EvaluationDataset.from_list([{"user_input": it["question"], "response": it["answer"],
                                       "retrieved_contexts": it["contexts"] or [""],
                                       "reference": it["reference"]} for it in items])
    res = evaluate(ds, metrics=[Faithfulness(), ResponseRelevancy(), LLMContextPrecisionWithReference(),
                                LLMContextRecall()], llm=judge, embeddings=emb, show_progress=False)
    df = res.to_pandas()
    out = {}
    for it, (_, row) in zip(items, df.iterrows()):
        out[it["id"]] = {k: (None if row.get(k) != row.get(k) else round(float(row.get(k)), 3)) for k in
                         ("faithfulness", "answer_relevancy", "llm_context_precision_with_reference", "context_recall")}
    return out


def contexts_for(r: dict, svc) -> list[str]:
    """The cited chunks' text (docs) or the rendered graph paths (graph): what the answer claims to rest on."""
    if r["route"] == "graph" and r.get("graph"):
        return [" -> ".join(p) for p in r["graph"]["paths"][:20]]
    texts = []
    for c in r["citations"]:
        cid = c.get("chunk_id")
        if svc and cid in svc.retriever.by_id:
            texts.append(svc.retriever.by_id[cid].text)
    return texts


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api")
    ap.add_argument("--only")
    ap.add_argument("--no-ragas", action="store_true")
    ap.add_argument("--no-store", action="store_true")
    args = ap.parse_args()
    golden = load_golden(set(args.only.split(",")) if args.only else None)

    svc = None
    if args.api:
        ask = ask_api(args.api)
    else:
        from app.main import load_services
        svc = load_services()
        ask = ask_inprocess(svc)

    results, ragas_in = [], []
    for g in golden:
        t0 = time.perf_counter()
        try:
            r = ask(g)
        except Exception as e:  # noqa: BLE001
            r = {"route": "error", "status": "error", "answer": "", "citations": [], "rewritten_query": "",
                 "role": "", "pipeline": {"error_class": type(e).__name__}}
        ms = int((time.perf_counter() - t0) * 1000)
        d = check(g, r, gold_rows_for(g) if not args.api or os.environ.get("DATABASE_URL") else None)
        d.update(ms=ms, route=r["route"], status=r["status"], answer=r["answer"][:400],
                 trace_id=r.get("pipeline", {}).get("trace_id"), error_class=r.get("pipeline", {}).get("error_class"),
                 tokens=r.get("pipeline", {}).get("tokens"))
        results.append((g, r, d))
        mark = "PASS" if d["passed"] else "FAIL"
        print(f"{mark} {g['id']:<5} {g['user_id']:<9} {r['route']:<12} {r['status']:<12} {ms:>6} ms  {g['question'][:60]}")
        if r["status"] == "answered" and r["route"] in ("docs", "graph"):
            ragas_in.append({"id": g["id"], "question": g["question"], "answer": r["answer"],
                             "contexts": contexts_for(r, svc), "reference": g["expected_answer"]})

    rag = {} if args.no_ragas else ragas_scores(ragas_in)
    for g, r, d in results:
        if g["id"] in rag:
            d["ragas"] = rag[g["id"]]

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(statistics.mean(xs), 3) if xs else None

    answered = [d for g, r, d in results if d["status"] == "answered"]
    refusal_set = [d for g, r, d in results if g["expected_status"] in ("not_found", "out_of_scope")]
    answerable = [d for g, r, d in results if g["expected_status"] == "answered"]
    faith = [d["ragas"]["faithfulness"] for d in answered if d.get("ragas")]
    metrics = {
        "questions": len(results),
        "passed": sum(d["passed"] for _, _, d in results),
        "route_accuracy": mean([float(d["route_ok"]) for _, _, d in results]),
        "citation_accuracy": mean([float(d["citation_ok"]) for d in answered if "citation_ok" in d]),
        "refusal_accuracy": mean([float(d["status_ok"]) for d in refusal_set] +
                                 [float(not d["refused_answerable"]) for d in answerable]),
        "access_leaks": sum(len(d["leaks"]) for _, _, d in results),
        "sql_execution_accuracy": mean([float(d["sql_ok"]) for _, _, d in results if "sql_ok" in d]),
        "faithfulness": mean(faith),
        "response_relevancy": mean([d["ragas"]["answer_relevancy"] for d in answered if d.get("ragas")]),
        "context_precision": mean([d["ragas"]["llm_context_precision_with_reference"] for d in answered if d.get("ragas")]),
        "context_recall": mean([d["ragas"]["context_recall"] for d in answered if d.get("ragas")]),
        "hallucination_rate": round(sum(f < 0.7 for f in faith if f is not None) / len(faith), 3) if faith else None,
        "latency_ms": {route: {"p50": pct([d["ms"] for _, _, d in results if d["route"] == route], 50),
                               "p95": pct([d["ms"] for _, _, d in results if d["route"] == route], 95)}
                       for route in ("docs", "data", "graph", "out_of_scope")},
    }
    from app.config import get_settings
    s = get_settings()
    pin, pout = PRICES.get(s.llm_model, (0.15, 0.60))
    toks = [d.get("tokens") or {} for _, _, d in results]
    cost_usd = sum(t.get("input", 0) * pin + t.get("output", 0) * pout for t in toks) / 1e6
    metrics["tokens_total"] = {"input": sum(t.get("input", 0) for t in toks), "output": sum(t.get("output", 0) for t in toks)}
    metrics["cost_per_question_inr"] = round(cost_usd * USD_INR / max(len(results), 1), 4)
    metrics["cost_run_inr"] = round(cost_usd * USD_INR, 2)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    run = {"run_id": f"run-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}", "git_commit": commit,
           "prompt_version": "answer-v1/sql-v1/graph-v1/understand-v1", "model": s.llm_model, "metrics": metrics,
           "results": [{"id": g["id"], "question": g["question"], "user_id": g["user_id"], **d} for g, r, d in results]}
    out = ROOT / "eval" / "runs"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(run, indent=2, default=str))
    (out / f"{run['run_id']}.json").write_text(json.dumps(run, indent=2, default=str))
    if not args.no_store and not args.api:
        store(run)
    print("\n" + json.dumps(metrics, indent=2))
    print(f"\nrun {run['run_id']} · commit {commit} · {metrics['passed']}/{metrics['questions']} passed")


def store(run: dict) -> None:
    import psycopg

    from app.config import get_settings
    with psycopg.connect(get_settings().database_url) as conn:
        conn.execute("INSERT INTO eval_runs (run_id, git_commit, prompt_version, model, metrics) VALUES (%s,%s,%s,%s,%s)",
                     (run["run_id"], run["git_commit"], run["prompt_version"], run["model"], json.dumps(run["metrics"])))
        for r in run["results"]:
            conn.execute("INSERT INTO eval_results (run_id, q_id, passed, detail) VALUES (%s,%s,%s,%s)",
                         (run["run_id"], r["id"], r["passed"], json.dumps(r, default=str)))
        conn.commit()


if __name__ == "__main__":
    main()
