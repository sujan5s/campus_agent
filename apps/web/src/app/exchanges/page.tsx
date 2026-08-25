"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, ArrowLeftRight, CalendarDays, RefreshCw,
} from "lucide-react";
import { api, getToken } from "../../lib/api";
import AppLayout from "../../components/AppLayout";

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
    <AppLayout title="Period Exchanges" subtitle="Confirmed swaps and effective daily schedule view.">
      <div className="max-w-4xl mx-auto relative">
        <div className="flex items-center space-x-3 mb-6">
          <div className="bg-[#00078b] p-2 rounded-xl text-[#fdb813] shadow-md">
            <ArrowLeftRight className="h-5 w-5" />
          </div>
          <div>
            <h1 className="font-bold text-xl text-[#00078b]">Period Exchanges</h1>
            <p className="text-xs text-[#00078b]/70 font-medium">
              Confirmed swaps overlaid on the timetable by date.
            </p>
          </div>
        </div>

        {error && (
          <div className="text-amber-700 font-medium text-sm bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-4">{error}</div>
        )}

        {/* --- Exchange board --- */}
        <div className="bg-white border border-[#00078b]/15 rounded-2xl p-5 mb-6 shadow-sm">
          <div className="flex items-center space-x-2 mb-3">
            <ArrowLeftRight className="h-4 w-4 text-[#00078b]" />
            <h2 className="text-sm font-bold text-[#00078b]">Upcoming exchanges</h2>
            {board && <span className="text-xs text-[#00078b]/60 font-semibold">{board.from} → {board.to}</span>}
          </div>

          {board && board.exchanges.length === 0 && (
            <p className="text-[#00078b]/60 font-medium text-sm py-6 text-center">No confirmed exchanges in this window.</p>
          )}

          {board && board.exchanges.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b border-[#00078b]/15 bg-[#f6f6f6]">
                  <tr>
                    {["Leave date", "Class", "Lesson taught", "In place of", "Recovery"].map((h) => (
                      <th key={h} className="text-left text-[10px] text-[#00078b] uppercase tracking-wider font-bold px-3 py-2 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#00078b]/10">
                  {board.exchanges.map((x) => (
                    <tr key={x.exchange_id} className="hover:bg-[#f6f6f6]/60 transition">
                      <td className="px-3 py-2.5 text-sm whitespace-nowrap">
                        <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded bg-[#fdb813] text-[#00078b]">exchanged in</span>
                        <div className="text-[#00078b] font-bold mt-1">{x.leave_date}</div>
                        <div className="text-[10px] text-[#00078b]/60 font-medium">{x.leave_day} P{x.leave_period} · {x.leave_room}</div>
                      </td>
                      <td className="px-3 py-2.5 text-sm text-[#00078b] font-bold">{x.section}</td>
                      <td className="px-3 py-2.5 text-sm">
                        <span className="text-emerald-700 font-bold">{x.partner}</span>
                        <div className="text-[10px] text-[#00078b]/60 font-mono font-medium">{x.partner_subject}</div>
                      </td>
                      <td className="px-3 py-2.5 text-sm">
                        <span className="text-[#00078b]/80 font-medium">{x.absent}</span>
                        <div className="text-[10px] text-[#00078b]/60 font-mono font-medium">{x.missed_subject}</div>
                      </td>
                      <td className="px-3 py-2.5 text-sm whitespace-nowrap">
                        <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300">recovery</span>
                        <div className="text-[#00078b] font-bold mt-1">{x.recovery_date}</div>
                        <div className="text-[10px] text-[#00078b]/60 font-medium">{x.recovery_day} P{x.recovery_period} · taught by {x.absent}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* --- Effective day grid --- */}
        <div className="bg-white border border-[#00078b]/15 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
            <div className="flex items-center space-x-2">
              <CalendarDays className="h-4 w-4 text-[#00078b]" />
              <h2 className="text-sm font-bold text-[#00078b]">Effective day view</h2>
            </div>
            <div className="flex items-center space-x-2">
              <input
                value={section} onChange={(e) => setSection(e.target.value)}
                placeholder="Section e.g. CSE-7B"
                className="bg-[#f6f6f6] border border-[#00078b]/20 rounded-xl px-3 py-2 text-sm text-[#00078b] font-medium w-36 outline-none focus:border-[#00078b]"
              />
              <input
                type="date" value={date} onChange={(e) => setDate(e.target.value)}
                className="bg-[#f6f6f6] border border-[#00078b]/20 rounded-xl px-3 py-2 text-sm text-[#00078b] font-medium outline-none focus:border-[#00078b]"
              />
              <button onClick={loadDay} disabled={dayLoading}
                className="flex items-center space-x-1.5 bg-[#00078b] hover:bg-[#000566] disabled:opacity-50 text-white text-sm font-bold rounded-xl px-4 py-2 shadow-md">
                {dayLoading ? <RefreshCw className="h-4 w-4 animate-spin text-[#fdb813]" /> : <CalendarDays className="h-4 w-4 text-[#fdb813]" />}
                <span>View</span>
              </button>
            </div>
          </div>

          {!day && <p className="text-[#00078b]/60 font-medium text-sm py-6 text-center">Pick a section and date, then click View.</p>}
          {day?.note && <p className="text-[#00078b]/60 font-medium text-sm py-6 text-center">{day.note}</p>}

          {day && !day.note && (
            <>
              <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                <p className="text-xs text-[#00078b]/70 font-semibold">{day.section} · {day.day} {day.date}</p>
                <div className="flex items-center space-x-1.5 text-[10px] text-[#00078b]/70 font-bold">
                  <span className="inline-block w-3 h-3 rounded-sm bg-[#fdb813]" />
                  <span>exchanged period</span>
                </div>
              </div>
              {day.entries.length === 0 ? (
                <p className="text-[#00078b]/60 font-medium text-sm text-center py-6">No periods scheduled for this day.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="border-b border-[#00078b]/15 bg-[#f6f6f6]">
                      <tr>
                        {["Period", "Subject", "Teacher", "Room", "Exchange"].map((h) => (
                          <th key={h} className="text-left text-[10px] text-[#00078b] uppercase tracking-wider font-bold px-3 py-2 whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#00078b]/10">
                      {day.entries.map((e) => (
                        <tr key={e.period} className={e.exchanged ? "bg-amber-50" : "hover:bg-[#f6f6f6]/60 transition"}>
                          <td className="px-3 py-2.5 whitespace-nowrap align-top">
                            <div className="text-sm font-bold text-[#00078b]">P{e.period}</div>
                            <div className="text-[10px] text-[#00078b]/60 font-medium">{e.time}</div>
                          </td>
                          <td className="px-3 py-2.5 align-top">
                            <div className="flex items-center space-x-1.5">
                              <span className="font-mono text-[#00078b] font-bold text-sm">{e.subject}</span>
                              {e.exchanged && <ArrowLeftRight className="h-3 w-3 text-[#00078b]" />}
                            </div>
                            <div className="text-[11px] text-[#00078b]/70 font-medium">{e.subject_name}</div>
                          </td>
                          <td className="px-3 py-2.5 text-sm text-[#00078b] font-semibold align-top whitespace-nowrap">{e.teacher}</td>
                          <td className="px-3 py-2.5 text-sm text-[#00078b]/70 font-medium align-top whitespace-nowrap">{e.room}</td>
                          <td className="px-3 py-2.5 align-top max-w-[280px]">
                            {e.exchanged && e.swap ? (
                              <span className="text-[10px] text-amber-900 font-semibold leading-relaxed">
                                {e.swap.role === "exchanged_in"
                                  ? `⇄ covers for ${e.swap.with} — their ${e.swap.their_subject} recovered ${e.swap.counterpart_day} P${e.swap.counterpart_period}${e.swap.counterpart_date ? ` (${e.swap.counterpart_date})` : ""}`
                                  : `⇄ recovery of ${e.teacher}'s lesson swapped with ${e.swap.with} (${e.swap.their_subject}, ${e.swap.counterpart_day} P${e.swap.counterpart_period}${e.swap.counterpart_date ? `, ${e.swap.counterpart_date}` : ""})`}
                              </span>
                            ) : (
                              <span className="text-[#00078b]/40 text-xs">—</span>
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
    </AppLayout>
  );
}
