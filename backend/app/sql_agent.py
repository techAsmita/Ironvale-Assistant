"""Data route: Text-to-SQL with guardrails and automatic charts.

1. The model sees only the schema of the views the user's role may query, plus examples and the metric
   definitions from the company page. It writes one SELECT.
2. sqlglot checks it: one statement, a SELECT, only that role's views, only allow-listed functions
   (set_config/current_setting would let a query change its own row scope), and adds LIMIT 500.
3. It runs inside a transaction as the role's read-only Postgres role, with app.user_id set for the
   Row-Level Security policies and a 5-second statement timeout.
4. On a database error, one repair attempt with the error message; then status "error".
5. Zero rows because of row scope -> not_found. Zero rows inside the scope -> "No matching records."
"""
from __future__ import annotations

import datetime as dt
import decimal
import re

import sqlglot
from sqlglot import exp

from . import llm
from .config import get_settings

PROMPT_VERSION = "sql-v1"
ROLE_DB = {"line_supervisor": ("sup", "ironvale_sup"), "quality_engineer": ("qe", "ironvale_qe"),
           "plant_head": ("head", "ironvale_head")}

VIEWS = {
    "machines": "machines(machine_id text, line int, type text, model text, commissioned_on date)",
    "work_orders": "work_orders(wo_id text, machine_id text, part_no text, qty_planned int, qty_good int, "
                   "started_at timestamp, ended_at timestamp)",
    "downtime_events": "downtime_events(event_id text, machine_id text, start_at timestamp, end_at timestamp, "
                       "category text -- one of 'planned','breakdown','changeover','material', reason_code text, "
                       "alarm_code text -- e.g. 'E-417', NULL unless an alarm caused it)",
    "defects": "defects(defect_id text, wo_id text, part_no text, defect_type text, qty int, found_at timestamp, "
               "stage text)",
    "supplier_parts_qe": "supplier_parts(part_no text, supplier text, valid_from date)",
    "supplier_parts": "supplier_parts(part_no text, supplier text, unit_price_inr numeric, valid_from date)",
}
ROLE_VIEWS = {
    "line_supervisor": ["machines", "work_orders", "downtime_events"],
    "quality_engineer": ["machines", "work_orders", "downtime_events", "defects", "supplier_parts_qe"],
    "plant_head": ["machines", "work_orders", "downtime_events", "defects", "supplier_parts"],
}
# sqlglot node keys (and names of unknown functions) that a reporting query may use. Everything else is
# rejected, including set_config/current_setting (they would let a query change its own row scope).
ALLOWED_FUNCS = {
    "count", "sum", "avg", "min", "max", "round", "coalesce", "nullif", "extract", "timestamptrunc", "datetrunc",
    "date_trunc", "date_part", "timetostr", "to_char", "lower", "upper", "abs", "greatest", "least", "cast",
    "trycast", "floor", "ceil", "concat", "length", "substring", "trim", "currentdate", "currenttimestamp",
    "percentilecont", "stddev", "rank", "rownumber", "denserank", "lag", "lead", "case", "if", "distinct",
    "window", "interval", "div", "safedivide", "countif", "anyvalue", "stringagg", "grouptoconcat", "arrayagg",
    "datediff", "tsordsadd", "dateadd", "datesub", "month", "year", "day", "dayofmonth", "dayofweek", "quarter",
}

METRICS = """Metric definitions (use exactly):
- Downtime minutes = EXTRACT(EPOCH FROM end_at - start_at) / 60, summed.
- Breakdown downtime = downtime with category = 'breakdown' only.
- Yield = SUM(qty_good) / SUM(qty_planned) (as numeric).
- Defect rate = defect qty / qty_good for the same part and period.
- A downtime event belongs to the month of its start_at. Line comes from machines.line (join on machine_id).
- Dates are plant local time. Data covers 2026-08-01 to 2026-10-31."""

EXAMPLES = """Examples:
Q: Breakdown downtime by machine on Line 1 in October 2026
SQL: SELECT d.machine_id, ROUND(SUM(EXTRACT(EPOCH FROM d.end_at - d.start_at) / 60)) AS breakdown_minutes FROM downtime_events d JOIN machines m ON m.machine_id = d.machine_id WHERE m.line = 1 AND d.category = 'breakdown' AND d.start_at >= '2026-10-01' AND d.start_at < '2026-11-01' GROUP BY d.machine_id ORDER BY d.machine_id
Q: Monthly downtime minutes on Line 3
SQL: SELECT DATE_TRUNC('month', d.start_at)::date AS month, ROUND(SUM(EXTRACT(EPOCH FROM d.end_at - d.start_at) / 60)) AS downtime_minutes FROM downtime_events d JOIN machines m ON m.machine_id = d.machine_id WHERE m.line = 3 GROUP BY 1 ORDER BY 1
Q: How many E-417 stops on CNC-L1-04 in September 2026?
SQL: SELECT COUNT(*) AS stops FROM downtime_events WHERE machine_id = 'CNC-L1-04' AND alarm_code = 'E-417' AND start_at >= '2026-09-01' AND start_at < '2026-10-01'
Q: Yield by part in August 2026
SQL: SELECT part_no, ROUND(SUM(qty_good)::numeric / SUM(qty_planned), 4) AS yield FROM work_orders WHERE started_at >= '2026-08-01' AND started_at < '2026-09-01' GROUP BY part_no ORDER BY part_no"""


