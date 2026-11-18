"""Render the Ironvale corpus into real files in mixed formats, plus a document register.

    python corpus/build_corpus.py

Digital PDFs, DOCX, Markdown and HTML go to corpus/files/. Documents marked "scanned" are rendered,
rasterised, rotated slightly and given noise, then saved as image-only PDFs, so they must go through
the week-2 OCR step. corpus/manifest.json is the document-control register the ingester reads for
access metadata (allowed roles, version, effective date, superseded).
"""
from __future__ import annotations

import io
import json
import random
import sys
from pathlib import Path

import cv2
import fitz  # PyMuPDF
import numpy as np
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

sys.path.insert(0, str(Path(__file__).parent))
from source_docs import DOCS  # noqa: E402

ROOT = Path(__file__).parent
OUT = ROOT / "files"
random.seed(7)
np.random.seed(7)

styles = getSampleStyleSheet()
H = ParagraphStyle("h", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=11, spaceBefore=8, spaceAfter=3)
B = ParagraphStyle("b", parent=styles["BodyText"], fontName="Helvetica", fontSize=10, leading=14)


def fname(d: dict, ext: str) -> str:
    suffix = f"_{d['version']}" if d["doc_id"] == "SOP-L2-011" else ""
    return f"{d['doc_id']}{suffix}{ext}"


def header_line(d: dict) -> str:
    return (f"Ironvale Components, Hosur plant · {d['doc_id']} {d['version']} · {d['title']} · "
            f"Effective {d['effective_date']}" + (" · SUPERSEDED" if d["superseded"] else ""))


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def render_pdf(d: dict) -> bytes:
    buf = io.BytesIO()
    printed = d.get("printed_pages") or list(range(1, len(d["pages"]) + 1))

    def deco(canvas, docobj):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(18 * mm, A4[1] - 12 * mm, header_line(d))
        canvas.drawCentredString(A4[0] / 2, 10 * mm, f"Page {printed[docobj.page - 1]}")
        canvas.restoreState()

    flow = [Paragraph(esc(f"{d['doc_id']} · {d['title']}"), styles["Title"])]
    for i, page in enumerate(d["pages"]):
        if i:
            flow.append(PageBreak())
        for head, body in page:
            flow += [Paragraph(esc(head), H), Paragraph(esc(body), B), Spacer(1, 3)]
    SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=18 * mm,
                      leftMargin=18 * mm, rightMargin=18 * mm).build(flow, onFirstPage=deco, onLaterPages=deco)
    return buf.getvalue()


def degrade(page_img: np.ndarray, level: float = 0.45) -> np.ndarray:
    img = page_img.astype(np.float32)
    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), random.uniform(-1.3, 1.3) * level, 1.0)
    img = cv2.warpAffine(img, m, (w, h), borderValue=255)
    img = cv2.GaussianBlur(img, (3, 3), 0.5 + 0.5 * level)
    img += np.random.normal(0, 8 + 12 * level, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def render_scanned(d: dict) -> bytes:
    """Digital render -> 200 dpi greyscale -> rotate + blur + noise -> image-only PDF (no text layer)."""
    src = fitz.open(stream=render_pdf(d), filetype="pdf")
    out = fitz.open()
    for p in src:
        pix = p.get_pixmap(dpi=200, colorspace=fitz.csGRAY)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
        ok, jpg = cv2.imencode(".jpg", degrade(img), [cv2.IMWRITE_JPEG_QUALITY, 72])
        page = out.new_page(width=A4[0], height=A4[1])
        page.insert_image(page.rect, stream=jpg.tobytes())
    return out.tobytes(deflate=True)


def render_docx(d: dict, path: Path):
    docx = Document()
    docx.add_paragraph(header_line(d)).runs[0].font.size = 8 * 12700
    docx.add_heading(f"{d['doc_id']} · {d['title']}", level=1)
    for page in d["pages"]:
        for head, body in page:
            docx.add_heading(head, level=2)
            for line in body.split("\n"):
                docx.add_paragraph(line)
    docx.save(path)


def render_md(d: dict) -> str:
    lines = [f"<!-- {header_line(d)} -->", f"# {d['doc_id']} · {d['title']}", ""]
    for page in d["pages"]:
        for head, body in page:
            lines += [f"## {head}", "", body.replace("\n", "  \n"), ""]
    return "\n".join(lines)


def render_html(d: dict) -> str:
    parts = [f"<html><head><meta charset='utf-8'><title>{d['doc_id']} · {d['title']}</title></head><body>",
             f"<p class='meta'>{esc(header_line(d))}</p>", f"<h1>{esc(d['doc_id'])} · {esc(d['title'])}</h1>"]
    for page in d["pages"]:
        for head, body in page:
            parts.append(f"<h2>{esc(head)}</h2>")
            rows = [r for r in body.split("\n") if r.strip()]
            if all("|" in r for r in rows) and len(rows) > 1:
                cells = [[c.strip() for c in r.split("|")] for r in rows]
                parts.append("<table border='1'><tr>" + "".join(f"<th>{esc(c)}</th>" for c in cells[0]) + "</tr>")
                parts += ["<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in cells[1:]]
                parts.append("</table>")
            else:
                parts += [f"<p>{esc(r)}</p>" for r in rows]
    parts.append("</body></html>")
    return "\n".join(parts)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.iterdir():
        old.unlink()
    register = []
    for d in DOCS:
        fmt = d["format"]
        if fmt == "pdf":
            name = fname(d, ".pdf"); (OUT / name).write_bytes(render_pdf(d))
        elif fmt == "scanned":
            name = fname(d, ".pdf"); (OUT / name).write_bytes(render_scanned(d))
        elif fmt == "docx":
            name = fname(d, ".docx"); render_docx(d, OUT / name)
        elif fmt == "md":
            name = fname(d, ".md"); (OUT / name).write_text(render_md(d))
        elif fmt == "html":
            name = fname(d, ".html"); (OUT / name).write_text(render_html(d))
        else:
            raise ValueError(fmt)
        register.append({
            "file": name, "doc_id": d["doc_id"], "title": d["title"], "version": d["version"],
            "effective_date": d["effective_date"], "superseded": d["superseded"],
            "allowed_roles": d["allowed_roles"], "scope": d["scope"],
            "source": "scanned" if fmt == "scanned" else "digital",
            "printed_pages": d.get("printed_pages"),
        })
        print(f"{name:<26} {fmt:<8} {','.join(r[0] for r in d['allowed_roles'])}")
    (ROOT / "manifest.json").write_text(json.dumps(register, indent=2))
    print(f"\n{len(register)} documents -> {OUT.relative_to(ROOT.parent)} · register -> corpus/manifest.json")


if __name__ == "__main__":
    main()
