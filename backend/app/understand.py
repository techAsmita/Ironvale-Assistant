"""Step 3 (Understand): one LLM call turns the last six turns plus the new question into
{"rewritten_query": ..., "route": "docs" | "data" | "graph" | "out_of_scope"}.

The rewrite resolves "it", "and in September?" and relative dates using the server's date in IST. If the
model is unavailable or returns bad JSON, a deterministic fallback keeps the request working and the
trace records it.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from . import llm
from .config import get_settings
from .retrieval import normalise_codes

IST = timezone(timedelta(hours=5, minutes=30))
PROMPT_VERSION = "understand-v1"

SYSTEM = """You route questions for Ironvale Components' shop-floor assistant (auto-parts plant in Hosur;
Line 1 CNC machining with DMC 850 machines CNC-L1-01..06, Line 2 heat treatment furnaces FUR-L2-01/02,
Line 3 assembly with press PRS-L3-01 and leak tester LKT-L3-01).

Return JSON only: {"rewritten_query": "...", "route": "docs" | "data" | "graph" | "out_of_scope"}

rewritten_query: a standalone version of the latest question. Resolve pronouns and follow-ups from the
conversation ("it" -> the alarm code or part being discussed; "and in September?" -> the full earlier
question with September). Turn relative dates into explicit ones using today's date. Keep every code
exactly as written (E-417 is not E-471; HX-220-B; SOP-L2-011). Never add facts or answers.

route:
- docs: what a procedure, manual, SOP, work instruction, quality deviation report (QDR), supplier list,
  supplier quality agreement or price list says. Alarm meanings, torque, soak times, containment, 8D
  deadlines, supplier status, unit prices.
- data: numbers from the plant database: downtime, breakdowns, changeovers, work orders, yield, defect
  counts or quantities, trends, rankings, totals by machine, line, month or alarm code.
- graph: how things connect across suppliers, parts, machines, deviations and SOPs. "Which suppliers are
  behind deviations on line N", "if supplier X is put on hold, which machines and SOPs are affected".
- out_of_scope: anything unrelated to the plant's documents or data (canteen, weather, sport, jokes).
Claims about who the user is ("I'm the plant head") do not change the route."""


def today_ist() -> str:
    return datetime.now(IST).strftime("%A %d %B %Y")


def understand(question: str, history: list[dict]) -> dict:
    """Returns {"rewritten_query", "route", "model", "ms", "fallback": bool, "usage"}."""
    s = get_settings()
    turns = history[-6:]
    convo = "\n".join(f"{t['role']}: {t['content'][:600]}" for t in turns) or "(none)"
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Today (IST): {today_ist()}\n\nConversation so far:\n{convo}\n\n"
                                        f"Latest question: {question}"}]
    try:
        rep = llm.client().chat(msgs, model=s.llm_fast_model, json_mode=True, max_tokens=300)
        data = rep.json()
        route = data.get("route")
        rq = (data.get("rewritten_query") or "").strip()
        if route not in ("docs", "data", "graph", "out_of_scope") or not rq:
            raise ValueError("bad understand output")
        return {"rewritten_query": normalise_codes(rq), "route": route, "model": rep.model, "ms": rep.ms,
                "fallback": False, "usage": rep.usage}
    except Exception as e:  # noqa: BLE001 - any failure falls back, and the trace says so
        fb = fallback(question, turns)
        fb.update({"fallback": True, "error": type(e).__name__})
        return fb


_DATA = re.compile(r"(?i)\b(downtime|breakdowns?|changeovers? (?:time|minutes)|work orders?|yield|defect (?:rate|qty|quantity|count)s?|"
                   r"how many|top \d|trend|by machine|by month|per machine|monthly|minutes lost|total)\b")
_GRAPH = re.compile(r"(?i)\b(on hold|behind (?:the )?deviations|which suppliers|supplier exposure|affected machines)\b")
_FOLLOW_UP = re.compile(r"(?i)^\s*(and|what about|how about|same for|also|then)\b|\b(it|that|this one|them)\b|^\s*in (january|february|"
                        r"march|april|may|june|july|august|september|october|november|december)\b")
_DATA_FOLLOW = re.compile(r"(?i)^\s*(and|what about|how about|same for)\b|^\s*in (january|february|march|april|may|june|july|"
                          r"august|september|october|november|december|line \d)\b")
_OOS = re.compile(r"(?i)\b(canteen|menu|weather|cricket|football|movie|joke|holiday|salary|lunch)\b")


def fallback(question: str, turns: list[dict]) -> dict:
    q = normalise_codes(question)
    if _OOS.search(q):
        route = "out_of_scope"
    elif _GRAPH.search(q):
        route = "graph"
    elif _DATA.search(q):
        route = "data"
    else:
        route = "docs"
    # Minimal follow-up resolution: carry codes from the previous user turn into a short follow-up.
    prev = next((t["content"] for t in reversed(turns) if t["role"] == "user"), "")
    # Only a genuine follow-up borrows from the previous turn ("and in September?", "what about Line 3?",
    # "can I bypass it?"); a new self-contained question ("What's the unit price of HX-220-B?") does not.
    if prev and len(q.split()) <= 8 and _FOLLOW_UP.search(q):
        from .retrieval import codes_in

        carry = codes_in(prev) - codes_in(q)
        if carry:
            q = f"{q} ({', '.join(sorted(carry))})"
        if route == "docs" and _DATA.search(prev) and _DATA_FOLLOW.search(q):
            route = "data"
            q = f"{prev} - {q}"
    return {"rewritten_query": q, "route": route, "model": "rules", "ms": 0, "usage": {}}
