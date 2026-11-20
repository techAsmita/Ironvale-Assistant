// Inline icon set (no icon font, works offline on the shop floor). 24px grid, 1.8 stroke.
const PATHS: Record<string, string> = {
  home: "M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  book: "M12 6.5C10.5 5 8 4.5 4 4.5v14c4 0 6.5.5 8 2 1.5-1.5 4-2 8-2v-14c-4 0-6.5.5-8 2zm0 0v14",
  chart: "M4 20h16M7 16v-5m5 5V7m5 9v-3",
  wrench: "M14.7 6.3a4 4 0 0 0 5 5L21 13l-8 8-2-2 6.3-6.3a4 4 0 0 1-5-5L10 6l-2 2-4-4 2-2 4 4 2-2z",
  report: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6m-6 4h6",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm7.4-3a7.4 7.4 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7.5 7.5 0 0 0-2-1.2L14.5 3h-5l-.4 2.6a7.5 7.5 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6a7.4 7.4 0 0 0 0 2.4l-2 1.6 2 3.4 2.4-1a7.5 7.5 0 0 0 2 1.2l.4 2.6h5l.4-2.6a7.5 7.5 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z",
  link: "M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5z",
  shield: "M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6zm-3.5 9l2.5 2.5 4.5-4.5",
  check: "M5 12l5 5L20 7",
  alert: "M12 4l9 16H3L12 4zm0 6v4m0 3h.01",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zm0-10v6m0-9h.01",
  search: "M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14zm10 3l-5-5",
  doc: "M7 3h7l5 5v13H7zM14 3v5h5",
  copy: "M8 8h12v12H8zM4 16V4h12",
  send: "M21 3L10 14M21 3l-7 18-4-7-7-4z",
  spark: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z",
  up: "M7 11v9H4v-9h3zm3 9h7.5a2 2 0 0 0 2-1.6l1.4-6A2 2 0 0 0 19 10h-5l1-4.5A1.7 1.7 0 0 0 12 5l-2 6v9z",
  down: "M17 13V4h3v9h-3zm-3-9H6.5a2 2 0 0 0-2 1.6l-1.4 6A2 2 0 0 0 5 14h5l-1 4.5A1.7 1.7 0 0 0 12 19l2-6V4z",
  scan: "M4 8V4h4M20 8V4h-4M4 16v4h4M20 16v4h-4M7 12h10",
  arrow: "M5 12h14m-5-5l5 5-5 5",
  chevron: "M9 6l6 6-6 6",
  chevdown: "M6 9l6 6 6-6",
  menu: "M4 6h16M4 12h16M4 18h16",
  close: "M6 6l12 12M18 6L6 18",
  plus: "M12 5v14M5 12h14",
  bulb: "M9 18h6m-5 3h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7z",
  database: "M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3zm8 3v12c0 1.7-3.6 3-8 3s-8-1.3-8-3V6m16 6c0 1.7-3.6 3-8 3s-8-1.3-8-3",
  machine: "M3 20h18M5 20V9h6v11m0-7h8v7M7 12h2m-2 3h2m4 0h4",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zm0-13v5l3 2",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 9a7 7 0 0 1 14 0",
  users: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 10a7 7 0 0 1 14 0M16 3.5a4 4 0 0 1 0 7.5M22 21a7 7 0 0 0-4-6.3",
  gauge: "M12 14l4-4M4 18a9 9 0 1 1 16 0",
  eye: "M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  external: "M14 4h6v6m0-6l-9 9M18 14v6H4V6h6",
  refresh: "M20 11a8 8 0 0 0-14.9-3M4 4v4h4m-4 5a8 8 0 0 0 14.9 3M20 20v-4h-4",
};

export default function Icon({ name, size = 18, className = "" }: { name: keyof typeof PATHS | string; size?: number; className?: string }) {
  return (
    <svg className={`icon ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name] ?? ""} />
    </svg>
  );
}

export function Logo({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="#102B55" />
      <path d="M12 48V30l10 6v-6l10 6v-6l10 6V16h8v32z" fill="#fff" />
      <rect x="17" y="40" width="5" height="4" rx="1" fill="#102B55" />
      <rect x="27" y="40" width="5" height="4" rx="1" fill="#102B55" />
      <rect x="37" y="40" width="5" height="4" rx="1" fill="#102B55" />
      <path d="M44 12h4" stroke="#7FA2E0" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
