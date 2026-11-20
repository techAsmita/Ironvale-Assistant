"use client";
import { useEffect } from "react";
import Icon from "@/components/Icon";
import { day, version } from "@/lib/format";
import { useSession } from "@/lib/session";

export default function SourceDrawer() {
  const { source, closeSource } = useSession();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") closeSource(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeSource]);
  if (!source) return null;
  const m = source.meta, c = source.chunk;
  const page = c?.page ?? m.page;
  return (
    <div className="drawer-bg" onClick={closeSource}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Source document" role="dialog">
        <div className="drawer-head">
          <div className="dh-icon"><Icon name="doc" size={20} /></div>
          <div className="dh-text">
            <span className="mono">{m.doc_id}</span>
            <h3>{m.title}</h3>
          </div>
          <button className="icon-btn" onClick={closeSource} aria-label="Close"><Icon name="close" /></button>
        </div>
        <div className="tags">
          {(c?.section ?? m.section) && <span className="tag">{c?.section ?? m.section}</span>}
          {page ? <span className="tag blue">Page {page}</span> : null}
          {(c?.version ?? m.version) && <span className="tag">{version(c?.version ?? m.version)}</span>}
          {(c?.effective_date ?? m.effective_date) && <span className="tag">Effective {day(c?.effective_date ?? m.effective_date)}</span>}
          {(c?.superseded ?? m.superseded) ? <span className="tag amber">Superseded version</span> : <span className="tag green"><Icon name="check" size={12} />Current version</span>}
          {c?.source === "scanned" && <span className="tag"><Icon name="scan" size={12} />Scanned manual, read by OCR</span>}
        </div>
        <div className="drawer-body">
          {c ? <div className="source-text">{c.text}</div>
            : source.failed ? <p className="muted">The text of this source isn&apos;t available to open here.</p>
            : <div className="loading-lines"><span /><span /><span /></div>}
        </div>
        <div className="drawer-foot"><Icon name="shield" size={14} />Names of people are masked (e.g. &lt;PERSON_1&gt;) before documents are indexed.</div>
      </aside>
    </div>
  );
}
