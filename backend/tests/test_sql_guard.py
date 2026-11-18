"""Text-to-SQL guardrails: only one SELECT over the role's views, no scope-changing functions."""
import pytest
from conftest import golden

from app.sql_agent import SqlRejected, pick_chart, validate

ATTACKS = [
    "SELECT set_config('app.user_id','u_head',true)",
    "SELECT * FROM machines WHERE line = (SELECT set_config('app.user_id','u_head',true))::int",
    "SELECT current_setting('app.user_id')",
    "SELECT * FROM public.downtime_events",
    "WITH x AS (SELECT * FROM head.supplier_parts) SELECT * FROM x",
    "DELETE FROM machines",
    "UPDATE machines SET line = 1",
    "SELECT 1; DROP TABLE machines",
    "SELECT pg_sleep(10)",
    "COPY machines TO '/tmp/x'",
    "SELECT * FROM users",
    "SELECT * FROM chunks",
]


@pytest.mark.parametrize("sql", ATTACKS)
def test_attacks_rejected_for_supervisor(sql):
    with pytest.raises(SqlRejected):
        validate(sql, "line_supervisor")


def test_role_views():
    with pytest.raises(SqlRejected):
        validate("SELECT * FROM defects", "line_supervisor")
    with pytest.raises(SqlRejected):
        validate("SELECT * FROM supplier_parts", "line_supervisor")
    assert "LIMIT 500" in validate("SELECT * FROM defects", "quality_engineer")
    assert "LIMIT 3" in validate("SELECT * FROM machines LIMIT 3", "plant_head")


def test_gold_queries_pass_the_guard():
    for g in golden():
        if g["gold_sql"]:
            role = {"u_sup_l1": "line_supervisor", "u_sup_l3": "line_supervisor", "u_qe": "quality_engineer",
                    "u_head": "plant_head"}[g["user_id"]]
            validate(g["gold_sql"], role)


def test_chart_from_result_shape():
    assert pick_chart(["machine_id", "minutes"], [["CNC-L1-01", 10.0], ["CNC-L1-02", 5.0]])["type"] == "bar"
    assert pick_chart(["month", "minutes"], [["2026-08-01", 1.0], ["2026-09-01", 2.0]])["type"] == "line"
    assert pick_chart(["stops"], [[48]]) is None
    assert pick_chart(["a", "b", "c"], [[1, 2, 3], [4, 5, 6]]) is None
