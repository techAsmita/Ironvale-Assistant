"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import AnswerCard from "@/components/AnswerCard";
import Icon from "@/components/Icon";
import { useNarrow } from "@/lib/format";
import { THINKING } from "@/lib/people";
import { useSession } from "@/lib/session";

export function Composer({ big = false, autoFocus = false }: { big?: boolean; autoFocus?: boolean }) {
  const { user, busy, submit } = useSession();
  const [text, setText] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const narrow = useNarrow();
  useEffect(() => { if (autoFocus && user) input.current?.focus(); }, [autoFocus, user]);
  useEffect(() => { if (!busy) input.current?.focus({ preventScroll: true }); }, [busy]);
  const go = (e: FormEvent) => { e.preventDefault(); if (text.trim() && !busy) { submit(text); setText(""); } };
  return (
    <form className={`composer ${big ? "big" : ""}`} onSubmit={go}>
      <Icon name="spark" size={big ? 24 : 20} className="spark" />
      <input ref={input} value={text} onChange={(e) => setText(e.target.value)} disabled={!user} aria-label="Your question"
        placeholder={!user ? "Connecting…" : narrow ? "Ask a question" : "Ask a question, e.g. “What does alarm E-417 mean?”"} />
      <button className="btn-primary" disabled={!user || busy || !text.trim()}><Icon name="send" size={17} /><span>Ask</span></button>
    </form>
  );
}

function Thinking() {
  const [i, setI] = useState(0);
  useEffect(() => { const t = setInterval(() => setI((x) => Math.min(x + 1, THINKING.length - 1)), 900); return () => clearInterval(t); }, []);
  return (
    <div className="card thinking" role="status" aria-live="polite">
      {THINKING.map((s, j) => (
        <div key={s} className={`step ${j < i ? "done" : j === i ? "now" : ""}`}>
          <span className="dot">{j < i && <Icon name="check" size={11} />}</span>{s}
        </div>
      ))}
    </div>
  );
}

export function Conversation() {
  const { msgs, busy, user, reset } = useSession();
  const end = useRef<HTMLDivElement>(null);
  const lastQ = useRef<HTMLDivElement>(null);
  // While thinking, follow the bottom. When the answer lands, show it from its question down, not its last line.
  useEffect(() => {
    const last = msgs[msgs.length - 1];
    if (!busy && last && last.kind !== "q") lastQ.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    else end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, busy]);
  const lastQi = msgs.map((m) => m.kind).lastIndexOf("q");
  return (
    <div className="convo">
      <div className="convo-head">
        <div><b>Conversation</b><span>Answering as {user?.name} · only from sources you can open</span></div>
        <button className="btn-secondary" onClick={reset} disabled={busy}><Icon name="plus" size={16} />New question</button>
      </div>
      <div className="thread">
        {msgs.map((m, i) => m.kind === "q" ? <div key={i} className="q" ref={i === lastQi ? lastQ : undefined}><span>{m.text}</span></div>
          : m.kind === "a" ? <AnswerCard key={i} r={m.r} />
          : <div key={i} className="notice error"><Icon name="alert" size={20} /><p>{m.text}</p></div>)}
        {busy && <Thinking />}
        <div ref={end} className="end" />
      </div>
      <div className="dock"><Composer /></div>
    </div>
  );
}
