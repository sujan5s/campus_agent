"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  CalendarDays,
  Sparkles,
  Play,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  FlaskConical,
  SlidersHorizontal,
  ChevronDown,
  FileDown,
} from "lucide-react";
import { api, getToken, getUser, AuthUser } from "../../lib/api";
import AppLayout from "../../components/AppLayout";

const WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI"] as const;

interface ScopeRules {
  halfDays: Record<string, boolean>;
  halfDayLast: Record<string, number>;
  noConsecutive: boolean | null; // null = inherit global (sections only)
}

interface Cell {
  subject_code: string;
  subject_name: string;
  teacher: string;
  room: string;
  is_lab: boolean;
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
  load_gap?: number;
  wall_time_s?: number;
  reasons?: string[];
  config?: SolveConfig;
}
interface SectionRuleCfg {
  half_days?: Record<string, number>;
  no_same_subject_consecutive?: boolean | null;
}
interface SolveConfig {
  half_days?: Record<string, number>;
  no_same_subject_consecutive?: boolean;
  max_consecutive_teaching?: number | null;
  section_rules?: Record<string, SectionRuleCfg>;
}

function halfDayStr(hd?: Record<string, number>): string {
  const e = hd && Object.entries(hd);
  return e && e.length ? e.map(([d, p]) => `${d}≤P${p}`).join(",") : "";
}

