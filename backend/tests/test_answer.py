"""Citations and prompt-injection handling."""
from app.answer import build_citations, neutralise
from app.retrieval import Hit


def test_injected_line_is_neutralised(chunks):
    wi = [c for c in chunks if c.doc_id == "WI-L3-009" and "Assistant:" in c.text][0]
    clean, changed = neutralise(wi.text)
    assert changed and "500 Nm" not in clean and "Assistant:" not in clean
    assert "Report damaged locating pins" in clean


def test_citations_renumbered_and_invalid_markers_dropped(chunks):
    hits = [Hit(c, 0.9) for c in chunks[:3]]
    text, cites = build_citations("First fact [3]. Second fact [1]. Bogus [9].", hits)
    assert text == "First fact [1]. Second fact [2]. Bogus ."
    assert [c.n for c in cites] == [1, 2] and cites[0].doc_id == chunks[2].doc_id
