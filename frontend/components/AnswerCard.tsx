"use client";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AskResponse, Citation, sendFeedback } from "@/lib/api";
import { ROUTE_LABEL } from "@/lib/people";

const STATUS_LABEL: Record<string, string> = {
  answered: "Answered", not_found: "Not found", out_of_scope: "Out of scope", error: "Error",
};
const pretty = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

function AnswerText({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className="answer">
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        return m ? (
          <button key={i} className="cite" onClick={() => onCite(Number(m[1]))} title="Show the source">{m[1]}</button>
        ) : (<span key={i}>{p}</span>);
      })}
    </p>
  );
}

function Chart({ r }: { r: AskResponse }) {
  const sql = r.sql!;
  if (!sql.chart) return null;
  const xi = sql.columns.indexOf(sql.chart.x), yi = sql.columns.indexOf(sql.chart.y);
  const data = sql.rows.map((row) => ({ x: String(row[xi]).slice(0, 10), y: Number(row[yi]) }));
  const yLabel = pretty(sql.chart.y);
  return (
    <div className="chart" aria-label={`${yLabel} chart`}>
      <ResponsiveContainer width="100%" height="100%">
        {sql.chart.type === "bar" ? (
          <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e3e1db" />
            <XAxis dataKey="x" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} width={60} />
            <Tooltip formatter={(v) => [Number(v).toLocaleString("en-IN"), yLabel]} />
            <Bar dataKey="y" fill="#364fc7" radius={[4, 4, 0, 0]} />
          </BarChart>
        ) : (
          <LineChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e3e1db" />
            <XAxis dataKey="x" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} width={60} />
            <Tooltip formatter={(v) => [Number(v).toLocaleString("en-IN"), yLabel]} />
            <Line type="monotone" dataKey="y" stroke="#364fc7" strokeWidth={2.5} dot={{ r: 4 }} />
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function Paths({ paths }: { paths: string[][] }) {
  return (
    <div className="paths">
      {paths.slice(0, 12).map((p, i) => (
        <div className="path" key={i}>
          {p.map((step, j) =>
            j % 2 === 0 ? (
              <span key={j} className={`node ${step.split(":")[0]}`}><i>{step.split(":")[0]}</i>{step.split(":").slice(1).join(":")}</span>
            ) : (<span key={j} className="edge">→ {step.toLowerCase()} →</span>)
          )}
        </div>
      ))}
      {paths.length > 12 && <span className="edge">and {paths.length - 12} more paths</span>}
    </div>
  );
}

function sourceMeta(c: Citation) {
  return [c.section, c.page ? `p. ${c.page}` : null, c.version, c.effective_date ? `effective ${c.effective_date}` : null]
    .filter(Boolean).join(" · ");
}

export default function AnswerCard({ r, onOpen }: { r: AskResponse; onOpen: (c: Citation) => void }) {
  const [vote, setVote] = useState<0 | 1 | null>(null);
  const ms = Object.values(r.pipeline.timings_ms || {}).reduce((a, b) => a + b, 0);
  const cite = (n: number) => { const c = r.citations.find((x) => x.n === n); if (c) onOpen(c); };
  const rewritten = r.rewritten_query && r.rewritten_query !== r.question;
  return (
    <article className="card">
      <div className="card-head">
        <span className="badge route">{ROUTE_LABEL[r.route] || r.route}</span>
        <span className={`badge ${r.status}`}>{STATUS_LABEL[r.status]}</span>
      </div>
      {rewritten && <div className="understood">Understood as: <b>{r.rewritten_query}</b></div>}
      <AnswerText text={r.answer} onCite={cite} />

      {r.sql && r.status === "answered" && (
        <>
          <Chart r={r} />
          <details open={!r.sql.chart}>
            <summary>Data table ({r.sql.row_count} rows)</summary>
            <table className="data">
              <thead><tr>{r.sql.columns.map((c) => <th key={c}>{pretty(c)}</th>)}</tr></thead>
              <tbody>{r.sql.rows.map((row, i) => (
                <tr key={i}>{row.map((v, j) => <td key={j}>{typeof v === "number" ? v.toLocaleString("en-IN") : String(v ?? "")}</td>)}</tr>
              ))}</tbody>
            </table>
          </details>
          <details><summary>SQL that produced this</summary><pre className="sql">{r.sql.query}</pre></details>
        </>
      )}

      {r.graph && r.status === "answered" && (
        <details open>
          <summary>Graph path · {r.graph.template.replace(/_/g, " ")} · {Object.values(r.graph.params).join(", ")}</summary>
          <Paths paths={r.graph.paths} />
        </details>
      )}

      {r.citations.length > 0 && (
        <div className="sources">
          {r.citations.map((c) => (
            <button key={c.n} className="source" onClick={() => onOpen(c)} disabled={!c.chunk_id}>
              <span className="n">[{c.n}]</span>
              <span><b>{c.doc_id}</b> {c.title}{c.superseded && <span className="superseded"> · superseded</span>}<br />
                <span className="meta">{sourceMeta(c)}</span></span>
            </button>
          ))}
        </div>
      )}

      <div className="foot">
        <span>{(ms / 1000).toFixed(1)} s</span>
        <span className="mono" title="Langfuse trace id">{r.pipeline.trace_id}</span>
        {r.pipeline.trace_id && (
          <>
            <button className={`thumb ${vote === 1 ? "on" : ""}`} aria-label="Helpful"
              onClick={() => { setVote(1); sendFeedback(r.pipeline.trace_id!, 1).catch(() => {}); }}>👍</button>
            <button className={`thumb ${vote === 0 ? "on" : ""}`} aria-label="Not helpful"
              onClick={() => { setVote(0); sendFeedback(r.pipeline.trace_id!, 0).catch(() => {}); }}>👎</button>
          </>
        )}
      </div>
    </article>
  );
}
