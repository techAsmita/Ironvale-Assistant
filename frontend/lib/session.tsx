"use client";
// One place for who is signed in, the conversation, plant figures for that user, and the source viewer.
// Switching user clears the conversation, because answers depend on what that user may see.
import { useRouter } from "next/navigation";
import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { ask, AskResponse, Citation, DemoUser, DocInfo, getChunk, getDocuments, getOverview, getUsers, Overview, Turn } from "@/lib/api";

export type Msg = { kind: "q"; text: string } | { kind: "a"; r: AskResponse } | { kind: "err"; text: string };
export type ChunkView = Awaited<ReturnType<typeof getChunk>>;
export type SourceMeta = Pick<Citation, "doc_id" | "title" | "section" | "page" | "version" | "effective_date" | "superseded"> & { chunk_id?: string | null };

interface Session {
  users: DemoUser[]; user: DemoUser | null; down: boolean; pick: (id: string) => void;
  msgs: Msg[]; busy: boolean; submit: (q: string) => void; askFromAnywhere: (q: string) => void; reset: () => void;
  overview: Overview | null; docs: DocInfo[] | null;
  source: { meta: SourceMeta; chunk: ChunkView | null; failed?: boolean } | null;
  openSource: (m: SourceMeta) => void; closeSource: () => void;
}

const Ctx = createContext<Session | null>(null);
const KEY = "ironvale.user";

function load(): string | null { try { return window.localStorage.getItem(KEY); } catch { return null; } }
function save(id: string) { try { window.localStorage.setItem(KEY, id); } catch { /* private mode */ } }

export function SessionProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [user, setUser] = useState<DemoUser | null>(null);
  const [down, setDown] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [docs, setDocs] = useState<DocInfo[] | null>(null);
  const [source, setSource] = useState<Session["source"]>(null);
  const msgsRef = useRef<Msg[]>([]);
  msgsRef.current = msgs;
  const userRef = useRef<DemoUser | null>(null);
  userRef.current = user;
  const busyRef = useRef(false);
  const docsRef = useRef<DocInfo[] | null>(null);
  docsRef.current = docs;

  useEffect(() => {
    let alive = true;
    const tryLoad = (attempt: number) => getUsers().then((u) => {
      if (!alive) return;
      setDown(false); setUsers(u);
      const saved = load();
      setUser(u.find((x) => x.user_id === saved) ?? u[0] ?? null);
    }).catch(() => { if (!alive) return; setDown(true); if (attempt < 20) setTimeout(() => tryLoad(attempt + 1), 3000); });
    tryLoad(0);
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!user) return;
    let alive = true;
    setOverview(null); setDocs(null);
    getOverview(user.user_id).then((o) => alive && setOverview(o)).catch(() => {});
    getDocuments(user.user_id).then((d) => alive && setDocs(d)).catch(() => alive && setDocs([]));
    return () => { alive = false; };
  }, [user]);

  const pick = useCallback((id: string) => {
    const u = users.find((x) => x.user_id === id);
    if (u && u.user_id !== userRef.current?.user_id) { setUser(u); setMsgs([]); setSource(null); save(u.user_id); }
  }, [users]);

  const submit = useCallback(async (q: string) => {
    const u = userRef.current;
    const text = q.trim();
    if (!u || !text || busyRef.current) return;
    const history: Turn[] = msgsRef.current.flatMap((m): Turn[] => m.kind === "q" ? [{ role: "user", content: m.text }]
      : m.kind === "a" ? [{ role: "assistant", content: m.r.answer }] : []).slice(-6);
    busyRef.current = true; setBusy(true);
    setMsgs((m) => [...m, { kind: "q", text }]);
    try {
      const r = await ask(u.user_id, text, history);
      if (userRef.current?.user_id === u.user_id) setMsgs((m) => [...m, { kind: "a", r }]);
    } catch {
      setMsgs((m) => [...m, { kind: "err", text: "Couldn't reach the assistant. Check the connection and try again." }]);
    } finally { busyRef.current = false; setBusy(false); }
  }, []);

  const askFromAnywhere = useCallback((q: string) => { router.push("/"); submit(q); }, [router, submit]);
  const reset = useCallback(() => { if (!busyRef.current) setMsgs([]); }, []);

  const openSource = useCallback(async (meta: SourceMeta) => {
    setSource({ meta, chunk: null });
    const u = userRef.current;
    // Graph answers cite whole documents; open the document's first section then.
    const id = meta.chunk_id ?? docsRef.current?.find((d) => d.doc_id === meta.doc_id && !d.superseded)?.first_chunk_id;
    if (!id || !u) { setSource({ meta, chunk: null, failed: true }); return; }
    try { const c = await getChunk(id, u.user_id); setSource({ meta, chunk: c }); }
    catch { setSource({ meta, chunk: null, failed: true }); }
  }, []);
  const closeSource = useCallback(() => setSource(null), []);

  return (
    <Ctx.Provider value={{ users, user, down, pick, msgs, busy, submit, askFromAnywhere, reset, overview, docs, source, openSource, closeSource }}>
      {children}
    </Ctx.Provider>
  );
}

export function useSession() {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSession outside SessionProvider");
  return s;
}
