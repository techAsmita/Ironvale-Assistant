import { useEffect, useState } from "react";

// Display helpers. Every label shown on screen starts with a capital letter.
export const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
export const initials = (n: string) => n.split(" ").map((p) => p[0]).slice(0, 2).join("");
export const num = (v: unknown, digits = 1) =>
  typeof v === "number" ? v.toLocaleString("en-IN", { maximumFractionDigits: Math.abs(v) < 10 ? Math.max(digits, 2) : digits }) : String(v ?? "");
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const monthShort = (s: string) => MON[Number(s.slice(5, 7)) - 1] ?? s;
export const month = (s: string) => `${monthShort(s)} ${s.slice(0, 4)}`;
export const day = (s?: string | null) => (s ? `${Number(s.slice(8, 10))} ${monthShort(s)} ${s.slice(0, 4)}` : "");
export const when = (s: string) => `${Number(s.slice(8, 10))} ${monthShort(s)} ${s.slice(0, 4)}, ${s.slice(11, 16)}`;
export const version = (v?: string | null) => (v ? `Version ${v.replace(/^v/i, "")}` : "");
export const period = (from?: string | null, to?: string | null) => {
  if (!from || !to) return "";
  return from.slice(0, 4) === to.slice(0, 4) ? `${monthShort(from)}–${monthShort(to)} ${to.slice(0, 4)}` : `${month(from)}–${month(to)}`;
};
export function greeting() {
  const h = Number(new Date().toLocaleString("en-IN", { hour: "numeric", hour12: false, timeZone: "Asia/Kolkata" }));
  return h < 5 ? "Working late" : h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

// True on phone-width screens; used to pick chart orientation and shorter placeholders.
export function useNarrow(px = 640) {
  const [n, setN] = useState(false);
  useEffect(() => {
    const q = window.matchMedia(`(max-width: ${px}px)`);
    const f = () => setN(q.matches); f();
    q.addEventListener("change", f);
    return () => q.removeEventListener("change", f);
  }, [px]);
  return n;
}
