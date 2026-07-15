"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, ArrowLeftRight, CalendarDays, RefreshCw,
} from "lucide-react";
import { api, getToken } from "../../lib/api";

interface ExchangeRow {
  exchange_id: number;
  section: string;
  leave_date: string; leave_day: string; leave_period: number; leave_time: string; leave_room: string;
  partner: string; partner_subject: string;
  absent: string; missed_subject: string;
  recovery_date: string | null; recovery_day: string; recovery_period: number; recovery_time: string; recovery_room: string;
}
interface ExchangeBoard { from: string; to: string; exchanges: ExchangeRow[]; }

interface Swap {
  role: "exchanged_in" | "recovery";
  with: string; their_subject: string;
  counterpart_date: string | null; counterpart_period: number; counterpart_day: string;
}
interface DayEntry {
  period: number; time: string; subject: string; subject_name: string;
  teacher: string; room: string; exchanged: boolean; swap?: Swap;
}
interface EffectiveDay {
  section: string; date: string; day: string | null;
  entries: DayEntry[]; note?: string;
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function ExchangesPage() {
  const router = useRouter();
  const [board, setBoard] = useState<ExchangeBoard | null>(null);
  const [error, setError] = useState("");

  const [section, setSection] = useState("CSE-7B");
  const [date, setDate] = useState(todayISO());
  const [day, setDay] = useState<EffectiveDay | null>(null);
  const [dayLoading, setDayLoading] = useState(false);

  const loadBoard = useCallback(async () => {
    try {
      setBoard(await api<ExchangeBoard>("/timetable/exchanges"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Load failed");
    }
  }, []);

  const loadDay = useCallback(async () => {
    setDayLoading(true);
    setError("");
    try {
      setDay(await api<EffectiveDay>(`/timetable/effective/${encodeURIComponent(section)}?date=${date}`));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Load failed");
      setDay(null);
    } finally {
      setDayLoading(false);
    }
  }, [section, date]);

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    loadBoard();
  }, [router, loadBoard]);

  return (
    <div className="min-h-screen p-6 relative overflow-x-hidden">
      <div className="absolute top-0 right-1/3 w-[500px] h-[300px] bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="max-w-4xl mx-auto relative">
        <div className="flex items-center space-x-4 mb-6">
          <Link href="/" className="glass-card rounded-xl p-2.5 text-slate-400 hover:text-slate-200"><ArrowLeft className="h-5 w-5" /></Link>
          <div className="flex items-center space-x-3">
            <div className="bg-indigo-500/10 p-2 rounded-xl border border-indigo-500/20 text-indigo-400">
              <ArrowLeftRight className="h-5 w-5" />
            </div>
            <div>
              <h1 className="font-bold text-xl text-slate-100">Period Exchanges</h1>
              <p className="text-xs text-slate-400">
                Confirmed swaps overlaid on the timetable by date. The original timetable is never changed.
              </p>
            </div>
          </div>
        </div>

        {error && (
          <div className="text-amber-400 text-sm bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3 mb-4">{error}</div>
        )}

        {/* --- Exchange board --- */}
        <div className="glass-panel rounded-2xl p-5 mb-6">
          <div className="flex items-center space-x-2 mb-3">
            <ArrowLeftRight className="h-4 w-4 text-indigo-400" />
            <h2 className="text-sm font-semibold text-slate-100">Upcoming exchanges</h2>
            {board && <span className="text-xs text-slate-500">{board.from} → {board.to}</span>}
          </div>

          {board && board.exchanges.length === 0 && (
            <p className="text-slate-400 text-sm py-6 text-center">No confirmed exchanges in this window.</p>
          )}

          {board && board.exchanges.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b border-slate-800">
                  <tr>
                    {["Leave date", "Class", "Lesson taught", "In place of", "Recovery"].map((h) => (
                      <th key={h} className="text-left text-[10px] text-slate-400 uppercase tracking-wider font-semibold px-3 py-2 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {board.exchanges.map((x) => (
                    <tr key={x.exchange_id}>
                      <td className="px-3 py-2.5 text-sm whitespace-nowrap">
                        <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">exchanged in</span>
                        <div className="text-slate-300 mt-1">{x.leave_date}</div>
                        <div className="text-[10px] text-slate-500">{x.leave_day} P{x.leave_period} · {x.leave_room}</div>
                      </td>
                      <td className="px-3 py-2.5 text-sm text-slate-300">{x.section}</td>
                      <td className="px-3 py-2.5 text-sm">
                        <span className="text-emerald-300 font-medium">{x.partner}</span>
                        <div className="text-[10px] text-slate-500 font-mono">{x.partner_subject}</div>
                      </td>
                      <td className="px-3 py-2.5 text-sm">
                        <span className="text-slate-400">{x.absent}</span>
                        <div className="text-[10px] text-slate-500 font-mono">{x.missed_subject}</div>
                      </td>
                      <td className="px-3 py-2.5 text-sm whitespace-nowrap">
                        <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">recovery</span>
                        <div className="text-slate-300 mt-1">{x.recovery_date}</div>
                        <div className="text-[10px] text-slate-500">{x.recovery_day} P{x.recovery_period} · taught by {x.absent}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* --- Effective day grid --- */}
        <div className="glass-panel rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
            <div className="flex items-center space-x-2">
              <CalendarDays className="h-4 w-4 text-indigo-400" />
              <h2 className="text-sm font-semibold text-slate-100">Effective day view</h2>
            </div>
            <div className="flex items-center space-x-2">
              <input
                value={section} onChange={(e) => setSection(e.target.value)}
                placeholder="Section e.g. CSE-7B"
                className="bg-slate-900/60 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 w-36"
              />
              <input
                type="date" value={date} onChange={(e) => setDate(e.target.value)}
                className="bg-slate-900/60 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200"
              />
              <button onClick={loadDay} disabled={dayLoading}
                className="flex items-center space-x-1.5 bg-indigo-600/80 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-xl px-4 py-2">
                {dayLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <CalendarDays className="h-4 w-4" />}
                <span>View</span>
              </button>
            </div>
          </div>

          {!day && <p className="text-slate-400 text-sm py-6 text-center">Pick a section and date, then click View.</p>}
          {day?.note && <p className="text-slate-400 text-sm py-6 text-center">{day.note}</p>}

          {day && !day.note && (
            <>
              <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                <p className="text-xs text-slate-400">{day.section} · {day.day} {day.date}</p>
                <div className="flex items-center space-x-1.5 text-[10px] text-slate-500">
                  <span className="inline-block w-3 h-3 rounded-sm bg-amber-500/20 border border-amber-500/40" />
                  <span>exchanged period</span>
                </div>
              </div>
              {day.entries.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-6">No periods scheduled for this day.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="border-b border-slate-800">
                      <tr>
                        {["Period", "Subject", "Teacher", "Room", "Exchange"].map((h) => (
                          <th key={h} className="text-left text-[10px] text-slate-400 uppercase tracking-wider font-semibold px-3 py-2 whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {day.entries.map((e) => (
                        <tr key={e.period} className={e.exchanged ? "bg-amber-500/[0.07]" : ""}>
                          <td className="px-3 py-2.5 whitespace-nowrap align-top">
                            <div className="text-sm font-semibold text-slate-300">P{e.period}</div>
                            <div className="text-[10px] text-slate-500">{e.time}</div>
                          </td>
                          <td className="px-3 py-2.5 align-top">
                            <div className="flex items-center space-x-1.5">
                              <span className="font-mono text-indigo-300 font-bold text-sm">{e.subject}</span>
                              {e.exchanged && <ArrowLeftRight className="h-3 w-3 text-amber-400" />}
                            </div>
                            <div className="text-[11px] text-slate-400">{e.subject_name}</div>
                          </td>
                          <td className="px-3 py-2.5 text-sm text-slate-300 align-top whitespace-nowrap">{e.teacher}</td>
                          <td className="px-3 py-2.5 text-sm text-slate-400 align-top whitespace-nowrap">{e.room}</td>
                          <td className="px-3 py-2.5 align-top max-w-[280px]">
                            {e.exchanged && e.swap ? (
                              <span className="text-[10px] text-amber-400/90 leading-relaxed">
                                {e.swap.role === "exchanged_in"
                                  ? `⇄ covers for ${e.swap.with} — their ${e.swap.their_subject} recovered ${e.swap.counterpart_day} P${e.swap.counterpart_period}${e.swap.counterpart_date ? ` (${e.swap.counterpart_date})` : ""}`
                                  : `⇄ recovery of ${e.teacher}'s lesson swapped with ${e.swap.with} (${e.swap.their_subject}, ${e.swap.counterpart_day} P${e.swap.counterpart_period}${e.swap.counterpart_date ? `, ${e.swap.counterpart_date}` : ""})`}
                              </span>
                            ) : (
                              <span className="text-slate-600 text-xs">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
