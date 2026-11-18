// Plain-language labels for non-technical users, and suggested questions per demo user.
export const ROLE_LABEL: Record<string, string> = {
  line_supervisor: "Line supervisor", quality_engineer: "Quality engineer", plant_head: "Plant head",
};
export const CAN_SEE: Record<string, string[]> = {
  line_supervisor: ["SOPs and work instructions", "Machine manuals", "Own line's downtime and work orders"],
  quality_engineer: ["Everything a supervisor sees, all lines", "Quality deviation reports", "Supplier list and agreements", "Defects"],
  plant_head: ["Everything, including supplier prices"],
};
export const SUGGESTIONS: Record<string, string[]> = {
  u_sup_l1: ["What does alarm E-417 mean on the DMC 850?", "Breakdown downtime by machine on Line 1 in October 2026",
             "What's the unit price of HX-220-B?", "What is the changeover target on Line 1?"],
  u_sup_l3: ["What torque for M8 flange bolts?", "soak time for HX-220-B?", "Yield by machine on Line 3 in October 2026"],
  u_qe: ["Which suppliers are behind deviations on Line 1 this year?", "What containment was put in place for QDR-2026-014?",
         "Defect quantity by defect type in September 2026"],
  u_head: ["If Arcflow is put on hold, which machines and SOPs are affected?", "Monthly breakdown downtime for the whole plant",
           "What is the unit price of HX-220-B?"],
};
export const ROUTE_LABEL: Record<string, string> = {
  docs: "From the procedures", data: "From plant data", graph: "How things connect", out_of_scope: "Out of scope",
};
