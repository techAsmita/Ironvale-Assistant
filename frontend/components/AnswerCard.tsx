"use client";
import { useMemo, useState } from "react";
import { BarView, LineView } from "@/components/Charts";
import Icon from "@/components/Icon";
import { AskResponse, Citation, GraphResult, sendFeedback } from "@/lib/api";
import { cap, day, num, version } from "@/lib/format";
import { KIND } from "@/lib/people";
import { useSession } from "@/lib/session";

const STATUS: Record<string, { label: string; icon: string }> = {
  answered: { label: "Verified from sources", icon: "check" }, not_found: { label: "Not found", icon: "search" },
  out_of_scope: { label: "Out of scope", icon: "alert" }, error: { label: "Something went wrong", icon: "alert" },
};
const pretty = (s: string) => cap(s.replace(/_id$/, "").replace(/_inr$/, " (₹)").replace(/_/g, " "));
const cell = (v: unknown) => {
  if (typeof v === "number") return num(v, 2);
  const s = String(v ?? "");
  if (/^\d{4}-\d{2}-\d{2}T00:00:00/.test(s) || /^\d{4}-\d{2}-\d{2}$/.test(s)) {
    return s.slice(8, 10) === "01" ? new Date(s.slice(0, 10) + "T00:00:00").toLocaleDateString("en-GB", { month: "short", year: "numeric" }) : day(s);
  }
  return cap(s);
};

