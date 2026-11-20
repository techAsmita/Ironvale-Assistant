"""GraphRAG: schema, entity resolution, templates, access inheritance."""
from datetime import date

from app.graph import LABELS, RELS, answer_graph, fill_rules, norm_supplier, openable_sources

T = date(2026, 11, 18)


def test_entity_resolution():
    assert norm_supplier("Arcflow Castings Pvt. Ltd.") == "Arcflow Castings"
    assert norm_supplier("ARCFLOW CASTINGS") == "Arcflow Castings"
    assert norm_supplier("Metsun Fasteners Limited") == "Metsun Fasteners"


def test_graph_respects_schema_and_has_sources(graph_store):
    g = graph_store.g
    assert {lab for lab, _ in g.nodes} <= LABELS
    assert {(e[0], e[2], e[3]) for e in g.edges} <= RELS
    assert all(v["source_doc_ids"] for v in g.nodes.values())
    assert all(v["source_doc_ids"] for v in g.edges.values())
    assert ("Supplier", "Arcflow Castings") in g.nodes  # one node, not several spellings


def test_deviation_trail_line1_qe(graph_store):
    a = answer_graph("Which suppliers are behind deviations on Line 1 this year?", "quality_engineer", None, graph_store, T)
    assert a["status"] == "answered" and a["template"] == "deviation_trail"
    assert "Arcflow Castings" in a["answer"] and "QDR-2026-014" in a["answer"]


def test_supplier_exposure_head(graph_store):
    a = answer_graph("If Arcflow is put on hold, which machines and SOPs are affected?", "plant_head", None, graph_store, T)
    assert a["status"] == "answered" and "CNC-L1-04" in a["answer"] and "SOP-L1-001" in a["answer"]
    assert "10 machines across 3 lines" in a["answer"] and a["answer"].count("[") <= 2  # concise, few inline cites


def test_paths_inherit_access(graph_store):
    for q in ("Which suppliers are behind deviations on Line 1 this year?",
              "If Arcflow is put on hold, which machines and SOPs are affected?"):
        a = answer_graph(q, "line_supervisor", 1, graph_store, T)
        assert a["status"] == "not_found"


def test_internal_deviation_not_blamed_on_supplier(graph_store):
    a = answer_graph("Which suppliers are behind deviations on Line 2 this year?", "quality_engineer", None, graph_store, T)
    assert "Arcflow" not in a.get("answer", "")  # QDR-2026-017 was a heat-treatment cause, not the supplier


def test_template_fill_dates():
    f = fill_rules("Which suppliers are behind deviations on Line 3 in August 2026?", T)
    assert f["params"] == {"line": "3", "date_from": "2026-08-01", "date_to": "2026-09-01"}


def test_openable_sources():
    sup = openable_sources("line_supervisor", 1)
    assert "DB:line1" in sup and "DB:line3" not in sup and "ASL-2026" not in sup and "PRC-2026-Q3" not in sup
    assert "PRC-2026-Q3" in openable_sources("plant_head", None)
