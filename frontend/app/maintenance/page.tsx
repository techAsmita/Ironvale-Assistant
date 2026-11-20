"use client";
import Icon from "@/components/Icon";
import { Kpi, Panel } from "@/components/Panels";
import { cap, month, num, when } from "@/lib/format";
import { useSession } from "@/lib/session";

const reason = (r: string) => cap(r.replace(/_/g, " ").toLowerCase());

export default function Maintenance() {
  const { overview: o, user, askFromAnywhere } = useSession();
  if (!o || !user) return <div className="page"><div className="page-head"><div><h1>Maintenance</h1><p>Loading breakdowns…</p></div></div>
    <div className="kpi-row">{[0, 1, 2, 3].map((i) => <div key={i} className="card kpi-tile skeleton-card" />)}</div></div>;
  const last = o.breakdown_by_month.at(-1);
  const worst = o.breakdown_by_machine[0];
  const topAlarm = o.alarms[0];
  const lines = Array.from(new Set(o.machines.map((m) => m.line))).sort();

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Maintenance</h1><p>Machine breakdowns and alarm codes {user.scope.startsWith("Line") ? `on ${user.scope}` : "across the plant"}. Look up what any alarm means and what the operator should do.</p></div>
      </div>
      <div className="kpi-row">
        <Kpi icon="alert" label={`Breakdowns, ${last ? month(last.month) : ""}`} value={last ? last.events.toLocaleString("en-IN") : "–"} note={last ? `${num(last.hours)} hours lost` : null} />
        <Kpi icon="machine" label="Most breakdown time" value={worst?.machine_id ?? "–"} note={worst ? `${num(worst.hours)} h in ${last ? month(last.month) : ""}` : null} />
        <Kpi icon="bolt" label="Most frequent alarm" value={topAlarm?.alarm_code ?? "–"} note={topAlarm ? `${topAlarm.events} events, ${num(topAlarm.hours)} h` : null} />
        <Kpi icon="settings" label="Machines in scope" value={o.machines.length} note={lines.map((l) => `Line ${l}`).join(", ")} />
      </div>

      <div className="grid-2 wide-left">
        <Panel title="Alarm codes by frequency" sub="Breakdowns that raised an alarm, whole period">
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Alarm</th><th className="num">Events</th><th className="num">Hours</th><th className="num">Machines</th><th /></tr></thead>
              <tbody>{o.alarms.map((a) => (
                <tr key={a.alarm_code}>
                  <td><span className="code">{a.alarm_code}</span></td>
                  <td className="num">{a.events}</td><td className="num">{num(a.hours)}</td><td className="num">{a.machines}</td>
                  <td className="act"><button className="btn-ghost" onClick={() => askFromAnywhere(`What does alarm ${a.alarm_code} mean and what should the operator do?`)}>
                    <Icon name="book" size={15} />What it means</button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Panel>
        <Panel title="Machines" sub="Equipment you can see">
          <div className="machine-list">
            {o.machines.map((m) => (
              <div key={m.machine_id} className="machine">
                <span className="m-icon"><Icon name="machine" size={18} /></span>
                <div><b className="mono">{m.machine_id}</b><span>{m.type} · {m.model}</span></div>
                <span className="tag">Line {m.line}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="Latest breakdowns" sub="Most recent unplanned stops in the plant data" ask={`Top 3 machines by breakdown downtime ${user.scope.startsWith("Line") ? `on ${user.scope}` : "in the plant"} in ${last ? month(last.month) : "the last month"}`}>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Machine</th><th>Started</th><th className="num">Duration</th><th>Reason</th><th>Alarm</th></tr></thead>
            <tbody>{o.recent_breakdowns.map((b, i) => (
              <tr key={i}><td className="mono">{b.machine_id}</td><td>{when(b.start_at)}</td><td className="num">{b.minutes} min</td>
                <td>{reason(b.reason_code)}</td><td>{b.alarm_code ? <span className="code">{b.alarm_code}</span> : <span className="muted">None</span>}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
