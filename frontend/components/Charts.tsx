"use client";
// Single-series charts in the Ironvale palette: blue bars, the highest bar in navy, a recessive grid,
// a hover tooltip on every mark and values labelled on the bars.
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { num, useNarrow } from "@/lib/format";

export const C = { navy: "#102B55", blue: "#2457B2", blueSoft: "#8EA9DB", grid: "#E6EAF2", axis: "#5B6577", ink: "#172033" };
type Pt = { x: string; y: number };

const tooltip = (unit: string) => ({
  cursor: { fill: "rgba(36,87,178,.06)" },
  contentStyle: { borderRadius: 10, border: "1px solid #E1E6EF", boxShadow: "0 6px 20px rgba(16,43,85,.10)", fontSize: 13 },
  formatter: (v: unknown) => [num(Number(v)), unit] as [string, string],
});

export function BarView({ data, unit, height = 260, highlightMax = true, layout = "vertical" }:
  { data: Pt[]; unit: string; height?: number; highlightMax?: boolean; layout?: "vertical" | "horizontal" | "auto" }) {
  const narrow = useNarrow();
  if (layout === "auto") layout = narrow && data.length > 3 ? "horizontal" : "vertical";
  const max = data.length ? Math.max(...data.map((d) => d.y)) : 0;
  if (layout === "horizontal") {
    return (
      <div style={{ height: Math.max(120, data.length * 40 + 20) }} aria-label={`${unit} chart`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, left: 4, bottom: 4 }}>
            <CartesianGrid horizontal={false} stroke={C.grid} />
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="x" width={104} tick={{ fontSize: 13, fill: C.ink }} tickLine={false} axisLine={false} />
            <Tooltip {...tooltip(unit)} />
            <Bar dataKey="y" radius={[0, 4, 4, 0]} barSize={20}>
              {data.map((d, i) => <Cell key={i} fill={highlightMax && d.y === max ? C.navy : C.blue} />)}
              <LabelList dataKey="y" position="right" formatter={(v) => num(Number(v))} style={{ fontSize: 12, fill: C.ink, fontWeight: 600 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }
  return (
    <div style={{ height }} aria-label={`${unit} chart`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 24, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={C.grid} />
          <XAxis dataKey="x" tick={{ fontSize: 12, fill: C.ink }} tickLine={false} axisLine={{ stroke: C.grid }} interval={0} />
          <YAxis tick={{ fontSize: 12, fill: C.axis }} width={52} tickLine={false} axisLine={false} />
          <Tooltip {...tooltip(unit)} />
          <Bar dataKey="y" radius={[4, 4, 0, 0]} maxBarSize={64}>
            {data.map((d, i) => <Cell key={i} fill={highlightMax && d.y === max ? C.navy : C.blue} />)}
            <LabelList dataKey="y" position="top" formatter={(v) => num(Number(v))} style={{ fontSize: 12, fill: C.ink, fontWeight: 600 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function LineView({ data, unit, height = 260, domain }: { data: Pt[]; unit: string; height?: number; domain?: [number | string, number | string] }) {
  return (
    <div style={{ height }} aria-label={`${unit} chart`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 24, right: 20, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={C.grid} />
          <XAxis dataKey="x" tick={{ fontSize: 12, fill: C.ink }} tickLine={false} axisLine={{ stroke: C.grid }} />
          <YAxis tick={{ fontSize: 12, fill: C.axis }} width={52} tickLine={false} axisLine={false} domain={domain ?? ["auto", "auto"]} tickFormatter={(v) => num(Number(v))} allowDecimals />
          <Tooltip {...tooltip(unit)} cursor={{ stroke: C.blueSoft, strokeWidth: 1 }} />
          <Line type="monotone" dataKey="y" stroke={C.blue} strokeWidth={2} dot={{ r: 4.5, fill: C.blue, stroke: "#fff", strokeWidth: 2 }} activeDot={{ r: 6 }}>
            <LabelList dataKey="y" position="top" formatter={(v) => num(Number(v))} style={{ fontSize: 12, fill: C.ink, fontWeight: 600 }} />
          </Line>
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
