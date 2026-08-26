"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Building2, CalendarDays, CheckCircle2, Bot, RefreshCw, Users,
  AlertTriangle, Ban, Clock, Sparkles,
} from "lucide-react";
import { api, getToken, getUser } from "../../lib/api";
import AppLayout from "../../components/AppLayout";

interface Venue { id: number; name: string; type: string; capacity: number }
interface Conflict { kind: string; what: string; who: string; window: string; detail: string }
interface Verdict {
  room: string; type: string; capacity: number; window: string;
  conflicts: Conflict[]; capacity_ok: boolean; capacity_note: string | null; available: boolean;
}
interface Alternative { room_id: number; room: string; type: string; capacity: number; why: string }
interface ChainStage {
  approval_id: number; kind: string; label: string; status: string;
  approver: string | null; decided_at: string | null;
}
interface BookingSummary {
  booking_id: number; title: string; description: string; category: string;
  headcount: number; organizer: string; organizer_role: string;
  venue: string; venue_type: string; capacity: number;
  date: string; window: string; status: string; purpose: string; rationale: string;
  created_at: string | null; chain: ChainStage[];
}
interface RequestResult {
  status: string; stage?: string; stage_index?: number; stages?: number;
  booking?: BookingSummary; alternatives?: Alternative[]; steps?: string[]; response?: string;
}
interface CalEvent {
  booking_id: number; title: string; category: string; headcount: number;
  organizer: string; venue: string; venue_type: string;
  date: string; start: string; end: string; window: string; status: string;
}

const CATEGORIES = ["fest", "workshop", "seminar", "sports", "meeting", "event"];

const STATUS_STYLE: Record<string, string> = {
  approved: "bg-emerald-100 text-emerald-800 border-emerald-200",
  pending: "bg-amber-100 text-amber-800 border-amber-200",
  rejected: "bg-rose-100 text-rose-700 border-rose-200",
  cancelled: "bg-slate-100 text-slate-600 border-slate-200",
};

function todayISO(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

/** Monday of the week containing `iso`. */
function weekStart(iso: string): Date {
  const d = new Date(`${iso}T00:00:00`);
  const shift = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - shift);
  return d;
}