class SqlRejected(Exception):
    pass


def schema_for(role: str) -> str:
    return "\n".join(VIEWS[v] for v in ROLE_VIEWS[role])


def allowed_tables(role: str) -> set[str]:
    return {v.replace("_qe", "") for v in ROLE_VIEWS[role]}


def system_prompt(role: str) -> str:
    return f"""You write one PostgreSQL SELECT for Ironvale Components' plant database.
You may only use these views (no other tables, no schema prefixes):
{schema_for(role)}

{METRICS}

{EXAMPLES}

Rules: one SELECT statement only. Name aggregate columns clearly. Order sensibly (by the category, or by the
value when the question asks for top or bottom). If the question asks for top N, use LIMIT N. For a time trend,
return the date column first. If the question uses a metric not defined above, pick a reasonable definition and
state it in "metric_note". If the question cannot be answered from these views, return "sql": null.
Return JSON only: {{"sql": "...", "metric_note": null}}"""


def validate(sql: str, role: str) -> str:
    """Raise SqlRejected unless sql is one safe SELECT over the role's views. Returns SQL with a LIMIT."""
    try:
        stmts = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise SqlRejected(f"parse error: {e}") from e
    if len(stmts) != 1:
        raise SqlRejected("exactly one statement is allowed")
    tree = stmts[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SqlRejected(f"only SELECT is allowed, got {type(tree).__name__}")
    for bad in (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command, exp.Into):
        if tree.find(bad):
            raise SqlRejected(f"{bad.__name__} is not allowed")
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    allowed = allowed_tables(role)
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if t.args.get("db") or t.args.get("catalog"):
            raise SqlRejected(f"schema-qualified table {t.sql()} is not allowed")
        if name not in allowed and name not in ctes:
            raise SqlRejected(f"table {name} is not available to this role")
    for f in tree.find_all(exp.Func):
        if isinstance(f, (exp.Binary, exp.Connector, exp.Unary, exp.Predicate)):
            continue  # operators (AND, =, +, NOT ...) are fine
        key = f.name.lower() if isinstance(f, exp.Anonymous) else f.key
        if key not in ALLOWED_FUNCS:
            raise SqlRejected(f"function {key} is not allowed")
    if re.search(r"(?i)\b(set_config|current_setting|pg_\w+|dblink|lo_\w+|copy|pg_sleep)\b", sql):
        raise SqlRejected("system functions are not allowed")
    if not tree.args.get("limit"):
        tree = tree.limit(500)
    return tree.sql(dialect="postgres")


def _jsonable(v):
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return v


class Executor:
    """Runs validated SQL as the role's restricted Postgres role, with row scope set per request."""

    def run(self, sql: str, role: str, user_id: str) -> tuple[list[str], list[list]]:
        import psycopg

        schema, dbrole = ROLE_DB[role]
        # One transaction per query; every SET is LOCAL, so nothing outlives it. Read-only, then rolled back.
        with psycopg.connect(get_settings().database_url, autocommit=False) as conn:
            try:
                conn.execute("SET TRANSACTION READ ONLY")
                conn.execute("SELECT set_config('app.user_id', %s, true)", (user_id,))
                conn.execute(f"SET LOCAL ROLE {dbrole}")
                conn.execute(f"SET LOCAL search_path = {schema}")
                conn.execute("SET LOCAL statement_timeout = '5s'")
                cur = conn.execute(sql)
                cols = [d.name for d in cur.description]
                rows = [[_jsonable(v) for v in r] for r in cur.fetchall()]
            finally:
                conn.rollback()
        return cols, rows


def pick_chart(cols: list[str], rows: list[list]) -> dict | None:
    """One category + one number -> bar. A date + a number -> line. Anything else -> table only."""
    if len(cols) != 2 or len(rows) < 2:
        return None

    def is_num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def is_date(v):
        return isinstance(v, str) and bool(re.match(r"^\d{4}-\d{2}-\d{2}", v))

    first, second = [r[0] for r in rows], [r[1] for r in rows]
    if not all(is_num(v) or v is None for v in second):
        return None
    if all(is_date(v) for v in first):
        return {"type": "line", "x": cols[0], "y": cols[1]}
    if all(isinstance(v, str) for v in first):
        return {"type": "bar", "x": cols[0], "y": cols[1]}
    return None


def generate_sql(question: str, role: str, error: str | None = None, previous: str | None = None) -> dict:
    s = get_settings()
    user = f"Question: {question}"
    if error:
        user += f"\n\nYour previous SQL failed.\nSQL: {previous}\nDatabase error: {error}\nReturn a corrected query."
    rep = llm.client().chat([{"role": "system", "content": system_prompt(role)}, {"role": "user", "content": user}],
                            model=s.llm_model, json_mode=True, max_tokens=500)
    data = rep.json()
    return {"sql": data.get("sql"), "metric_note": data.get("metric_note"), "ms": rep.ms, "usage": rep.usage,
            "model": rep.model}


def summarise(question: str, cols: list[str], rows: list[list], metric_note: str | None) -> str:
    """Aggregate results only (no person-level columns exist in this schema). Deterministic, no LLM call."""
    if len(rows) == 1 and len(cols) == 1:
        text = f"{cols[0].replace('_', ' ').capitalize()}: {_fmt(rows[0][0])}."
    elif len(cols) == 2 and all(isinstance(r[1], (int, float)) for r in rows):
        top = max(rows, key=lambda r: r[1])
        low = min(rows, key=lambda r: r[1])
        label = cols[1].replace("_", " ")
        what = cols[0].replace("_id", "").replace("_", " ")
        text = (f"{label.capitalize()} for {len(rows)} {what}{'s' if not what.endswith('s') else ''}. "
                f"Highest: {top[0]} ({_fmt(top[1])}). Lowest: {low[0]} ({_fmt(low[1])}).")
    else:
        text = f"{len(rows)} rows."
    if metric_note:
        text += f" Definition used: {metric_note}"
    return text


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:,.4f}".rstrip("0").rstrip(".") if abs(v) < 10 else f"{v:,.0f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def answer_data(question: str, role: str, user_id: str, executor=None, timings: dict | None = None) -> dict:
    """Returns {"status", "answer", "sql": SqlResult-dict | None, "error_class", "spans": [...]}."""
    import time

    ex = executor or Executor()
    timings = timings if timings is not None else {}
    spans = []
    t0 = time.perf_counter()
    gen = generate_sql(question, role)
    timings["sql_generate"] = int((time.perf_counter() - t0) * 1000)
    spans.append(("sql.generate", {"model": gen["model"]}))
    if not gen["sql"]:
        return {"status": "not_found", "sql": None, "error_class": None, "spans": spans, "usage": gen["usage"]}

    sql, last_err = gen["sql"], None
    for attempt in range(2):
        t0 = time.perf_counter()
        try:
            safe = validate(sql, role)
        except SqlRejected as e:
            spans.append(("sql.validate", {"ok": False, "reason": str(e)[:200]}))
            return {"status": "error", "sql": {"query": sql, "columns": [], "rows": [], "row_count": 0, "chart": None},
                    "error_class": "sql_rejected", "spans": spans, "usage": gen["usage"]}
        timings["sql_validate"] = int((time.perf_counter() - t0) * 1000)
        spans.append(("sql.validate", {"ok": True}))
        t0 = time.perf_counter()
        try:
            cols, rows = ex.run(safe, role, user_id)
            timings["sql_execute"] = int((time.perf_counter() - t0) * 1000)
            spans.append(("sql.execute", {"row_count": len(rows)}))
            break
        except Exception as e:  # noqa: BLE001 - database error: one repair attempt
            last_err = str(e).split("\n")[0][:300]
            spans.append(("sql.execute", {"ok": False, "error": type(e).__name__}))
            if attempt == 1:
                cls = "sql_timeout" if "timeout" in last_err.lower() else "sql_invalid"
                return {"status": "error", "sql": {"query": safe, "columns": [], "rows": [], "row_count": 0,
                                                   "chart": None}, "error_class": cls, "spans": spans,
                        "usage": gen["usage"]}
            gen = generate_sql(question, role, error=last_err, previous=safe)
            sql = gen["sql"] or sql

    result = {"query": safe, "columns": cols, "rows": rows[:50], "row_count": len(rows),
              "chart": pick_chart(cols, rows)}
    if not rows:
        if out_of_scope_rows(safe, role, user_id, ex):
            return {"status": "not_found", "sql": None, "error_class": None, "spans": spans, "usage": gen["usage"]}
        return {"status": "answered", "answer": "No matching records.", "sql": result, "error_class": None,
                "spans": spans, "usage": gen["usage"]}
    return {"status": "answered", "answer": summarise(question, cols, rows, gen.get("metric_note")),
            "sql": result, "error_class": None, "spans": spans, "usage": gen["usage"]}


def out_of_scope_rows(sql: str, role: str, user_id: str, ex) -> bool:
    """Zero rows for a scoped user: would the same query return rows plant-wide? Only a boolean comes back,
    and the user still gets the same not_found message as for missing data."""
    if role != "line_supervisor":
        return False
    try:
        _, rows = ex.run(f"SELECT 1 FROM ({sql.rstrip(';')}) AS q LIMIT 1", "plant_head", "u_head")
        return bool(rows)
    except Exception:  # noqa: BLE001
        return False
