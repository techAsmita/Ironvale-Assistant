"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EvalData, getEval } from "@/lib/api";

// Targets from the Week 3 project rules. "max" means lower is better.
const TARGETS: { key: string; label: string; target: number; max?: boolean; pct?: boolean }[] = [
  { key: "faithfulness", label: "Faithfulness", target: 0.85 },
  { key: "response_relevancy", label: "Response relevancy", target: 0.8 },
  { key: "citation_accuracy", label: "Citation accuracy", target: 0.9 },
  { key: "refusal_accuracy", label: "Refusal accuracy", target: 0.9 },
  { key: "access_leaks", label: "Access leaks", target: 0, max: true },
  { key: "sql_execution_accuracy", label: "SQL execution accuracy", target: 0.8 },
  { key: "hallucination_rate", label: "Hallucination rate", target: 0.1, max: true },
  { key: "context_precision", label: "Context precision", target: 0 },
  { key: "context_recall", label: "Context recall", target: 0 },
];

const fmt = (v: unknown) => v === null || v === undefined ? "–" : typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(2)) : String(v);

export default function EvalPage() {
  const [data, setData] = useState<EvalData | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => { getEval().then(setData).catch(() => setErr(true)); }, []);
  const latest = data?.runs[0];
  const trend = [...(data?.runs ?? [])].reverse().map((r) => ({
    run: r.created_at.slice(5, 16).replace("T", " "),
    faithfulness: r.metrics.faithfulness, citation: r.metrics.citation_accuracy, refusal: r.metrics.refusal_accuracy,
    sql: r.metrics.sql_execution_accuracy, passed: r.metrics.passed / Math.max(r.metrics.questions, 1),
  }));
  const traceUrl = (id?: string) => id && data?.langfuse_host && id.startsWith("lf-")
    ? `${data.langfuse_host.replace(/\/$/, "")}/trace/${id.slice(3)}` : null;

  return (
    <div className="eval">
      <nav className="nav" style={{ marginBottom: 12 }}><Link href="/">← Assistant</Link></nav>
      <h1 style={{ margin: 0 }}>Evaluation</h1>
      {err && <p className="thinking">Couldn&apos;t load evaluation runs.</p>}
      {latest && (
        <p className="understood">
          Latest run <b>{latest.run_id}</b> · commit <span className="mono">{latest.git_commit}</span> · {latest.model} ·
          {" "}{latest.metrics.passed}/{latest.metrics.questions} questions passed · prompts {latest.prompt_version}
        </p>
      )}
      {latest && (
        <div className="cards">
          {TARGETS.map((t) => {
            const v = latest.metrics[t.key];
            const good = v === null || v === undefined ? undefined : t.max ? v <= t.target : t.target === 0 ? undefined : v >= t.target;
            return (
              <div key={t.key} className={`metric ${good === true ? "good" : good === false ? "bad" : ""}`}>
                <span>{t.label}</span><b>{fmt(v)}</b>
                <small>{t.target === 0 && !t.max ? "reported" : `target ${t.max ? "≤" : "≥"} ${t.target}`}</small>
              </div>
            );
          })}
          <div className="metric"><span>Cost per question</span><b>₹{fmt(latest.metrics.cost_per_question_inr)}</b>
            <small>run total ₹{fmt(latest.metrics.cost_run_inr)}</small></div>
          {Object.entries(latest.metrics.latency_ms ?? {}).map(([route, l]: [string, any]) => l.p50 !== null && (
            <div key={route} className="metric"><span>Latency · {route}</span><b>{(l.p50 / 1000).toFixed(1)} s</b>
              <small>p95 {(l.p95 / 1000).toFixed(1)} s</small></div>
          ))}
        </div>
      )}
      {trend.length > 1 && (
        <div className="panel">
          <h3 style={{ marginTop: 0 }}>Trend across runs</h3>
          <div style={{ height: 260 }}>
            <ResponsiveContainer>
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e3e1db" />
                <XAxis dataKey="run" tick={{ fontSize: 11 }} /><YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
                <Tooltip /><Legend />
                <Line dataKey="passed" name="Passed share" stroke="#1d1f22" strokeWidth={2} />
                <Line dataKey="faithfulness" stroke="#2b8a3e" />
                <Line dataKey="citation" name="Citation acc." stroke="#364fc7" />
                <Line dataKey="refusal" name="Refusal acc." stroke="#b7791f" />
                <Line dataKey="sql" name="SQL acc." stroke="#d9480f" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Failed questions in the latest run</h3>
        {data && data.failed.length === 0 && <p className="thinking">None.</p>}
        {data && data.failed.length > 0 && (
          <table className="data">
            <thead><tr><th>Id</th><th>User</th><th>Question</th><th>Got</th><th>Why</th><th>Trace</th></tr></thead>
            <tbody>{data.failed.map((f) => {
              const why = [!f.route_ok && "route", !f.status_ok && "status", f.leaks?.length && `leak: ${f.leaks.join(", ")}`,
                f.citation_ok === false && "citation", f.sql_ok === false && "SQL result", f.chart_ok === false && "chart",
                f.template_ok === false && "template", !f.rewrite_ok && "rewrite", !f.must_contain_ok && "missing text"]
                .filter(Boolean).join(", ");
              const url = traceUrl(f.trace_id);
              return (
                <tr key={f.id}><td>{f.id}</td><td className="mono">{f.user_id}</td><td>{f.question}</td>
                  <td>{f.route} / {f.status}</td><td>{why}</td>
                  <td>{url ? <a href={url} target="_blank" rel="noreferrer">open</a> : <span className="mono">{f.trace_id}</span>}</td></tr>
              );
            })}</tbody>
          </table>
        )}
      </div>
    </div>
  );
}
