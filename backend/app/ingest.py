"""Step 1 (Ingest) and the write half of step 2 (Index).

    python -m app.ingest            # from backend/: parse, OCR, mask, chunk, embed, write to Postgres

PDF, DOCX, Markdown and HTML are parsed. Scanned PDFs go through the week-2 Read (Tesseract) and Mask
(Presidio) steps; every document is masked for people, phones, emails and ID numbers before indexing.
Chunks split on headings; each carries the metadata the rules require, and scanned pages keep the
printed page number from the page footer, not the PDF index.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz
from bs4 import BeautifulSoup
from docx import Document

from .config import ROOT
from .week2.ocr import ocr_pages
from .week2.pii import IRONVALE_ENTITIES, mask

CORPUS = ROOT / "corpus"
CHUNKS_JSONL = CORPUS / "index" / "chunks.jsonl"

MAX_TOKENS, WINDOW_TOKENS, OVERLAP = 600, 500, 0.15
_HEADER = re.compile(r"^.*Components, Hosur p[l1I]ant\b.*$", re.M)  # tolerant of OCR misreads
_FOOTER = re.compile(r"^\s*Page\s+(\d{1,3})\s*$", re.M | re.I)
_HEADING = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?\s+[A-Z][^\n]{2,70}|Chapter \d+\.[^\n]{2,60}|Section \d+\.[^\n]{2,60}|"
    r"Revision history|Document control|Summary|Details|Containment|Root cause and actions|Status|Notes?|"
    r"Approved suppliers|Status notes|Prices, Q3 2026|Fixture cleaning)$")


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    section: str | None
    page: int | None
    version: str
    effective_date: str
    superseded: bool
    allowed_roles: list[str]
    scope: str
    source: str
    text: str

    def search_text(self) -> str:
        """What BM25 and the embedder see: the document identity plus the chunk body."""
        from .guard import neutralise

        flag = " (superseded)" if self.superseded else ""
        body, _ = neutralise(self.text)
        return f"{self.doc_id} {self.version}{flag} · {self.title} · {self.section or ''}\n{body}"


def tokens(text: str) -> int:
    return int(len(text.split()) * 1.3) + 1


# ---------------------------------------------------------------------------------------------- parsers
def _sections_from_lines(lines: list[str]) -> list[tuple[str | None, str]]:
    sections, head, buf = [], None, []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if _HEADING.match(s) and not s.endswith("."):
            if buf:
                sections.append((head, "\n".join(buf)))
            head, buf = s, []
        else:
            buf.append(s)
    if buf:
        sections.append((head, "\n".join(buf)))
    # Text before the first heading that is only a few words is the wrapped title line, not content.
    return [(h, b) for h, b in sections if h is not None or len(b.split()) >= 6]


def _clean_page(text: str) -> tuple[str, int | None]:
    m = _FOOTER.search(text)
    printed = int(m.group(1)) if m else None
    text = _FOOTER.sub("", _HEADER.sub("", text))
    return text, printed


def parse_pdf(path: Path, entry: dict) -> list[tuple[int | None, str | None, str]]:
    """Returns (page, section, text) triples. Scanned PDFs are OCR'd page by page."""
    out = []
    if entry["source"] == "scanned":
        # OCR reads a leading "5" as "§" on some pages; fix it so numbered headings are found.
        pages = [re.sub(r"(?m)^§", "5", p.text) for p in ocr_pages(path.read_bytes())]
    else:
        with fitz.open(path) as doc:
            pages = [p.get_text("text") for p in doc]
    printed_fallback = entry.get("printed_pages") or []
    for i, raw in enumerate(pages):
        text, printed = _clean_page(raw)
        if printed is None and i < len(printed_fallback):
            printed = printed_fallback[i]
        lines = [ln for ln in text.splitlines() if not ln.strip().startswith(entry["doc_id"])]  # title line
        for head, body in _sections_from_lines(lines):
            out.append((printed or i + 1, head, body))
    return out


def parse_docx(path: Path, entry: dict):
    out, head, buf = [], None, []
    for p in Document(path).paragraphs:
        t = p.text.strip()
        if not t or _HEADER.match(t):
            continue
        if p.style.name.startswith("Heading 1"):
            continue
        if p.style.name.startswith("Heading"):
            if buf:
                out.append((1, head, "\n".join(buf)))
            head, buf = t, []
        else:
            buf.append(t)
    if buf:
        out.append((1, head, "\n".join(buf)))
    return out


def parse_md(path: Path, entry: dict):
    out, head, buf = [], None, []
    for line in path.read_text().splitlines():
        if line.startswith("<!--") or line.startswith("# "):
            continue
        if line.startswith("## "):
            if buf:
                out.append((1, head, "\n".join(buf)))
            head, buf = line[3:].strip(), []
        elif line.strip():
            buf.append(line.strip())
    if buf:
        out.append((1, head, "\n".join(buf)))
    return out


