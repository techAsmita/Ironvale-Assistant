"use client";
import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import { Panel } from "@/components/Panels";
import { getHealth, Health } from "@/lib/api";
import { initials, period } from "@/lib/format";
import { ACCESS, MATRIX, ROLE_LABEL } from "@/lib/people";
import { useSession } from "@/lib/session";

const ROLES = [["line_supervisor", "sup"], ["quality_engineer", "qe"], ["plant_head", "head"]] as const;

function Mark({ v }: { v: string | boolean }) {
  if (v === true) return <span className="yes"><Icon name="check" size={16} />Yes</span>;
  if (v === false) return <span className="no"><Icon name="lock" size={15} />No</span>;
  return <span className="part">{v}</span>;
}

export default function Settings() {
  const { users, user, pick, overview, docs } = useSession();
  const [health, setHealth] = useState<Health | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => { getHealth().then(setHealth).catch(() => setErr(true)); }, []);
  const a = user ? ACCESS[user.role] : null;

  return (
    <div className="page">
      <div className="page-head"><div><h1>Settings</h1><p>Who is signed in, what each role can open, and the state of the system.</p></div></div>

      <div className="grid-2">
        <Panel title="Signed in as" sub="Demo users. Switching starts a new conversation.">
          <div className="user-list">
            {users.map((u) => (
              <button key={u.user_id} className={`user-row ${u.user_id === user?.user_id ? "on" : ""}`} onClick={() => pick(u.user_id)}>
                <span className="avatar">{initials(u.name)}</span>
                <span className="who-meta"><b>{u.name}</b><small>{ROLE_LABEL[u.role]} · {u.scope}</small></span>
                {u.user_id === user?.user_id ? <span className="tag green"><Icon name="check" size={12} />Active</span> : <span className="tag">Switch</span>}
              </button>
            ))}
          </div>
        </Panel>
        {a && user && (
          <Panel title={`What ${user.name.split(" ")[0]} can see`} sub={`${ROLE_LABEL[user.role]} · ${user.scope}`}>
            <ul className="access-list">
              {a.can.map((s) => <li key={s} className="yes"><Icon name="check" size={16} />{s}</li>)}
              {a.cannot.map((s) => <li key={s} className="no"><Icon name="lock" size={16} />{s}</li>)}
            </ul>
            <div className="why"><Icon name="info" size={16} /><span>Restricted information looks the same as missing information, so nothing leaks by being refused. Saying &ldquo;I&apos;m the plant head&rdquo; in a question doesn&apos;t change access; it comes from the sign-in.</span></div>
          </Panel>
        )}
      </div>

      <Panel title="Access by role" sub="Enforced on documents, database rows and graph paths, not only in the screen">
        <div className="table-wrap">
          <table className="data matrix">
            <thead><tr><th>Information</th>{ROLES.map(([r]) => <th key={r} className={user?.role === r ? "me" : ""}>{ROLE_LABEL[r]}</th>)}</tr></thead>
            <tbody>{MATRIX.map((m) => (
              <tr key={m.what}><td>{m.what}</td>{ROLES.map(([r, k]) => <td key={r} className={user?.role === r ? "me" : ""}><Mark v={m[k]} /></td>)}</tr>
            ))}</tbody>
          </table>
        </div>
      </Panel>

      <div className="grid-2">
        <Panel title="System status" sub="Live from the assistant">
          {err && <div className="notice error"><Icon name="alert" size={18} /><p>The assistant isn&apos;t reachable.</p></div>}
          {health && (
            <dl className="facts">
              <div><dt>Status</dt><dd>{health.status === "ok" ? <span className="tag green"><Icon name="check" size={12} />Running</span> : <span className="tag amber">Starting or degraded</span>}</dd></div>
              <div><dt>Language model</dt><dd>{health.llm_model}{!health.llm_configured && <span className="tag amber">No key set</span>}</dd></div>
              <div><dt>Indexed sections</dt><dd>{health.chunks}</dd></div>
              <div><dt>Answer confidence threshold</dt><dd>{health.rerank_threshold}</dd></div>
              <div><dt>Tracing (Langfuse)</dt><dd>{health.langfuse ? "On" : "Off"}</dd></div>
            </dl>
          )}
        </Panel>
        <Panel title="Your data" sub="What the assistant answers from for you">
          <dl className="facts">
            <div><dt>Documents you can open</dt><dd>{docs ? docs.filter((d) => !d.superseded).length : "–"}</dd></div>
            <div><dt>Plant data period</dt><dd>{overview ? period(overview.coverage.from, overview.coverage.to) : "–"}</dd></div>
            <div><dt>Machines in scope</dt><dd>{overview ? overview.machines.length : "–"}</dd></div>
            <div><dt>Downtime events in scope</dt><dd>{overview ? overview.coverage.downtime_events.toLocaleString("en-IN") : "–"}</dd></div>
            <div><dt>Personal data</dt><dd>Names, phones and emails masked before indexing</dd></div>
          </dl>
        </Panel>
      </div>
    </div>
  );
}
