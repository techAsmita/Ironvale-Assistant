// Small inline icon set (no icon font, works offline on the shop floor).
const PATHS: Record<string, string> = {
  book: "M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2V5zm0 16a2 2 0 0 1 2-2h12v2H6a2 2 0 0 1-2 0z",
  chart: "M4 20V10m6 10V4m6 16v-7m4 7H2",
  link: "M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1",
  lock: "M6 11V8a6 6 0 0 1 12 0v3M5 11h14v10H5z",
  check: "M5 12l5 5L20 7",
  alert: "M12 4l9 16H3L12 4zm0 6v4m0 3h.01",
  search: "M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14zm10 3l-5-5",
  doc: "M7 3h7l5 5v13H7zM14 3v5h5",
  copy: "M8 8h12v12H8zM4 16V4h12",
  send: "M4 12l16-8-6 16-2-7-8-1z",
  up: "M7 11v9H4v-9h3zm3 9h7.5a2 2 0 0 0 2-1.6l1.4-6A2 2 0 0 0 19 10h-5l1-4.5A1.7 1.7 0 0 0 12 5l-2 6v9z",
  down: "M17 13V4h3v9h-3zm-3-9H6.5a2 2 0 0 0-2 1.6l-1.4 6A2 2 0 0 0 5 14h5l-1 4.5A1.7 1.7 0 0 0 12 19l2-6V4z",
  scan: "M4 8V4h4M20 8V4h-4M4 16v4h4M20 16v4h-4M7 12h10",
  arrow: "M5 12h14m-5-5l5 5-5 5",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 9a7 7 0 0 1 14 0",
  gauge: "M12 14l4-4M4 18a9 9 0 1 1 16 0",
};

export default function Icon({ name, size = 18, className = "" }: { name: keyof typeof PATHS | string; size?: number; className?: string }) {
  return (
    <svg className={`icon ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name] ?? ""} />
    </svg>
  );
}
