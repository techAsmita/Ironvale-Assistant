"use client";
import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import AnswerCard from "@/components/AnswerCard";
import { ask, AskResponse, Citation, DemoUser, getChunk, getUsers, Turn } from "@/lib/api";
import { CAN_SEE, ROLE_LABEL, SUGGESTIONS } from "@/lib/people";

type Msg = { kind: "q"; text: string } | { kind: "a"; r: AskResponse } | { kind: "err"; text: string };
type ChunkView = Awaited<ReturnType<typeof getChunk>>;

export default function Home() {
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [user, setUser] = useState<DemoUser | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [down, setDown] = useState(false);
  const [open, setOpen] = useState<{ c: Citation; chunk: ChunkView | null } | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getUsers().then((u) => { setUsers(u); setUser(u[0] ?? null); }).catch(() => setDown(true));
  }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  const history = (): Turn[] =>
    msgs.flatMap((m): Turn[] => m.kind === "q" ? [{ role: "user", content: m.text }]
      : m.kind === "a" ? [{ role: "assistant", content: m.r.answer }] : []).slice(-6);

  async function submit(q: string) {
    if (!user || !q.trim() || busy) return;
    const h = history();
    setMsgs((m) => [...m, { kind: "q", text: q }]);
    setText(""); setBusy(true);
    try {
      const r = await ask(user.user_id, q, h);
      setMsgs((m) => [...m, { kind: "a", r }]);
    } catch {
      setMsgs((m) => [...m, { kind: "err", text: "Couldn't reach the assistant. Check your connection and try again." }]);
    } finally { setBusy(false); }
  }

  function pick(u: DemoUser) { setUser(u); setMsgs([]); }

  async function openCitation(c: Citation) {
    setOpen({ c, chunk: null });
    if (c.chunk_id && user) {
      try { setOpen({ c, chunk: await getChunk(c.chunk_id, user.user_id) }); } catch { /* stays as metadata only */ }
    }
  }

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">
          <div className="brand-mark">IV</div>
          <div><h1>Ironvale Components</h1><p>Shop-floor assistant · Hosur plant</p></div>
        </div>
        <section>
          <h2>Signed in as</h2>
          <div className="users">
            {users.map((u) => (
              <button key={u.user_id} className={`user ${user?.user_id === u.user_id ? "on" : ""}`} onClick={() => pick(u)}>
                <b>{u.name}</b><span>{ROLE_LABEL[u.role] ?? u.role} · {u.scope}</span>
              </button>
            ))}
            {down && <span className="thinking">The assistant is waking up (free hosting sleeps when idle). Refresh in a minute.</span>}
          </div>
        </section>
        {user && (
          <section>
            <h2>What {user.name.split(" ")[0]} can see</h2>
            <ul className="cansee">{(CAN_SEE[user.role] ?? []).map((s) => <li key={s}>{s}</li>)}</ul>
          </section>
        )}
        <nav className="nav"><Link href="/">Assistant</Link><Link href="/eval">Evaluation</Link></nav>
      </aside>

      <main className="main">
        <div className="thread">
          {msgs.length === 0 && user && (
            <div className="empty">
              <h2>Ask about procedures, numbers or suppliers</h2>
              <p>Answers come only from Ironvale&apos;s documents and plant data you are allowed to see, with the source for every fact.</p>
              <div className="chips">
                {(SUGGESTIONS[user.user_id] ?? []).map((s) => <button key={s} className="chip" onClick={() => submit(s)}>{s}</button>)}
              </div>
            </div>
          )}
          {msgs.map((m, i) => m.kind === "q" ? <div key={i} className="q">{m.text}</div>
            : m.kind === "a" ? <AnswerCard key={i} r={m.r} onOpen={openCitation} />
            : <div key={i} className="card"><span className="badge error">Error</span><p>{m.text}</p></div>)}
          {busy && <div className="thinking">Checking the documents and data…</div>}
          <div ref={end} />
        </div>
        <form className="composer" onSubmit={(e: FormEvent) => { e.preventDefault(); submit(text); }}>
          <input value={text} onChange={(e) => setText(e.target.value)} disabled={!user}
            placeholder={user ? `Ask as ${user.name.split(" ")[0]}, e.g. "What does alarm E-417 mean?"` : "Loading…"} />
          <button className="send" disabled={!user || busy || !text.trim()}>Ask</button>
        </form>
      </main>

      {open && (
        <div className="drawer-bg" onClick={() => setOpen(null)}>
          <div className="drawer" onClick={(e) => e.stopPropagation()}>
            <button className="thumb" onClick={() => setOpen(null)} style={{ float: "right" }}>Close</button>
            <h3>{open.c.doc_id} · {open.c.title}</h3>
            <p className="understood">
              {[open.c.section, open.c.page ? `page ${open.c.page}` : null, open.c.version,
                open.c.effective_date ? `effective ${open.c.effective_date}` : null].filter(Boolean).join(" · ")}
              {open.c.superseded && <span className="superseded"> · superseded version</span>}
              {open.chunk?.source === "scanned" && " · scanned manual, text read by OCR"}
            </p>
            {open.chunk ? <div className="text">{open.chunk.text}</div> : <p className="thinking">Loading the source…</p>}
          </div>
        </div>
      )}
    </div>
  );
}
