"use client";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import Icon from "@/components/Icon";
import { AskResponse, Citation, sendFeedback } from "@/lib/api";
import { KIND } from "@/lib/people";

const STATUS: Record<string, { label: string; icon: string }> = {
  answered: { label: "Answered", icon: "check" }, not_found: { label: "Not found", icon: "search" },
  out_of_scope: { label: "Out of scope", icon: "alert" }, error: { label: "Something went wrong", icon: "alert" },
};
const pretty = (s: string) => s.replace(/_id$/, "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
const fmt = (v: unknown) => typeof v === "number" ? v.toLocaleString("en-IN", { maximumFractionDigits: v < 10 ? 3 : 0 }) : String(v ?? "");
const short = (v: unknown) => { const s = String(v); return /^\d{4}-\d{2}-\d{2}/.test(s) ? new Date(s.slice(0, 10)).toLocaleDateString("en-IN", { month: "short", year: "numeric" }) : s; };

function AnswerText({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  return (
    <p className="answer">
      {text.split(/(\[\d+\])/g).map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        return m ? <button key={i} className="cite" onClick={() => onCite(Number(m[1]))} title="Open this source">{m[1]}</button>
          : <span key={i}>{p}</span>;
      })}
    </p>
  );
}

function DataView({ r }: { r: AskResponse }) {
  const sql = r.sql!;
  const chart = sql.chart;
  const xi = chart ? sql.columns.indexOf(chart.x) : 0, yi = chart ? sql.columns.indexOf(chart.y) : 1;
  const data = useMemo(() => sql.rows.map((row) => ({ x: short(row[xi]), y: Number(row[yi]) })), [sql, xi, yi]);
  const yLabel = chart ? pretty(chart.y) : "";
  const top = data.length ? data.reduce((a, b) => (b.y > a.y ? b : a)) : null;
  const total = data.reduce((s, d) => s + (Number.isFinite(d.y) ? d.y : 0), 0);
  const isRatio = data.every((d) => d.y <= 1.5);
  return (
    <>
      {chart && top && (
        <div className="kpis">
          <div className="kpi hot"><span>Highest · {top.x}</span><b>{fmt(top.y)}</b></div>
          {!isRatio && chart.type === "bar" && <div className="kpi"><span>Total {yLabel.toLowerCase()}</span><b>{fmt(total)}</b></div>}
          <div className="kpi"><span>{chart.type === "line" ? "Periods" : "Compared"}</span><b>{data.length}</b></div>
        </div>
      )}
      {chart && (
        <div className="chart" aria-label={`${yLabel} chart`}>
          <ResponsiveContainer width="100%" height="100%">
            {chart.type === "bar" ? (
              <BarChart data={data} margin={{ top: 24, right: 8, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2dfd8" />
                <XAxis dataKey="x" tick={{ fontSize: 12, fill: "#3a3e45" }} tickLine={false} axisLine={{ stroke: "#d3cfc6" }} />
                <YAxis tick={{ fontSize: 12, fill: "#6a6f77" }} width={56} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: "rgba(47,75,184,.06)" }} formatter={(v) => [fmt(Number(v)), yLabel]} />
                <Bar dataKey="y" radius={[6, 6, 0, 0]} maxBarSize={72}>
                  {data.map((d, i) => <Cell key={i} fill={d === top ? "#c2410c" : "#2f4bb8"} fillOpacity={d === top ? 1 : 0.8} />)}
                  <LabelList dataKey="y" position="top" formatter={(v) => fmt(Number(v))} style={{ fontSize: 12, fill: "#17191c", fontWeight: 600 }} />
                </Bar>
              </BarChart>
            ) : (
              <LineChart data={data} margin={{ top: 24, right: 16, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2dfd8" />
                <XAxis dataKey="x" tick={{ fontSize: 12, fill: "#3a3e45" }} tickLine={false} axisLine={{ stroke: "#d3cfc6" }} />
                <YAxis tick={{ fontSize: 12, fill: "#6a6f77" }} width={56} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v) => [fmt(Number(v)), yLabel]} />
                <Line type="monotone" dataKey="y" stroke="#2f4bb8" strokeWidth={3} dot={{ r: 5, fill: "#2f4bb8" }}>
                  <LabelList dataKey="y" position="top" formatter={(v) => fmt(Number(v))} style={{ fontSize: 12, fill: "#17191c", fontWeight: 600 }} />
                </Line>
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
      <details className="disclosure" open={!chart}>
        <summary>Data table · {sql.row_count} row{sql.row_count === 1 ? "" : "s"}</summary>
        <div>
          <table className="data">
            <thead><tr>{sql.columns.map((c, j) => <th key={c} className={typeof sql.rows[0]?.[j] === "number" ? "num" : ""}>{pretty(c)}</th>)}</tr></thead>
            <tbody>{sql.rows.map((row, i) => (
              <tr key={i}>{row.map((v, j) => <td key={j} className={typeof v === "number" ? "num" : ""}>{typeof v === "number" ? fmt(v) : short(v)}</td>)}</tr>
            ))}</tbody>
          </table>
        </div>
      </details>
      <details className="disclosure">
        <summary>How this was calculated (SQL)</summary>
        <div><pre className="sql">{sql.query}</pre></div>
      </details>
    </>
  );
}

function GraphView({ paths }: { paths: string[][] }) {
  const unique = Array.from(new Map(paths.map((p) => [p.join("|"), p])).values());
  return (
    <details className="disclosure" open>
      <summary>How it connects · {unique.length} path{unique.length === 1 ? "" : "s"}</summary>
      <div className="chains">
        {unique.slice(0, 10).map((p, i) => (
          <div className="chain" key={i}>
            {p.map((step, j) => {
              if (j % 2 === 1) return <span key={j} className="edge">{step.toLowerCase()} <Icon name="arrow" size={14} /></span>;
              const [label, ...rest] = step.split(":");
              return <span key={j} className={`node ${label}`}><i>{label}</i><b>{rest.join(":")}</b></span>;
            })}
          </div>
        ))}
        {unique.length > 10 && <span className="muted" style={{ fontSize: 12 }}>and {unique.length - 10} more</span>}
      </div>
    </details>
  );
}

function SourceList({ cites, onOpen }: { cites: Citation[]; onOpen: (c: Citation) => void }) {
  return (
    <div>
      <div className="understood" style={{ marginBottom: 8 }}><Icon name="doc" size={15} /> Sources</div>
      <div className="sources">
        {cites.map((c) => (
          <button key={c.n} className="source" onClick={() => onOpen(c)} disabled={!c.chunk_id} title={c.chunk_id ? "Open the source text" : c.title}>
            <span className="n">{c.n}</span>
            <span>
              <b>{c.doc_id}</b>
              <span className="t">{c.title}{c.section ? ` · ${c.section}` : ""}</span>
              <span className="m">
                {c.page ? <span className="tag page">p. {c.page}</span> : null}
                {c.version ? <span className="tag">{c.version}</span> : null}
                {c.effective_date ? <span className="tag">effective {c.effective_date}</span> : null}
                {c.doc_id.startsWith("MAN-CNC-04") || c.doc_id.startsWith("MAN-FUR-02") ? <span className="tag scan">scanned manual</span> : null}
                {c.superseded ? <span className="tag old">superseded</span> : null}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function AnswerCard({ r, onOpen }: { r: AskResponse; onOpen: (c: Citation) => void }) {
  const [vote, setVote] = useState<0 | 1 | null>(null);
  const [copied, setCopied] = useState(false);
  const ms = Object.values(r.pipeline.timings_ms || {}).reduce((a, b) => a + b, 0);
  const cite = (n: number) => { const c = r.citations.find((x) => x.n === n); if (c) onOpen(c); };
  const rewritten = r.rewritten_query && r.rewritten_query.trim() !== r.question.trim();
  const kind = KIND[r.route] ?? KIND.docs;
  const st = STATUS[r.status];
  const copy = () => { navigator.clipboard?.writeText(r.answer.replace(/\[\d+\]/g, "")).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }).catch(() => {}); };
  return (
    <article className="card">
      <div className="card-head">
        <span className="chip route"><Icon name={kind.icon} size={14} />{kind.label}</span>
        <span className={`chip ${r.status}`}><Icon name={st.icon} size={14} />{st.label}</span>
        {ms >= 100 && <span className="time">{(ms / 1000).toFixed(1)} s</span>}
      </div>
      <div className="card-body">
        {rewritten && <div className="understood"><Icon name="search" size={15} />Understood as: <b>{r.rewritten_query}</b></div>}

        {r.status === "answered" && <AnswerText text={r.answer} onCite={cite} />}
        {r.status === "not_found" && (
          <div className="notice"><Icon name="lock" size={20} /><div>
            <p><b>{r.answer}</b></p>
            <ul><li>Check the alarm code, part number or line in your question.</li>
              <li>Some documents and lines are only open to other roles. Ask your quality engineer or plant head if you need them.</li></ul>
          </div></div>
        )}
        {r.status === "out_of_scope" && (
          <div className="notice"><Icon name="alert" size={20} /><div><p><b>{r.answer}</b></p>
            <ul><li>Ask about procedures, plant numbers or suppliers at Ironvale.</li></ul></div></div>
        )}
        {r.status === "error" && (
          <div className="notice error"><Icon name="alert" size={20} /><div><p><b>{r.answer}</b></p>
            <ul><li>Wait a few seconds and ask again.</li></ul></div></div>
        )}

        {r.sql && r.status === "answered" && <DataView r={r} />}
        {r.graph && r.status === "answered" && <GraphView paths={r.graph.paths} />}
        {r.citations.length > 0 && <SourceList cites={r.citations} onOpen={onOpen} />}
      </div>
      <div className="card-foot">
        {r.status === "answered" && (
          <button className="btn-ghost" onClick={copy}><Icon name="copy" size={14} />{copied ? "Copied" : "Copy answer"}</button>
        )}
        {r.pipeline.trace_id && (
          <>
            <span>Was this useful?</span>
            <button className={`btn-ghost ${vote === 1 ? "on" : ""}`} aria-label="Helpful"
              onClick={() => { setVote(1); sendFeedback(r.pipeline.trace_id!, 1).catch(() => {}); }}><Icon name="up" size={14} /></button>
            <button className={`btn-ghost ${vote === 0 ? "on" : ""}`} aria-label="Not helpful"
              onClick={() => { setVote(0); sendFeedback(r.pipeline.trace_id!, 0).catch(() => {}); }}><Icon name="down" size={14} /></button>
          </>
        )}
        {r.pipeline.trace_id && <span className="trace" title="Trace id (Langfuse)">{r.pipeline.trace_id}</span>}
      </div>
    </article>
  );
}
