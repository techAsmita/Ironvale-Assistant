"use client";
import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import AnswerCard from "@/components/AnswerCard";
import Icon from "@/components/Icon";
import { ask, AskResponse, Citation, DemoUser, getChunk, getUsers, Turn } from "@/lib/api";
import { ACCESS, KIND, Kind, ROLE_LABEL, SUGGESTIONS, THINKING } from "@/lib/people";

type Msg = { kind: "q"; text: string } | { kind: "a"; r: AskResponse } | { kind: "err"; text: string };
type ChunkView = Awaited<ReturnType<typeof getChunk>>;

const initials = (n: string) => n.split(" ").map((p) => p[0]).slice(0, 2).join("");
function greeting() {
  const h = Number(new Date().toLocaleString("en-IN", { hour: "numeric", hour12: false, timeZone: "Asia/Kolkata" }));
  return h < 5 ? "Working late" : h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

function Thinking() {
  const [i, setI] = useState(0);
  useEffect(() => { const t = setInterval(() => setI((x) => Math.min(x + 1, THINKING.length - 1)), 900); return () => clearInterval(t); }, []);
  return (
    <div className="thinking" role="status" aria-live="polite">
      {THINKING.map((s, j) => (
        <div key={s} className={`step ${j < i ? "done" : j === i ? "now" : ""}`}><span className="dot" />{s}</div>
      ))}
    </div>
  );
}

export default function Home() {
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [user, setUser] = useState<DemoUser | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [down, setDown] = useState(false);
  const [open, setOpen] = useState<{ c: Citation; chunk: ChunkView | null } | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getUsers().then((u) => { setUsers(u); setUser(u[0] ?? null); }).catch(() => setDown(true));
  }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, busy]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const history = (): Turn[] =>
    msgs.flatMap((m): Turn[] => m.kind === "q" ? [{ role: "user", content: m.text }]
      : m.kind === "a" ? [{ role: "assistant", content: m.r.answer }] : []).slice(-6);

  async function submit(q: string) {
    if (!user || !q.trim() || busy) return;
    const h = history();
    setMsgs((m) => [...m, { kind: "q", text: q.trim() }]);
    setText(""); setBusy(true);
    try {
      const r = await ask(user.user_id, q.trim(), h);
      setMsgs((m) => [...m, { kind: "a", r }]);
    } catch {
      setMsgs((m) => [...m, { kind: "err", text: "Couldn't reach the assistant. Check the connection and try again." }]);
    } finally { setBusy(false); input.current?.focus(); }
  }

  function pick(id: string) {
    const u = users.find((x) => x.user_id === id);
    if (u) { setUser(u); setMsgs([]); setOpen(null); }
  }

  async function openCitation(c: Citation) {
    setOpen({ c, chunk: null });
    if (c.chunk_id && user) {
      try { setOpen({ c, chunk: await getChunk(c.chunk_id, user.user_id) }); } catch { /* metadata only */ }
    }
  }

  const access = user ? ACCESS[user.role] : null;
  const first = user?.name.split(" ")[0] ?? "";
  const suggestions = user ? SUGGESTIONS[user.user_id] ?? [] : [];
  const byKind = (k: Kind) => suggestions.filter((s) => s.kind === k);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">IV</div>
          <div><b>Ironvale shop-floor assistant</b><span>Hosur plant · Lines 1–3</span></div>
        </div>
        <div className="spacer" />
        <span className="pill-dark">Plant data: Aug–Oct 2026</span>
        <nav className="topnav"><Link className="on" href="/">Assistant</Link><Link href="/eval">Evaluation</Link></nav>
        <div className="who">
          <select aria-label="Signed in as" value={user?.user_id ?? ""} onChange={(e) => pick(e.target.value)}>
            {users.map((u) => <option key={u.user_id} value={u.user_id}>{u.name} · {ROLE_LABEL[u.role]} · {u.scope}</option>)}
          </select>
        </div>
      </header>

      <div className="body">
        <aside className="rail">
          <section>
            <h2>Signed in as</h2>
            <div className="people">
              {users.map((u) => (
                <button key={u.user_id} className={`person ${user?.user_id === u.user_id ? "on" : ""}`} onClick={() => pick(u.user_id)}>
                  <span className="avatar">{initials(u.name)}</span>
                  <span className="pmeta"><b>{u.name}</b><small>{ROLE_LABEL[u.role] ?? u.role} · {u.scope}</small></span>
                </button>
              ))}
              {down && <span className="muted" style={{ fontSize: 13 }}>The assistant is starting up. Refresh in a minute.</span>}
            </div>
          </section>
          {access && (
            <section>
              <h2>What {first} can see</h2>
              <div className="access">
                {access.can.map((s) => <div key={s} className="row yes"><Icon name="check" size={16} />{s}</div>)}
                {access.cannot.map((s) => <div key={s} className="row no"><Icon name="lock" size={16} />{s}</div>)}
                <small>Anything outside this looks the same as missing. Saying &quot;I&apos;m the plant head&quot; doesn&apos;t change it.</small>
              </div>
            </section>
          )}
          <section>
            <h2>Every answer</h2>
            <div className="access">
              <div className="row yes"><Icon name="doc" size={16} />Cites the document, page and version</div>
              <div className="row yes"><Icon name="scan" size={16} />Reads scanned manuals too</div>
              <div className="row yes"><Icon name="gauge" size={16} />Shows numbers as a chart and table</div>
            </div>
          </section>
        </aside>

        <main className="main">
          <div className="thread">
            <div className="column">
              {msgs.length === 0 && user && (
                <section className="welcome">
                  <h1>{greeting()}, {first}.</h1>
                  <p>Ask about a procedure, an alarm, your line&apos;s numbers or a supplier. Answers come only from documents and data you&apos;re allowed to see, with the source for every fact.</p>
                  <div className="groups">
                    {(["docs", "data", "graph"] as Kind[]).filter((k) => byKind(k).length).map((k) => (
                      <div key={k} className="group">
                        <div className="group-head"><Icon name={KIND[k].icon} />{KIND[k].label}</div>
                        <div className="group-hint">{KIND[k].hint}</div>
                        {byKind(k).map((s) => <button key={s.q} className="suggest" onClick={() => submit(s.q)}>{s.q}</button>)}
                      </div>
                    ))}
                  </div>
                </section>
              )}
              {msgs.map((m, i) => m.kind === "q" ? <div key={i} className="q">{m.text}</div>
                : m.kind === "a" ? <AnswerCard key={i} r={m.r} onOpen={openCitation} />
                : <div key={i} className="notice error"><Icon name="alert" size={20} /><p>{m.text}</p></div>)}
              {busy && <Thinking />}
              <div ref={end} />
            </div>
          </div>
          <div className="composer-wrap">
            <form className="composer" onSubmit={(e: FormEvent) => { e.preventDefault(); submit(text); }}>
              <input ref={input} value={text} onChange={(e) => setText(e.target.value)} disabled={!user}
                placeholder={user ? `Ask as ${first}, e.g. "What does alarm E-417 mean?"` : "Loading…"} aria-label="Your question" />
              <button className="send" disabled={!user || busy || !text.trim()}><Icon name="send" size={16} /><span>Ask</span></button>
            </form>
            {user && <div className="composer-hint"><Icon name="lock" size={13} />Answering as {user.name} · {ROLE_LABEL[user.role]} · {user.scope}</div>}
          </div>
        </main>
      </div>

      {open && (
        <div className="drawer-bg" onClick={() => setOpen(null)}>
          <aside className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Source">
            <div className="drawer-head">
              <div>
                <h3>{open.c.doc_id} · {open.c.title}</h3>
                <div className="m">
                  {open.c.section && <span className="tag">{open.c.section}</span>}
                  {open.c.page && <span className="tag page">page {open.c.page}</span>}
                  {open.c.version && <span className="tag">{open.c.version}</span>}
                  {open.c.effective_date && <span className="tag">effective {open.c.effective_date}</span>}
                  {open.c.superseded && <span className="tag old">superseded version</span>}
                  {open.chunk?.source === "scanned" && <span className="tag scan">scanned manual · read by OCR</span>}
                </div>
              </div>
              <button className="btn-ghost" onClick={() => setOpen(null)}>Close</button>
            </div>
            <div className="drawer-body">
              {open.chunk ? <div className="text">{open.chunk.text}</div> : <p className="muted">Loading the source…</p>}
              <p className="note">Names of people in documents are replaced with placeholders like &lt;PERSON_1&gt; before indexing.</p>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
