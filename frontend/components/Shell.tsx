"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useRef, useState } from "react";
import Icon, { Logo } from "@/components/Icon";
import SourceDrawer from "@/components/SourceDrawer";
import { initials, period } from "@/lib/format";
import { ACCESS, NAV, ROLE_LABEL } from "@/lib/people";
import { useSession } from "@/lib/session";

function UserMenu() {
  const { users, user, pick } = useSession();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  if (!user) return <div className="whoami skeleton" />;
  return (
    <div className="usermenu" ref={box}>
      <button className="whoami" onClick={() => setOpen((o) => !o)} aria-haspopup="listbox" aria-expanded={open}>
        <span className="avatar">{initials(user.name)}</span>
        <span className="who-meta"><b>{user.name}</b><small>{ROLE_LABEL[user.role]} · {user.scope}</small></span>
        <Icon name="chevdown" size={16} className="caret" />
      </button>
      {open && (
        <div className="menu" role="listbox" aria-label="Switch user">
          <div className="menu-label">Switch demo user</div>
          {users.map((u) => (
            <button key={u.user_id} role="option" aria-selected={u.user_id === user.user_id}
              className={`menu-item ${u.user_id === user.user_id ? "on" : ""}`} onClick={() => { pick(u.user_id); setOpen(false); }}>
              <span className="avatar sm">{initials(u.name)}</span>
              <span className="who-meta"><b>{u.name}</b><small>{ROLE_LABEL[u.role]} · {u.scope}</small></span>
              {u.user_id === user.user_id && <Icon name="check" size={16} className="tick" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function AccessCard() {
  const { user } = useSession();
  if (!user) return null;
  const a = ACCESS[user.role];
  return (
    <Link href="/settings" className="access-card">
      <div className="ac-head"><Icon name="shield" size={18} />Your access</div>
      <ul>
        {a.can.slice(0, 3).map((s) => <li key={s}><Icon name="check" size={14} />{s}</li>)}
        {a.cannot.slice(0, 2).map((s) => <li key={s} className="no"><Icon name="lock" size={14} />{s}</li>)}
      </ul>
      <span className="ac-link">View access details <Icon name="arrow" size={14} /></span>
    </Link>
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { user, overview, down } = useSession();
  const [nav, setNav] = useState(false);
  useEffect(() => { setNav(false); }, [path]);
  const current = NAV.find((n) => (n.href === "/" ? path === "/" : path.startsWith(n.href))) ?? NAV[0];
  const cov = overview ? period(overview.coverage.from, overview.coverage.to) : "";

  return (
    <div className="shell">
      <aside className={`side ${nav ? "open" : ""}`} aria-label="Main navigation">
        <div className="brand">
          <Logo size={38} />
          <div><b>Ironvale</b><span>Shop-Floor Assistant</span></div>
          <button className="icon-btn side-close" onClick={() => setNav(false)} aria-label="Close menu"><Icon name="close" /></button>
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className={`nav-item ${current.href === n.href ? "on" : ""}`}>
              <Icon name={n.icon} size={20} /><span>{n.label}</span>
            </Link>
          ))}
        </nav>
        <div className="side-sep" />
        <div className="side-label">Signed in as</div>
        <UserMenu />
        <AccessCard />
        <div className="side-foot">Hosur plant · Lines 1–3</div>
      </aside>
      {nav && <div className="scrim" onClick={() => setNav(false)} />}

      <div className="frame">
        <header className="top">
          <button className="icon-btn burger" onClick={() => setNav(true)} aria-label="Open menu"><Icon name="menu" size={22} /></button>
          <div className="top-title"><b>{current.label}</b><span>{current.hint}</span></div>
          <div className="top-spacer" />
          {down && <span className="status-pill warn"><span className="dot" />Connecting to the assistant…</span>}
          {cov && <span className="status-pill" title={`${overview!.coverage.downtime_events.toLocaleString("en-IN")} downtime events in your scope`}>
            <Icon name="database" size={15} />Plant data · {cov}</span>}
          {user && <span className="status-pill scope"><Icon name="lock" size={14} />{user.scope}</span>}
          {user && <Link href="/settings" className="avatar top-avatar" title={`${user.name} · ${ROLE_LABEL[user.role]}`}>{initials(user.name)}</Link>}
        </header>
        <main className="content" id="content">{children}</main>
      </div>
      <SourceDrawer />
    </div>
  );
}
