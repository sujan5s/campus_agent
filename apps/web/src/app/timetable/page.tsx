"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  CalendarDays,
  Sparkles,
  Play,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  FlaskConical,
  SlidersHorizontal,
  Layers,
  FileDown,
} from "lucide-react";
import { api, getToken, getUser, AuthUser } from "../../lib/api";
import AppLayout from "../../components/AppLayout";

interface ElectiveOption {
  subject_code: string;
  subject_name: string;
  teacher: string;
  room: string;
}
interface Cell {
  subject_code: string;
  subject_name: string;
  teacher: string;
  room: string;
  is_lab: boolean;
  /** Present when the period is an open-elective band: the parallel baskets. */
  elective?: { group: string; offerings: ElectiveOption[] };
}
interface Grid {
  section: string;
  version: number;
  days: string[];
  periods: Record<string, string>; // period_no -> "09:00–09:55"
  cells: Record<string, Cell>; // "MON-1" -> Cell
}
interface SectionRow {
  id: number;
  name: string;
}
interface GenerateResult {
  status: string;
  version?: number;
  lessons?: number;
  elective_periods?: number;
  load_gap?: number;
  wall_time_s?: number;
  reasons?: string[];
}
interface StatusResult {
  latest_version: number | null;
  active_rules: string[];
}

