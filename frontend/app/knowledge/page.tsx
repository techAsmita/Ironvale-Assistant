"use client";
import { useMemo, useState } from "react";
import Icon from "@/components/Icon";
import { DocInfo } from "@/lib/api";
import { day, version } from "@/lib/format";
import { ROLE_LABEL } from "@/lib/people";
import { useSession } from "@/lib/session";

const GROUPS: { key: string; label: string; match: (d: DocInfo) => boolean }[] = [
  { key: "all", label: "All", match: () => true },
  { key: "sop", label: "SOPs", match: (d) => d.doc_id.startsWith("SOP") },
  { key: "man", label: "Manuals", match: (d) => d.doc_id.startsWith("MAN") },
  { key: "wi", label: "Work instructions", match: (d) => d.doc_id.startsWith("WI") },
  { key: "qdr", label: "Quality reports", match: (d) => d.doc_id.startsWith("QDR") },
  { key: "sup", label: "Supplier documents", match: (d) => /^(ASL|SQA|PRC)/.test(d.doc_id) },
];
const ICON: Record<string, string> = { SOP: "doc", MAN: "book", WI: "wrench", QDR: "alert", ASL: "users", SQA: "shield", PRC: "database" };
const scopeLabel = (s: string) => s.startsWith("line:") ? `Line ${s.slice(5)}` : "Plant-wide";

function question(d: DocInfo) {
  if (d.doc_id.startsWith("QDR")) return `What happened in ${d.doc_id} and what containment was put in place?`;
  if (d.doc_id === "MAN-CNC-04") return "What does alarm E-417 mean on the DMC 850?";
  return `What are the key points of ${d.title}?`;
}

export default function Knowledge() {
  const { docs, user, openSource, askFromAnywhere } = useSession();
  const [group, setGroup] = useState("all");
  const [q, setQ] = useState("");
  const [old, setOld] = useState(false);
  const list = useMemo(() => (docs ?? []).filter((d) => (old || !d.superseded) && GROUPS.find((g) => g.key === group)!.match(d)
    && (!q.trim() || `${d.doc_id} ${d.title} ${d.kind}`.toLowerCase().includes(q.trim().toLowerCase()))), [docs, group, q, old]);
  const counts = (g: (typeof GROUPS)[number]) => (docs ?? []).filter((d) => !d.superseded && g.match(d)).length;
  const hasOld = (docs ?? []).some((d) => d.superseded);

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Knowledge Base</h1><p>SOPs, machine manuals, work instructions and quality documents you can open. Ask about any of them, or open the text.</p></div>
      </div>
      {user && (
        <div className="banner"><Icon name="shield" size={18} />
          <span>Showing documents open to <b>{ROLE_LABEL[user.role]}s</b>. Restricted documents are not listed, and the assistant never answers from them for {user.name.split(" ")[0]}.</span></div>
      )}
      <div className="toolbar">
        <label className="search"><Icon name="search" size={17} /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by title or document number" aria-label="Search documents" /></label>
        <div className="seg">
          {GROUPS.filter((g) => g.key === "all" || counts(g) > 0).map((g) => (
            <button key={g.key} className={group === g.key ? "on" : ""} onClick={() => setGroup(g.key)}>{g.label}<span>{counts(g)}</span></button>
          ))}
        </div>
        {hasOld && <label className="toggle"><input type="checkbox" checked={old} onChange={(e) => setOld(e.target.checked)} />Show superseded versions</label>}
      </div>

      {docs === null ? <div className="doc-grid">{[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="card doc skeleton-card" />)}</div> : (
        <div className="doc-grid">
          {list.map((d) => (
            <article key={`${d.doc_id}-${d.version}`} className={`card doc ${d.superseded ? "is-old" : ""}`}>
              <div className="doc-top">
                <span className="doc-icon"><Icon name={ICON[d.doc_id.split("-")[0]] ?? "doc"} size={20} /></span>
                <div className="doc-id"><span className="mono">{d.doc_id}</span><small>{d.kind}</small></div>
                {d.superseded ? <span className="tag amber">Superseded</span> : <span className="tag green"><Icon name="check" size={12} />Current</span>}
              </div>
              <h3>{d.title}</h3>
              <div className="tags">
                {d.version && <span className="tag">{version(d.version)}</span>}
                {d.effective_date && <span className="tag">Effective {day(d.effective_date)}</span>}
                {d.page_range && <span className="tag blue">{d.page_range[0] === d.page_range[1] ? `Page ${d.page_range[0]}` : `Pages ${d.page_range[0]}–${d.page_range[1]}`}</span>}
                <span className="tag">{scopeLabel(d.scope)}</span>
                {d.source === "scanned" && <span className="tag"><Icon name="scan" size={11} />Scanned, read by OCR</span>}
              </div>
              <div className="doc-actions">
                <button className="btn-secondary" onClick={() => openSource({ doc_id: d.doc_id, title: d.title, version: d.version, effective_date: d.effective_date, superseded: d.superseded, chunk_id: d.first_chunk_id })}>
                  <Icon name="eye" size={16} />Preview</button>
                {!d.superseded && <button className="btn-primary sm" onClick={() => askFromAnywhere(question(d))}><Icon name="spark" size={16} />Ask about this</button>}
              </div>
            </article>
          ))}
          {list.length === 0 && <div className="empty"><Icon name="search" size={24} /><b>No documents match</b><span>Try another word or clear the filter.</span></div>}
        </div>
      )}
    </div>
  );
}
