"use client";
import Link from "next/link";
import { Composer, Conversation } from "@/components/Assistant";
import Icon from "@/components/Icon";
import { greeting, month, num, period } from "@/lib/format";
import { QUICK, ROLE_LABEL, SUGGESTIONS } from "@/lib/people";
import { useSession } from "@/lib/session";

function Plant() {
  // Line-art plant skyline; decorative only.
  return (
    <svg className="hero-art" viewBox="0 0 520 220" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round">
      <path d="M0 200h520" />
      <path d="M20 200v-70l40 22v-22l40 22v-22l40 22v48" />
      <path d="M150 200V96h56v104M164 96V40h10v56M186 96V58h9v38" />
      <path d="M220 200v-64h92v64M232 150h16v14h-16zM260 150h16v14h-16zM288 150h16v14h-16z" />
      <path d="M330 200V120a24 24 0 0 1 48 0v80M336 132h36M336 150h36M336 168h36" />
      <path d="M392 200v-46h56v46M404 154v-20h32v20M412 134v-30h16v30" />
      <path d="M462 200V86h14v114M469 86V64M454 112h30M454 140h30" />
      <path d="M178 52c6-8 18-10 26-4M190 34c8-10 22-10 30 0" opacity=".55" />
      <path d="M312 176h18M378 176h14M448 176h14" />
    </svg>
  );
}

export default function Home() {
  const { user, msgs, overview, docs, submit, down } = useSession();
  if (msgs.length > 0) return <Conversation />;
  const first = user?.name.split(" ")[0] ?? "";
  const sugg = user ? SUGGESTIONS[user.user_id] ?? [] : [];
  const lastMonth = overview?.breakdown_by_month.at(-1);
  const current = docs?.filter((d) => !d.superseded).length;

  return (
    <div className="page home">
      <section className="hero">
        <Plant />
        <div className="hero-text">
          <h1>{greeting()}{first && <>, <span className="accent">{first}.</span></>}</h1>
          <p>Your AI shop-floor assistant. Ask about procedures, alarms, plant numbers and suppliers. Every answer cites the document, page and version it came from.</p>
        </div>
        <Composer big autoFocus />
        {user && <div className="hero-note"><Icon name="shield" size={15} />Answering as {user.name} · {ROLE_LABEL[user.role]} · {user.scope}. Restricted information is never shown.</div>}
        {down && <div className="notice"><Icon name="info" size={20} /><p>The assistant is starting up. This page connects automatically.</p></div>}
      </section>

      <section className="stats" aria-label="Your scope">
        <div className="stat"><Icon name="book" size={20} /><div><b>{current ?? "–"}</b><span>Documents you can open</span></div></div>
        <div className="stat"><Icon name="machine" size={20} /><div><b>{overview ? overview.machines.length : "–"}</b><span>Machines in your scope</span></div></div>
        <div className="stat"><Icon name="clock" size={20} /><div><b>{lastMonth ? `${num(lastMonth.hours)} h` : "–"}</b><span>Breakdown time{lastMonth ? `, ${month(lastMonth.month)}` : ""}</span></div></div>
        <div className="stat"><Icon name="database" size={20} /><div><b>{overview ? period(overview.coverage.from, overview.coverage.to) : "–"}</b><span>Plant data period</span></div></div>
      </section>

      <section>
        <div className="section-head"><h2><Icon name="bolt" size={20} />Quick actions</h2></div>
        <div className="quick">
          {QUICK.map((q) => (
            <Link key={q.href} href={q.href} className="qcard">
              <span className="qicon"><Icon name={q.icon} size={22} /></span>
              <b>{q.title}</b><span>{q.text}</span>
              <span className="qgo"><Icon name="chevron" size={16} /></span>
            </Link>
          ))}
        </div>
      </section>

      {sugg.length > 0 && (
        <section className="suggest-panel">
          <div className="section-head"><h2><Icon name="bulb" size={20} />Suggested questions for {first}</h2></div>
          <div className="chips-row">
            {sugg.map((s) => <button key={s.q} className="chip-q" onClick={() => submit(s.q)}>{s.q}</button>)}
          </div>
        </section>
      )}
    </div>
  );
}
