"use client";
import { ReactNode } from "react";
import Icon from "@/components/Icon";
import { useSession } from "@/lib/session";

export function Panel({ title, sub, ask, children }: { title: string; sub?: string; ask?: string; children: ReactNode }) {
  const { askFromAnywhere } = useSession();
  return (
    <section className="card panel">
      <div className="panel-head">
        <div><h3>{title}</h3>{sub && <span>{sub}</span>}</div>
        {ask && <button className="btn-ghost" onClick={() => askFromAnywhere(ask)} title={ask}><Icon name="spark" size={15} />Ask</button>}
      </div>
      {children}
    </section>
  );
}

export function Kpi({ label, value, note, icon, locked }: { label: string; value: ReactNode; note?: ReactNode; icon: string; locked?: boolean }) {
  return (
    <div className={`card kpi-tile ${locked ? "locked" : ""}`}>
      <span className="kpi-icon"><Icon name={locked ? "lock" : icon} size={18} /></span>
      <span className="kpi-label">{label}</span>
      <b>{value}</b>
      {note && <small>{note}</small>}
    </div>
  );
}

