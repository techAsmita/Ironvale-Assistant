// Plain-language labels for shop-floor users, and suggested questions per demo user.
export const ROLE_LABEL: Record<string, string> = {
  line_supervisor: "Line supervisor", quality_engineer: "Quality engineer", plant_head: "Plant head",
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
    { kind: "docs", q: "soak time for HX-220-B?" },
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
  data: { label: "Plant numbers", icon: "chart", hint: "Downtime, yield and defects as a chart" },
  graph: { label: "Connections", icon: "link", hint: "Suppliers, parts, machines and deviations" },
  out_of_scope: { label: "Out of scope", icon: "alert", hint: "" },
};

export const THINKING = ["Understanding your question", "Checking what you have access to", "Searching manuals, SOPs and plant data",
  "Ranking the best sources", "Writing the answer with sources"];