function AnswerText({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  return (
    <div className="answer">
      {text.split(/\n{2,}/).map((para, k) => (
        <p key={k}>{para.split(/(\[\d+\])/g).map((p, i) => {
          const m = p.match(/^\[(\d+)\]$/);
          return m ? <button key={i} className="cite" onClick={() => onCite(Number(m[1]))} title="Open this source">{m[1]}</button>
            : <span key={i}>{p}</span>;
        })}</p>
      ))}
    </div>
  );
}

function DataView({ r }: { r: AskResponse }) {
  const sql = r.sql!;
  const chart = sql.chart;
  const xi = chart ? sql.columns.indexOf(chart.x) : 0, yi = chart ? sql.columns.indexOf(chart.y) : 1;
  const data = useMemo(() => sql.rows.map((row) => ({ x: String(cell(row[xi])), y: Number(row[yi]) })), [sql, xi, yi]);
  const unit = chart ? pretty(chart.y) : "";
  const top = data.length ? data.reduce((a, b) => (b.y > a.y ? b : a)) : null;
  const total = data.reduce((s, d) => s + (Number.isFinite(d.y) ? d.y : 0), 0);
  const isRatio = data.every((d) => d.y <= 1.5);
  return (
    <div className="dataview">
      {chart && top && (
        <div className="kpis">
          <div className="kpi"><span>Highest · {top.x}</span><b>{num(top.y)}</b></div>
          {!isRatio && chart.type === "bar" && <div className="kpi"><span>Total {unit.toLowerCase()}</span><b>{num(total)}</b></div>}
          <div className="kpi"><span>{chart.type === "line" ? "Periods" : "Compared"}</span><b>{data.length}</b></div>
        </div>
      )}
      {chart && <div className="chart-box"><div className="chart-title">{unit} by {pretty(chart.x).toLowerCase()}</div>
        {chart.type === "bar" ? <BarView data={data} unit={unit} layout="auto" /> : <LineView data={data} unit={unit} />}</div>}
      <details className="disclosure" open={!chart}>
        <summary><Icon name="chevron" size={14} className="chev" />Data table · {sql.row_count} row{sql.row_count === 1 ? "" : "s"}</summary>
        <div className="table-wrap">
          <table className="data">
            <thead><tr>{sql.columns.map((c, j) => <th key={c} className={typeof sql.rows[0]?.[j] === "number" ? "num" : ""}>{pretty(c)}</th>)}</tr></thead>
            <tbody>{sql.rows.map((row, i) => (
              <tr key={i}>{row.map((v, j) => <td key={j} className={typeof v === "number" ? "num" : ""}>{cell(v)}</td>)}</tr>
            ))}</tbody>
          </table>
        </div>
      </details>
      <details className="disclosure">
        <summary><Icon name="chevron" size={14} className="chev" />How this was calculated (SQL)</summary>
        <pre className="sql">{sql.query}</pre>
      </details>
    </div>
  );
}

const nodeOf = (s: string) => { const [t, ...rest] = s.split(":"); return { type: t, id: rest.join(":") }; };
const lineOf = (m: string) => { const x = m.match(/-L(\d+)-/); return x ? `Line ${x[1]}` : "Other"; };

function GraphView({ g }: { g: GraphResult }) {
  const [all, setAll] = useState(false);
  if (g.template === "supplier_exposure") {
    const supplier = nodeOf(g.paths[0][0]).id, parts = new Set<string>();
    const machines = new Map<string, Set<string>>(), sops = new Set<string>();
    for (const p of g.paths) {
      parts.add(nodeOf(p[2]).id);
      const m = nodeOf(p[4]).id;
      if (!machines.has(lineOf(m))) machines.set(lineOf(m), new Set());
      machines.get(lineOf(m))!.add(m);
      if (p[6]) sops.add(nodeOf(p[6]).id);
    }
    return (
      <div className="impact">
        <div className="impact-row">
          <div className="inode supplier"><i>Supplier</i><b>{supplier}</b></div>
          <span className="iedge">Supplies <Icon name="arrow" size={14} /></span>
          <div className="inode part"><i>Part</i><b>{Array.from(parts).join(", ")}</b></div>
          <span className="iedge">Runs on <Icon name="arrow" size={14} /></span>
          <div className="inode machine"><i>Machines</i><b>{Array.from(machines.values()).reduce((n, s) => n + s.size, 0)} across {machines.size} line{machines.size > 1 ? "s" : ""}</b></div>
        </div>
        <div className="impact-lines">
          {Array.from(machines.entries()).sort().map(([line, ms]) => (
            <div key={line} className="iline">
              <span className="iline-h">{line}</span>
              <div className="chips">{Array.from(ms).sort().map((m) => <span key={m} className="chip-m">{m}</span>)}</div>
              <div className="chips">{Array.from(sops).filter((s) => s.includes(line.replace("Line ", "-L"))).sort().map((s) => <span key={s} className="chip-s"><Icon name="doc" size={12} />{s}</span>)}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }
  const unique = Array.from(new Map(g.paths.map((p) => [p.join("|"), p])).values());
  const shown = all ? unique : unique.slice(0, 6);
  return (
    <div className="chains">
      {shown.map((p, i) => (
        <div className="chain" key={i}>
          {p.map((step, j) => {
            if (j % 2 === 1) return <span key={j} className="iedge">{cap(step.toLowerCase())} <Icon name="arrow" size={13} /></span>;
            const n = nodeOf(step);
            return <span key={j} className={`inode ${n.type.toLowerCase()}`}><i>{n.type}</i><b>{n.id}</b></span>;
          })}
        </div>
      ))}
      {unique.length > 6 && <button className="link-btn" onClick={() => setAll((a) => !a)}>{all ? "Show fewer" : `Show all ${unique.length} connections`}</button>}
    </div>
  );
}

const SCANNED = new Set(["MAN-CNC-04", "MAN-FUR-02"]);
function SourceList({ cites, onOpen }: { cites: Citation[]; onOpen: (c: Citation) => void }) {
  const [all, setAll] = useState(false);
  const shown = all ? cites : cites.slice(0, 4);
  return (
    <div className="sources-block">
      <div className="block-label"><Icon name="doc" size={15} />Sources</div>
      <div className="sources">
        {shown.map((c) => (
          <button key={c.n} className="source" onClick={() => onOpen(c)} title={c.chunk_id ? "Open the source text" : c.title}>
            <span className="n">{c.n}</span>
            <span className="s-body">
              <span className="s-top"><b className="mono">{c.doc_id}</b>{c.page ? <span className="tag blue">Page {c.page}</span> : null}</span>
              <span className="t">{c.title}{c.section ? ` · ${c.section}` : ""}</span>
              <span className="s-meta">
                {[c.version && version(c.version), c.effective_date && `Effective ${day(c.effective_date)}`, SCANNED.has(c.doc_id) && "Scanned manual"].filter(Boolean).join(" · ")}
                {c.superseded ? <span className="old"> · Superseded</span> : null}
              </span>
            </span>
          </button>
        ))}
      </div>
      {cites.length > 4 && <button className="link-btn" onClick={() => setAll((a) => !a)}>{all ? "Show fewer sources" : `Show all ${cites.length} sources`}</button>}
    </div>
  );
}

export default function AnswerCard({ r }: { r: AskResponse }) {
  const { openSource } = useSession();
  const [vote, setVote] = useState<0 | 1 | null>(null);
  const [copied, setCopied] = useState(false);
  const ms = Object.values(r.pipeline.timings_ms || {}).reduce((a, b) => a + b, 0);
  const cite = (n: number) => { const c = r.citations.find((x) => x.n === n); if (c) openSource(c); };
  const rewritten = r.rewritten_query && r.rewritten_query.trim().toLowerCase() !== r.question.trim().toLowerCase();
  const kind = KIND[r.route] ?? KIND.docs;
  const st = STATUS[r.status];
  const copy = () => { navigator.clipboard?.writeText(r.answer.replace(/\s?\[\d+\]/g, "")).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }).catch(() => {}); };
  return (
    <article className="card answer-card">
      <div className="card-head">
        <span className="badge route"><Icon name={kind.icon} size={14} />{kind.label}</span>
        <span className={`badge st-${r.status}`}><Icon name={st.icon} size={14} />{st.label}</span>
        <span className="grow" />
        {ms >= 100 && <span className="time"><Icon name="clock" size={13} />{(ms / 1000).toFixed(1)} s</span>}
      </div>
      <div className="card-body">
        {rewritten && <div className="understood"><Icon name="search" size={14} />Understood as <b>{cap(r.rewritten_query)}</b></div>}
        {r.status === "answered" && <AnswerText text={r.answer} onCite={cite} />}
        {r.status === "not_found" && (
          <div className="notice"><Icon name="lock" size={20} /><div>
            <p><b>{r.answer}</b></p>
            <ul><li>Check the alarm code, part number or line in your question.</li>
              <li>Some documents and lines are open only to other roles. Ask your quality engineer or plant head if you need them.</li></ul>
          </div></div>
        )}
        {r.status === "out_of_scope" && (
          <div className="notice"><Icon name="info" size={20} /><div><p><b>{r.answer}</b></p>
            <ul><li>Ask about procedures, plant numbers or suppliers at Ironvale.</li></ul></div></div>
        )}
        {r.status === "error" && (
          <div className="notice error"><Icon name="alert" size={20} /><div><p><b>{r.answer}</b></p>
            <ul><li>Wait a few seconds and ask again.</li></ul></div></div>
        )}
        {r.sql && r.status === "answered" && <DataView r={r} />}
        {r.graph && r.status === "answered" && r.graph.paths.length > 0 && <GraphView g={r.graph} />}
        {r.citations.length > 0 && <SourceList cites={r.citations} onOpen={openSource} />}
      </div>
      <div className="card-foot">
        {r.status === "answered" && <button className="btn-ghost" onClick={copy}><Icon name="copy" size={14} />{copied ? "Copied" : "Copy answer"}</button>}
        <span className="grow" />
        {r.pipeline.trace_id && (
          <>
            <span className="muted">Was this useful?</span>
            <button className={`icon-btn sm ${vote === 1 ? "on" : ""}`} aria-label="Helpful"
              onClick={() => { setVote(1); sendFeedback(r.pipeline.trace_id!, 1).catch(() => {}); }}><Icon name="up" size={15} /></button>
            <button className={`icon-btn sm ${vote === 0 ? "on" : ""}`} aria-label="Not helpful"
              onClick={() => { setVote(0); sendFeedback(r.pipeline.trace_id!, 0).catch(() => {}); }}><Icon name="down" size={15} /></button>
          </>
        )}
      </div>
    </article>
  );
}
