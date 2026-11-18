"""Exact codes, access filtering before retrieval, metadata, superseded versions."""
from app.retrieval import codes_in, normalise_codes, tokenize


def test_tokenizer_keeps_codes_whole():
    t = tokenize("What does alarm E-417 mean on HX-220-B per SOP-L2-011?")
    assert "e-417" in t and "hx-220-b" in t and "sop-l2-011" in t
    assert "e-471" not in t


def test_code_normalisation():
    assert normalise_codes("alarm e417") == "alarm E-417"
    assert normalise_codes("E 471 again") == "E-471 again"
    assert normalise_codes("hx220b soak") == "HX-220-B soak"
    assert codes_in("E-417 on CNC-L1-04") == {"E-417", "CNC-L1-04"}


def test_every_chunk_has_required_metadata(chunks):
    for c in chunks:
        assert c.doc_id and c.title and c.version and c.effective_date
        assert c.allowed_roles and c.scope and c.source in ("digital", "scanned")
        assert isinstance(c.superseded, bool)


def test_scanned_pages_keep_printed_numbers(chunks):
    pages = {(c.section or "").split(" ")[0]: c.page for c in chunks if c.doc_id == "MAN-CNC-04"}
    assert pages["7.2"] == 42 and pages["7.3"] == 42  # E-417 and E-471 text: printed page 42, PDF index 2
    assert pages["7.1"] == 41 and pages["7.6"] == 44
    assert all(c.source == "scanned" for c in chunks if c.doc_id in ("MAN-CNC-04", "MAN-FUR-02"))


def test_superseded_version_indexed_and_flagged(chunks):
    v2 = [c for c in chunks if c.doc_id == "SOP-L2-011" and c.version == "v2"]
    v3 = [c for c in chunks if c.doc_id == "SOP-L2-011" and c.version == "v3"]
    assert v2 and all(c.superseded for c in v2)
    assert v3 and not any(c.superseded for c in v3)
    assert any("40 minutes" in c.text for c in v2) and any("45 minutes" in c.text for c in v3)


def test_people_masked_companies_kept(chunks):
    text = "\n".join(c.text for c in chunks)
    for name in ("Meenakshi Raghavan", "Farah Qureshi", "Vikram Rao", "Arjun Pillai"):
        assert name not in text
    for company in ("Arcflow Castings", "Metsun Fasteners", "2026-08-15", "HX-220-B"):
        assert company in text


def test_e417_never_returns_e471_chunk(retriever):
    res = retriever.retrieve("What does alarm E-417 mean on the DMC 850?", "line_supervisor")
    assert res["hits"], "E-417 should be found"
    for h in res["hits"]:
        assert "E-417" in h.chunk.search_text()
    top = res["hits"][0].chunk
    assert top.doc_id == "MAN-CNC-04" and top.page in (42, 44)


def test_unknown_code_finds_nothing(retriever):
    assert retriever.retrieve("What does alarm E-999 mean?", "line_supervisor")["hits"] == []


def test_access_filter_runs_inside_both_retrievers(retriever):
    q = "unit price HX-220-B price list Rs"
    for role in ("line_supervisor", "quality_engineer"):
        ids = [c for c, _ in retriever.search_bm25(q, role, 50)] + [c for c, _ in retriever.search_dense(q, role, 200)]
        assert not any(i.startswith("PRC-") for i in ids), role
    sup_ids = [c for c, _ in retriever.search_dense("deviation cracked housings QDR", "line_supervisor", 200)]
    assert not any(i.startswith(("QDR-", "ASL-", "SQA-")) for i in sup_ids)
    head = [c for c, _ in retriever.search_bm25(q, "plant_head")]
    assert any(i.startswith("PRC-") for i in head)


def test_rrf_fuses_two_lists():
    from app.retrieval import Retriever
    fused = Retriever.rrf([("a", 9), ("b", 8)], [("b", .9), ("c", .8)])
    assert fused[0][0] == "b" and {x for x, _ in fused} == {"a", "b", "c"}