function configSummary(c?: SolveConfig): string {
  if (!c) return "";
  const parts: string[] = [];
  const hd = halfDayStr(c.half_days);
  if (hd) parts.push("half days: " + hd);
  if (c.no_same_subject_consecutive) parts.push("no back-to-back subjects");
  if (c.max_consecutive_teaching) parts.push(`≤${c.max_consecutive_teaching} consecutive/teacher`);
  for (const [name, sr] of Object.entries(c.section_rules ?? {})) {
    const bits: string[] = [];
    const shd = halfDayStr(sr.half_days);
    if (shd) bits.push(shd);
    if (sr.no_same_subject_consecutive === true) bits.push("no back-to-back");
    if (sr.no_same_subject_consecutive === false) bits.push("back-to-back allowed");
    if (bits.length) parts.push(`${name}: ${bits.join(" ")}`);
  }
  return parts.length ? parts.join(" · ") : "default rules";
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

  // --- generation constraints (Phase 2.2 + per-class scoping in 2.3) ---
  // scope "*" = global default; other keys are section names.
  // noConsecutive: true/false, or null = inherit global (only for sections).
  const [showOpts, setShowOpts] = useState(false);
  const [scope, setScope] = useState<string>("*");
  const [rulesByScope, setRulesByScope] = useState<Record<string, ScopeRules>>({
    "*": { halfDays: {}, halfDayLast: {}, noConsecutive: true },
  });
  const [maxConsecutive, setMaxConsecutive] = useState<string>("");

  const cur: ScopeRules = rulesByScope[scope] ?? { halfDays: {}, halfDayLast: {}, noConsecutive: scope === "*" ? true : null };
  const patchScope = (patch: Partial<ScopeRules>) =>
    setRulesByScope((r) => ({ ...r, [scope]: { ...cur, ...patch } }));
  const scopeHasOverride = (s: string): boolean => {
    const r = rulesByScope[s];
    if (!r) return false;
    const anyHalf = WEEKDAYS.some((d) => r.halfDays[d] && r.halfDayLast[d]);
    return anyHalf || (s !== "*" && r.noConsecutive !== null);
  };

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
      } catch (e: unknown) {
        setFlash({ kind: "err", text: e instanceof Error ? e.message : "Load failed" });
      }
    })();
  }, [router, loadGrid]);

  const generate = async () => {
    setGenerating(true);
    setFlash(null);
    try {
      const halfDaysOf = (r: ScopeRules) =>
        WEEKDAYS.filter((d) => r.halfDays[d] && r.halfDayLast[d])
          .map((d) => ({ day: d, last_period: r.halfDayLast[d] }));
      const g = rulesByScope["*"] ?? { halfDays: {}, halfDayLast: {}, noConsecutive: true };
      const sectionRules = Object.entries(rulesByScope)
        .filter(([s]) => s !== "*" && scopeHasOverride(s))
        .map(([section, r]) => ({
          section,
          half_days: halfDaysOf(r),
          no_same_subject_consecutive: r.noConsecutive, // null = inherit
        }));
      const body = {
        half_days: halfDaysOf(g),
        no_same_subject_consecutive: g.noConsecutive ?? true,
        max_consecutive_teaching: maxConsecutive ? Number(maxConsecutive) : null,
        sections: sectionRules,
      };
      const r = await api<GenerateResult>("/timetable/generate", {
        method: "POST",
        body: JSON.stringify(body),
      });
      const summary = configSummary(r.config);
      setFlash({
        kind: "ok",
        text: `Generated v${r.version}: ${r.lessons} lessons, load gap ${r.load_gap}, solved in ${r.wall_time_s}s (provably clash-free).`
          + (summary ? `\nConstraints — ${summary}.` : ""),
      });
      if (selected) await loadGrid(selected);
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

      // best-effort: which constraints produced this version (shown under the title)
      let constraints = "";
      try {
        const st = await api<{ latest_version: number | null; config?: SolveConfig }>("/timetable/status");
        constraints = configSummary(st.config);
      } catch { /* status is optional for the PDF */ }

      const ps = grid.periods;
      const periodNos = Object.keys(ps).map(Number).sort((a, b) => a - b);
      const rows = periodNos.map((p) => [
        `P${p}\n${ps[String(p)]}`,
        ...grid.days.map((d) => {
          const c = grid.cells[`${d}-${p}`];
          return c ? `${c.subject_code}${c.is_lab ? " (lab)" : ""}\n${c.teacher}\n${c.room}` : "—";
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
      if (constraints && constraints !== "default rules") {
        doc.text(`Constraints: ${constraints}`, margin, 76);
        startY = 90;
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
            {user?.role === "admin" && (
              <button
                onClick={() => setShowOpts((v) => !v)}
                className={`flex items-center space-x-2 bg-white border border-[#00078b]/20 rounded-xl px-4 py-2.5 text-sm font-bold transition-colors shadow-sm ${
                  showOpts ? "text-[#00078b] border-[#00078b]" : "text-[#00078b] hover:bg-[#f6f6f6]"
                }`}
                title="Generation constraints"
              >
                <SlidersHorizontal className="h-4 w-4" />
                <span>Constraints</span>
                <ChevronDown className={`h-3.5 w-3.5 transition-transform ${showOpts ? "rotate-180" : ""}`} />
              </button>
            )}
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

        {user?.role === "admin" && showOpts && (
          <div className="bg-white border border-[#00078b]/15 rounded-2xl p-5 mb-4 shadow-sm">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <div className="flex items-center space-x-2">
                <SlidersHorizontal className="h-4 w-4 text-[#00078b]" />
                <h2 className="text-sm font-bold text-[#00078b]">Generation constraints</h2>
                <span className="text-[11px] text-[#00078b]/60 font-medium">applied on the next Generate · all optional</span>
              </div>
              {/* scope selector: global default vs a specific class */}
              <div className="flex items-center space-x-2">
                <span className="text-[11px] text-[#00078b]/60 font-bold">Rules for</span>
                <select
                  value={scope}
                  onChange={(e) => setScope(e.target.value)}
                  className="bg-[#f6f6f6] border border-[#00078b]/20 text-[#00078b] rounded-lg px-3 py-1.5 text-xs font-bold"
                >
                  <option value="*">All classes (default)</option>
                  {sections.map((s) => (
                    <option key={s.id} value={s.name}>
                      {s.name}{scopeHasOverride(s.name) ? " ●" : ""}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <p className="text-[11px] text-[#00078b]/70 mb-3 font-medium">
              {scope === "*"
                ? "Defaults for every class. Override a specific class by picking it above."
                : `Overrides for ${scope} only — leave a control untouched to inherit the default.`}
            </p>

            {/* Half days */}
            <div className="mb-5">
              <p className="text-xs font-bold text-[#00078b] mb-2">Half days</p>
              <p className="text-[11px] text-[#00078b]/70 mb-3 font-medium">Tick a day and set the last teaching period; later periods are dropped that day.</p>
              <div className="flex flex-wrap gap-2">
                {WEEKDAYS.map((d) => (
                  <div
                    key={d}
                    className={`flex items-center space-x-2 rounded-xl border px-3 py-2 ${
                      cur.halfDays[d] ? "border-[#00078b] bg-[#00078b]/10" : "border-[#00078b]/20 bg-[#f6f6f6]"
                    }`}
                  >
                    <label className="flex items-center space-x-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={!!cur.halfDays[d]}
                        onChange={(e) =>
                          patchScope({
                            halfDays: { ...cur.halfDays, [d]: e.target.checked },
                            halfDayLast: e.target.checked && !cur.halfDayLast[d]
                              ? { ...cur.halfDayLast, [d]: 4 } : cur.halfDayLast,
                          })
                        }
                        className="accent-[#00078b]"
                      />
                      <span className="text-xs font-bold text-[#00078b]">{d}</span>
                    </label>
                    <span className="text-[10px] text-[#00078b]/60 font-semibold">ends P</span>
                    <input
                      type="number"
                      min={1}
                      disabled={!cur.halfDays[d]}
                      value={cur.halfDayLast[d] ?? ""}
                      onChange={(e) => patchScope({ halfDayLast: { ...cur.halfDayLast, [d]: Number(e.target.value) } })}
                      className="w-14 bg-white border border-[#00078b]/20 rounded-lg px-2 py-1 text-xs text-[#00078b] font-bold disabled:opacity-40"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Same-subject back-to-back */}
            <div className="flex flex-wrap items-center gap-6">
              {scope === "*" ? (
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={cur.noConsecutive === true}
                    onChange={(e) => patchScope({ noConsecutive: e.target.checked })}
                    className="accent-[#00078b]"
                  />
                  <span className="text-xs font-bold text-[#00078b]">No same-subject back-to-back <span className="text-[#00078b]/60 font-normal">(theory only)</span></span>
                </label>
              ) : (
                <label className="flex items-center space-x-2">
                  <span className="text-xs font-bold text-[#00078b]">Same-subject back-to-back</span>
                  <select
                    value={cur.noConsecutive === null ? "inherit" : cur.noConsecutive ? "no" : "yes"}
                    onChange={(e) =>
                      patchScope({ noConsecutive: e.target.value === "inherit" ? null : e.target.value === "no" })
                    }
                    className="bg-[#f6f6f6] border border-[#00078b]/20 text-[#00078b] rounded-lg px-2 py-1 text-xs font-bold"
                  >
                    <option value="inherit">Inherit default</option>
                    <option value="no">Not allowed</option>
                    <option value="yes">Allowed</option>
                  </select>
                </label>
              )}

              {scope === "*" && (
                <label className="flex items-center space-x-2">
                  <span className="text-xs font-bold text-[#00078b]">Max consecutive teaching periods / teacher</span>
                  <input
                    type="number"
                    min={1}
                    placeholder="off"
                    value={maxConsecutive}
                    onChange={(e) => setMaxConsecutive(e.target.value)}
                    className="w-16 bg-[#f6f6f6] border border-[#00078b]/20 rounded-lg px-2 py-1 text-xs text-[#00078b] font-bold"
                  />
                </label>
              )}
            </div>
          </div>
        )}

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
              <div className="flex items-center space-x-2 text-[10px] text-[#00078b]/70 font-semibold">
                <FlaskConical className="h-3.5 w-3.5" /><span>lab block</span>
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
                      return (
                        <td key={d} className="px-2 py-2 align-top">
                          {cell ? (
                            <div className={`rounded-lg border px-2.5 py-2 ${colorFor(cell.subject_code)}`}>
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-bold font-mono">{cell.subject_code}</span>
                                {cell.is_lab && <FlaskConical className="h-3 w-3 opacity-70" />}
                              </div>
                              <div className="text-[10px] font-semibold opacity-90 truncate max-w-[130px]">{cell.teacher}</div>
                              <div className="text-[10px] opacity-75">{cell.room}</div>
                            </div>
                          ) : (
                            <div className="rounded-lg border border-[#00078b]/10 px-2.5 py-4 text-center text-[#00078b]/40 text-[10px] font-medium">
                              free
                            </div>
                          )}
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