// deterministic high-contrast pastel per subject code
const PALETTE = [
  "bg-blue-50 border-blue-200 text-[#00078b]",
  "bg-amber-50 border-amber-200 text-amber-900",
  "bg-emerald-50 border-emerald-200 text-emerald-900",
  "bg-purple-50 border-purple-200 text-purple-900",
  "bg-rose-50 border-rose-200 text-rose-900",
  "bg-sky-50 border-sky-200 text-sky-900",
  "bg-indigo-50 border-indigo-200 text-indigo-900",
  "bg-[#fdb813]/20 border-[#fdb813]/50 text-[#00078b]",
];
function colorFor(code: string): string {
  let h = 0;
  for (const ch of code) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export default function TimetablePage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [sections, setSections] = useState<SectionRow[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [grid, setGrid] = useState<Grid | null>(null);
  const [generating, setGenerating] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [flash, setFlash] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [noTimetable, setNoTimetable] = useState(false);
  // The rules that generation will use — owned by the Constraints page, shown
  // here read-only so there is exactly one source of truth.
  const [activeRules, setActiveRules] = useState<string[]>([]);

  const loadGrid = useCallback(async (name: string) => {
    try {
      const g = await api<Grid>(`/timetable/section/${encodeURIComponent(name)}`);
      setGrid(g);
      setNoTimetable(false);
    } catch (e: unknown) {
      setGrid(null);
      const msg = e instanceof Error ? e.message : "";
      setNoTimetable(msg.includes("No timetable"));
      if (!msg.includes("No timetable")) setFlash({ kind: "err", text: msg });
    }
  }, []);

  const loadRules = useCallback(async () => {
    try {
      const st = await api<StatusResult>("/timetable/status");
      setActiveRules(st.active_rules ?? []);
    } catch {
      /* the grid is still usable without the rule summary */
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setUser(getUser());
    (async () => {
      try {
        const secs = await api<SectionRow[]>("/setup/sections");
        setSections(secs);
        if (secs.length > 0) {
          setSelected(secs[0].name);
          await loadGrid(secs[0].name);
        }
        await loadRules();
      } catch (e: unknown) {
        setFlash({ kind: "err", text: e instanceof Error ? e.message : "Load failed" });
      }
    })();
  }, [router, loadGrid, loadRules]);

  const generate = async () => {
    setGenerating(true);
    setFlash(null);
    try {
      // No body: the solver reads the constraint registry (see /constraints).
      const r = await api<GenerateResult>("/timetable/generate", { method: "POST" });
      setFlash({
        kind: "ok",
        text:
          `Generated v${r.version}: ${r.lessons} lessons` +
          (r.elective_periods ? ` + ${r.elective_periods} open-elective period(s)` : "") +
          `, load gap ${r.load_gap}, solved in ${r.wall_time_s}s (provably clash-free).`,
      });
      if (selected) await loadGrid(selected);
      await loadRules();
    } catch (e: unknown) {
      // 422 carries the infeasibility explanation
      const msg = e instanceof Error ? e.message : "Generation failed";
      setFlash({ kind: "err", text: msg });
    } finally {
      setGenerating(false);
    }
  };

  const downloadPdf = async () => {
    if (!grid) return;
    setDownloading(true);
    setFlash(null);
    try {
      // dynamic import — jsPDF touches `window`, so keep it out of SSR/initial bundle
      const { jsPDF } = await import("jspdf");
      const autoTable = (await import("jspdf-autotable")).default;

      const constraints = activeRules.join(" · ");
      const ps = grid.periods;
      const periodNos = Object.keys(ps).map(Number).sort((a, b) => a - b);
      const rows = periodNos.map((p) => [
        `P${p}\n${ps[String(p)]}`,
        ...grid.days.map((d) => {
          const c = grid.cells[`${d}-${p}`];
          if (!c) return "—";
          if (c.elective) {
            return `${c.elective.group} (open elective)\n${c.elective.offerings
              .map((o) => `${o.subject_code} · ${o.teacher} · ${o.room}`)
              .join("\n")}`;
          }
          return `${c.subject_code}${c.is_lab ? " (lab)" : ""}\n${c.teacher}\n${c.room}`;
        }),
      ]);

      const doc = new jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
      const margin = 40;
      doc.setFont("helvetica", "bold");
      doc.setFontSize(16);
      doc.setTextColor(15, 23, 42);
      doc.text(`Timetable — ${grid.section}`, margin, 46);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      doc.setTextColor(100, 116, 139);
      doc.text(`Version ${grid.version}  ·  Generated ${new Date().toLocaleString()}`, margin, 62);
      let startY = 76;
      if (constraints) {
        const wrapped = doc.splitTextToSize(`Constraints: ${constraints}`, 760) as string[];
        doc.text(wrapped, margin, 76);
        startY = 76 + wrapped.length * 11 + 4;
      }

      autoTable(doc, {
        startY,
        head: [["Period", ...grid.days]],
        body: rows,
        theme: "grid",
        styles: { fontSize: 8, cellPadding: 3, valign: "middle",
          lineColor: [226, 232, 240], lineWidth: 0.3, textColor: [30, 41, 59] },
        headStyles: { fillColor: [79, 70, 229], textColor: 255, fontStyle: "bold", halign: "center" },
        columnStyles: { 0: { fontStyle: "bold", halign: "center", cellWidth: 60, fillColor: [241, 245, 249] } },
        didParseCell: (data) => {
          if (data.section === "body" && data.column.index > 0) {
            const raw = Array.isArray(data.cell.raw) ? data.cell.raw.join("\n") : String(data.cell.raw ?? "");
            if (raw.includes("(lab)")) data.cell.styles.fillColor = [254, 243, 199];
            if (raw.includes("(open elective)")) data.cell.styles.fillColor = [237, 233, 254];
          }
        },
        didDrawPage: () => {
          doc.setFontSize(8);
          doc.setTextColor(148, 163, 184);
          doc.text("Smart Campus Agent System", margin, doc.internal.pageSize.getHeight() - 20);
        },
      });

      const safe = grid.section.replace(/[^\w.-]+/g, "_");
      doc.save(`timetable-${safe}-v${grid.version}.pdf`);
    } catch (e: unknown) {
      setFlash({ kind: "err", text: e instanceof Error ? e.message : "PDF export failed" });
    } finally {
      setDownloading(false);
    }
  };

  const periods = grid ? Object.keys(grid.periods).map(Number).sort((a, b) => a - b) : [];

  return (
    <AppLayout title="Timetable" subtitle="Generated by OR-Tools CP-SAT solver — clash-free schedule grid.">
      <div className="max-w-6xl mx-auto relative">
        {/* header */}
        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          <div className="flex items-center space-x-3">
            <div className="bg-[#00078b] p-2 rounded-xl text-[#fdb813] shadow-md">
              <CalendarDays className="h-5 w-5" />
            </div>
            <div>
              <h1 className="font-bold text-xl text-[#00078b]">Timetable Control</h1>
              <p className="text-xs text-[#00078b]/70 font-medium">
                View section timetables or generate new clash-free schedules.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <select
              value={selected}
              onChange={(e) => {
                setSelected(e.target.value);
                loadGrid(e.target.value);
              }}
              className="bg-white border border-[#00078b]/20 rounded-xl px-4 py-2.5 text-sm text-[#00078b] font-bold shadow-sm outline-none"
            >
              {sections.map((s) => (
                <option key={s.id} value={s.name}>{s.name}</option>
              ))}
            </select>
            {grid && (
              <button
                onClick={downloadPdf}
                disabled={downloading}
                className="flex items-center space-x-2 bg-white border border-[#00078b]/20 rounded-xl px-4 py-2.5 text-sm font-bold text-[#00078b] hover:bg-[#f6f6f6] disabled:opacity-60 transition-colors shadow-sm"
                title="Download this section's timetable as PDF"
              >
                {downloading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <FileDown className="h-4 w-4 text-[#00078b]" />}
                <span>PDF</span>
              </button>
            )}
            <Link
              href="/constraints"
              className="flex items-center space-x-2 bg-white border border-[#00078b]/20 rounded-xl px-4 py-2.5 text-sm font-bold text-[#00078b] hover:bg-[#f6f6f6] transition-colors shadow-sm"
              title="Edit the rules generation obeys"
            >
              <SlidersHorizontal className="h-4 w-4" />
              <span>Constraints</span>
            </Link>
            {user?.role === "admin" && (
              <button
                onClick={generate}
                disabled={generating}
                className="flex items-center space-x-2 bg-[#00078b] hover:bg-[#000566] disabled:opacity-60 text-white text-sm font-bold rounded-xl px-5 py-2.5 transition-colors shadow-md"
              >
                {generating ? <RefreshCw className="h-4 w-4 animate-spin text-[#fdb813]" /> : <Play className="h-4 w-4 text-[#fdb813]" />}
                <span>{generating ? "Solving…" : "Generate Timetable"}</span>
              </button>
            )}
          </div>
        </div>

        {/* the rules in force — edited on the Constraints page */}
        <div className="bg-white border border-[#00078b]/15 rounded-2xl px-5 py-3 mb-4 shadow-sm">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="flex items-start space-x-2 min-w-0">
              <SlidersHorizontal className="h-4 w-4 text-[#00078b] shrink-0 mt-0.5" />
              <div className="min-w-0">
                <p className="text-xs font-bold text-[#00078b]">Rules in force</p>
                <p className="text-[11px] text-[#00078b]/70 font-medium">
                  {activeRules.length
                    ? activeRules.join(" · ")
                    : "Default rules only — nothing customised yet."}
                </p>
              </div>
            </div>
            <Link
              href="/constraints"
              className="text-[11px] font-bold text-[#00078b] underline underline-offset-2 hover:opacity-80 shrink-0"
            >
              Edit constraints →
            </Link>
          </div>
        </div>

        {flash && (
          <div
            className={`flex items-start space-x-2 text-sm rounded-xl px-4 py-3 mb-4 border font-medium ${
              flash.kind === "ok"
                ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                : "text-amber-700 bg-amber-50 border-amber-200"
            }`}
          >
            {flash.kind === "ok" ? <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5 text-emerald-600" /> : <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-600" />}
            <span className="whitespace-pre-wrap">{flash.text}</span>
          </div>
        )}

        {/* grid */}
        {grid ? (
          <div className="bg-white border border-[#00078b]/15 rounded-2xl overflow-x-auto shadow-sm">
            <div className="flex items-center justify-between px-5 pt-4">
              <h2 className="text-sm font-bold text-[#00078b]">
                {grid.section} <span className="text-[#00078b]/60 font-medium">· version {grid.version}</span>
              </h2>
              <div className="flex items-center space-x-3 text-[10px] text-[#00078b]/70 font-semibold">
                <span className="flex items-center space-x-1"><FlaskConical className="h-3.5 w-3.5" /><span>lab block</span></span>
                <span className="flex items-center space-x-1"><Layers className="h-3.5 w-3.5" /><span>open elective</span></span>
              </div>
            </div>
            <table className="w-full mt-3">
              <thead>
                <tr className="border-b border-[#00078b]/15 bg-[#f6f6f6]">
                  <th className="text-left text-[10px] text-[#00078b] uppercase tracking-wider font-bold px-4 py-3 w-28">Period</th>
                  {grid.days.map((d) => (
                    <th key={d} className="text-left text-[10px] text-[#00078b] uppercase tracking-wider font-bold px-3 py-3">{d}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#00078b]/10">
                {periods.map((p) => (
                  <tr key={p}>
                    <td className="px-4 py-2 align-top">
                      <div className="text-sm font-bold text-[#00078b]">P{p}</div>
                      <div className="text-[10px] text-[#00078b]/60 font-semibold">{grid.periods[String(p)]}</div>
                    </td>
                    {grid.days.map((d) => {
                      const cell = grid.cells[`${d}-${p}`];
                      if (!cell) {
                        return (
                          <td key={d} className="px-2 py-2 align-top">
                            <div className="rounded-lg border border-[#00078b]/10 px-2.5 py-4 text-center text-[#00078b]/40 text-[10px] font-medium">
                              free
                            </div>
                          </td>
                        );
                      }
                      if (cell.elective) {
                        // one shared band for the whole semester — list the baskets
                        return (
                          <td key={d} className="px-2 py-2 align-top">
                            <div className="rounded-lg border px-2.5 py-2 bg-violet-50 border-violet-200 text-violet-900">
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-bold font-mono">{cell.elective.group}</span>
                                <Layers className="h-3 w-3 opacity-70" />
                              </div>
                              <div className="text-[10px] font-semibold opacity-90">Open Elective</div>
                              <div className="mt-1 space-y-0.5">
                                {cell.elective.offerings.map((o) => (
                                  <div key={o.subject_code} className="text-[10px] opacity-80 truncate max-w-[150px]">
                                    {o.subject_code} · {o.teacher} · {o.room}
                                  </div>
                                ))}
                              </div>
                            </div>
                          </td>
                        );
                      }
                      return (
                        <td key={d} className="px-2 py-2 align-top">
                          <div className={`rounded-lg border px-2.5 py-2 ${colorFor(cell.subject_code)}`}>
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold font-mono">{cell.subject_code}</span>
                              {cell.is_lab && <FlaskConical className="h-3 w-3 opacity-70" />}
                            </div>
                            <div className="text-[10px] font-semibold opacity-90 truncate max-w-[130px]">{cell.teacher}</div>
                            <div className="text-[10px] opacity-75">{cell.room}</div>
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-5 py-3" />
          </div>
        ) : (
          <div className="bg-white border border-[#00078b]/15 rounded-2xl p-12 text-center shadow-sm">
            <Sparkles className="h-8 w-8 text-[#00078b]/40 mx-auto mb-3" />
            <p className="text-[#00078b] font-semibold text-sm">
              {noTimetable
                ? "No timetable generated yet."
                : "Select a section to view its timetable."}
            </p>
            {noTimetable && user?.role === "admin" && (
              <p className="text-[#00078b]/70 text-xs mt-2 font-medium">
                Make sure Data Setup is complete, then click <b>Generate Timetable</b>.
              </p>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
