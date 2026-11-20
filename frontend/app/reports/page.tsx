"use client";
import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import Icon from "@/components/Icon";
import { Panel } from "@/components/Panels";
import { EvalData, getEval } from "@/lib/api";
import { when } from "@/lib/format";

// Targets from the Week 3 project rules. "max" means lower is better.
const TARGETS: { key: string; label: string; target: number; max?: boolean; plain: string }[] = [
  { key: "faithfulness", label: "Faithfulness", target: 0.85, plain: "Answers stick to the sources" },
  { key: "citation_accuracy", label: "Citation accuracy", target: 0.9, plain: "Cites the right document and page" },
  { key: "refusal_accuracy", label: "Refusal accuracy", target: 0.9, plain: "Says “not found” when it should" },
  { key: "access_leaks", label: "Access leaks", target: 0, max: true, plain: "Restricted facts shown to the wrong role" },
  { key: "sql_execution_accuracy", label: "Number accuracy", target: 0.8, plain: "Plant numbers match the checked answer" },
  { key: "hallucination_rate", label: "Hallucination rate", target: 0.1, max: true, plain: "Claims with no source behind them" },
  { key: "response_relevancy", label: "Relevance", target: 0.8, plain: "Answers the question that was asked" },
];
const fmt = (v: unknown) => v === null || v === undefined ? "–" : typeof v === "number" ? (Number.isInteger(v) ? String(v) : `${Math.round(v * 100)}%`) : String(v);
const COLORS = ["#102B55", "#2457B2", "#15966A", "#B7791F"];

export default function Reports() {
  const [data, setData] = useState<EvalData | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => { getEval().then(setData).catch(() => setErr(true)); }, []);
  const latest = data?.runs[0];
  const trend = [...(data?.runs ?? [])].reverse().map((r) => ({
    run: when(r.created_at), Passed: r.metrics.passed / Math.max(r.metrics.questions, 1),
    Faithfulness: r.metrics.faithfulness, Citations: r.metrics.citation_accuracy, Refusals: r.metrics.refusal_accuracy,
  }));
  const traceUrl = (id?: string) => id && data?.langfuse_host && id.startsWith("lf-") ? `${data.langfuse_host.replace(/\/$/, "")}/trace/${id.slice(3)}` : null;

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Reports</h1><p>How accurately the assistant answers. Every run asks all 35 golden questions as the real users and scores the answers, sources and access rules.</p></div>
      </div>
      {err && <div className="notice error"><Icon name="alert" size={20} /><p>Couldn&apos;t load the reports. Check that the assistant is running.</p></div>}
      {data && !latest && (
        <div className="card empty big">
          <span className="empty-icon"><Icon name="report" size={28} /></span>
          <b>No evaluation run yet</b>
          <span>Run the golden question set once and the scores appear here with the date, model and prompt version.</span>
          <code>cd backend && python ../eval/run_eval.py</code>
        </div>
      )}
      {latest && (
        <>
          <div className="banner"><Icon name="report" size={18} /><span>Latest run <b>{when(latest.created_at)}</b> · {latest.metrics.passed} of {latest.metrics.questions} questions passed · Model {latest.model} · Commit <span className="mono">{latest.git_commit}</span></span></div>
          <div className="metric-grid">
            {TARGETS.map((t) => {
              const v = latest.metrics[t.key];
              const good = v === null || v === undefined ? undefined : t.max ? v <= t.target : v >= t.target;
              return (
                <div key={t.key} className="card metric">
                  <div className="metric-top"><span>{t.label}</span>
                    {good !== undefined && <span className={`tag ${good ? "green" : "amber"}`}>{good ? "On target" : "Below target"}</span>}</div>
                  <b>{t.key === "access_leaks" ? fmt(v) : fmt(v)}</b>
                  <small>{t.plain} · Target {t.max ? "≤" : "≥"} {t.key === "access_leaks" ? t.target : `${t.target * 100}%`}</small>
                </div>
              );
            })}
          </div>
          {trend.length > 1 && (
            <Panel title="Trend across runs" sub="Share of questions, higher is better">
              <div style={{ height: 260 }}>
                <ResponsiveContainer>
                  <LineChart data={trend} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E6EAF2" />
                    <XAxis dataKey="run" tick={{ fontSize: 12 }} tickLine={false} /><YAxis domain={[0, 1]} tick={{ fontSize: 12 }} width={40} tickLine={false} axisLine={false} />
                    <Tooltip formatter={(v) => `${Math.round(Number(v) * 100)}%`} /><Legend />
                    {["Passed", "Faithfulness", "Citations", "Refusals"].map((k, i) => <Line key={k} dataKey={k} stroke={COLORS[i]} strokeWidth={2} dot={{ r: 4 }} />)}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          )}
          <Panel title="Questions that failed in the latest run" sub="Each links to its trace">
            {data!.failed.length === 0 ? <div className="empty"><Icon name="check" size={22} /><b>Every question passed</b></div> : (
              <div className="table-wrap"><table className="data">
                <thead><tr><th>Id</th><th>User</th><th>Question</th><th>Why it failed</th><th>Trace</th></tr></thead>
                <tbody>{data!.failed.map((f) => {
                  const why = [!f.route_ok && "Wrong route", !f.status_ok && "Wrong status", f.leaks?.length && `Leak: ${f.leaks.join(", ")}`,
                    f.citation_ok === false && "Citation", f.sql_ok === false && "Number result", f.chart_ok === false && "Chart type",
                    f.template_ok === false && "Graph template", !f.rewrite_ok && "Rewrite", !f.must_contain_ok && "Missing text"].filter(Boolean).join(", ");
                  const url = traceUrl(f.trace_id);
                  return <tr key={f.id}><td className="mono">{f.id}</td><td className="mono">{f.user_id}</td><td>{f.question}</td><td>{why}</td>
                    <td>{url ? <a href={url} target="_blank" rel="noreferrer">Open <Icon name="external" size={12} /></a> : <span className="mono">{f.trace_id}</span>}</td></tr>;
                })}</tbody>
              </table></div>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
