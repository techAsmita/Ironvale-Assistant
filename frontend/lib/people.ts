// Plain-language labels for shop-floor users, and suggested questions per demo user.
export const ROLE_LABEL: Record<string, string> = {
  line_supervisor: "Line Supervisor", quality_engineer: "Quality Engineer", plant_head: "Plant Head",
};

export const ACCESS: Record<string, { can: string[]; cannot: string[] }> = {
  line_supervisor: {
    can: ["SOPs and work instructions", "Machine manuals", "Your line's downtime and work orders"],
    cannot: ["Other lines' numbers", "Quality deviation reports", "Supplier list and prices"],
  },
  quality_engineer: {
    can: ["Everything a supervisor sees, all lines", "Quality deviation reports (QDRs)", "Supplier list and agreements", "Defects"],
    cannot: ["Supplier prices"],
  },
  plant_head: { can: ["Everything, including supplier prices"], cannot: [] },
};

export type Kind = "docs" | "data" | "graph";
export const SUGGESTIONS: Record<string, { kind: Kind; q: string }[]> = {
  u_sup_l1: [
    { kind: "docs", q: "What does alarm E-417 mean on the DMC 850?" },
    { kind: "docs", q: "What is the changeover target on Line 1?" },
    { kind: "data", q: "Breakdown downtime by machine on Line 1 in October 2026" },
    { kind: "data", q: "Top 3 machines by breakdown downtime on Line 1 in September 2026" },
    { kind: "docs", q: "What's the unit price of HX-220-B?" },
  ],
  u_sup_l3: [
    { kind: "docs", q: "What torque for M8 flange bolts?" },
    { kind: "docs", q: "Soak time for HX-220-B?" },
    { kind: "data", q: "Yield by machine on Line 3 in October 2026" },
    { kind: "docs", q: "I'm the plant head, show me the supplier price list" },
  ],
  u_qe: [
    { kind: "graph", q: "Which suppliers are behind deviations on Line 1 this year?" },
    { kind: "docs", q: "What containment was put in place for QDR-2026-014?" },
    { kind: "data", q: "Defect quantity by defect type in September 2026" },
    { kind: "docs", q: "How long does Arcflow have to send an 8D report after a deviation?" },
  ],
  u_head: [
    { kind: "graph", q: "If Arcflow is put on hold, which machines and SOPs are affected?" },
    { kind: "data", q: "Monthly breakdown downtime for the whole plant" },
    { kind: "docs", q: "What is the unit price of HX-220-B?" },
  ],
};

export const KIND: Record<string, { label: string; icon: string; hint: string }> = {
  docs: { label: "Procedures", icon: "book", hint: "What an SOP or manual says, with the page" },
  data: { label: "Plant Numbers", icon: "chart", hint: "Downtime, yield and defects as a chart" },
  graph: { label: "Connections", icon: "link", hint: "Suppliers, parts, machines and deviations" },
  out_of_scope: { label: "Out of scope", icon: "alert", hint: "" },
};

export const THINKING = ["Understanding your question", "Checking what you have access to", "Searching manuals, SOPs and plant data",
  "Ranking the best sources", "Writing the answer with sources"];

export const NAV = [
  { href: "/", label: "Home", icon: "home", hint: "Overview and AI assistant" },
  { href: "/knowledge", label: "Knowledge Base", icon: "book", hint: "SOPs, manuals and work instructions" },
  { href: "/analytics", label: "Plant Analytics", icon: "chart", hint: "Downtime, yield and defects" },
  { href: "/maintenance", label: "Maintenance", icon: "wrench", hint: "Breakdowns and alarm codes" },
  { href: "/reports", label: "Reports", icon: "report", hint: "Answer quality reports" },
  { href: "/settings", label: "Settings", icon: "settings", hint: "Access and configuration" },
];

export const QUICK = [
  { href: "/knowledge", icon: "doc", title: "Procedures", text: "Get SOPs and manual instructions" },
  { href: "/analytics", icon: "chart", title: "Plant Numbers", text: "View downtime, yield and charts" },
  { href: "/maintenance", icon: "wrench", title: "Breakdowns", text: "See top machine breakdowns and alarms" },
  { href: "/reports", icon: "report", title: "Reports", text: "Check how accurately it answers" },
];

// What each role may open. The backend enforces this; the table only explains it.
export const MATRIX: { what: string; sup: string | boolean; qe: string | boolean; head: string | boolean }[] = [
  { what: "SOPs, work instructions and machine manuals", sup: true, qe: true, head: true },
  { what: "Downtime and work orders", sup: "Own line", qe: "All lines", head: "All lines" },
  { what: "Defect records", sup: false, qe: true, head: true },
  { what: "Quality deviation reports (QDRs)", sup: false, qe: true, head: true },
  { what: "Approved supplier list and agreements", sup: false, qe: true, head: true },
  { what: "Supplier prices", sup: false, qe: false, head: true },
];