def parse_html(path: Path, entry: dict):
    soup = BeautifulSoup(path.read_text(), "html.parser")
    out = []
    for h2 in soup.find_all("h2"):
        parts = []
        for sib in h2.find_next_siblings():
            if sib.name == "h2":
                break
            if sib.name == "table":
                for tr in sib.find_all("tr"):
                    parts.append(" | ".join(c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])))
            else:
                parts.append(sib.get_text(" ", strip=True))
        out.append((1, h2.get_text(strip=True), "\n".join(p for p in parts if p)))
    return out


PARSERS = {".pdf": parse_pdf, ".docx": parse_docx, ".md": parse_md, ".html": parse_html}


# ---------------------------------------------------------------------------------------------- chunking
def split_long(text: str) -> list[str]:
    """Sections over 600 tokens are cut into ~500-token windows with 15% overlap."""
    if tokens(text) <= MAX_TOKENS:
        return [text]
    words = text.split()
    size = int(WINDOW_TOKENS / 1.3)
    step = int(size * (1 - OVERLAP))
    return [" ".join(words[i:i + size]) for i in range(0, max(len(words) - size, 0) + step, step)]


def chunk_document(entry: dict, sections: list[tuple]) -> list[Chunk]:
    chunks = []
    for page, head, body in sections:
        body = mask(body, IRONVALE_ENTITIES).masked_text  # placeholder map is discarded, never stored
        for j, piece in enumerate(split_long(body)):
            key = f"{entry['doc_id']}|{entry['version']}|{page}|{head}|{j}"
            cid = f"{entry['doc_id']}-{entry['version']}-p{page}-" + hashlib.sha1(key.encode()).hexdigest()[:8]
            chunks.append(Chunk(cid, entry["doc_id"], entry["title"], head, page, entry["version"],
                                entry["effective_date"], entry["superseded"], entry["allowed_roles"],
                                entry["scope"], entry["source"], piece))
    return chunks


def table_rows(entry: dict, sections: list[tuple]) -> list[Chunk]:
    """Stretch goal: table-aware ingestion. Each row of an alarm table becomes its own chunk, so an
    alarm lookup returns the exact row with its page."""
    rows = []
    for page, head, body in sections:
        lines = [ln for ln in body.splitlines() if ln.count("|") >= 2]
        if len(lines) < 3:
            continue
        header = [c.strip() for c in lines[0].split("|")]
        for ln in lines[1:]:
            cells = [c.strip() for c in ln.split("|")]
            if len(cells) != len(header) or not re.match(r"^[A-Z]-\d{2,3}$", cells[0]):
                continue
            text = "; ".join(f"{h}: {c}" for h, c in zip(header, cells))
            key = f"{entry['doc_id']}|row|{page}|{cells[0]}"
            cid = f"{entry['doc_id']}-row-{cells[0]}-" + hashlib.sha1(key.encode()).hexdigest()[:6]
            rows.append(Chunk(cid, entry["doc_id"], entry["title"], f"{head} · row {cells[0]}", page,
                              entry["version"], entry["effective_date"], entry["superseded"],
                              entry["allowed_roles"], entry["scope"], entry["source"], text))
    return rows


def build_chunks(table_aware: bool = True, verbose: bool = True) -> list[Chunk]:
    manifest = json.loads((CORPUS / "manifest.json").read_text())
    all_chunks: list[Chunk] = []
    for entry in manifest:
        path = CORPUS / "files" / entry["file"]
        sections = PARSERS[path.suffix](path, entry)
        chunks = chunk_document(entry, sections)
        if table_aware:
            chunks += table_rows(entry, sections)
        all_chunks += chunks
        if verbose:
            pages = sorted({c.page for c in chunks if c.page})
            print(f"{entry['file']:<24} {entry['source']:<8} {len(chunks):>3} chunks  pages {pages}")
    return all_chunks


def write_jsonl(chunks: list[Chunk], path: Path = CHUNKS_JSONL) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(asdict(c), ensure_ascii=False) for c in chunks) + "\n")


def load_jsonl(path: Path = CHUNKS_JSONL) -> list[Chunk]:
    return [Chunk(**json.loads(ln)) for ln in path.read_text().splitlines() if ln.strip()]


def write_postgres(chunks: list[Chunk], embed) -> None:
    import psycopg

    from .config import get_settings

    vectors = embed([c.search_text() for c in chunks])
    with psycopg.connect(get_settings().database_url) as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE chunks")
        for c, v in zip(chunks, vectors):
            cur.execute(
                "INSERT INTO chunks (chunk_id, doc_id, title, section, page, version, effective_date, superseded,"
                " allowed_roles, scope, source, text, embedding) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)",
                (c.chunk_id, c.doc_id, c.title, c.section, c.page, c.version, c.effective_date, c.superseded,
                 c.allowed_roles, c.scope, c.source, c.text, "[" + ",".join(f"{x:.6f}" for x in v) + "]"))
        conn.commit()


def main() -> None:
    chunks = build_chunks()
    write_jsonl(chunks)
    print(f"\n{len(chunks)} chunks -> {CHUNKS_JSONL.relative_to(ROOT)}")
    if "--no-db" in sys.argv:
        return
    from .models import embed_passages

    write_postgres(chunks, embed_passages)
    print("embedded and written to Postgres (pgvector)")


if __name__ == "__main__":
    main()
