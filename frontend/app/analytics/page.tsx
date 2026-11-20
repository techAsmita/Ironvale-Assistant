"use client";
import { BarView, LineView } from "@/components/Charts";
import Icon from "@/components/Icon";
import { Kpi, Panel } from "@/components/Panels";
import { cap, month, monthShort, num, period } from "@/lib/format";
import { useSession } from "@/lib/session";

export default function Analytics() {
  const { overview: o, user } = useSession();
  if (!o || !user) return <div className="page"><div className="page-head"><div><h1>Plant Analytics</h1><p>Loading plant figures…</p></div></div>
    <div className="kpi-row">{[0, 1, 2, 3].map((i) => <div key={i} className="card kpi-tile skeleton-card" />)}</div></div>;
  const scope = user.scope.startsWith("Line") ? `on ${user.scope}` : "for the whole plant";
  const months = o.breakdown_by_month;
  const last = months.at(-1), prev = months.at(-2);
  const delta = last && prev ? ((last.hours - prev.hours) / prev.hours) * 100 : null;
  const lastName = last ? month(last.month) : "";
  const yieldLast = o.yield_by_month.at(-1);

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Plant Analytics</h1><p>Downtime, yield and defects {scope}, computed from the plant database for {period(o.coverage.from, o.coverage.to)}.</p></div>
      </div>
      <div className="kpi-row">
        <Kpi icon="clock" label={`Breakdown time, ${lastName}`} value={last ? `${num(last.hours)} h` : "–"}
          note={delta !== null ? <span className={delta > 0 ? "bad" : "good"}>{delta > 0 ? "Up" : "Down"} {Math.abs(delta).toFixed(0)}% on {prev && monthShort(prev.month)}</span> : null} />
        <Kpi icon="gauge" label="Yield (good ÷ planned)" value={o.work_orders.yield_pct !== null ? `${o.work_orders.yield_pct}%` : "–"}
          note={yieldLast ? `${monthShort(yieldLast.month)}: ${yieldLast.yield_pct}%` : null} />
        <Kpi icon="report" label="Work orders" value={o.work_orders.count.toLocaleString("en-IN")} note={period(o.coverage.from, o.coverage.to)} />
        {o.defects ? <Kpi icon="alert" label="Defective parts" value={o.defects.qty.toLocaleString("en-IN")} note={`${o.defects.records} defect records`} />
          : <Kpi icon="alert" locked label="Defect records" value="Not in your access" note="Open to quality engineers and the plant head" />}
      </div>

      <div className="grid-2">
        <Panel title="Breakdown time by month" sub="Hours of unplanned stops" ask={`Monthly breakdown downtime ${scope}`}>
          <BarView data={months.map((m) => ({ x: month(m.month), y: m.hours }))} unit="Hours" />
        </Panel>
        <Panel title={`Breakdown time by machine, ${lastName}`} sub="Highest machine in navy" ask={`Breakdown downtime by machine ${scope} in ${lastName}`}>
          <BarView layout="horizontal" data={o.breakdown_by_machine.map((m) => ({ x: m.machine_id, y: m.hours }))} unit="Hours" />
        </Panel>
        <Panel title="Downtime by category" sub="All stops, whole period" ask={`Downtime hours by category ${scope}`}>
          <BarView layout="horizontal" highlightMax={false} data={o.downtime_by_category.map((c) => ({ x: cap(c.category), y: c.hours }))} unit="Hours" />
        </Panel>
        <Panel title="Yield by month" sub="Good parts as a share of planned" ask={`Yield by month ${scope}`}>
          <LineView data={o.yield_by_month.map((m) => ({ x: month(m.month), y: m.yield_pct }))} unit="Yield %" domain={["dataMin - 1", "dataMax + 1"]} />
        </Panel>
      </div>
      <p className="footnote"><Icon name="database" size={14} />Figures are read live from the plant database under your access, the same way the assistant answers number questions. {o.coverage.downtime_events.toLocaleString("en-IN")} downtime events in scope.</p>
    </div>
  );
}