function isoOf(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function BookingsPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"request" | "calendar">("request");
  const [venues, setVenues] = useState<Venue[]>([]);
  const [error, setError] = useState("");

  // --- request form -----------------------------------------------------------
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("event");
  const [date, setDate] = useState(todayISO(2));
  const [start, setStart] = useState("14:00");
  const [end, setEnd] = useState("17:00");
  const [headcount, setHeadcount] = useState(60);
  const [roomId, setRoomId] = useState<number | "">("");
  const [description, setDescription] = useState("");

  const [probe, setProbe] = useState<{ requested: Verdict | null; alternatives: Alternative[] } | null>(null);
  const [probing, setProbing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<RequestResult | null>(null);

  // --- lists ------------------------------------------------------------------
  const [mine, setMine] = useState<BookingSummary[]>([]);
  const [events, setEvents] = useState<CalEvent[]>([]);
  const [calFrom, setCalFrom] = useState(isoOf(weekStart(todayISO())));
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  const loadMine = useCallback(async () => {
    try {
      setMine(await api<BookingSummary[]>("/bookings"));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load your bookings");
    }
  }, []);

  const loadCalendar = useCallback(async (from: string) => {
    const to = isoOf(new Date(new Date(`${from}T00:00:00`).getTime() + 27 * 864e5));
    try {
      const r = await api<{ events: CalEvent[] }>(`/bookings/calendar?from=${from}&to=${to}`);
      setEvents(r.events);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load the calendar");
    }
  }, []);

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    api<Venue[]>("/bookings/venues").then(setVenues).catch(() => setVenues([]));
    loadMine();
    loadCalendar(calFrom);
  }, [router, loadMine, loadCalendar, calFrom]);

  // Live availability probe — the whole point of the form is that you find out
  // BEFORE you submit that a class already owns the room.
  useEffect(() => {
    if (!date || !start || !end || end <= start) { setProbe(null); return; }
    let cancelled = false;
    setProbing(true);
    const t = setTimeout(async () => {
      try {
        const q = new URLSearchParams({ date, start, end, headcount: String(headcount || 0) });
        if (roomId !== "") q.set("room_id", String(roomId));
        const r = await api<{ requested: Verdict | null; alternatives: Alternative[] }>(
          `/bookings/availability?${q.toString()}`);
        if (!cancelled) setProbe(r);
      } catch {
        if (!cancelled) setProbe(null);
      } finally {
        if (!cancelled) setProbing(false);
      }
    }, 350);
    return () => { cancelled = true; clearTimeout(t); };
  }, [date, start, end, headcount, roomId]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    setResult(null);
    try {
      const body: Record<string, unknown> = {
        title, date, start, end, headcount: Number(headcount) || 0,
        description, category,
      };
      if (roomId !== "") body.room_id = Number(roomId);
      const r = await api<RequestResult>("/bookings", { method: "POST", body: JSON.stringify(body) });
      setResult(r);
      setTitle("");
      setDescription("");
      await loadMine();
      await loadCalendar(calFrom);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setSubmitting(false);
    }
  };

  const cancel = async (id: number) => {
    try {
      await api(`/bookings/${id}/cancel`, { method: "POST" });
      await loadMine();
      await loadCalendar(calFrom);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    }
  };

  const weeks = useMemo(() => {
    const first = new Date(`${calFrom}T00:00:00`);
    return Array.from({ length: 4 }, (_, w) =>
      Array.from({ length: 7 }, (_, d) => {
        const day = new Date(first.getTime() + (w * 7 + d) * 864e5);
        return isoOf(day);
      }));
  }, [calFrom]);

  const byDate = useMemo(() => {
    const m: Record<string, CalEvent[]> = {};
    for (const ev of events) (m[ev.date] ||= []).push(ev);
    return m;
  }, [events]);

  const user = getUser();

  return (
    <AppLayout
      title="Event & Venue Booking"
      subtitle="Conflict-checked against live bookings and the class timetable."
    >
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center space-x-3 mb-6">
          <div className="bg-[#00078b] p-2 rounded-xl text-[#fdb813] shadow-md">
            <Building2 className="h-5 w-5" />
          </div>
          <div className="flex-1">
            <h1 className="font-bold text-xl text-[#00078b]">Venue Bookings</h1>
            <p className="text-xs text-[#00078b]/70 font-medium">
              The Booking Agent checks other reservations <em>and</em> scheduled classes,
              then routes your request through the approval chain.
            </p>
          </div>
          <div className="flex bg-white border border-[#00078b]/15 rounded-xl p-1 shadow-sm">
            {(["request", "calendar"] as const).map((t) => (
              <button key={t} type="button" onClick={() => setTab(t)}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition ${
                  tab === t ? "bg-[#00078b] text-white shadow-sm" : "text-[#00078b]/70 hover:text-[#00078b]"}`}>
                {t === "request" ? "Request" : "Calendar"}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="text-rose-700 font-medium text-sm bg-rose-50 border border-rose-200 rounded-xl px-4 py-3 mb-4">
            {error}
          </div>
        )}

        {tab === "request" && (
          <>
            <form onSubmit={submit} className="bg-white border border-[#00078b]/15 rounded-2xl p-5 mb-5 shadow-sm">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-[10px] uppercase tracking-wider font-bold text-[#00078b]/70 mb-1">Event title</label>
                  <input required value={title} onChange={(e) => setTitle(e.target.value)}
                    placeholder="Coding Club Hackathon"
                    className="w-full border border-[#00078b]/20 rounded-xl px-3 py-2 text-sm text-[#00078b] font-medium focus:outline-none focus:ring-2 focus:ring-[#fdb813]" />
                </div>
                <div>
                  <label className="block text-[10px] uppercase tracking-wider font-bold text-[#00078b]/70 mb-1">Category</label>
                  <select value={category} onChange={(e) => setCategory(e.target.value)}
                    className="w-full border border-[#00078b]/20 rounded-xl px-3 py-2 text-sm text-[#00078b] font-medium bg-white">
                    {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>

                <div>
                  <label className="block text-[10px] uppercase tracking-wider font-bold text-[#00078b]/70 mb-1">Date</label>
                  <input type="date" required value={date} min={todayISO()} onChange={(e) => setDate(e.target.value)}
                    className="w-full border border-[#00078b]/20 rounded-xl px-3 py-2 text-sm text-[#00078b] font-medium" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] uppercase tracking-wider font-bold text-[#00078b]/70 mb-1">From</label>
                    <input type="time" required value={start} onChange={(e) => setStart(e.target.value)}
                      className="w-full border border-[#00078b]/20 rounded-xl px-3 py-2 text-sm text-[#00078b] font-medium" />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase tracking-wider font-bold text-[#00078b]/70 mb-1">To</label>
                    <input type="time" required value={end} onChange={(e) => setEnd(e.target.value)}
                      className="w-full border border-[#00078b]/20 rounded-xl px-3 py-2 text-sm text-[#00078b] font-medium" />
                  </div>
                </div>
                <div>
                  <label className="block text-[10px] uppercase tracking-wider font-bold text-[#00078b]/70 mb-1">Expected headcount</label>
                  <input type="number" min={0} value={headcount} onChange={(e) => setHeadcount(Number(e.target.value))}
                    className="w-full border border-[#00078b]/20 rounded-xl px-3 py-2 text-sm text-[#00078b] font-medium" />
                </div>

                <div>
                  <label className="block text-[10px] uppercase tracking-wider font-bold text-[#00078b]/70 mb-1">Venue</label>
                  <select value={roomId} onChange={(e) => setRoomId(e.target.value === "" ? "" : Number(e.target.value))}
                    className="w-full border border-[#00078b]/20 rounded-xl px-3 py-2 text-sm text-[#00078b] font-medium bg-white">
                    <option value="">Let the agent choose</option>
                    {venues.map((v) => (
                      <option key={v.id} value={v.id}>{v.name} — {v.type}, {v.capacity}</option>
                    ))}
                  </select>
                </div>
                <div className="md:col-span-2">
                  <label className="block text-[10px] uppercase tracking-wider font-bold text-[#00078b]/70 mb-1">Purpose (optional)</label>
                  <input value={description} onChange={(e) => setDescription(e.target.value)}
                    placeholder="24-hour hackathon finals, judging panel of 6"
                    className="w-full border border-[#00078b]/20 rounded-xl px-3 py-2 text-sm text-[#00078b] font-medium" />
                </div>
              </div>

              {/* live availability strip */}
              <div className="mt-4">
                {probing && (
                  <div className="flex items-center space-x-2 text-xs text-[#00078b]/60 font-semibold">
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" /><span>Checking availability…</span>
                  </div>
                )}
                {!probing && probe?.requested && (
                  probe.requested.available ? (
                    <div className="flex items-center space-x-2 text-sm bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl px-4 py-2.5 font-semibold">
                      <CheckCircle2 className="h-4 w-4" />
                      <span>{probe.requested.room} is free {probe.requested.window} — no class, no other booking.</span>
                    </div>
                  ) : (
                    <div className="bg-rose-50 border border-rose-200 rounded-xl px-4 py-3">
                      <div className="flex items-center space-x-2 text-sm text-rose-800 font-bold mb-1.5">
                        <AlertTriangle className="h-4 w-4" />
                        <span>{probe.requested.room} is not free {probe.requested.window}</span>
                      </div>
                      <ul className="text-xs text-rose-700 font-medium space-y-1">
                        {probe.requested.conflicts.map((c, i) => (
                          <li key={i} className="flex items-start space-x-1.5">
                            <span className="mt-0.5">{c.kind === "class" ? "📚" : "📌"}</span>
                            <span>{c.detail}</span>
                          </li>
                        ))}
                        {probe.requested.capacity_note && (
                          <li className="flex items-start space-x-1.5"><span>👥</span><span>{probe.requested.capacity_note}</span></li>
                        )}
                      </ul>
                      {probe.alternatives.length > 0 && (
                        <div className="mt-2.5 pt-2.5 border-t border-rose-200">
                          <p className="text-[10px] uppercase tracking-wider font-bold text-rose-700/80 mb-1.5">Free instead — click to switch</p>
                          <div className="flex flex-wrap gap-1.5">
                            {probe.alternatives.map((a) => (
                              <button key={a.room_id} type="button" onClick={() => setRoomId(a.room_id)}
                                className="text-xs font-bold bg-white border border-[#00078b]/20 hover:border-[#fdb813] hover:bg-[#fdb813]/10 text-[#00078b] rounded-lg px-2.5 py-1 transition">
                                {a.room} <span className="font-medium text-[#00078b]/60">· {a.capacity}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                )}
                {!probing && probe && !probe.requested && (
                  <div className="bg-[#f6f6f6] border border-[#00078b]/15 rounded-xl px-4 py-3">
                    <p className="text-[10px] uppercase tracking-wider font-bold text-[#00078b]/70 mb-1.5">
                      {probe.alternatives.length} venue(s) free in this window — the agent will pick the tightest fit
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {probe.alternatives.map((a) => (
                        <button key={a.room_id} type="button" onClick={() => setRoomId(a.room_id)}
                          className="text-xs font-bold bg-white border border-[#00078b]/20 hover:border-[#fdb813] text-[#00078b] rounded-lg px-2.5 py-1 transition">
                          {a.room} <span className="font-medium text-[#00078b]/60">· {a.capacity}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <button type="submit" disabled={submitting}
                className="mt-4 flex items-center space-x-2 bg-[#00078b] hover:bg-[#000450] disabled:opacity-50 text-white text-sm font-bold rounded-xl px-5 py-2.5 shadow-sm">
                {submitting ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4 text-[#fdb813]" />}
                <span>{submitting ? "Agent is checking…" : "Send to Booking Agent"}</span>
              </button>
            </form>

            {result && (
              <div className="bg-white border border-[#00078b]/15 rounded-2xl p-5 mb-5 shadow-sm">
                <div className="flex items-center space-x-2 text-[#00078b] text-sm font-bold mb-3">
                  <Bot className="h-4 w-4 text-[#fdb813]" />
                  <span>Booking Agent</span>
                  {result.status === "awaiting_approval" && (
                    <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded bg-[#fdb813] text-[#00078b]">
                      stage {result.stage_index}/{result.stages} · {result.stage}
                    </span>
                  )}
                </div>
                {result.booking ? (
                  <>
                    <p className="text-sm text-[#00078b] font-bold">
                      {result.booking.title} — {result.booking.venue}
                      <span className="font-medium text-[#00078b]/60">
                        {" "}({result.booking.venue_type}, seats {result.booking.capacity})
                      </span>
                    </p>
                    <p className="text-xs text-[#00078b]/70 font-medium mt-0.5">
                      {result.booking.date} · {result.booking.window} · {result.booking.headcount} expected
                    </p>
                    <p className="text-sm text-[#00078b]/80 font-medium mt-2 bg-[#f6f6f6] rounded-xl px-3 py-2">
                      {result.booking.rationale}
                    </p>
                    <div className="flex items-center flex-wrap gap-2 mt-3">
                      {result.booking.chain.map((s) => (
                        <span key={s.approval_id}
                          className={`text-[10px] uppercase tracking-wider font-bold px-2 py-1 rounded border ${STATUS_STYLE[s.status] || STATUS_STYLE.pending}`}>
                          {s.label}: {s.status}{s.approver ? ` · ${s.approver}` : ""}
                        </span>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-[#00078b]/80 font-medium whitespace-pre-wrap">{result.response}</p>
                )}
                {result.steps && result.steps.length > 0 && (
                  <details className="mt-3">
                    <summary className="text-[10px] uppercase tracking-wider font-bold text-[#00078b]/60 cursor-pointer">
                      Workflow trace
                    </summary>
                    <ul className="mt-2 space-y-1">
                      {result.steps.map((s, i) => (
                        <li key={i} className="text-xs text-[#00078b]/70 font-medium font-mono">{s}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            )}

            <div className="bg-white border border-[#00078b]/15 rounded-2xl p-5 shadow-sm">
              <h2 className="text-sm font-bold text-[#00078b] mb-3">
                {user?.role === "admin" ? "All booking requests" : "My requests"}
              </h2>
              {mine.length === 0 ? (
                <p className="text-xs text-[#00078b]/60 font-medium py-6 text-center">No booking requests yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="border-b border-[#00078b]/15 bg-[#f6f6f6]">
                      <tr>
                        {["Event", "Venue", "When", "Approval chain", "Status", ""].map((h) => (
                          <th key={h} className="text-left text-[10px] text-[#00078b] uppercase tracking-wider font-bold px-3 py-2 whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#00078b]/10">
                      {mine.map((b) => (
                        <tr key={b.booking_id} className="hover:bg-[#f6f6f6]/60 transition">
                          <td className="px-3 py-2.5 text-sm">
                            <span className="text-[#00078b] font-bold">{b.title}</span>
                            <div className="text-[10px] text-[#00078b]/60 font-medium">
                              {b.category} · {b.headcount || "—"} people · {b.organizer}
                            </div>
                          </td>
                          <td className="px-3 py-2.5 text-sm text-[#00078b] font-semibold whitespace-nowrap">
                            {b.venue}
                            <div className="text-[10px] text-[#00078b]/60 font-medium">{b.venue_type}</div>
                          </td>
                          <td className="px-3 py-2.5 text-sm text-[#00078b] font-semibold whitespace-nowrap">
                            {b.date}
                            <div className="text-[10px] text-[#00078b]/60 font-medium">{b.window}</div>
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="flex flex-wrap gap-1">
                              {b.chain.map((s) => (
                                <span key={s.approval_id}
                                  className={`text-[9px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded border ${STATUS_STYLE[s.status] || STATUS_STYLE.pending}`}>
                                  {s.label.split(" ")[0]}: {s.status}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded border ${STATUS_STYLE[b.status] || STATUS_STYLE.pending}`}>
                              {b.status}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-right">
                            {(b.status === "pending" || b.status === "approved") && (
                              <button onClick={() => cancel(b.booking_id)}
                                className="flex items-center space-x-1 text-xs font-bold text-rose-600 hover:text-rose-700">
                                <Ban className="h-3.5 w-3.5" /><span>Cancel</span>
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}

        {tab === "calendar" && (
          <div className="bg-white border border-[#00078b]/15 rounded-2xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
              <div className="flex items-center space-x-2">
                <CalendarDays className="h-4 w-4 text-[#00078b]" />
                <h2 className="text-sm font-bold text-[#00078b]">Campus calendar</h2>
                <span className="text-xs text-[#00078b]/60 font-medium">
                  {events.length} event{events.length === 1 ? "" : "s"} in this window
                </span>
              </div>
              <div className="flex items-center space-x-2">
                <button onClick={() => setCalFrom(isoOf(new Date(new Date(`${calFrom}T00:00:00`).getTime() - 28 * 864e5)))}
                  className="text-xs font-bold text-[#00078b] border border-[#00078b]/20 rounded-lg px-3 py-1.5 hover:bg-[#f6f6f6]">
                  ← Previous
                </button>
                <button onClick={() => setCalFrom(isoOf(weekStart(todayISO())))}
                  className="text-xs font-bold text-[#00078b] border border-[#00078b]/20 rounded-lg px-3 py-1.5 hover:bg-[#f6f6f6]">
                  Today
                </button>
                <button onClick={() => setCalFrom(isoOf(new Date(new Date(`${calFrom}T00:00:00`).getTime() + 28 * 864e5)))}
                  className="text-xs font-bold text-[#00078b] border border-[#00078b]/20 rounded-lg px-3 py-1.5 hover:bg-[#f6f6f6]">
                  Next →
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <div className="min-w-[700px]">
                <div className="grid grid-cols-7 gap-1.5 mb-1.5">
                  {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                    <div key={d} className="text-[10px] uppercase tracking-wider font-bold text-[#00078b]/60 text-center py-1">{d}</div>
                  ))}
                </div>
                {weeks.map((week, wi) => (
                  <div key={wi} className="grid grid-cols-7 gap-1.5 mb-1.5">
                    {week.map((day) => {
                      const dayEvents = byDate[day] || [];
                      const isToday = day === todayISO();
                      return (
                        <button key={day} type="button" onClick={() => setSelectedDay(day === selectedDay ? null : day)}
                          className={`min-h-[86px] text-left rounded-xl border p-1.5 transition ${
                            selectedDay === day ? "border-[#fdb813] bg-[#fdb813]/10"
                              : isToday ? "border-[#00078b]/40 bg-[#f6f6f6]"
                              : "border-[#00078b]/10 hover:border-[#00078b]/30"}`}>
                          <div className={`text-[11px] font-bold mb-1 ${isToday ? "text-[#00078b]" : "text-[#00078b]/60"}`}>
                            {Number(day.slice(8, 10))}
                          </div>
                          <div className="space-y-1">
                            {dayEvents.slice(0, 3).map((ev) => (
                              <div key={ev.booking_id}
                                className={`text-[9px] font-bold rounded px-1 py-0.5 truncate border ${STATUS_STYLE[ev.status] || STATUS_STYLE.pending}`}
                                title={`${ev.title} · ${ev.venue} · ${ev.window}`}>
                                {ev.start} {ev.title}
                              </div>
                            ))}
                            {dayEvents.length > 3 && (
                              <div className="text-[9px] font-bold text-[#00078b]/60">+{dayEvents.length - 3} more</div>
                            )}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>

            {selectedDay && (
              <div className="mt-5 pt-4 border-t border-[#00078b]/10">
                <h3 className="text-xs uppercase tracking-wider font-bold text-[#00078b]/70 mb-3">{selectedDay}</h3>
                {(byDate[selectedDay] || []).length === 0 ? (
                  <p className="text-xs text-[#00078b]/60 font-medium">Nothing booked on this day.</p>
                ) : (
                  <div className="space-y-2">
                    {(byDate[selectedDay] || []).map((ev) => (
                      <div key={ev.booking_id} className="flex items-center justify-between bg-[#f6f6f6] rounded-xl px-4 py-2.5 flex-wrap gap-2">
                        <div>
                          <p className="text-sm font-bold text-[#00078b]">{ev.title}</p>
                          <p className="text-[11px] text-[#00078b]/70 font-medium flex items-center flex-wrap gap-x-3">
                            <span className="flex items-center gap-1"><Building2 className="h-3 w-3" />{ev.venue}</span>
                            <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{ev.window}</span>
                            <span className="flex items-center gap-1"><Users className="h-3 w-3" />{ev.headcount || "—"}</span>
                            <span>{ev.organizer}</span>
                          </p>
                        </div>
                        <span className={`text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded border ${STATUS_STYLE[ev.status] || STATUS_STYLE.pending}`}>
                          {ev.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
